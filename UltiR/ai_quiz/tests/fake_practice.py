"""What the fake model answers to the three practice prompts: write an exercise, check a value, give feedback.

The default replies are well formed and agree with each other, so that a test only queues a reply
for the part of the run it is about.
"""

import json
import re

from .fake_llm import sources_in

EXERCISE_ASKED = re.compile(r"Type: (abierta|numerica)\.")
CHECK = re.compile(r"BEGIN EXERCISE (\w+)\n(.*?)\nEND EXERCISE \1", re.DOTALL)
ANSWER = re.compile(r"BEGIN ANSWER (\w+)\n(.*?)\nEND ANSWER \1", re.DOTALL)
KEY_POINT = re.compile(r"^(K\d): ", re.MULTILINE)
FAKE_VALUE = re.compile(r"\(fake answer (-?[\d.]+)\)")


def user_text(messages) -> str:
    return "\n".join(m["content"] for m in messages if m["role"] == "user")


def kind_of(messages) -> str | None:
    """Which practice prompt this is, or None for any other."""
    text = user_text(messages)
    if ANSWER.search(text):
        return "feedback"
    if CHECK.search(text) and "Solve the exercise now." in text:
        return "check"
    if EXERCISE_ASKED.search(text):
        return "exercise"
    return None


def exercise(source: str, text: str, kind: str = "abierta", n: int = 1, value: float = 72, **changes) -> dict:
    """One valid exercise about `text`, quoting its first words as the excerpt."""
    words = text.split()
    item = {
        "type": kind,
        "task": "explicar",
        "statement": f"Exercise {n} about source {source}: explain what the material says in your own words.",
        "reference_solution": f"Reference solution {n}: in short, {' '.join(words[:10])}.",
        "key_points": [f"Key point {n}.1 of the rubric", f"Key point {n}.2 of the rubric"],
        "typical_mistakes": [f"Typical mistake {n}.1", f"Typical mistake {n}.2"],
        "source": source,
        "excerpt": " ".join(words[:14]),
    }
    if kind == "numerica":
        item["statement"] = f"Exercise {n} about source {source}: compute the value (fake answer {value})."
        item["answer"] = {"value": value, "unit": "", "tolerance": 0.01}
    item.update(changes)
    return item


def exercise_reply(messages, n: int = 1, **changes) -> str:
    first, text = next(iter(sources_in(messages).items()))
    kind = EXERCISE_ASKED.search(user_text(messages)).group(1)
    return json.dumps(exercise(first, text, kind, n, **changes))


def check_reply(messages, value=None) -> str:
    """The checker works out the value the exercise was written with, unless told another."""
    if value is None:
        found = FAKE_VALUE.search(CHECK.search(user_text(messages)).group(2))
        value = float(found.group(1)) if found else None
    return json.dumps({"value": value, "unit": ""})


def answer_in(messages) -> str:
    return ANSWER.search(user_text(messages)).group(2)


def feedback_reply(messages, statuses=None, mistake=None, evidence=None, **changes) -> str:
    """Feedback that marks every key point met and quotes the first words of the answer as its evidence."""
    text = user_text(messages)
    ids = list(dict.fromkeys(KEY_POINT.findall(text.split("BEGIN ANSWER")[0])))
    answer = answer_in(messages)
    quote = " ".join(answer.split()[:5]) if evidence is None else evidence
    statuses = statuses or {}
    reply = {
        "key_points": [{"id": kid, "status": statuses.get(kid, "cumplido"),
                        "evidence": "" if statuses.get(kid) == "falta" else quote} for kid in ids],
        "mistake": mistake,
        "feedback": "Your answer covers the main idea. Look again at how the two parts connect. Keep going.",
        "next_step": "Try a harder exercise on the same topic.",
    }
    reply.update(changes)
    return json.dumps(reply)


def reply(messages, serial: int) -> str | None:
    """The default answer to a practice prompt, or None when it is not one."""
    kind = kind_of(messages)
    if kind == "exercise":
        return exercise_reply(messages, serial)
    if kind == "check":
        return check_reply(messages)
    if kind == "feedback":
        return feedback_reply(messages)
    return None
