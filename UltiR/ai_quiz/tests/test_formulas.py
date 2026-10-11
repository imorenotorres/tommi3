"""Formulas on the server side: the prompt for a full reading, LaTeX in the model's JSON, what a question records."""

import json

import pytest

from UltiR.ai_quiz import generation

from .conftest import BASE
from .fake_llm import question, sources_in
from .readers import install_recorded_docling, upload_full
from .test_documents import upload
from .test_figures import approve, draft, publish, system_prompt

TEXT_NOTES = b"Plain notes about feature matching, long enough to be read as a document. " * 4


@pytest.fixture(autouse=True)
def docling(monkeypatch):
    install_recorded_docling(monkeypatch)


@pytest.fixture
def instructor(launch):
    return launch.token(role="Instructor", course="course-A")


@pytest.fixture
def learner(launch):
    return launch.token(role="Learner", course="course-A", user="student-1")


@pytest.fixture
def doc(client, instructor) -> dict:
    return upload_full(client, instructor)


def reply_about(marker: str, **changes):
    """A model reply: one question about the source that contains `marker`."""
    def reply(messages):
        sources = sources_in(messages)
        sid = next(s for s, text in sources.items() if marker in text)
        return json.dumps({"questions": [question(sid, sources[sid], 1, **changes)]})
    return reply


# ── The prompt ──────────────────────────────────────────────────────────────

def test_the_prompt_for_a_full_reading_asks_for_latex_between_dollar_signs(client, instructor, doc, fake_llm):
    draft(client, instructor, doc["doc_id"])

    prompt = system_prompt(fake_llm)
    assert "LaTeX between single dollar signs" in prompt
    assert "Do not use LaTeX" not in prompt
    assert "backslash" in prompt                               # how to write one inside a JSON string


def test_the_prompt_for_a_text_reading_still_asks_for_plain_text_formulas(client, instructor, fake_llm):
    text_doc = upload(client, instructor, "notes.txt", TEXT_NOTES).json()

    draft(client, instructor, text_doc["doc_id"], topic="")

    assert "Write formulas in plain text" in system_prompt(fake_llm)
    assert "Do not use LaTeX" in system_prompt(fake_llm)


def test_the_two_prompts_differ_only_in_the_formula_rule_and_the_figure_rule():
    text, full = generation.SYSTEM_PROMPTS["text"].split("\n"), generation.SYSTEM_PROMPTS["full"].split("\n")

    removed = [line for line in text if line not in full]
    added = [line for line in full if line not in text]
    assert len(removed) == 1 and removed[0].startswith("- Write formulas in plain text")
    assert len(added) == 2
    assert sum("LaTeX" in line for line in added) == 1 and sum("[FIGURE" in line for line in added) == 1


# ── LaTeX inside the model's JSON ───────────────────────────────────────────

@pytest.mark.parametrize("written, meant", [
    (r'{"q": "$\frac{1}{2}$"}', r"$\frac{1}{2}$"),                      # \f would be a form feed
    (r'{"q": "$\theta \times \tau$"}', r"$\theta \times \tau$"),        # \t would be a tab
    (r'{"q": "$\nabla f \neq \nu$"}', r"$\nabla f \neq \nu$"),          # \n would be a line break
    (r'{"q": "$\rho \rightarrow \beta$"}', r"$\rho \rightarrow \beta$"),
    (r'{"q": "$\underline{x} \uparrow$"}', r"$\underline{x} \uparrow$"),  # \u would start a character code
    (r'{"q": "$\sigma_b^2 + \lambda \mathbf{x}$"}', r"$\sigma_b^2 + \lambda \mathbf{x}$"),   # not JSON at all
    (r'{"q": "$\{a\} \, b \; c \! d \| e$"}', r"$\{a\} \, b \; c \! d \| e$"),
    (r'{"q": "$\\frac{1}{2}$ and $\\theta$"}', r"$\frac{1}{2}$ and $\theta$"),        # written correctly: untouched
    (r'{"q": "$a \\\\ b$"}', r"$a \\ b$"),                              # a LaTeX line break, written correctly
    (r'{"q": "one\nTwo"}', "one\nTwo"),                                 # a real line break stays one
    (r'{"q": "a\tb"}', "a\tb"),
    (r'{"q": "café and \"quotes\" and a\/b"}', 'café and "quotes" and a/b'),
    (r'{"q": "no backslash at all"}', "no backslash at all"),
])
def test_latex_commands_written_with_one_backslash_are_read_as_latex(written, meant):
    assert json.loads(generation.repair_latex_escapes(written))["q"] == meant


RAW_REPLY = r'''{"questions": [{"source": "S1", "question": "What does $\frac{\partial G}{\partial \sigma}$ approximate, with $\theta$ fixed?",
 "options": [{"id": "A", "text": "$\sigma \nabla^{2} G$"}, {"id": "B", "text": "$\beta \times \rho$"},
             {"id": "C", "text": "$\lambda_1 \geq \lambda_2$"}, {"id": "D", "text": "nothing"}],
 "correct_option_id": "A", "explanation": "Because $\nabla^{2}$ is the Laplacian.", "difficulty": "advanced",
 "excerpt": "%s"}]}'''


def raw_reply(messages):
    """A reply as models tend to write it: LaTeX with single backslashes inside JSON strings."""
    text = sources_in(messages)["S1"]
    return RAW_REPLY % " ".join(w for w in text.split() if w.isalpha())[:10]


def test_a_reply_with_singly_escaped_latex_becomes_a_question_with_its_formulas_whole(client, instructor, doc, fake_llm):
    fake_llm.queue(raw_reply)

    q = draft(client, instructor, doc["doc_id"])["questions"][0]

    assert q["question"] == r"What does $\frac{\partial G}{\partial \sigma}$ approximate, with $\theta$ fixed?"
    assert [o["text"] for o in q["options"]][:3] == [r"$\sigma \nabla^{2} G$", r"$\beta \times \rho$", r"$\lambda_1 \geq \lambda_2$"]
    assert q["explanation"] == r"Because $\nabla^{2}$ is the Laplacian."
    assert len(fake_llm.calls) == 1                           # no second try was needed


def test_replies_for_a_text_reading_are_read_exactly_as_before(client, instructor, fake_llm):
    text_doc = upload(client, instructor, "notes.txt", TEXT_NOTES).json()
    fake_llm.queue(lambda messages: json.dumps({"questions": [question("S1", sources_in(messages)["S1"], 1,
                                                                       explanation="first line\nsecond line")]}))

    q = draft(client, instructor, text_doc["doc_id"], topic="")["questions"][0]

    assert q["explanation"] == "first line second line"       # a line break in a reply is a space, as it always was
    assert "math" not in q


def test_replies_for_a_text_reading_are_not_searched_for_latex(client, instructor, fake_llm):
    text_doc = upload(client, instructor, "notes.txt", TEXT_NOTES).json()
    fake_llm.queue(lambda messages: json.dumps({"questions": [question("S1", sources_in(messages)["S1"], 1)]})
                   .replace("Explanation 1", r"The angle \theta in explanation 1"))

    q = draft(client, instructor, text_doc["doc_id"], topic="")["questions"][0]

    # In JSON "\t" is a tab. For a text reading the reply is taken as the JSON it is, as before.
    assert q["explanation"].startswith("The angle heta in explanation 1")


# ── What a question records ─────────────────────────────────────────────────

def test_a_question_from_a_full_reading_says_that_its_formulas_are_latex(client, instructor, learner, doc):
    quiz = draft(client, instructor, doc["doc_id"])
    assert quiz["questions"][0]["math"] == "latex"
    assert quiz["questions"][0]["source"]["mode"] == "full"
    approve(client, instructor, quiz)
    publish(client, instructor, quiz)

    seen = client.get(f"{BASE}/api/published/{quiz['quiz_id']}", params={"token": learner}).json()["questions"][0]
    result = client.post(f"{BASE}/api/quizzes/{quiz['quiz_id']}/attempts", params={"token": learner},
                         json={"revision": 1, "answers": {}}).json()["results"][0]

    assert seen["math"] == "latex" and result["math"] == "latex"
    assert "mode" not in json.dumps(seen)                      # how the document was read is not the student's business


def test_a_question_from_a_text_reading_says_nothing_about_latex(client, instructor, learner):
    text_doc = upload(client, instructor, "notes.txt", TEXT_NOTES).json()
    quiz = draft(client, instructor, text_doc["doc_id"], topic="")
    approve(client, instructor, quiz)
    publish(client, instructor, quiz)

    seen = client.get(f"{BASE}/api/published/{quiz['quiz_id']}", params={"token": learner}).json()["questions"][0]

    assert "math" not in quiz["questions"][0] and "math" not in seen
    assert quiz["questions"][0]["source"]["mode"] == "text"


def test_an_instructor_s_edit_cannot_switch_formula_display_on_or_off(client, instructor, doc):
    quiz = draft(client, instructor, doc["doc_id"])
    q = quiz["questions"][0]

    response = client.put(f"{BASE}/api/quizzes/{quiz['quiz_id']}/questions/{q['question_id']}",
                          params={"token": instructor}, json={"math": "plain", "explanation": "Edited."})

    assert response.json()["questions"][0]["math"] == "latex"


# ── The passage rule holds in both reading modes ────────────────────────────

FORMULA_8 = r"$$D ( x , y , \sigma ) = L ( x , y , k \sigma ) - L ( x , y , \sigma ) .$$"


@pytest.mark.parametrize("claimed, located", [
    # ends inside the formula: widened to its closing delimiter
    (r"gives the difference-of-Gaussians function D ( x , y , \sigma ) = L ( x , y , k",
     "gives the difference-of-Gaussians function\n\n" + FORMULA_8),
    # begins inside the formula: widened to its opening delimiter
    (r"L ( x , y , k \sigma ) - L ( x , y , \sigma ) . (8) Since the Gaussian images are needed anyway",
     FORMULA_8 + " (8)\n\nSince the Gaussian images are needed anyway"),
    # no formula touched: exactly the words that were matched
    ("Since the Gaussian images are needed anyway", "Since the Gaussian images are needed anyway"),
])
def test_a_located_passage_never_begins_or_ends_in_the_middle_of_a_formula(claimed, located):
    text = ("Subtracting two neighbouring levels of the pyramid gives the difference-of-Gaussians function\n\n"
            + FORMULA_8 + " (8)\n\nSince the Gaussian images are needed anyway, the difference costs one subtraction.")

    assert generation.locate_excerpt(claimed, text) == located


@pytest.mark.parametrize("excerpt, shown", [
    # ordinary prose of the full reading: quoted
    ("Subtracting two neighbouring levels of the pyramid gives the difference-of-Gaussians function", "shown"),
    # a recognised formula is in the passage: not quoted, the flag does not look at how the document was read
    ("gives the difference-of-Gaussians function " + FORMULA_8, "hidden_math"),
    # an inline formula that arrived flattened, with a sign the flag knows: not quoted
    ("Let nin of the n matches be inliers, so that the inlier fraction is w = nin/n", "hidden_math"),
    # the flag's known limit, in both modes: a flattened subscript on its own ("D0") is not seen, so this is quoted
    ("where D0 is the value at the sample and the gradient g and the Hessian H collect", "shown"),
])
def test_a_passage_with_a_formula_is_not_quoted_to_students_in_a_full_reading_either(
        client, instructor, learner, doc, fake_llm, excerpt, shown):
    marker = excerpt.split(" $$")[0][:40]
    fake_llm.queue(reply_about(marker, excerpt=excerpt))
    quiz = draft(client, instructor, doc["doc_id"], topic=excerpt[:60])
    q = quiz["questions"][0]
    assert q["grounded"], q["source"]

    assert q["passage_for_students"] == shown
    approve(client, instructor, quiz)
    publish(client, instructor, quiz)
    result = client.post(f"{BASE}/api/quizzes/{quiz['quiz_id']}/attempts", params={"token": learner},
                         json={"revision": 1, "answers": {}}).json()["results"][0]
    assert (result["source"]["excerpt"] is not None) == (shown == "shown")
    assert result["source"]["page"] == q["source"]["page"]
