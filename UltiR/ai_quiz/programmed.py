"""Practice with programmed tutors: serving an exercise, answering it, and what the instructor reviews.

A topic is served by a tutor when the sentence its spec rests on is found in the topic's own passages; the
pages every text names come from finding the spec's sentences in the course's copy of the handout. An exercise
is made for each student from a seed and kept like any other exercise, with the parameters, the answer and the
value of every catalogued mistake. Answers are read and diagnosed by the tutor, and the feedback is made of the
spec's texts only. No model is asked, and the student's answer never leaves the server.
"""

import secrets

from UltiR.ai_quiz import documents, exercises, topics, tutors

KIND = "programado"


def places(course_id: str) -> dict[str, dict]:
    """tutor name -> {"topic_id", "found"}: the topic whose passages hold the tutor's sentence, and where it is."""
    placed = {}
    for topic in topics.course_topics(course_id):
        chunks = topics.topic_chunks(course_id, topic)
        for name in tutors.NAMES:
            if name in placed:
                continue
            found = tutors.locate(tutors.spec(name)["skill"]["anchor"], chunks)
            if found:
                placed[name] = {"topic_id": topic["topic_id"], "found": found}
    return placed


def topic_tutors(course_id: str) -> dict[str, str]:
    """topic id -> the tutor that serves it."""
    return {place["topic_id"]: name for name, place in places(course_id).items()}


def _document_chunks(course_id: str, doc_id: str) -> list[dict]:
    document = documents.get_document(course_id, doc_id)
    if document is None:
        return []
    return [{"doc_id": doc_id, "doc_label": document["label"], **chunk} for chunk in documents.load_chunks(course_id, doc_id)]


def page_of(course_id: str, exercise: dict, anchor: str) -> dict | None:
    """Where a sentence of the spec is in the exercise's handout: page and the handout's own wording."""
    return tutors.locate(anchor, _document_chunks(course_id, exercise["source"]["doc_id"]))


def new_exercise(course_id: str, topic: dict, name: str, level: str, language: str, aim: str | None) -> dict:
    """One exercise of the tutor for one student, stored. The seed is drawn here; the parameters follow from it."""
    found = places(course_id)[name]["found"]
    instance = tutors.make(name, level, secrets.randbits(31), aim)
    spec = tutors.spec(name)
    exercise = {
        "type": KIND, "tutor": name, "level": level, "language": language, "topic_id": topic["topic_id"],
        "seed": instance.seed, "params": instance.params, "solution_value": instance.answer, "form": instance.form,
        "wrong": instance.wrong, "scales": instance.scales or {},
        "statement": tutors.statement(instance, language),
        "reference_solution": tutors.solution(instance, language),
        "key_points": [],
        "typical_mistakes": [{"id": m["id"], "text": m[f"title_{language}"]} for m in spec["mistakes"]
                             if m["id"] in instance.wrong],
        "named_quantities": [],
        "source": {"doc_id": found["doc_id"], "doc_label": found["doc_label"], "chunk_id": found["chunk_id"],
                   "page": found["page"], "excerpt": found["excerpt"], "mode": "text"},
    }
    return exercises.store(course_id, exercise, aim)


LANGUAGES = ("es", "en")


def _both(table: dict, key: str) -> dict[str, str]:
    """A text of the spec in both languages: key "es" is the field `es` (or `{key}_es`)."""
    return {lang: table[f"{key}_{lang}" if key else lang] for lang in LANGUAGES}


def review(course_id: str, detections: dict, topic_names: dict[str, str]) -> list[dict]:
    """What the instructor reviews of each tutor: the texts of its spec, where the sentences they rest on are in
    this course's handout (None where they are not found), and how often each mistake was recognised.

    `detections` is progress.tutor_detections(): counts that already leave out groups below the minimum.
    """
    placed = places(course_id)
    shown = []
    for name in tutors.NAMES:
        spec, place = tutors.spec(name), placed.get(name)
        chunks = _document_chunks(course_id, place["found"]["doc_id"]) if place else []

        def where(anchor):
            found = tutors.locate(anchor, chunks) if chunks else None
            return {"doc_label": found["doc_label"], "page": found["page"], "excerpt": found["excerpt"]} if found else None

        counted = detections.get(name, {})
        shown.append({
            "tutor": name, "file": f"tutors/{name}.toml", "title": _both(spec["skill"], "title"),
            "formula": spec["skill"]["formula"], "handout": spec["skill"]["handout"],
            "topic": topic_names.get(place["topic_id"]) if place else None, "where": where(spec["skill"]["anchor"]),
            "levels": [{"level": level, "about": _both(about, "about")} for level, about in spec["levels"].items()],
            "right": {"text": _both(spec["right"], ""), "next": _both(spec["right"], "next"),
                      "detected": counted.get("correcto")},
            "unknown": {"text": _both(spec["unknown"], ""), "next": _both(spec["unknown"], "next"),
                        "detected": counted.get("unknown")},
            "mistakes": [{"id": m["id"], "title": _both(m, "title"), "what": _both(m, "what"), "why": _both(m, "why"),
                          "next": _both(m, "next"), "where": where(m["anchor"]), "detected": counted.get(m["id"])}
                         for m in spec["mistakes"]],
            "answered": counted.get("exercises"),
        })
    return shown


def read_value(exercise: dict, body: dict) -> tuple[float | None, str]:
    """The value the student typed, read as the tutor reads it, and as they typed it. ValueError if it is not one."""
    raw = body.get("value")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, ""
    typed = " ".join(raw.split()) if isinstance(raw, str) else str(raw)
    return tutors.parse(raw, exercise["form"]), typed


def feedback(course_id: str, exercise: dict, value: float, typed: str, language: str) -> dict:
    """The verdict, the mistake recognised, and texts of the spec for what went wrong, why and what next."""
    name, spec = exercise["tutor"], tutors.spec(exercise["tutor"])
    verdict, mistake = tutors.diagnose(exercise["solution_value"], exercise["wrong"], exercise["form"], value,
                                       exercise.get("scales"))
    params = exercise["params"]
    if verdict == "correcto":
        where = page_of(course_id, exercise, spec["skill"]["anchor"])
        said = tutors.fill(name, spec["right"][language], params, language, value=typed)
        step = spec["right"][f"next_{language}"]
        title = None
    elif mistake:
        catalogued = tutors.mistake_spec(name, mistake)
        where = page_of(course_id, exercise, catalogued["anchor"])
        page = where["page"] if where else exercise["source"]["page"]
        said = " ".join([tutors.fill(name, catalogued[f"what_{language}"], params, language, value=typed),
                         tutors.fill(name, catalogued[f"why_{language}"], params, language, page=page)])
        step = catalogued[f"next_{language}"]
        title = catalogued[f"title_{language}"]
    else:
        where = page_of(course_id, exercise, spec["skill"]["anchor"])
        page = where["page"] if where else exercise["source"]["page"]
        said = tutors.fill(name, spec["unknown"][language], params, language, page=page)
        step = spec["unknown"][f"next_{language}"]
        title = None
    where = where or {"doc_label": exercise["source"]["doc_label"], "page": exercise["source"]["page"],
                      "excerpt": exercise["source"]["excerpt"]}
    return {"verdict": verdict, "mistake": mistake, "mistake_title": title, "feedback": said, "next_step": step,
            "review": {"doc_label": where["doc_label"], "page": where["page"], "excerpt": where["excerpt"]}}
