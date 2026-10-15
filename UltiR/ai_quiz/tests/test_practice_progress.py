"""Practice, part five: what the next exercise aims at, the suggested level, and the instructor's view.

From the student's own record only: the key point they missed most recently, or a typical mistake
they made twice, is what the next exercise practises. After three exercises on a topic at one
level, a change of level is suggested. The instructor sees every exercise and every discard, and
totals that show nothing for fewer than three students.
"""

import pytest

from UltiR.ai_quiz import exercises, progress

from .conftest import cid
from .fake_practice import feedback_reply, kind_of, user_text
from .practice_helpers import PRACTICE, PracticeCourse
from .test_practice_feedback import GOOD_ANSWER, Student


def code(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


@pytest.fixture
def course(client, launch):
    return PracticeCourse(client, launch)


@pytest.fixture
def student(course):
    return Student(course)


def topic(course, number=1):
    return course.topics()[number]["topic_id"]


def missing(*ids):
    return lambda m: feedback_reply(m, statuses={kid: "falta" for kid in ids})


# ── What the next exercise aims at ──────────────────────────────────────────

def test_a_missed_key_point_is_what_the_next_exercise_practises(student, course, fake_llm):
    first = student.exercise(topic_id=topic(course), level="intermedio")
    fake_llm.queue(missing("K2"))
    student.answer(first)

    response = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                                   json={"topic_id": topic(course), "level": "intermedio"})

    assert response.json()["aim"] == "key_point"
    written = [c for c in fake_llm.calls if kind_of(c["messages"]) == "exercise"][-1]
    assert '"Key point 1.2 of the rubric"' in user_text(written["messages"])     # the point that was missed


def test_a_mistake_made_twice_comes_before_a_missed_key_point(student, course, fake_llm):
    for _ in range(2):
        exercise = student.exercise(topic_id=topic(course), level="intermedio")
        fake_llm.queue(lambda m: feedback_reply(m, statuses={"K1": "falta"}, mistake="M2"), )
        student.answer(exercise, "I used the table.", value="72") if exercise["type"] == "numerica" else student.answer(exercise)

    response = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                                   json={"topic_id": topic(course), "level": "intermedio"})

    assert response.json()["aim"] == "mistake"
    written = [c for c in fake_llm.calls if kind_of(c["messages"]) == "exercise"][-1]
    assert "Typical mistake" in user_text(written["messages"]).split("This student recently missed")[1]


def test_a_point_put_right_on_the_second_try_is_still_what_the_next_exercise_practises(student, course, fake_llm):
    exercise = student.exercise(topic_id=topic(course), level="intermedio")
    fake_llm.queue(lambda m: feedback_reply(m, statuses={"K1": "falta"}, mistake="M1"), lambda m: feedback_reply(m))
    student.answer(exercise)
    assert student.answer(exercise)["verdict"] == "correcto"             # right after the feedback

    response = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                                   json={"topic_id": topic(course), "level": "intermedio"})

    assert response.json()["aim"] == "key_point"
    written = [c for c in fake_llm.calls if kind_of(c["messages"]) == "exercise"][-1]
    assert '"Key point 1.1 of the rubric"' in user_text(written["messages"])


def test_a_first_try_without_assessment_does_not_hide_what_the_second_try_shows(student, course, fake_llm):
    exercise = student.exercise(topic_id=topic(course), level="intermedio")
    fake_llm.queue("not json", "not json", lambda m: feedback_reply(m, statuses={"K2": "falta"}))
    student.answer(exercise)                                              # no feedback could be checked
    student.answer(exercise)

    response = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                                   json={"topic_id": topic(course), "level": "intermedio"})

    assert response.json()["aim"] == "key_point"


def test_the_totals_count_what_was_missed_on_the_first_try_and_the_verdict_of_the_last(client, course, fake_llm):
    for user in ("s-1", "s-2", "s-3"):
        s = Student(course, user)
        exercise = s.exercise(topic_id=topic(course), level="intermedio")
        fake_llm.queue(lambda m: feedback_reply(m, statuses={"K2": "falta"}, mistake="M2"), lambda m: feedback_reply(m))
        s.answer(exercise)
        s.answer(exercise)

    summary = client.get(f"{PRACTICE}/summary", params={"token": course.instructor}).json()

    assert summary["rows"][0]["verdicts"] == {"correcto": 3}
    assert [m["id"] for m in summary["mistakes"]] == ["M2"] and [p["id"] for p in summary["missed_key_points"]] == ["K2"]


def test_without_anything_missed_there_is_no_aim(student, course):
    student.answer(student.exercise(topic_id=topic(course), level="intermedio"))

    response = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                                   json={"topic_id": topic(course), "level": "intermedio"})

    assert response.json()["aim"] is None


def test_an_exercise_of_the_pool_that_practises_the_point_is_served_without_a_call(course, fake_llm):
    # s-2 misses the point s-1 missed, and gets the exercise that was written for s-1, without a model call.
    def miss_then_aim(student):
        first = student.exercise(topic_id=topic(course), level="intermedio")
        fake_llm.queue(missing("K2"))
        student.answer(first)
        return first, student.exercise(topic_id=topic(course), level="intermedio")

    first_1, aimed_1 = miss_then_aim(Student(course, "s-1"))
    assert exercises.load(cid("course-A"), aimed_1["exercise_id"])["target"] == "Key point 1.2 of the rubric"
    written = sum(kind_of(c["messages"]) == "exercise" for c in fake_llm.calls)

    first_2, aimed_2 = miss_then_aim(Student(course, "s-2"))

    assert first_2["exercise_id"] == first_1["exercise_id"] and aimed_2["exercise_id"] == aimed_1["exercise_id"]
    assert sum(kind_of(c["messages"]) == "exercise" for c in fake_llm.calls) == written


def test_an_exercise_of_the_pool_that_does_not_practise_the_point_is_not_served_for_it(course, fake_llm):
    s1 = Student(course, "s-1")
    first = s1.exercise(topic_id=topic(course), level="intermedio")
    s1.exercise(topic_id=topic(course), level="intermedio")            # one more in the pool, written with no aim
    fake_llm.queue(missing("K2"))
    s1.answer(first)

    assert exercises.from_pool(cid("course-A"), topic(course), "intermedio", "es", set(), "Ransac homographies tables") is None


def test_the_record_of_one_student_does_not_steer_another(course, fake_llm):
    s1, s2 = Student(course, "s-1"), Student(course, "s-2")
    fake_llm.queue(missing("K2"))
    s1.answer(s1.exercise(topic_id=topic(course), level="intermedio"))

    response = s2.client.post(f"{PRACTICE}/exercise", params={"token": s2.token},
                              json={"topic_id": topic(course), "level": "intermedio"})

    assert response.json()["aim"] is None


def test_with_no_topic_chosen_the_topic_with_most_missed_is_chosen(student, course, fake_llm):
    third = student.exercise(topic_id=topic(course, 2), level="basico")
    fake_llm.queue(missing("K1", "K2"))
    student.answer(third)
    student.answer(student.exercise(topic_id=topic(course, 0), level="basico"))

    got = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token}, json={}).json()

    assert got["topic"]["topic_id"] == topic(course, 2) and got["chosen"]["topic"] == "for_you"


# ── The level ───────────────────────────────────────────────────────────────

def three(student, course, fake_llm, reply=None, level="intermedio"):
    last = None
    for _ in range(3):
        exercise = student.exercise(topic_id=topic(course), level=level)
        if reply:
            fake_llm.queue(reply)
        if exercise["type"] == "numerica":
            last = student.answer(exercise, "Table.", value="72" if reply is None else "5")
        else:
            last = student.answer(exercise)
    return last


def test_three_right_at_a_level_suggest_going_up(student, course, fake_llm):
    assert three(student, course, fake_llm)["level_suggestion"] == "subir"


def test_most_wrong_at_a_level_suggest_going_down(student, course, fake_llm):
    assert three(student, course, fake_llm, missing("K1", "K2"))["level_suggestion"] == "bajar"


def test_nothing_is_suggested_before_three_exercises_or_beyond_the_levels(student, course, fake_llm):
    exercise = student.exercise(topic_id=topic(course), level="intermedio")
    assert student.answer(exercise)["level_suggestion"] is None
    assert three(Student(course, "s-9"), course, fake_llm, level="avanzado")["level_suggestion"] is None


def test_without_a_level_chosen_the_suggestion_is_followed(student, course, fake_llm):
    three(student, course, fake_llm)

    got = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                              json={"topic_id": topic(course)}).json()

    assert got["exercise"]["level"] == "avanzado" and got["chosen"]["level"] == "for_you"


def test_the_rules_of_the_suggestion():
    def record(*verdicts, level="intermedio"):
        return {"exercises": {f"e{n}": {"exercise_id": f"e{n}", "topic_id": "t", "level": level, "served_at": f"{n:03d}",
                                        "tries": [{"verdict": v}]} for n, v in enumerate(verdicts)}}

    assert progress.level_suggestion(record("correcto", "correcto", "correcto"), "t", "intermedio") == "subir"
    assert progress.level_suggestion(record("incorrecto", "correcto", "correcto", "correcto"), "t", "intermedio") == "subir"
    assert progress.level_suggestion(record("incorrecto", "incorrecto", "correcto"), "t", "intermedio") == "bajar"
    assert progress.level_suggestion(record("incorrecto", "parcial", "correcto"), "t", "intermedio") is None
    assert progress.level_suggestion(record("incorrecto", "incorrecto", "incorrecto", level="basico"), "t", "basico") is None
    assert progress.level_suggestion(record("correcto", "correcto"), "t", "intermedio") is None
    assert progress.level_suggestion(record("parcial", "correcto", "correcto"), "t", "intermedio") is None
    # Only the exercises at the level asked about count.
    three_basic = record("correcto", "correcto", "correcto", level="basico")
    assert progress.level_suggestion(three_basic, "t", "intermedio") is None


def test_a_mistake_made_once_does_not_come_before_a_missed_key_point(student, course, fake_llm):
    exercise = student.exercise(topic_id=topic(course), level="intermedio")
    fake_llm.queue(lambda m: feedback_reply(m, statuses={"K1": "falta"}, mistake="M2"))
    student.answer(exercise)

    response = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                                   json={"topic_id": topic(course), "level": "intermedio"})

    assert response.json()["aim"] == "key_point"


def test_for_a_missed_point_the_pool_skips_an_older_exercise_that_does_not_practise_it(course, fake_llm):
    from .fake_practice import exercise_reply
    s1, s2 = Student(course, "s-1"), Student(course, "s-2")
    first = s1.exercise(topic_id=topic(course), level="intermedio")
    fake_llm.queue(lambda m: exercise_reply(m, statement="Compute something else entirely (fake answer 72).",
                                            key_points=["Alpha beta gamma", "Delta epsilon zeta"]))
    unrelated = s1.exercise(topic_id=topic(course), level="intermedio")
    fake_llm.queue(missing("K2"))
    s1.answer(first)
    aimed = s1.exercise(topic_id=topic(course), level="intermedio")

    assert s2.exercise(topic_id=topic(course), level="intermedio")["exercise_id"] == first["exercise_id"]
    fake_llm.queue(missing("K2"))
    s2.answer(first)
    got = s2.exercise(topic_id=topic(course), level="intermedio")

    assert got["exercise_id"] == aimed["exercise_id"] != unrelated["exercise_id"]


# ── The instructor ──────────────────────────────────────────────────────────

def test_the_instructor_sees_every_exercise_with_everything_and_every_discard(client, student, course, fake_llm):
    from .fake_practice import check_reply, exercise_reply
    first = student.exercise(topic_id=topic(course), level="intermedio")
    student.answer(first)
    fake_llm.queue(lambda m: exercise_reply(m, value=5), lambda m: check_reply(m, value=17))
    student.exercise(topic_id=topic(course), level="intermedio")

    pool = client.get(f"{PRACTICE}/pool", params={"token": course.instructor}).json()

    newest, oldest = pool["exercises"]
    assert oldest["exercise_id"] == first["exercise_id"] and oldest["served"] == 1 and oldest["topic"] == "Counting iterations"
    assert {"reference_solution", "key_points", "typical_mistakes", "source", "status", "calls", "seconds"} <= set(oldest)
    assert newest["answer"]["value_text"] == "72" and newest["answer"]["checked_text"] == "72"
    [discard] = pool["rejections"]
    assert discard["reason"] == "numeric_mismatch: 5 vs 17" and discard["topic"] == "Counting iterations"


def test_the_instructor_retires_an_exercise_and_approves_a_reported_one(client, course):
    s1 = Student(course, "s-1")
    exercise = s1.exercise(topic_id=topic(course), level="intermedio")
    client.post(f"{PRACTICE}/exercises/{exercise['exercise_id']}/report", params={"token": s1.token}, json={"reason": "otro"})
    path = f"{PRACTICE}/pool/{exercise['exercise_id']}"

    assert client.post(f"{path}/approve", params={"token": course.instructor}).status_code == 200
    assert exercises.load(cid("course-A"), exercise["exercise_id"])["status"] == "servido"
    assert code(client.post(f"{path}/approve", params={"token": course.instructor})) == "not_reported"

    assert client.post(f"{path}/retire", params={"token": course.instructor}).status_code == 200
    assert exercises.load(cid("course-A"), exercise["exercise_id"])["status"] == "retirado"
    assert code(client.post(f"{path}/approve", params={"token": course.instructor})) == "not_reported"
    assert code(client.post(f"{PRACTICE}/pool/e_0000000000000000/retire", params={"token": course.instructor})) == "exercise_not_found"
    assert client.post(f"{PRACTICE}/pool/../retire", params={"token": course.instructor}).status_code == 404


def test_a_student_may_not_see_the_pool_retire_approve_or_read_the_totals(client, student, course):
    exercise = student.exercise(topic_id=topic(course))
    for method, path in (("get", "pool"), ("post", f"pool/{exercise['exercise_id']}/retire"),
                         ("post", f"pool/{exercise['exercise_id']}/approve"), ("get", "summary")):
        assert getattr(client, method)(f"{PRACTICE}/{path}", params={"token": student.token}).status_code == 403


def practised(course, fake_llm, users, reply=None):
    for user in users:
        s = Student(course, user)
        exercise = s.exercise(topic_id=topic(course), level="intermedio")
        if reply:
            fake_llm.queue(reply)
        s.answer(exercise)


def test_with_two_students_the_totals_show_no_number(client, course, fake_llm):
    practised(course, fake_llm, ["s-1", "s-2"], lambda m: feedback_reply(m, statuses={"K2": "falta"}, mistake="M1"))

    summary = client.get(f"{PRACTICE}/summary", params={"token": course.instructor}).json()

    assert summary["min_group"] == 3
    assert summary["rows"] == [{"topic_id": topic(course), "topic": "Counting iterations", "level": "intermedio", "too_few": True}]
    assert summary["mistakes"] == [] and summary["missed_key_points"] == []
    assert (summary["hidden_mistakes"], summary["hidden_key_points"]) == (1, 1)


def test_with_three_students_the_totals_are_shown_and_name_nobody(client, course, fake_llm):
    practised(course, fake_llm, ["s-1", "s-2", "s-3"], lambda m: feedback_reply(m, statuses={"K2": "falta"}, mistake="M1"))

    summary = client.get(f"{PRACTICE}/summary", params={"token": course.instructor}).json()

    [row] = summary["rows"]
    assert (row["students"], row["exercises"], row["verdicts"]) == (3, 3, {"parcial": 3})
    [mistake] = summary["mistakes"]
    assert (mistake["text"], mistake["students"], mistake["id"]) == ("Typical mistake 1.1", 3, "M1")
    [point] = summary["missed_key_points"]
    assert (point["text"], point["students"]) == ("Key point 1.2 of the rubric", 3)
    text = str(summary)
    for private in ("s-1", "s-2", "s-3", progress.owner(cid("course-A"), "s-1"), GOOD_ANSWER, "Minimal samples"):
        assert private not in text


def test_one_student_with_three_exercises_is_still_one_student(client, course, fake_llm):
    student = Student(course, "s-1")
    for _ in range(3):
        exercise = student.exercise(topic_id=topic(course), level="intermedio")
        student.answer(exercise, "Table.", value="72") if exercise["type"] == "numerica" else student.answer(exercise)

    summary = client.get(f"{PRACTICE}/summary", params={"token": course.instructor}).json()

    assert summary["rows"][0].get("too_few") is True


def test_an_instructor_practising_is_not_counted(client, course, fake_llm):
    practised(course, fake_llm, ["s-1", "s-2"])
    teacher = Student(course)
    teacher.token = course.instructor
    teacher.answer(teacher.exercise(topic_id=topic(course), level="intermedio"))

    summary = client.get(f"{PRACTICE}/summary", params={"token": course.instructor}).json()

    assert summary["rows"][0].get("too_few") is True
