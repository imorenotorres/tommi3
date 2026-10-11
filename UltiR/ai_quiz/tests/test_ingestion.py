"""Reading a stored file into pages and chunks (the ingestion seam). No HTTP here."""

import pytest

from UltiR.ai_quiz import ingestion

from .pdfs import HANDOUT, HEADER, handout_pdf, make_pdf, scanned_pdf


def read(tmp_path, name: str, data: bytes, mode: str = "text"):
    path = tmp_path / name
    path.write_bytes(data)
    return ingestion.get_reader(mode).read(path)


# ── Text reader ─────────────────────────────────────────────────────────────

def test_pdf_pages_are_numbered_from_one_and_keep_their_own_text(tmp_path):
    parsed = read(tmp_path, "h.pdf", handout_pdf())

    assert [p.number for p in parsed.pages] == [1, 2, 3]
    assert "ratio test" in parsed.pages[1].text
    assert "ratio test" not in parsed.pages[0].text
    assert "RANSAC" in parsed.pages[2].text
    assert (parsed.mode, parsed.engine) == ("text", "pypdf")


def test_text_and_markdown_files_are_one_page_without_a_number(tmp_path):
    for name in ("notes.txt", "notes.md"):
        parsed = read(tmp_path, name, "# Visión\n\nLa correspondencia de características…".encode("utf-8"))

        assert [p.number for p in parsed.pages] == [None]
        assert "correspondencia de características" in parsed.pages[0].text
        assert parsed.engine == "plain"


def test_running_header_and_bare_page_numbers_are_removed(tmp_path):
    parsed = read(tmp_path, "h.pdf", handout_pdf())

    for page in parsed.pages:
        assert HEADER not in page.text
        assert page.text.strip().splitlines()[-1] != str(page.number)
    assert "A local feature is an image pattern" in parsed.pages[0].text


def test_a_line_that_repeats_on_a_two_page_document_is_kept(tmp_path):
    # Too few pages to tell a running header from content.
    parsed = read(tmp_path, "two.pdf", make_pdf([["Same first line", "page one text is here for the reader"],
                                                 ["Same first line", "page two text is here for the reader"]]))

    assert "Same first line" in parsed.pages[0].text


def test_ligatures_and_line_end_hyphens_are_repaired(tmp_path):
    parsed = read(tmp_path, "t.txt", "The ﬁrst ﬂow of the rank-\ning step is efﬁcient.".encode("utf-8"))

    assert "The first flow of the ranking step is efficient." in parsed.pages[0].text.replace("\n", " ")


def test_superscripts_are_not_silently_turned_into_plain_digits(tmp_path):
    parsed = read(tmp_path, "t.txt", "The area is 3 m² and the ratio is ½.".encode("utf-8"))

    assert "m²" in parsed.pages[0].text
    assert "½" in parsed.pages[0].text


def test_a_pdf_without_a_text_layer_is_reported_as_a_scan(tmp_path):
    with pytest.raises(ingestion.Unreadable) as error:
        read(tmp_path, "scan.pdf", scanned_pdf())

    assert error.value.code == "no_text"


def test_a_pdf_with_some_empty_pages_is_read_and_says_which(tmp_path):
    parsed = read(tmp_path, "mixed.pdf", make_pdf([HANDOUT[0], [], HANDOUT[2]]))

    assert [p.number for p in parsed.pages] == [1, 2, 3]
    assert {"code": "pages_without_text", "pages": [2]} in parsed.warnings


def test_a_broken_pdf_is_reported_as_corrupt(tmp_path):
    with pytest.raises(ingestion.Unreadable) as error:
        read(tmp_path, "broken.pdf", b"%PDF-1.4\nthis is not really a pdf\n")

    assert error.value.code == "corrupt"


def test_a_text_file_with_nothing_in_it_is_reported_as_empty(tmp_path):
    with pytest.raises(ingestion.Unreadable) as error:
        read(tmp_path, "blank.txt", b"   \n\n  ")

    assert error.value.code == "no_text"


def test_full_reading_is_not_available_yet_and_says_why():
    with pytest.raises(ingestion.ReaderUnavailable) as error:
        ingestion.get_reader("full")

    assert error.value.reason


def test_an_unknown_reading_mode_is_refused():
    with pytest.raises(ValueError):
        ingestion.get_reader("magic")


# ── Chunks ──────────────────────────────────────────────────────────────────

def long_page(number: int, word: str, sentences: int = 60) -> ingestion.Page:
    text = " ".join(f"Sentence {i} of page {number} talks about {word} in some detail." for i in range(sentences))
    return ingestion.Page(number=number, text=text)


def test_every_chunk_carries_the_page_it_came_from_and_stays_within_the_size_limit():
    pages = [long_page(1, "apples"), long_page(2, "bridges"), long_page(3, "clouds")]

    chunks = ingestion.chunk_pages(pages)

    assert len(chunks) > 3
    assert all(len(c["text"]) <= ingestion.CHUNK_CHARS for c in chunks)
    for c in chunks:
        word = {1: "apples", 2: "bridges", 3: "clouds"}[c["page"]]
        assert word in c["text"]
        assert f"of page {c['page']} " in c["text"]


def test_chunks_lose_no_text_and_have_distinct_ids_in_reading_order():
    pages = [long_page(1, "apples"), long_page(2, "bridges")]

    chunks = ingestion.chunk_pages(pages)

    assert [c["chunk_id"] for c in chunks] == [f"c_{i:04d}" for i in range(1, len(chunks) + 1)]
    rebuilt = " ".join(c["text"] for c in chunks).split()
    assert rebuilt == " ".join(p.text for p in pages).split()


def test_chunks_break_at_sentence_ends_when_they_can():
    chunks = ingestion.chunk_pages([long_page(1, "apples")])

    assert all(c["text"].endswith(".") for c in chunks)


def test_a_file_without_pages_gives_chunks_without_page_numbers():
    chunks = ingestion.chunk_pages([ingestion.Page(number=None, text="One paragraph.\n\nAnother paragraph.")])

    assert [c["page"] for c in chunks] == [None]
    assert "One paragraph." in chunks[0]["text"] and "Another paragraph." in chunks[0]["text"]


def test_empty_pages_give_no_chunks():
    assert ingestion.chunk_pages([ingestion.Page(number=1, text="   \n ")]) == []


# ── Choosing chunks for a request ───────────────────────────────────────────

def chunks_about(*topics: str) -> list[dict]:
    return [{"chunk_id": f"c_{i:04d}", "page": i, "text": f"This passage explains {t} and nothing else at all."}
            for i, t in enumerate(topics, start=1)]


def test_a_topic_picks_the_chunks_that_talk_about_it():
    chunks = chunks_about("scale space", "descriptors", "the ratio test", "homography", "the ratio threshold")

    chosen = ingestion.select_chunks(chunks, topic="ratio", limit=2)

    assert [c["chunk_id"] for c in chosen] == ["c_0003", "c_0005"]


def test_without_a_topic_the_choice_is_spread_over_the_whole_document():
    chunks = chunks_about(*[f"topic {i}" for i in range(1, 11)])

    chosen = ingestion.select_chunks(chunks, topic="", limit=4)

    assert len(chosen) == 4
    assert chosen[0]["chunk_id"] == "c_0001"
    assert chosen[-1]["chunk_id"] == "c_0010"
    assert [c["chunk_id"] for c in chosen] == sorted(c["chunk_id"] for c in chosen)


def test_a_topic_nobody_mentions_falls_back_to_the_spread():
    chunks = chunks_about("scale space", "descriptors", "homography")

    chosen = ingestion.select_chunks(chunks, topic="zebra", limit=2)

    assert [c["chunk_id"] for c in chosen] == ["c_0001", "c_0003"]


def test_asking_for_more_chunks_than_exist_returns_them_all_once():
    chunks = chunks_about("a topic", "b topic")

    assert ingestion.select_chunks(chunks, topic="", limit=10) == chunks


def test_topic_matching_works_for_accented_words():
    chunks = chunks_about("la visión por computador", "el descriptor binario")

    chosen = ingestion.select_chunks(chunks, topic="visión", limit=1)

    assert [c["chunk_id"] for c in chosen] == ["c_0001"]
