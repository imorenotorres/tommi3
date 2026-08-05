"""Build a static keyword-indexed chunk database from PDFs and markdown docs.

Extracts text from all documents in data/docs/ and data/project_docs/,
splits into chunks, and tags each chunk with keywords derived from:
  - Paper concepts (from papers.json, matched by paper ID in filename)
  - TF-IDF-style top terms extracted from the chunk text itself

Output: data/chunk_db.json — a lightweight, vectorless search index.

Usage:
    python build_chunk_db.py                  # default settings
    python build_chunk_db.py --chunk-size 800 # custom chunk size
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(filepath: str) -> str:
    """Extract text from a PDF file."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts)
    except Exception as e:
        print(f"  Warning: could not extract {filepath}: {e}")
        return ""


def extract_md_text(filepath: str) -> str:
    """Read a markdown file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"  Warning: could not read {filepath}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Chunking (same logic as BaseRAGAgent smart chunking)
# ---------------------------------------------------------------------------

def smart_chunk(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks at natural boundaries."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if end < len(text):
            for sep in ["\n\n", ". ", "\n"]:
                last_sep = chunk.rfind(sep)
                if last_sep > chunk_size * 0.6:
                    chunk = chunk[: last_sep + len(sep)]
                    end = start + len(chunk)
                    break
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

# Common English stop words (kept small for speed)
STOP_WORDS = frozenset(
    "a an the and or but in on of to for is are was were be been being "
    "have has had do does did will would shall should may might can could "
    "this that these those it its i we you he she they them their our "
    "with from by at as not no nor so if than too very also about above "
    "after before between into through during over under up down out off "
    "then once here there when where which who whom what how all each "
    "both few more most other some such only own same just because "
    "while however although though even still already yet since until "
    "much many well back new also make like use used using one two "
    "first et al based among within results study studies paper work "
    "approach method methods proposed model data analysis research "
    "system systems found show shows shown figure table section "
    "different provide provides provided including included include "
    "respectively thus therefore hence moreover furthermore".split()
)

_WORD_RE = re.compile(r"[a-z][a-z0-9]{2,}", re.IGNORECASE)


def extract_keywords(text: str, top_n: int = 20) -> list[str]:
    """Extract top-N keywords from text using term frequency."""
    words = _WORD_RE.findall(text.lower())
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    counts = Counter(words)
    return [w for w, _ in counts.most_common(top_n)]


# ---------------------------------------------------------------------------
# Build the chunk database
# ---------------------------------------------------------------------------

def load_paper_concepts(agent_dir: str) -> dict:
    """Load concept tags per paper ID from papers.json."""
    papers_path = os.path.join(agent_dir, "data", "papers.json")
    concepts = {}  # paper_id -> list of concept names
    if not os.path.exists(papers_path):
        return concepts
    with open(papers_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for uni_data in data.get("universities", {}).values():
        for p in uni_data.get("papers", []):
            pid = p.get("id", "")
            if pid:
                concept_names = [
                    c["name"].lower()
                    for c in p.get("concepts", [])
                    if c.get("score", 0) >= 0.3
                ]
                title = p.get("title", "").lower()
                concepts[pid] = {
                    "concepts": concept_names,
                    "title": title,
                    "authors": [a.get("name", "") for a in p.get("authors", [])],
                }
        return concepts


def build_chunk_db(agent_dir: str, chunk_size: int = 600, overlap: int = 100) -> list[dict]:
    """Build the chunk database from all documents."""
    paper_meta = load_paper_concepts(agent_dir)
    chunks_db = []
    chunk_id = 0

    # Document directories
    docs_dirs = [os.path.join(agent_dir, "data", "docs")]
    config_path = os.path.join(agent_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        for extra in config.get("extra_docs_dirs", []):
            docs_dirs.append(os.path.join(agent_dir, "data", extra))

    for docs_dir in docs_dirs:
        if not os.path.exists(docs_dir):
            continue
        files = sorted(os.listdir(docs_dir))
        print(f"Processing {len(files)} files in {os.path.basename(docs_dir)}/...")

        for filename in files:
            filepath = os.path.join(docs_dir, filename)
            if not os.path.isfile(filepath):
                continue

            # Extract text
            if filename.endswith(".pdf"):
                text = extract_pdf_text(filepath)
            elif filename.endswith((".md", ".txt")):
                text = extract_md_text(filepath)
            else:
                continue

            if not text or len(text) < 50:
                continue

            # Get paper-level metadata if available (match by paper ID in filename)
            paper_id = filename.rsplit(".", 1)[0]  # e.g., "W12345" from "W12345.pdf"
            meta = paper_meta.get(paper_id, {})
            paper_concepts = meta.get("concepts", [])
            paper_title = meta.get("title", "")
            paper_authors = meta.get("authors", [])

            # Chunk the document
            doc_chunks = smart_chunk(text, chunk_size, overlap)

            for i, chunk_text in enumerate(doc_chunks):
                # Extract chunk-level keywords
                chunk_keywords = extract_keywords(chunk_text, top_n=15)

                # Combine paper concepts + chunk keywords (deduplicated)
                all_keywords = list(dict.fromkeys(paper_concepts + chunk_keywords))

                chunks_db.append({
                    "id": f"{filename}_{i}",
                    "source": filename,
                    "paper_id": paper_id if meta else "",
                    "paper_title": paper_title,
                    "chunk_index": i,
                    "text": chunk_text,
                    "keywords": all_keywords,
                })
                chunk_id += 1

    return chunks_db


# ---------------------------------------------------------------------------
# IDF computation (for BM25-style retrieval at query time)
# ---------------------------------------------------------------------------

def compute_idf(chunks_db: list) -> dict:
    """Compute IDF scores across all chunks for BM25 retrieval."""
    n_docs = len(chunks_db)
    doc_freq = Counter()
    for chunk in chunks_db:
        unique_words = set(chunk["keywords"])
        for w in unique_words:
            doc_freq[w] += 1
    idf = {}
    for word, df in doc_freq.items():
        idf[word] = round(math.log((n_docs - df + 0.5) / (df + 0.5) + 1), 4)
    return idf


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build vectorless chunk database")
    parser.add_argument("--agent-dir", default=os.path.dirname(__file__),
                        help="Agent directory (default: script directory)")
    parser.add_argument("--chunk-size", type=int, default=600, help="Chunk size in characters")
    parser.add_argument("--overlap", type=int, default=100, help="Chunk overlap in characters")
    parser.add_argument("--output", default=None, help="Output path (default: data/chunk_db.json)")
    args = parser.parse_args()

    agent_dir = os.path.abspath(args.agent_dir)
    output = args.output or os.path.join(agent_dir, "data", "chunk_db.json")

    print(f"Agent dir: {agent_dir}")
    print(f"Chunk size: {args.chunk_size}, overlap: {args.overlap}")

    chunks_db = build_chunk_db(agent_dir, args.chunk_size, args.overlap)

    if not chunks_db:
        print("No chunks extracted. Check that data/docs/ contains PDF/MD files.")
        return

    # Compute IDF for BM25 retrieval
    idf = compute_idf(chunks_db)

    # Save
    output_data = {
        "version": 1,
        "chunk_size": args.chunk_size,
        "overlap": args.overlap,
        "total_chunks": len(chunks_db),
        "total_sources": len(set(c["source"] for c in chunks_db)),
        "idf": idf,
        "chunks": chunks_db,
    }

    with open(output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False)

    size_mb = os.path.getsize(output) / (1024 * 1024)
    print(f"\nDone: {len(chunks_db)} chunks from {output_data['total_sources']} documents")
    print(f"IDF vocabulary: {len(idf)} terms")
    print(f"Saved: {output} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
