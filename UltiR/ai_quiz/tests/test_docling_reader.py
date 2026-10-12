"""The Docling reader: what becomes of a worker result, when full reading is available, and how the worker is run.

Docling itself is not needed here. `build_document` is checked against a part
of a real worker result (docling_recorded.py); the worker process is replaced
by a small program of the tests. One test at the end runs the real thing, and
only when asked to.
"""

import copy
import json
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from UltiR.ai_quiz import docling_reader, ingestion, limits, storage

from .conftest import cid
from .docling_recorded import RAW, images
from .images import SVG, jpeg_start, png
from .pdfs import handout_pdf
from .test_documents import DOCS, upload

FORMULA = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)


def build(raw=None, pictures=None) -> ingestion.ParsedDocument:
    return docling_reader.build_document(copy.deepcopy(RAW) if raw is None else raw,
                                         images() if pictures is None else pictures)


def recorded(**changes) -> dict:
    raw = copy.deepcopy(RAW)
    raw.update(changes)
    return raw


def page(parsed, number) -> str:
    return parsed.pages[number - 1].text


def everything(parsed) -> str:
    return "\n\n".join(p.text for p in parsed.pages)


def text_item(text, page_number=3, **more) -> dict:
    return {"kind": "text", "label": "text", "text": text, "orig": text,
            "prov": [{"page": page_number, "charspan": [0, len(text)]}], **more}


# ── Pages ───────────────────────────────────────────────────────────────────

def test_every_page_of_the_pdf_has_an_entry_numbered_from_one():
    parsed = build()

    assert [p.number for p in parsed.pages] == list(range(1, 19))
    assert (parsed.mode, parsed.engine) == ("full", "docling")
    assert "difference-of-Gaussians" in page(parsed, 3)
    assert "Binary descriptors replace histograms" in page(parsed, 7)
    assert page(parsed, 1) == ""                                # no item of page 1 is in the recording


def test_a_paragraph_that_runs_over_a_page_break_is_split_where_docling_says():
    item = next(i for i in RAW["items"] if len(i["prov"]) == 2)
    (first, second), (start, end) = [p["page"] for p in item["prov"]], item["prov"][1]["charspan"]
    assert (first, second) == (2, 3)

    parsed = build()

    assert item["text"][:80] in page(parsed, 2)
    assert item["text"][start:end][:80] in page(parsed, 3)
    assert item["text"][:80] not in page(parsed, 3)
    assert item["text"][start:end][:80] not in page(parsed, 2)


def test_items_without_a_usable_page_are_left_out():
    strays = [
        {"kind": "text", "label": "text", "text": "ORPHAN without provenance", "prov": []},
        text_item("ORPHAN beyond the last page", 99),
        text_item("ORPHAN on page zero", 0),
        {"kind": "text", "label": "text", "text": "ORPHAN with a page that is not a number", "prov": [{"page": "3"}]},
        {"kind": "text", "label": "text", "text": "ORPHAN with a page that is a truth value", "prov": [{"page": True}]},
        "ORPHAN that is not an item at all",
    ]
    raw = recorded(items=RAW["items"] + strays)

    assert "ORPHAN" not in everything(build(raw))


def test_a_result_with_fields_of_the_wrong_kind_does_not_break_the_reader():
    odd = [
        {"kind": "text", "text": 5, "prov": [{"page": 2, "charspan": "ab"}, {"page": 3, "charspan": None}]},
        {"kind": "formula", "text": None, "orig": ["x"], "prov": [{"page": 2}]},
        {"kind": "table", "rows": "not rows", "prov": [{"page": 2}]},
        {"kind": "table", "rows": [["a", 7, None], "not a row"], "prov": [{"page": 2}]},
        {"kind": "picture", "file": 12, "caption": None, "width": "wide", "height": None, "prov": [{"page": 2}]},
        {"kind": "something new", "prov": [{"page": 2}]},
    ]

    parsed = build(recorded(items=RAW["items"] + odd))

    assert len(parsed.figures) == 3


@pytest.mark.parametrize("raw, error", [
    (recorded(items=[]), "no_text"),
    (recorded(n_pages=0), "no_text"),
    (recorded(n_pages="18"), "no_text"),
    (recorded(n_pages=limits.MAX_FULL_READING_PAGES + 1), "too_long"),
])
def test_a_result_with_nothing_usable_in_it_is_an_unreadable_document(raw, error):
    with pytest.raises(ingestion.Unreadable) as refused:
        build(raw)

    assert refused.value.code == error


def test_a_result_of_an_unknown_version_is_not_guessed_at():
    with pytest.raises(RuntimeError):
        build(recorded(version=2))


# ── Formulas ────────────────────────────────────────────────────────────────

def test_a_recognised_formula_is_kept_as_latex_between_double_dollars_with_its_number():
    parsed = build()

    assert r"$$D ( x , y , \sigma ) = L ( x , y , k \sigma ) - L ( x , y , \sigma ) .$$ (8)" in page(parsed, 3)
    assert r"$$\hat { \delta } = - H ^ { - 1 } g ,$$ (12)" in page(parsed, 4)


def test_formula_delimiters_come_in_pairs_and_never_inside_a_formula():
    parsed = build()

    formulas = FORMULA.findall(everything(parsed))
    assert len(formulas) >= 10
    assert all(p.text.count("$$") % 2 == 0 for p in parsed.pages)
    assert not any("$" in formula for formula in formulas)
    assert all(docling_reader.formula_is_sound(formula) for formula in formulas)


def test_a_formula_that_came_out_broken_is_given_as_the_page_s_own_text_instead():
    parsed = build()

    text = page(parsed, 15)
    assert r"\ a b s" not in text and "p s b s b" not in text           # formula 41, with a stray "&"
    assert "(1 - ws )N ≤ 1 - p" in text
    assert r"\overline" not in text                                      # the pseudocode read as one formula
    assert "2: while c < N do" in text
    assert r"$$N = \left \lceil" in text                                 # formula 42 on the same page is fine
    assert {"code": "formulas_as_text", "pages": [15]} in parsed.warnings


def test_the_text_used_instead_of_a_broken_formula_carries_no_private_use_characters():
    raw = recorded()
    formula = next(i for i in raw["items"] if i["kind"] == "formula" and "" in i["orig"])
    formula["text"] += " }"                                              # now it does not pass the check

    parsed = build(raw)

    assert "log(1 - p) log (1 - ( |I ∗ | n )s)" in page(parsed, 15)
    assert not re.search("[-]", everything(parsed))


@pytest.mark.parametrize("latex", [
    r"a ^ { 2 } + b ^ { 2 } = c ^ { 2 }",
    r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
    r"\tau = \begin{cases} 1 & \text {if } a < b , \\ 0 & \text {otherwise,} \end{cases}",
    r"\{ x \} \cup \{ y \}",
    r"a \& b",
    r"N = \left \lceil \frac { \log ( 1 - p ) } { \log \left ( 1 - w ^ { s } \right ) } \right \rceil \leftarrow \rightarrow",
])
def test_ordinary_formulas_pass_the_check(latex):
    assert docling_reader.formula_is_sound(latex)


@pytest.mark.parametrize("latex", [
    "",
    "   ",
    r"p ( N ) & = ( 1 - w ^ { s } ) ^ { N } \\ & \leq 1 - p",           # alignment marks without an environment
    r"\frac { 1 } { 2",
    r"x } { y",
    r"\begin{cases} 1 & a \\ 0 & b",
    r"F = K ^ { \prime - \top } \left [ t | _ { \times } \, R \, K ^ { - 1 } , \quad \left [ t \right ] _ { \times }",   # \left without its \right
    r"\left ( a \right ) \right ]",
    r"a $ b",
    r"\frac { \text {Algorithm 1 RANSAC with an adaptive number of iterations} } { x }",
    "x + " * 400,
])
def test_broken_formulas_do_not_pass_the_check(latex):
    assert not docling_reader.formula_is_sound(latex)


def test_double_dollars_in_ordinary_text_cannot_open_a_formula():
    raw = recorded(items=RAW["items"] + [text_item("The licence costs $$5 per seat and $$7 per site.", 2)])

    parsed = build(raw)

    assert "costs $ $5 per seat" in page(parsed, 2)
    assert page(parsed, 2).count("$$") % 2 == 0


# ── Figures ─────────────────────────────────────────────────────────────────

def test_figures_get_our_own_ids_their_page_and_their_caption_and_the_logo_is_not_one():
    parsed = build()

    assert [(f.figure_id, f.page, f.media_type) for f in parsed.figures] == [
        ("f0001", 3, "image/png"), ("f0002", 4, "image/png"), ("f0003", 7, "image/png")]
    assert parsed.figures[0].caption.startswith("Figure 1: Scale-space pyramid with three octaves")
    assert parsed.figures[1].caption.startswith("Figure 2: Response of the difference of Gaussians to a blob.")
    assert (parsed.figures[0].width, parsed.figures[0].height) == (789, 494)
    assert parsed.figures[0].image == images()["p0004.png"]


def test_a_caption_without_its_figure_label_is_replaced_by_the_labelled_caption_on_the_page():
    picture = next(i for i in RAW["items"] if i["kind"] == "picture" and i["prov"][0]["page"] == 7 and i["width"] > 100)
    assert picture["caption"] == "4 by 4 cells with 8 orientation bins"   # what Docling attached

    parsed = build()

    assert parsed.figures[2].caption.startswith("Figure 5: Construction of a gradient histogram descriptor.")


def test_a_figure_is_marked_in_the_text_of_its_page_and_its_caption_is_written_once():
    parsed = build()

    assert "[FIGURE f0001] Figure 1: Scale-space pyramid" in page(parsed, 3)
    assert page(parsed, 3).count("Figure 1: Scale-space pyramid") == 1
    assert "[FIGURE f0003] Figure 5: Construction" in page(parsed, 7)
    assert page(parsed, 7).count("Figure 5: Construction") == 1
    assert docling_reader.FIGURE_MARK.findall(everything(parsed)) == ["f0001", "f0002", "f0003"]


def test_figure_ids_do_not_depend_on_the_names_the_worker_gave_its_files():
    raw, pictures = recorded(), images()
    for item in raw["items"]:
        if item["kind"] == "picture":
            renamed = f"p{9000 + int(item['file'][1:5]):04d}.png"
            pictures[renamed] = pictures.pop(item["file"])
            item["file"] = renamed

    parsed = build(raw, pictures)

    assert [f.figure_id for f in parsed.figures] == ["f0001", "f0002", "f0003"]


@pytest.mark.parametrize("data, kept, dropped", [
    (SVG, False, 1),                                    # not an image by its first bytes
    (b"GIF89a" + b"\x00" * 200, False, 1),
    (b"<html><script>alert(1)</script></html>", False, 1),
    (jpeg_start(), True, 0),                            # a JPEG is accepted; its size is the worker's word
    (png(60, 400), False, 0),                           # an image, but too narrow to be a figure
    (b"", False, 0),                                    # no image was made: nothing to drop
])
def test_only_png_and_jpeg_images_of_a_sensible_size_become_figures(data, kept, dropped):
    pictures = images()
    pictures["p0004.png"] = data                        # the file of Figure 1

    parsed = build(pictures=pictures)

    assert (len(parsed.figures) == 3) == kept
    assert any(f.caption.startswith("Figure 1:") for f in parsed.figures) == kept
    assert ({"code": "figures_dropped", "count": 1} in parsed.warnings) == bool(dropped)
    if not kept:
        assert "[FIGURE f0003]" not in everything(parsed)   # no mark for a figure that does not exist


def test_the_size_of_a_png_is_read_from_the_image_not_taken_from_the_worker():
    pictures = images()
    pictures["p0003.png"] = png(800, 500)               # the logo's file, which the result calls 30 by 28

    parsed = build(pictures=pictures)

    assert len(parsed.figures) == 4
    assert (parsed.figures[0].width, parsed.figures[0].height) == (800, 500)


def test_an_image_over_the_size_limit_is_dropped(monkeypatch):
    sizes = sorted(len(data) for data in images().values())
    assert sizes[-1] > sizes[-2]                              # one file is the largest: one of the three figures
    monkeypatch.setattr(limits, "MAX_FIGURE_BYTES", sizes[-1] - 1)

    parsed = build()

    assert len(parsed.figures) == 2
    assert {"code": "figures_dropped", "count": 1} in parsed.warnings


def test_the_number_of_figures_per_document_is_capped(monkeypatch):
    monkeypatch.setattr(limits, "MAX_FIGURES_PER_DOCUMENT", 1)

    parsed = build()

    assert [f.figure_id for f in parsed.figures] == ["f0001"]
    assert {"code": "figures_dropped", "count": 2} in parsed.warnings


def test_a_very_long_caption_is_shortened(monkeypatch):
    monkeypatch.setattr(limits, "MAX_CAPTION_CHARS", 60)

    parsed = build()

    assert all(len(f.caption) <= 61 for f in parsed.figures)
    assert parsed.figures[0].caption.startswith("Figure 1: Scale-space pyramid")


# ── Tables ──────────────────────────────────────────────────────────────────

def test_a_table_becomes_one_line_of_text_per_row():
    table = {"kind": "table", "prov": [{"page": 2, "charspan": [0, 0]}],
             "rows": [["Threshold", "Accepted", "Correct"], ["0.5", "213", "213"], ["0.8", "550", "528"]]}

    parsed = build(recorded(items=RAW["items"] + [table]))

    assert "Threshold | Accepted | Correct\n\n0.5 | 213 | 213\n\n0.8 | 550 | 528" in page(parsed, 2)
    assert {"code": "table_collapsed", "pages": [2]} not in parsed.warnings


def test_a_table_that_collapsed_into_one_row_is_kept_as_text_and_reported():
    parsed = build()

    assert "Descriptor | Dimension | Type | Distance measure" in page(parsed, 8)
    assert "SIFT RootSIFT SURF BRIEF ORB BRISK FREAK" in page(parsed, 8)
    assert {"code": "table_collapsed", "pages": [8]} in parsed.warnings


# ── Chunks of a full reading ────────────────────────────────────────────────

@pytest.mark.parametrize("size", [150, 300, 600, 1200])
def test_a_chunk_never_ends_inside_a_formula(monkeypatch, size):
    monkeypatch.setattr(ingestion, "CHUNK_CHARS", size)
    parsed = build()

    chunks = ingestion.chunk_pages(parsed.pages)

    assert all(c["text"].count("$$") % 2 == 0 for c in chunks)
    in_pages = sorted(" ".join(f.split()) for f in FORMULA.findall(everything(parsed)))
    in_chunks = sorted(" ".join(f.split()) for c in chunks for f in FORMULA.findall(c["text"]))
    assert in_chunks == in_pages                              # every formula is whole in exactly one chunk
    too_long = [c["text"] for c in chunks if len(c["text"]) > size]
    assert all(t.startswith("$$") and t.count("$$") == 2 for t in too_long)   # only a formula longer than a chunk


def test_chunks_of_a_full_reading_keep_their_page():
    chunks = ingestion.chunk_pages(build().pages)

    by_formula = {c["page"] for c in chunks if r"\hat { \delta } = - H ^ { - 1 } g" in c["text"]}
    assert by_formula == {4}
    assert {c["page"] for c in chunks} == {2, 3, 4, 5, 6, 7, 8, 15}     # 6: the first half of a paragraph that ends on 7


# ── What the worker left behind is read with care ───────────────────────────

def leave(folder: Path, items, **files):
    (folder / "result.json").write_text(json.dumps({"version": 1, "n_pages": 1, "items": items}), encoding="utf-8")
    for name, data in files.items():
        (folder / name).write_bytes(data)


def test_only_images_with_the_worker_s_own_kind_of_name_are_read(tmp_path):
    out, outside = tmp_path / "out", tmp_path / "secret.png"
    out.mkdir()
    outside.write_bytes(png(200, 200))
    leave(out, [{"kind": "picture", "file": name} for name in
                ["p0001.png", "../secret.png", str(outside), "p0002.png", "p0003.png", "P0001.PNG", "p1.png", 7, None]],
          **{"p0001.png": png(200, 200), "p0003.png": b"x" * 50})
    (out / "p0002.png").symlink_to(outside)                   # a name of the right shape that leads elsewhere

    raw, pictures = docling_reader._collect(out)

    assert sorted(pictures) == ["p0001.png", "p0003.png"]
    assert len(raw["items"]) == 9


def test_an_image_over_the_size_limit_is_not_read_at_all(tmp_path, monkeypatch):
    monkeypatch.setattr(limits, "MAX_FIGURE_BYTES", 100)
    leave(tmp_path, [{"kind": "picture", "file": "p0001.png"}], **{"p0001.png": b"x" * 101})

    assert docling_reader._collect(tmp_path)[1] == {}


@pytest.mark.parametrize("content", [None, "[]", '{"items": "none"}', "not json"])
def test_a_missing_or_misshapen_result_is_a_failure(tmp_path, content):
    if content is not None:
        (tmp_path / "result.json").write_text(content, encoding="utf-8")

    with pytest.raises((RuntimeError, ValueError)):
        docling_reader._collect(tmp_path)


def test_a_result_over_the_size_limit_is_not_read(tmp_path, monkeypatch):
    leave(tmp_path, [])
    monkeypatch.setattr(docling_reader, "MAX_RESULT_BYTES", 10)

    with pytest.raises(RuntimeError):
        docling_reader._collect(tmp_path)


# ── When full reading is available ──────────────────────────────────────────

@pytest.fixture
def engine(monkeypatch, tmp_path):
    """A server on which everything full reading needs is in place (the probes are answered, not run)."""
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setenv("AI_QUIZ_DOCLING_PYTHON", sys.executable)
    monkeypatch.setenv("AI_QUIZ_DOCLING_MODELS", str(models))
    monkeypatch.setattr(docling_reader, "_can_block_network", lambda: True)
    monkeypatch.setattr(docling_reader, "_has_docling", lambda python: True)
    return monkeypatch


def test_full_reading_is_available_when_everything_it_needs_is_there(engine):
    assert docling_reader.unavailable_reason() is None
    assert ingestion.full_reading_available()
    assert ingestion.get_reader("full").name == "docling"


def test_without_the_setting_full_reading_is_unavailable_and_text_reading_is_not_affected(client, launch):
    token = launch.token(role="Instructor")

    assert "AI_QUIZ_DOCLING_PYTHON" in docling_reader.unavailable_reason()
    assert not ingestion.full_reading_available()
    with pytest.raises(ingestion.ReaderUnavailable):
        ingestion.get_reader("full")
    assert upload(client, token, mode="full").json()["detail"]["code"] == "full_reading_unavailable"
    assert upload(client, token).status_code == 201


@pytest.mark.parametrize("break_it, word", [
    (lambda m, tmp: m.setenv("AI_QUIZ_DOCLING_PYTHON", "python3"), "interpreter"),            # not a full path
    (lambda m, tmp: m.setenv("AI_QUIZ_DOCLING_PYTHON", os.path.relpath(sys.executable)), "interpreter"),   # nor this
    (lambda m, tmp: m.setenv("AI_QUIZ_DOCLING_PYTHON", str(tmp / "no-such-python")), "interpreter"),
    (lambda m, tmp: m.setenv("AI_QUIZ_DOCLING_PYTHON", str(tmp / "models")), "interpreter"),  # a folder
    (lambda m, tmp: m.setenv("AI_QUIZ_DOCLING_PYTHON", __file__), "interpreter"),             # a file that cannot be run
    (lambda m, tmp: m.setenv("AI_QUIZ_DOCLING_MODELS", str(tmp / "no-models")), "models"),
    (lambda m, tmp: m.setattr(docling_reader, "_can_block_network", lambda: False), "network"),
    (lambda m, tmp: m.setattr(docling_reader, "_has_docling", lambda python: False), "docling package"),
])
def test_one_missing_piece_makes_full_reading_unavailable(engine, tmp_path, break_it, word):
    break_it(engine, tmp_path)

    assert word in docling_reader.unavailable_reason()
    assert not ingestion.full_reading_available()
    with pytest.raises(ingestion.ReaderUnavailable):
        ingestion.get_reader("full")


@pytest.mark.parametrize("value, device", [("cuda", "cuda"), (" CPU ", "cpu"), ("", "auto"), ("gpu; rm -rf /", "auto")])
def test_the_device_setting_takes_three_values_and_nothing_else(monkeypatch, value, device):
    from UltiR.ai_quiz import config

    monkeypatch.setenv("AI_QUIZ_DOCLING_DEVICE", value)

    assert config.docling_device() == device


def test_the_interpreter_is_asked_whether_it_has_docling_without_importing_it():
    docling_reader._has_docling.cache_clear()

    assert docling_reader._has_docling(sys.executable) is False     # the repo's own environment has none
    assert docling_reader._has_docling("/no/such/python") is False


# ── Running the worker ──────────────────────────────────────────────────────
# The worker here is a small program of the test, run exactly as the real one would be.

needs_unshare = pytest.mark.skipif(not docling_reader._can_block_network(),
                                   reason="this machine cannot start a process without network access")

STUB = '''
import json, os, socket, sys, time
pdf, out = sys.argv[1], sys.argv[2]
order = open(pdf, encoding="utf-8").read().split()
report = {"argv": sys.argv[1:], "env": sorted(os.environ), "pid": os.getpid(), "cwd": os.getcwd()}
open(os.path.join(os.path.dirname(pdf), "worker-started"), "w").write(str(os.getpid()))
if order[0] == "connect":
    try:
        socket.create_connection(("127.0.0.1", int(order[1])), timeout=2).close()
        report["network"] = "reached"
    except OSError as error:
        report["network"] = "blocked"
if order[0] == "sleep":
    time.sleep(20)
if order[0] == "fail":
    print("details of the failure", file=sys.stderr)
    sys.exit(3)
json.dump({"version": 1, "n_pages": 1, "items": [], "report": report}, open(os.path.join(out, "result.json"), "w"))
if order[0] == "fail-late":
    sys.exit(3)
'''


@pytest.fixture
def stub(engine, tmp_path):
    """Full reading set up to run the test's own worker. Returns the folder the 'PDF' goes into."""
    worker = tmp_path / "stub_worker.py"
    worker.write_text(STUB, encoding="utf-8")
    engine.setattr(docling_reader, "WORKER", worker)
    folder = tmp_path / "doc"
    folder.mkdir()
    return folder


def order(folder: Path, text: str) -> Path:
    pdf = folder / "source.pdf"
    pdf.write_text(text, encoding="utf-8")
    return pdf


@needs_unshare
def test_the_worker_gets_the_document_a_folder_of_its_own_and_none_of_the_server_s_settings(stub, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET", "must-not-leak")
    monkeypatch.setenv("MISTRAL_API_KEY", "must-not-leak")
    monkeypatch.setenv("AI_QUIZ_DOCLING_DEVICE", "cpu")
    pdf = order(stub, "run")

    raw, pictures = docling_reader.run_worker(pdf)

    report = raw["report"]
    assert report["argv"][0] == str(pdf)
    assert Path(report["argv"][1]).parent == stub                       # its folder is inside the document's
    assert report["argv"][2:4] == [os.environ["AI_QUIZ_DOCLING_MODELS"], "cpu"]
    assert not [name for name in report["env"] if name.startswith("AI_QUIZ") or "KEY" in name or "SECRET" in name]
    assert set(report["env"]) >= {"PATH", "HOME", "HF_HUB_OFFLINE"}
    assert pictures == {}
    assert [p.name for p in stub.iterdir() if p.name.startswith("reading-")] == []   # and it is gone afterwards


@needs_unshare
def test_the_worker_cannot_reach_the_network_not_even_this_machine(stub):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)

        raw, _ = docling_reader.run_worker(order(stub, f"connect {listener.getsockname()[1]}"))

    assert raw["report"]["network"] == "blocked"


@needs_unshare
@pytest.mark.parametrize("how", ["fail", "fail-late"])       # fail-late: a result was written, then the worker failed
def test_a_worker_that_fails_is_a_failed_reading_and_leaves_nothing(stub, how):
    with pytest.raises(RuntimeError) as failure:
        docling_reader.run_worker(order(stub, how))

    assert "code 3" in str(failure.value)
    assert "details" not in str(failure.value)
    assert [p.name for p in stub.iterdir() if p.name.startswith("reading-")] == []


@needs_unshare
def test_a_running_worker_is_killed_when_the_reading_is_stopped(stub):
    stop = threading.Event()
    pdf = order(stub, "sleep")
    threading.Timer(0.5, stop.set).start()
    started = time.monotonic()

    with pytest.raises(ingestion.ReadingStopped):
        docling_reader.run_worker(pdf, stop)

    assert time.monotonic() - started < 10
    pid = int((stub / "worker-started").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)                                                 # the process no longer exists
    assert [p.name for p in stub.iterdir() if p.name.startswith("reading-")] == []


def test_the_worker_is_not_started_when_full_reading_is_unavailable(tmp_path):
    with pytest.raises(ingestion.ReaderUnavailable):
        docling_reader.run_worker(order(tmp_path, "run"))

    assert not (tmp_path / "worker-started").exists()


# ── Through the tool ────────────────────────────────────────────────────────

def test_a_pdf_uploaded_for_full_reading_ends_up_as_pages_and_chunks_from_docling(client, launch, engine):
    engine.setattr(docling_reader, "run_worker", lambda pdf, stop=None: (copy.deepcopy(RAW), images()))
    token = launch.token(role="Instructor", course="course-A")

    doc = upload(client, token, mode="full").json()
    deadline = time.monotonic() + 5
    while client.get(f"{DOCS}/{doc['doc_id']}", params={"token": token}).json()["status"] == "processing":
        assert time.monotonic() < deadline
        time.sleep(0.01)
    done = client.get(f"{DOCS}/{doc['doc_id']}", params={"token": token}).json()

    assert (done["status"], done["mode"], done["engine"], done["n_pages"]) == ("ready", "full", "docling", 18)
    assert {"code": "formulas_as_text", "pages": [15]} in done["warnings"]
    chunks = storage.read_json(storage.course_dir(cid("course-A")) / "docs" / doc["doc_id"] / "chunks.json")
    assert any(r"$$\hat { \delta } = - H ^ { - 1 } g ,$$ (12)" in c["text"] and c["page"] == 4 for c in chunks)


# ── The real thing, only when asked for ─────────────────────────────────────

@pytest.mark.skipif(not os.environ.get("AI_QUIZ_TEST_DOCLING_PYTHON"),
                    reason="set AI_QUIZ_TEST_DOCLING_PYTHON to an interpreter with Docling to run the real reader")
def test_the_real_docling_reads_a_small_pdf_without_network(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_QUIZ_DOCLING_PYTHON", os.environ["AI_QUIZ_TEST_DOCLING_PYTHON"])
    docling_reader._has_docling.cache_clear()
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(handout_pdf())

    parsed = ingestion.get_reader("full").read(pdf)

    assert [p.number for p in parsed.pages] == [1, 2, 3]
    assert "ratio test" in page(parsed, 2) and "RANSAC" in page(parsed, 3)
    assert "ratio test" not in page(parsed, 1)
    assert list(tmp_path.iterdir()) == [pdf]
