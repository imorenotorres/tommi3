"""A student's own practice record, what the next exercise aims at, and the instructor's totals.

One file per student and course, under the keyed hash of the Moodle user id that attempts use
(attempts.owner_key): never the id, a name or an email. It keeps, per exercise the student was
given, each try's verdict, the status of each key point and the typical mistake matched. It does
not keep the text of an answer, nor the model's feedback.

    practice/students/<owner>.json

What the next exercise aims at comes from that record alone: the typical mistake the student
made in two of their last exercises on the topic, or else the key point they missed most
recently. What a student missed is read from their first try that was assessed, the one made
without help: a point put right on the second try, after the feedback, is still a weak point.
The verdict of an exercise is that of its last try. After PRACTICE_LEVEL_AFTER exercises on a topic at one level, the record suggests going
up (all of the last ones correct) or down (most of them incorrect).

The instructor's totals count students, not tries, and show nothing for a group smaller than
config.min_group(): no name, no single answer, no hash.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone

from UltiR.ai_quiz import attempts, config, limits, storage

LEVELS = ("basico", "intermedio", "avanzado")


def _path(course_id: str, owner: str):
    return storage.course_dir(course_id) / "practice" / "students" / f"{owner}.json"


def owner(course_id: str, user_id: str) -> str:
    return attempts.owner_key(course_id, user_id)


def load(course_id: str, owner_key: str) -> dict:
    record = storage.read_json(_path(course_id, owner_key), default=None) or {}
    return {"days": record.get("days") or {}, "exercises": record.get("exercises") or {},
            "preview": bool(record.get("preview"))}


def save(course_id: str, owner_key: str, record: dict) -> None:
    storage.write_json(_path(course_id, owner_key), record)


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def final(entry: dict) -> dict | None:
    """The last try of an exercise, or None if it was not answered."""
    return entry["tries"][-1] if entry.get("tries") else None


def unaided(entry: dict) -> dict:
    """The first try of an exercise that the feedback assessed (it has key point statuses, or a programmed tutor
    diagnosed it), else {}."""
    return next((t for t in entry.get("tries") or [] if t.get("statuses") or t.get("programmed")), {})


def _on_topic(record: dict, topic_id: str, level: str | None = None) -> list[dict]:
    """The answered exercises of the record on a topic (at a level), oldest first."""
    return [e for e in sorted(record["exercises"].values(), key=lambda e: e["served_at"])
            if e["topic_id"] == topic_id and final(e) and (level is None or e["level"] == level)]


# ── What the next exercise aims at ────────────────────────────────────────────

def misses(record: dict, topic_id: str, lookup) -> list[str]:
    """What the student missed in their recent exercises on the topic, as texts, oldest first:
    key points marked "falta" or "parcial" in the first assessed try, and typical mistakes made in it."""
    said = []
    for entry in _on_topic(record, topic_id)[-limits.MAX_PRACTICE_HISTORY:]:
        exercise = lookup(entry["exercise_id"])
        if exercise is None:
            continue
        last = unaided(entry)
        points = {p["id"]: p["text"] for p in exercise["key_points"]}
        said += [points[kid] for kid, status in (last.get("statuses") or {}).items()
                 if status in ("falta", "parcial") and kid in points]
        mistakes = {m["id"]: m["text"] for m in exercise["typical_mistakes"]}
        if last.get("mistake") in mistakes:
            said.append(mistakes[last["mistake"]])
    return said


def target(record: dict, topic_id: str, lookup) -> dict | None:
    """What the next exercise on the topic should practise: {"kind": "mistake" | "key_point", "text"} or None.

    A mistake made in two of the last three exercises comes first: the latest of them. Otherwise the
    key point missed most recently ("falta" before "parcial" in the same exercise).
    """
    recent = _on_topic(record, topic_id)[-3:]
    made = []
    for entry in recent:
        exercise, last = lookup(entry["exercise_id"]), unaided(entry)
        if exercise and last.get("mistake"):
            made += [m["text"] for m in exercise["typical_mistakes"] if m["id"] == last["mistake"]]
    if len(made) >= 2:
        return {"kind": "mistake", "text": made[-1]}
    for entry in reversed(recent):
        exercise, last = lookup(entry["exercise_id"]), unaided(entry)
        if not exercise:
            continue
        statuses = last.get("statuses") or {}
        for wanted in ("falta", "parcial"):
            for point in exercise["key_points"]:
                if statuses.get(point["id"]) == wanted:
                    return {"kind": "key_point", "text": point["text"]}
    return None


def last_mistake(record: dict, topic_id: str) -> str | None:
    """The catalogued mistake of the student's last answered exercise on the topic, made without help, or None."""
    done = _on_topic(record, topic_id)
    return unaided(done[-1]).get("mistake") if done else None


def level_suggestion(record: dict, topic_id: str, level: str) -> str | None:
    """"subir", "bajar" or None, from the last PRACTICE_LEVEL_AFTER exercises on the topic at this level."""
    last = [final(e)["verdict"] for e in _on_topic(record, topic_id, level)][-limits.PRACTICE_LEVEL_AFTER:]
    if len(last) < limits.PRACTICE_LEVEL_AFTER:
        return None
    if all(v == "correcto" for v in last) and level != LEVELS[-1]:
        return "subir"
    if sum(v == "incorrecto" for v in last) * 2 > len(last) and level != LEVELS[0]:
        return "bajar"
    return None


def choose_level(record: dict, topic_id: str) -> str:
    """The level for a student who did not choose one: where they were on the topic, moved by the suggestion."""
    done = _on_topic(record, topic_id)
    if not done:
        return LEVELS[0]
    level = done[-1]["level"]
    step = {"subir": 1, "bajar": -1}.get(level_suggestion(record, topic_id, level), 0)
    return LEVELS[max(0, min(len(LEVELS) - 1, LEVELS.index(level) + step))]


def choose_topic(record: dict, open_topics: list[dict], lookup) -> dict:
    """The topic for a student who did not choose one: where they have most to practise, else one they have not tried."""
    worst = max(open_topics, key=lambda t: len(misses(record, t["topic_id"], lookup)))
    if misses(record, worst["topic_id"], lookup):
        return worst
    done = Counter(e["topic_id"] for e in record["exercises"].values())
    return min(open_topics, key=lambda t: done.get(t["topic_id"], 0))


def kind_for(record: dict, topic_id: str) -> str:
    """Open and numerical exercises in turn on a topic (numerical only where the passages allow it)."""
    return "numerica" if sum(1 for e in record["exercises"].values() if e["topic_id"] == topic_id) % 2 else "abierta"


# ── The instructor's totals ───────────────────────────────────────────────────

def _records(course_id: str) -> list[dict]:
    folder = storage.course_dir(course_id) / "practice" / "students"
    if not folder.is_dir():
        return []
    found = [storage.read_json(p) for p in sorted(folder.glob("*.json"))]
    return [r for r in found if r and not r.get("preview")]


def tutor_detections(course_id: str, lookup) -> dict[str, dict]:
    """How often each programmed tutor recognised each of its mistakes, over every try in the course.

    tutor -> key -> {"tries", "students"}, or {"too_few": True} when fewer than min_group students are in it. The
    keys are the mistake ids, "correcto", "unknown" (a wrong value no catalogued mistake gives) and "exercises"
    (exercises answered at least once; "tries" counts them).
    """
    minimum = config.min_group()
    tries, students = defaultdict(Counter), defaultdict(lambda: defaultdict(set))
    for number, record in enumerate(_records(course_id)):
        for entry in record.get("exercises", {}).values():
            done = [t for t in entry.get("tries") or [] if t.get("programmed")]
            exercise = lookup(entry["exercise_id"]) if done else None
            if exercise is None or not exercise.get("tutor"):
                continue
            name = exercise["tutor"]
            tries[name]["exercises"] += 1
            students[name]["exercises"].add(number)
            for made in done:
                key = "correcto" if made["verdict"] == "correcto" else made.get("mistake") or "unknown"
                tries[name][key] += 1
                students[name][key].add(number)
    return {name: {key: {"tries": tries[name][key], "students": len(who)} if len(who) >= minimum else {"too_few": True}
                   for key, who in groups.items()}
            for name, groups in students.items()}


def summary(course_id: str, topic_names: dict[str, str], lookup) -> dict:
    """Totals of practice in the course. A row is shown only when at least min_group students are in it.

    attempts per topic and level, the typical mistakes most made, the key points most often missed.
    """
    minimum = config.min_group()
    rows = defaultdict(lambda: {"students": set(), "exercises": 0, "verdicts": Counter()})
    mistakes, missed = defaultdict(set), defaultdict(set)
    for number, record in enumerate(_records(course_id)):
        for entry in record.get("exercises", {}).values():
            last = final(entry)
            if not last:
                continue
            row = rows[(entry["topic_id"], entry["level"])]
            row["students"].add(number)
            row["exercises"] += 1
            row["verdicts"][last.get("verdict") or "sin_valorar"] += 1
            first = unaided(entry)                      # what was missed or mistaken: the try made without help
            if first.get("mistake") and not first.get("programmed"):      # a tutor's mistakes: tutor_detections
                mistakes[(entry["exercise_id"], first["mistake"])].add(number)
            for kid, status in (first.get("statuses") or {}).items():
                if status in ("falta", "parcial"):
                    missed[(entry["exercise_id"], kid)].add(number)

    def described(key, kind):
        exercise = lookup(key[0])
        if exercise is None:
            return None
        items = {i["id"]: i["text"] for i in exercise["key_points" if kind == "K" else "typical_mistakes"]}
        return {"exercise_id": key[0], "statement": exercise["statement"], "topic": topic_names.get(exercise["topic_id"]),
                "level": exercise["level"], "id": key[1], "text": items.get(key[1])}

    def ranked(groups, kind):
        shown = [{**found, "students": len(who)} for key, who in groups.items()
                 if len(who) >= minimum and (found := described(key, kind))]
        return sorted(shown, key=lambda item: -item["students"])[: limits.MAX_PRACTICE_SUMMARY_ROWS]

    return {
        "min_group": minimum,
        "rows": [{"topic_id": topic_id, "topic": topic_names.get(topic_id), "level": level,
                  **({"students": len(row["students"]), "exercises": row["exercises"], "verdicts": dict(row["verdicts"])}
                     if len(row["students"]) >= minimum else {"too_few": True})}
                 for (topic_id, level), row in sorted(rows.items(), key=lambda item: (item[0][0], LEVELS.index(item[0][1])))],
        "mistakes": ranked(mistakes, "M"),
        "missed_key_points": ranked(missed, "K"),
        "hidden_mistakes": sum(1 for who in mistakes.values() if len(who) < minimum),
        "hidden_key_points": sum(1 for who in missed.values() if len(who) < minimum),
    }
