"""A deterministic stand-in for the language model. No network, no key.

By default it answers every request with well-formed questions built from the
sources in the prompt. A test can queue other replies (strings, exceptions or
functions of the messages) to play a misbehaving model.
"""

import json
import re

SOURCE = re.compile(r"BEGIN SOURCE (S\d+) (\w+)\n(.*?)\nEND SOURCE \1 \2", re.DOTALL)
ASKED = re.compile(r"Write (?:exactly )?(\d+) question")


def sources_in(messages) -> dict[str, str]:
    """The sources the prompt hands to the model, by id."""
    user = "\n".join(m["content"] for m in messages if m["role"] == "user")
    return {m.group(1): m.group(3) for m in SOURCE.finditer(user)}


def asked_for(messages) -> int:
    found = ASKED.findall("\n".join(m["content"] for m in messages))
    return int(found[-1]) if found else 1


def question(source: str, text: str, n: int, **changes) -> dict:
    """One valid question about `text`, quoting its first words as the excerpt."""
    words = text.split()
    q = {
        "source": source,
        "question": f"Question {n} about source {source}: which statement is made in the material?",
        "options": [
            {"id": "A", "text": f"Statement {n}.1 that the material does not make"},
            {"id": "B", "text": " ".join(words[:8])},
            {"id": "C", "text": f"Statement {n}.3 that the material does not make"},
            {"id": "D", "text": f"Statement {n}.4 that the material does not make"},
        ],
        "correct_option_id": "B",
        "explanation": f"Explanation {n}: the material says so directly.",
        "difficulty": "intermediate",
        "excerpt": " ".join(words[:14]),
    }
    q.update(changes)
    return q


def good_reply(messages, count: int | None = None, start: int = 1, **changes) -> str:
    sources = list(sources_in(messages).items())
    count = asked_for(messages) if count is None else count
    questions = [question(*sources[i % len(sources)], start + i, **changes) for i in range(count)]
    return json.dumps({"questions": questions})


QUESTION = re.compile(r"BEGIN QUESTION (Q\d+) (\w+)\n(.*?)\nEND QUESTION \1 \2", re.DOTALL)


def questions_in(messages) -> dict[str, str]:
    """The questions an analysis prompt hands to the model, by the label it calls them."""
    user = "\n".join(m["content"] for m in messages if m["role"] == "user")
    return {m.group(1): m.group(3) for m in QUESTION.finditer(user)}


def analysis_reply(messages, count: int = 2) -> str:
    """A well-formed analysis: one point for each of the first `count` questions of the prompt."""
    labels = list(questions_in(messages))[:count]
    return json.dumps({"points": [
        {"question": label, "text": f"Point {n}: many students chose the same wrong option in {label}."}
        for n, label in enumerate(labels, start=1)]})


class FakeLLM:
    def __init__(self):
        self.calls: list[dict] = []
        self.replies: list = []
        self._serial = 0

    def queue(self, *replies):
        self.replies.extend(replies)

    def __call__(self, messages, max_tokens):
        reply = self._reply(messages, max_tokens)
        from . import fake_practice                     # imported here: it builds on this module
        if fake_practice.kind_of(messages) == "feedback":
            self.last_feedback = reply                  # the default second grading agrees with it
        return reply

    last_feedback = None

    def _reply(self, messages, max_tokens):
        self.calls.append({"messages": messages, "max_tokens": max_tokens})
        from . import fake_practice                     # imported here: it builds on this module
        grading = fake_practice.kind_of(messages) == "grading"
        # A second grading of practice feedback takes a queued reply only if it is marked as one (Grading);
        # otherwise it agrees with the feedback, and the queue is left for the calls the test is about.
        if self.replies and grading != isinstance(self.replies[0], fake_practice.Grading):
            return fake_practice.reply(messages, self._serial + 1, self.last_feedback)
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, fake_practice.Grading):
                reply = reply.reply
            if isinstance(reply, BaseException):
                raise reply
            return reply(messages) if callable(reply) else reply
        if questions_in(messages):
            return analysis_reply(messages)             # a request to analyse a class summary
        from . import fake_practice                     # imported here: it builds on this module
        practised = fake_practice.reply(messages, self._serial + 1, self.last_feedback)
        if practised is not None:                       # an exercise, a check of its value, or feedback
            self._serial += 1
            return practised
        # Default: exactly what was asked for, numbered so that no two calls repeat a question.
        count = asked_for(messages)
        self._serial += count
        return good_reply(messages, count, start=self._serial - count + 1)

    @property
    def prompts(self) -> list[str]:
        return ["\n".join(m["content"] for m in call["messages"]) for call in self.calls]
