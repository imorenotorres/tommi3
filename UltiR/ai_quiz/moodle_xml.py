"""Export: the questions of a published revision as a Moodle XML file.

Moodle's question bank imports this format ("Moodle XML format"). The file
holds one category, named after the quiz, and one multiple-choice question per
published question: the four options in the order the instructor approved,
the key as the only option that scores, the explanation as general feedback.

This seam knows nothing about HTTP, sessions or storage. It gets a revision
and returns bytes. Everything in a revision was typed by an instructor or
written by a model, so every text is escaped twice on its way out: once as
HTML, because Moodle shows these fields as HTML, and once as XML, by the
library that writes the file. Nothing here builds markup from a text.

Not exported: figures. A question that is shown with a figure in the tool
arrives in Moodle without it.
"""

import html
import re
import unicodedata
from xml.etree import ElementTree as ET

# The same rule as static/math.js: $$…$$ first; a single $ opens a formula only if no space follows
# it, and closes one only if no space comes before it and no digit after it ("$5 and $6" is text).
_FORMULA = re.compile(r"\$\$(.+?)\$\$|\$((?:[^\s$\\]|\\.)(?:(?:[^$\\]|\\.)*?(?:[^\s$\\]|\\.))?)\$(?!\d)", re.DOTALL)

# Characters an XML 1.0 file may not contain at all, escaped or not.
_NOT_XML = re.compile("[^\t\n\r\x20-퟿-�\U00010000-\U0010ffff]")

CATEGORY_ROOT = "$course$/top/"        # Moodle: a category at the top of the course the file is imported into


def _html(text: str, latex: bool) -> str:
    """`text` as HTML for Moodle. With `latex`, formulas get the delimiters of Moodle's MathJax filter.

    The tool writes a formula between dollar signs. Moodle's MathJax filter reads \\( … \\) inside
    a line and \\[ … \\] set apart, and leaves a single dollar sign alone.
    """
    text = _NOT_XML.sub("", text or "")
    if not latex:
        return html.escape(text, quote=False)
    parts, last = [], 0
    for match in _FORMULA.finditer(text):
        parts.append(html.escape(text[last:match.start()], quote=False))
        set_apart = match.group(1) is not None
        tex = html.escape((match.group(1) if set_apart else match.group(2)).strip(), quote=False)
        parts.append(f"\\[{tex}\\]" if set_apart else f"\\({tex}\\)")
        last = match.end()
    parts.append(html.escape(text[last:], quote=False))
    return "".join(parts)


def _text(parent: ET.Element, tag: str, value: str, **attributes) -> ET.Element:
    """<tag …><text>value</text></tag>, the shape of nearly every field of the format."""
    node = ET.SubElement(parent, tag, attributes)
    ET.SubElement(node, "text").text = value
    return node


def _plain(parent: ET.Element, tag: str, value: str) -> None:
    ET.SubElement(parent, tag).text = value


def category_path(title: str) -> str:
    """The category the questions go into. Moodle reads "/" as "sub-category", and "//" as the sign itself."""
    return CATEGORY_ROOT + _NOT_XML.sub("", title).replace("/", "//")


def file_name(revision: dict) -> str:
    """A name for the download: plain ASCII letters, digits and hyphens, whatever the title is."""
    plain = unicodedata.normalize("NFKD", revision.get("title") or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:60].strip("-")
    return f"ai-quiz-{slug or 'quiz'}-v{int(revision['revision'])}.xml"


def export(revision: dict) -> bytes:
    """The Moodle XML file for one published revision, as UTF-8 bytes."""
    title = _NOT_XML.sub("", revision["title"])
    quiz = ET.Element("quiz")
    category = ET.SubElement(quiz, "question", {"type": "category"})
    _text(category, "category", category_path(title))
    _text(category, "info", "", format="html")

    for number, question in enumerate(revision["questions"], start=1):
        latex = question.get("math") == "latex"
        node = ET.SubElement(quiz, "question", {"type": "multichoice"})
        _text(node, "name", f"{title} {number:02d}")
        _text(node, "questiontext", f"<p>{_html(question['question'], latex)}</p>", format="html")
        explanation = _html(question.get("explanation") or "", latex)
        _text(node, "generalfeedback", f"<p>{explanation}</p>" if explanation else "", format="html")
        _plain(node, "defaultgrade", "1")
        _plain(node, "penalty", "0.3333333")
        _plain(node, "hidden", "0")
        _plain(node, "single", "true")
        # The order the instructor approved is kept: an explanation may name an option by its letter.
        _plain(node, "shuffleanswers", "false")
        _plain(node, "answernumbering", "ABCD")
        for name in ("correctfeedback", "partiallycorrectfeedback", "incorrectfeedback"):
            _text(node, name, "", format="html")
        for option in question["options"]:
            fraction = "100" if option["id"] == question["correct_option_id"] else "0"
            answer = _text(node, "answer", _html(option["text"], latex), fraction=fraction, format="html")
            _text(answer, "feedback", "", format="html")

    ET.indent(quiz)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(quiz, encoding="utf-8") + b"\n"
