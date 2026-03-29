#!/usr/bin/env python3
"""
Add a manual (non-OpenAlex) paper to a RAG+Metadata agent.

Copies the PDF into the agent's data/docs/ directory and updates
metadata.json and researchers.json so the agent picks it up on next restart.

Usage:
  python add_paper.py --agent responsible_ai \
      --pdf /path/to/paper.pdf \
      --university UMA \
      --title "Paper Title" \
      --authors "Author One, Author Two" \
      [--year 2025] [--date 2025-06-15] [--doi https://doi.org/...]

  # Interactive mode (prompts for missing fields):
  python add_paper.py --agent responsible_ai --pdf /path/to/paper.pdf
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

SCRIPT_DIR = Path(__file__).resolve().parent
AGENTS_DIR = SCRIPT_DIR.parent / "agents"


def load_json(path: Path) -> dict | list:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Updated {path.name}")


def load_config(agent_dir: Path) -> dict:
    config_path = agent_dir / "config.json"
    if not config_path.exists():
        print(f"Error: {config_path} not found")
        sys.exit(1)
    return load_json(config_path)


def valid_universities(config: dict) -> list[str]:
    return list(config.get("universities", {}).keys())


def prompt_if_missing(value, prompt_text: str, required: bool = True) -> str:
    if value:
        return value
    val = input(f"  {prompt_text}: ").strip()
    if required and not val:
        print("Error: This field is required.")
        sys.exit(1)
    return val


def generate_paper_id() -> str:
    """Generate a unique ID for manual papers (M prefix + timestamp)."""
    return f"M{datetime.now().strftime('%Y%m%d%H%M%S')}"


def extract_pdf_metadata(pdf_path: Path) -> dict:
    """Extract metadata from PDF: title, authors, year, date, DOI.

    Reads both the PDF info dict (embedded metadata) and the first page text
    to maximise the chance of finding useful fields.
    """
    result = {"title": None, "authors": None, "year": None, "date": None, "doi": None}

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"  Warning: could not read PDF: {e}")
        return result

    # --- 1. Embedded PDF metadata ---
    info = reader.metadata
    if info:
        if info.title and info.title.strip():
            result["title"] = info.title.strip()
        if info.author and info.author.strip():
            result["authors"] = info.author.strip()
        if info.creation_date:
            try:
                dt = info.creation_date
                if hasattr(dt, "year"):
                    result["year"] = dt.year
                    result["date"] = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

    # --- 2. First-page text heuristics ---
    first_page_text = ""
    if reader.pages:
        try:
            first_page_text = reader.pages[0].extract_text() or ""
        except Exception:
            pass

    if first_page_text:
        # DOI (often printed on first page)
        if not result["doi"]:
            doi_match = re.search(r'(10\.\d{4,9}/[^\s,;]+)', first_page_text)
            if doi_match:
                result["doi"] = f"https://doi.org/{doi_match.group(1).rstrip('.')}"

        # Year from a pattern like "(2024)" or "Published: 2024" on first page
        if not result["year"]:
            year_match = re.search(r'(?:20[12]\d)', first_page_text[:2000])
            if year_match:
                result["year"] = int(year_match.group(0))

    return result


def add_to_metadata(metadata_path: Path, paper_id: str, uni_acronym: str,
                    uni_name: str, title: str, authors: list[dict],
                    year: int, date: str, doi: str):
    """Add paper entry to metadata.json under universities.<ACRONYM>.papers[]."""
    metadata = load_json(metadata_path)

    # Ensure structure exists
    if "universities" not in metadata:
        metadata["universities"] = {}
    if "collection_date" not in metadata:
        metadata["collection_date"] = datetime.now().isoformat()

    unis = metadata["universities"]
    if uni_acronym not in unis:
        unis[uni_acronym] = {"name": uni_name, "papers_count": 0, "papers": []}

    uni_data = unis[uni_acronym]

    # Check for duplicate by filename
    existing_ids = {p.get("id") for p in uni_data.get("papers", [])}
    if paper_id in existing_ids:
        print(f"  Paper {paper_id} already in metadata.json, skipping")
        return

    paper_entry = {
        "id": paper_id,
        "doi": doi,
        "title": title,
        "abstract": "",
        "publication_date": date,
        "publication_year": year,
        "type": "article",
        "cited_by_count": 0,
        "authors": authors,
        "affiliations": [uni_name],
        "concepts": [],
        "is_open_access": False,
        "pdf_url": None,
        "source": "manual",
        "language": None,
    }

    uni_data["papers"].append(paper_entry)
    uni_data["papers_count"] = len(uni_data["papers"])

    save_json(metadata_path, metadata)


def add_to_uni_papers(agent_data_dir: Path, uni_acronym: str, paper_id: str,
                      title: str, authors: list[dict], year: int, date: str,
                      doi: str, uni_name: str):
    """Add paper to the per-university JSON file (e.g. UMA_papers.json)."""
    papers_path = agent_data_dir / f"{uni_acronym}_papers.json"
    papers = load_json(papers_path) if papers_path.exists() else []
    if not isinstance(papers, list):
        papers = []

    existing_ids = {p.get("id") for p in papers}
    if paper_id in existing_ids:
        print(f"  Paper {paper_id} already in {papers_path.name}, skipping")
        return

    papers.append({
        "id": paper_id,
        "doi": doi,
        "title": title,
        "abstract": "",
        "publication_date": date,
        "publication_year": year,
        "type": "article",
        "cited_by_count": 0,
        "authors": authors,
        "affiliations": [uni_name],
        "concepts": [],
        "is_open_access": False,
        "pdf_url": None,
        "source": "manual",
        "language": None,
    })

    save_json(papers_path, papers)


def add_to_researchers(researchers_path: Path, uni_acronym: str,
                       authors: list[dict], paper_id: str, title: str,
                       year: int, affiliations: list[str] = None):
    """Update researchers.json with new authors/papers."""
    researchers = load_json(researchers_path)
    if not isinstance(researchers, dict):
        researchers = {}

    if uni_acronym not in researchers:
        researchers[uni_acronym] = []

    uni_researchers = researchers[uni_acronym]
    name_to_entry = {r["name"]: r for r in uni_researchers}

    for author in authors:
        name = author["name"]
        paper_ref = {"id": paper_id, "title": title, "year": year}

        if name in name_to_entry:
            entry = name_to_entry[name]
            existing_paper_ids = {p["id"] for p in entry.get("papers", [])}
            if paper_id not in existing_paper_ids:
                entry["papers"].append(paper_ref)
                entry["paper_count"] = len(entry["papers"])
            # Merge new affiliations into existing ones
            if affiliations:
                existing_affs = entry.get("affiliations", [])
                for aff in affiliations:
                    if aff not in existing_affs:
                        existing_affs.append(aff)
                entry["affiliations"] = existing_affs
        else:
            new_entry = {
                "name": name,
                "paper_count": 1,
                "topics": [],
                "affiliations": affiliations or [],
                "papers": [paper_ref],
            }
            uni_researchers.append(new_entry)
            name_to_entry[name] = new_entry

    save_json(researchers_path, researchers)


def main():
    parser = argparse.ArgumentParser(
        description="Add a manual paper (PDF + metadata) to a RAG+Metadata agent"
    )
    parser.add_argument("--agent", "-a", required=True,
                        help="Agent name (e.g. responsible_ai, health_tech)")
    parser.add_argument("--pdf", "-p", required=True,
                        help="Path to the PDF file")
    parser.add_argument("--university", "-u", default=None,
                        help="University acronym (e.g. UMA, THUAS)")
    parser.add_argument("--title", "-t", default=None,
                        help="Paper title")
    parser.add_argument("--authors", default=None,
                        help="Comma-separated author names")
    parser.add_argument("--year", "-y", type=int, default=None,
                        help="Publication year")
    parser.add_argument("--date", "-d", default=None,
                        help="Publication date (YYYY-MM-DD)")
    parser.add_argument("--doi", default=None,
                        help="DOI URL")
    parser.add_argument("--id", dest="paper_id", default=None,
                        help="Custom paper ID (default: auto-generated M<timestamp>)")

    args = parser.parse_args()

    # Validate agent
    agent_dir = AGENTS_DIR / args.agent
    if not agent_dir.exists():
        print(f"Error: Agent directory not found: {agent_dir}")
        sys.exit(1)

    config = load_config(agent_dir)
    unis = valid_universities(config)

    # Validate PDF
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"Adding paper to agent '{args.agent}'")
    print(f"  PDF: {pdf_path.name}")
    print(f"  Valid universities: {', '.join(unis)}")

    # Extract metadata from the PDF
    print()
    print("Extracting metadata from PDF...")
    pdf_meta = extract_pdf_metadata(pdf_path)

    extracted = {k: v for k, v in pdf_meta.items() if v}
    if extracted:
        print("  Found in PDF:")
        for k, v in extracted.items():
            print(f"    {k}: {v}")
    else:
        print("  No metadata found in PDF.")
    print()

    # Use PDF metadata as defaults; CLI args override; prompt for the rest
    uni = args.university
    uni = prompt_if_missing(uni, f"University acronym ({'/'.join(unis)})")
    uni = uni.upper()
    if uni not in unis:
        print(f"Error: '{uni}' is not a valid university. Choose from: {', '.join(unis)}")
        sys.exit(1)

    uni_name = config["universities"][uni]["name"]

    default_title = args.title or pdf_meta["title"]
    title = prompt_if_missing(default_title, "Paper title")

    default_authors = args.authors or pdf_meta["authors"]
    authors_str = prompt_if_missing(default_authors, "Authors (comma-separated)")
    authors = [{"name": a.strip(), "orcid": None} for a in authors_str.split(",")]

    year = args.year or pdf_meta["year"]
    if not year:
        year_str = prompt_if_missing(None, "Publication year", required=False)
        year = int(year_str) if year_str else datetime.now().year

    date = args.date or pdf_meta["date"] or f"{year}-01-01"
    doi = args.doi or pdf_meta["doi"] or ""
    paper_id = args.paper_id or generate_paper_id()

    # Paths
    data_dir = agent_dir / "data"
    docs_dir = data_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = data_dir / "metadata.json"
    researchers_path = data_dir / "researchers.json"

    # 1. Copy PDF
    dest_pdf = docs_dir / f"{paper_id}.pdf"
    if dest_pdf.exists():
        print(f"  PDF {dest_pdf.name} already exists, skipping copy")
    else:
        shutil.copy2(pdf_path, dest_pdf)
        print(f"  Copied PDF → {dest_pdf.name}")

    # 2. Update metadata.json
    add_to_metadata(metadata_path, paper_id, uni, uni_name, title, authors,
                    year, date, doi)

    # 3. Update <UNI>_papers.json
    add_to_uni_papers(data_dir, uni, paper_id, title, authors, year, date,
                      doi, uni_name)

    # 4. Update researchers.json
    add_to_researchers(researchers_path, uni, authors, paper_id, title, year)

    # Summary
    print()
    print(f"Done! Paper '{paper_id}' added to {args.agent}.")
    print(f"  PDF:    data/docs/{paper_id}.pdf")
    print(f"  Uni:    {uni} ({uni_name})")
    print(f"  Title:  {title}")
    print(f"  Authors: {', '.join(a['name'] for a in authors)}")
    print()
    print("Restart the agent to index the new paper into ChromaDB.")


if __name__ == "__main__":
    main()
