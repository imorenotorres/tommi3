#!/usr/bin/env python3
"""
OpenAlex Data Collector for UNINOVIS Alliance
Collects papers on AI & Responsibility from alliance universities.

Two-step workflow:
  Step 1 (collect): Query OpenAlex and produce a CSV table for manual review.
  Step 2 (download): Read the reviewed CSV and download PDFs + metadata for
                     papers that were kept (column "keep" == "yes").

Usage:
  python openalex_collector.py collect  -t TOPICS_FILE [-o DIR] [-m N]
  python openalex_collector.py download [-o DIR] [--csv PATH]
  python openalex_collector.py discover                        # only resolve institution IDs
"""

import csv
import json
import os
import time
import requests
from pathlib import Path
from typing import Optional
from datetime import datetime

# Script directory and default data output
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = SCRIPT_DIR / "data"

# UNINOVIS Alliance Universities with their OpenAlex institution IDs
UNINOVIS_UNIVERSITIES = {
    "USPN": {
        "name": "University of Sorbonne Paris Nord",
        "country": "France",
        "search_names": ["Sorbonne Paris Nord", "Paris 13", "Université Paris Nord"],
    },
    "UDCLV": {
        "name": "University of Campania Luigi Vanvitelli",
        "country": "Italy",
        "search_names": [
            "Campania Luigi Vanvitelli",
            "Seconda Università di Napoli",
            "University of Campania",
        ],
    },
    "UMA": {
        "name": "University of Malaga",
        "country": "Spain",
        "search_names": ["University of Malaga", "Universidad de Málaga", "Malaga University"],
    },
    "KK": {
        "name": "Kauno Kolegija Higher Education Institution",
        "country": "Lithuania",
        "search_names": ["Kauno Kolegija", "Kaunas College", "Kaunas kolegija"],
    },
    "UT": {
        "name": "University of Tirana",
        "country": "Albania",
        "search_names": ["University of Tirana", "Universiteti i Tiranës"],
    },
    "THWS": {
        "name": "Technical University of Applied Sciences Würzburg-Schweinfurt",
        "country": "Germany",
        "search_names": [
            "THWS",
            "Würzburg-Schweinfurt",
            "Hochschule für angewandte Wissenschaften Würzburg-Schweinfurt",
        ],
    },
    "TAMK": {
        "name": "Tampere University of Applied Sciences",
        "country": "Finland",
        "search_names": [
            "TAMK",
            "Tampere University of Applied Sciences",
            "Tampereen ammattikorkeakoulu",
        ],
    },
    "THUAS": {
        "name": "The Hague University of Applied Sciences",
        "country": "Netherlands",
        "search_names": [
            "The Hague University of Applied Sciences",
            "Haagse Hogeschool",
            "THUAS",
        ],
    },
}

def load_queries(topics_file: str) -> list[str]:
    """Load search queries from an external text file (one query per line).
    Lines starting with # are comments and are ignored."""
    path = Path(topics_file)
    if not path.exists():
        raise FileNotFoundError(f"Topics file not found: {topics_file}")
    queries = [
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not queries:
        raise ValueError(f"Topics file is empty: {topics_file}")
    return queries


def load_relevance_filter(filter_file: str) -> dict:
    """Load relevance filter terms from a file.

    The file has two sections separated by headers:
        [ai_terms]
        artificial intelligence
        machine learning
        ...

        [domain_terms]
        ethic
        bias
        ...

    Lines starting with # are comments. Each line is a substring to match
    (case-insensitive) against title + abstract.

    Returns: {"ai_terms": [...], "domain_terms": [...]}
    If no file is provided, returns None (no filtering).
    """
    if not filter_file:
        return None
    path = Path(filter_file)
    if not path.exists():
        raise FileNotFoundError(f"Relevance filter file not found: {filter_file}")

    result = {"ai_terms": [], "domain_terms": []}
    current_section = None

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() == "[ai_terms]":
            current_section = "ai_terms"
        elif line.lower() == "[domain_terms]":
            current_section = "domain_terms"
        elif current_section:
            result[current_section].append(line.lower())

    if not result["ai_terms"] and not result["domain_terms"]:
        raise ValueError(f"Relevance filter file has no terms: {filter_file}")

    return result

# OpenAlex API
OPENALEX_BASE_URL = "https://api.openalex.org"
POLITE_EMAIL = "imoreno@uma.es"
OPENALEX_API_KEY = "6W3BYzvteRggqFVXQi9fth"  # Premium API key for higher rate limits

# CSV columns produced during Step 1
CSV_COLUMNS = [
    "keep",
    "university",
    "openalex_id",
    "doi",
    "title",
    "authors",
    "affiliations",
    "publication_year",
    "cited_by_count",
    "is_open_access",
    "pdf_url",
    "source",
    "language",
    "abstract",
    "collected_on",
]


class OpenAlexCollector:
    def __init__(self, output_dir: str = None, queries: list[str] = None, relevance_filter: dict = None):
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_DATA_DIR
        self.queries = queries or []
        self.relevance_filter = relevance_filter  # None = no filtering
        self.papers_dir = self.output_dir / "papers"
        self.metadata_dir = self.output_dir / "metadata"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": f"UNINOVIS-RAG-Collector/1.0 (mailto:{POLITE_EMAIL})"}
        )

    # ------------------------------------------------------------------
    # OpenAlex helpers
    # ------------------------------------------------------------------

    def _api_request(self, endpoint: str, params: dict = None, max_retries: int = 8) -> dict:
        """Make a request to OpenAlex API with rate limiting and retry on 429."""
        url = f"{OPENALEX_BASE_URL}/{endpoint}"
        if params is None:
            params = {}
        params["mailto"] = POLITE_EMAIL
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params)
                if response.status_code == 429:
                    # Respect Retry-After header if present, otherwise exponential backoff
                    # Cap at 120s to avoid absurdly long waits
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        wait = min(int(retry_after), 120)
                    else:
                        wait = min(2 ** attempt, 60)
                    print(f"  Rate limited (429), retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                time.sleep(0.5)  # Rate limiting — premium API key allows faster requests
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1 and "429" in str(e):
                    wait = min(2 ** attempt, 60)
                    print(f"  Rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"  API request error: {e}")
                return {}
        print(f"  Max retries exceeded for {endpoint}")
        return {}

    def find_institution(self, search_name: str) -> Optional[dict]:
        """Find an institution by name in OpenAlex."""
        result = self._api_request("institutions", {"search": search_name, "per_page": 5})
        if result and "results" in result and len(result["results"]) > 0:
            return result["results"][0]
        return None

    def discover_institution_ids(self) -> dict:
        """Discover OpenAlex IDs for all UNINOVIS universities."""
        print("Discovering OpenAlex institution IDs...")
        discovered = {}

        for acronym, info in UNINOVIS_UNIVERSITIES.items():
            print(f"\nSearching for {info['name']}...")
            for search_name in info["search_names"]:
                institution = self.find_institution(search_name)
                if institution:
                    openalex_id = institution["id"].replace("https://openalex.org/", "")
                    discovered[acronym] = {
                        "openalex_id": openalex_id,
                        "display_name": institution.get("display_name"),
                        "country_code": institution.get("country_code"),
                        "works_count": institution.get("works_count", 0),
                        "ror": institution.get("ror"),
                    }
                    print(f"  Found: {institution.get('display_name')} (ID: {openalex_id})")
                    break
            else:
                print(f"  Not found for any search term")
                discovered[acronym] = None

        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_dir / "institution_ids.json", "w", encoding="utf-8") as f:
            json.dump(discovered, f, indent=2, ensure_ascii=False)

        return discovered

    def _load_institutions(self) -> dict:
        """Load or discover institution IDs."""
        ids_file = self.metadata_dir / "institution_ids.json"
        if ids_file.exists():
            print("Loading cached institution IDs...")
            with open(ids_file, encoding="utf-8") as f:
                return json.load(f)
        return self.discover_institution_ids()

    # ------------------------------------------------------------------
    # Abstract reconstruction
    # ------------------------------------------------------------------

    @staticmethod
    def _reconstruct_abstract(abstract_inverted_index: dict) -> str:
        if not abstract_inverted_index:
            return ""
        word_positions = []
        for word, positions in abstract_inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions)

    # ------------------------------------------------------------------
    # Relevance filter
    # ------------------------------------------------------------------

    def _is_relevant(self, paper: dict) -> bool:
        """Check that the paper matches the relevance filter.

        If no relevance filter is configured, all papers are considered relevant.
        If a filter is configured, the paper must contain at least one ai_term
        AND at least one domain_term in its title + abstract.
        """
        if self.relevance_filter is None:
            return True

        title = (paper.get("title") or "").lower()
        abstract_inv = paper.get("abstract_inverted_index")
        abstract = ""
        if abstract_inv:
            abstract = " ".join(abstract_inv.keys()).lower()
        text = title + " " + abstract

        ai_terms = self.relevance_filter.get("ai_terms", [])
        domain_terms = self.relevance_filter.get("domain_terms", [])

        ai_match = (not ai_terms) or any(t in text for t in ai_terms)
        domain_match = (not domain_terms) or any(t in text for t in domain_terms)
        return ai_match and domain_match

    # ------------------------------------------------------------------
    # Affiliation check — only keep papers where a UNINOVIS institution
    # actually appears among the authors' affiliations.
    # ------------------------------------------------------------------

    @staticmethod
    def _has_uninovis_affiliation(paper: dict, institution_id: str) -> bool:
        """Return True if at least one author is affiliated with *institution_id*."""
        full_id = f"https://openalex.org/{institution_id}"
        for authorship in paper.get("authorships", []):
            for inst in authorship.get("institutions", []):
                if inst.get("id") == full_id:
                    return True
        return False

    # ------------------------------------------------------------------
    # Step 1: Collect metadata → CSV
    # ------------------------------------------------------------------

    def _load_existing_ids(self, csv_path: Path) -> set:
        """Load OpenAlex IDs already present in an existing CSV."""
        ids = set()
        if csv_path.exists():
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    oa_id = row.get("openalex_id", "").strip()
                    if oa_id:
                        ids.add(f"https://openalex.org/{oa_id}")
        return ids

    def _paginated_search(self, inst_id: str, query: str, per_page: int = 50) -> list:
        """Fetch ALL pages of results for a given institution + query using cursor pagination."""
        all_results = []
        cursor = "*"
        while cursor:
            params = {
                "filter": f"authorships.institutions.id:{inst_id}",
                "search": query,
                "per_page": per_page,
                "sort": "cited_by_count:desc",
                "cursor": cursor,
            }
            result = self._api_request("works", params)
            if not result or "results" not in result:
                break
            results = result["results"]
            if not results:
                break
            all_results.extend(results)
            # Get next cursor from metadata
            cursor = result.get("meta", {}).get("next_cursor")
        return all_results

    def collect(self, max_per_institution: int = 0, continue_from_csv: bool = False, only_university: str = None) -> Path:
        """Query OpenAlex and write a CSV table for manual review.

        Args:
            max_per_institution: Max papers per institution (0 = unlimited).
            continue_from_csv: If True, skip papers already in the existing CSV
                               and append new papers to it.
            only_university: If set, restrict collection to this university acronym.
        """
        print("=" * 60)
        print("STEP 1 — Collect paper metadata for review")
        print("=" * 60)

        institutions = self._load_institutions()
        if only_university:
            key = only_university.upper()
            if key not in institutions:
                raise ValueError(f"University '{key}' not found. Available: {', '.join(institutions.keys())}")
            institutions = {key: institutions[key]}
            print(f"Restricting collection to: {key}")
        csv_path = self.output_dir / "papers_to_review.csv"
        batch_date = datetime.now().strftime("%Y-%m-%d")

        # If continuing, load existing IDs and rows
        existing_rows: list[dict] = []
        seen_ids: set[str] = set()
        if continue_from_csv and csv_path.exists():
            seen_ids = self._load_existing_ids(csv_path)
            with open(csv_path, newline="", encoding="utf-8") as f:
                existing_rows = list(csv.DictReader(f))
            print(f"Continuing from existing CSV: {len(existing_rows)} papers, "
                  f"{len(seen_ids)} IDs already collected")
        rows: list[dict] = []

        for acronym, inst_info in institutions.items():
            if not inst_info or not inst_info.get("openalex_id"):
                print(f"\nSkipping {acronym}: no OpenAlex ID")
                continue

            inst_id = inst_info["openalex_id"]
            inst_name = inst_info["display_name"]
            print(f"\n--- {inst_name} ({acronym}) ---")

            inst_papers: list[dict] = []

            for query in self.queries:
                if max_per_institution > 0 and len(inst_papers) >= max_per_institution:
                    break

                print(f"  Query: {query}")
                all_page_results = self._paginated_search(inst_id, query)
                print(f"    Raw results from API: {len(all_page_results)}")

                for paper in all_page_results:
                    if max_per_institution > 0 and len(inst_papers) >= max_per_institution:
                        break

                    pid = paper.get("id", "")
                    if pid in seen_ids:
                        continue

                    # Verify the UNINOVIS institution really appears in affiliations
                    if not self._has_uninovis_affiliation(paper, inst_id):
                        continue

                    # Relevance filter
                    if not self._is_relevant(paper):
                        continue

                    seen_ids.add(pid)
                    inst_papers.append(paper)

            print(f"  {len(inst_papers)} NEW papers after filtering")

            for paper in inst_papers:
                authors = "; ".join(
                    a.get("author", {}).get("display_name", "")
                    for a in paper.get("authorships", [])
                )
                affiliations = "; ".join(
                    {
                        inst.get("display_name") or ""
                        for auth in paper.get("authorships", [])
                        for inst in auth.get("institutions", [])
                    } - {""}
                )
                oa = paper.get("open_access", {})
                pdf_url = oa.get("oa_url") or (paper.get("primary_location") or {}).get("pdf_url") or ""
                abstract = self._reconstruct_abstract(paper.get("abstract_inverted_index"))

                rows.append(
                    {
                        "keep": "yes",
                        "university": acronym,
                        "openalex_id": paper.get("id", "").replace("https://openalex.org/", ""),
                        "doi": paper.get("doi") or "",
                        "title": paper.get("title") or "",
                        "authors": authors,
                        "affiliations": affiliations,
                        "publication_year": paper.get("publication_year") or "",
                        "cited_by_count": paper.get("cited_by_count", 0),
                        "is_open_access": oa.get("is_oa", False),
                        "pdf_url": pdf_url,
                        "source": ((paper.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
                        "language": paper.get("language") or "",
                        "abstract": abstract,
                        "collected_on": batch_date,
                    }
                )

            # Auto-save CSV after each university (crash recovery)
            all_rows = existing_rows + rows
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                writer.writerows(all_rows)
            print(f"  CSV saved: {len(all_rows)} papers so far")

        # Final CSV is already saved (last auto-save)
        all_rows = existing_rows + rows

        print(f"\n{'=' * 60}")
        if continue_from_csv:
            print(f"Added {len(rows)} NEW papers (total now: {len(all_rows)})")
        else:
            print(f"Wrote {len(all_rows)} papers to: {csv_path}")
        print(f"CSV: {csv_path}")
        print("Review the CSV and set 'keep' to 'no' for papers to exclude.")
        print(f"Then run:  python {Path(__file__).name} download")
        print("=" * 60)
        return csv_path

    # ------------------------------------------------------------------
    # Step 2: Read reviewed CSV → download PDFs + save metadata
    # ------------------------------------------------------------------

    def download(self, csv_path: Path = None) -> dict:
        """Read the reviewed CSV and download PDFs + metadata for kept papers."""
        if csv_path is None:
            csv_path = self.output_dir / "papers_to_review.csv"

        if not csv_path.exists():
            print(f"CSV not found: {csv_path}")
            print("Run 'collect' first to generate the review table.")
            return {}

        print("=" * 60)
        print("STEP 2 — Download papers from reviewed CSV")
        print("=" * 60)

        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Prepare download log (append to existing log if present)
        log_dir = self.output_dir / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "download.tsv"
        log_columns = [
            "openalex_id", "university", "title", "keep",
            "pdf_url", "status", "detail", "timestamp",
        ]
        log_exists = log_path.exists() and log_path.stat().st_size > 0
        log_file = open(log_path, "a", newline="", encoding="utf-8")
        log_writer = csv.DictWriter(log_file, fieldnames=log_columns, delimiter="\t")
        if not log_exists:
            log_writer.writeheader()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        kept = [r for r in rows if r.get("keep", "").strip().lower() == "yes"]
        print(f"Total rows: {len(rows)}, kept: {len(kept)}")

        # Log skipped rows (keep != yes)
        for row in rows:
            if row.get("keep", "").strip().lower() != "yes":
                log_writer.writerow({
                    "openalex_id": row.get("openalex_id", ""),
                    "university": row.get("university", ""),
                    "title": row.get("title", ""),
                    "keep": row.get("keep", ""),
                    "pdf_url": row.get("pdf_url", ""),
                    "status": "SKIPPED",
                    "detail": "keep != yes",
                    "timestamp": datetime.now().isoformat(),
                })

        # Load existing papers.json to resume from where we left off
        papers_json_path = self.metadata_dir / "papers.json"
        existing_paper_ids = set()  # Papers with metadata already fetched
        papers_with_pdf_ids = set()  # Papers with PDF already downloaded
        collection = {
            "collection_date": datetime.now().isoformat(),
            "universities": {},
            "total_papers": 0,
            "papers_with_pdf": 0,
        }
        if papers_json_path.exists():
            try:
                with open(papers_json_path, "r", encoding="utf-8") as f:
                    prev = json.load(f)
                for acronym, uni_data in prev.get("universities", {}).items():
                    papers_list = uni_data.get("papers", [])
                    collection["universities"][acronym] = {
                        "name": uni_data.get("name", acronym),
                        "papers_count": len(papers_list),
                        "papers": papers_list,
                    }
                    collection["total_papers"] += len(papers_list)
                    for p in papers_list:
                        pid = p.get("id", "")
                        existing_paper_ids.add(pid)
                        if p.get("local_pdf_path"):
                            papers_with_pdf_ids.add(pid)
                            collection["papers_with_pdf"] += 1
                without_pdf = len(existing_paper_ids) - len(papers_with_pdf_ids)
                print(f"Resuming: {len(existing_paper_ids)} papers in papers.json "
                      f"({len(papers_with_pdf_ids)} with PDF, {without_pdf} will retry PDF)")
            except Exception as e:
                print(f"Warning: Could not load existing papers.json: {e}")

        skipped = 0
        processed = 0
        for row in kept:
            acronym = row["university"]
            paper_id = row["openalex_id"]
            title = row["title"]

            if acronym not in collection["universities"]:
                collection["universities"][acronym] = {
                    "name": UNINOVIS_UNIVERSITIES.get(acronym, {}).get("name", acronym),
                    "papers_count": 0,
                    "papers": [],
                }

            # Skip papers that already have metadata AND a PDF
            if paper_id in papers_with_pdf_ids:
                skipped += 1
                continue

            # Paper has metadata but no PDF — retry PDF only
            if paper_id in existing_paper_ids:
                processed += 1
                to_retry = len(existing_paper_ids) - len(papers_with_pdf_ids)
                new_to_dl = len(kept) - len(existing_paper_ids)
                print(f"\n[{processed}/{to_retry + new_to_dl}] [{acronym}] {title[:70]}... (retry PDF)")
                # Use existing metadata, just retry PDF
                metadata = None
                for p in collection["universities"].get(acronym, {}).get("papers", []):
                    if p.get("id") == paper_id:
                        metadata = p
                        break
                if not metadata:
                    metadata = {k: row[k] for k in CSV_COLUMNS if k != "keep"}
                    metadata["local_pdf_path"] = None
                pdf_url = row.get("pdf_url") or metadata.get("pdf_url") or ""
            else:
                # New paper — fetch metadata + PDF
                processed += 1
                to_retry = len(existing_paper_ids) - len(papers_with_pdf_ids)
                new_to_dl = len(kept) - len(existing_paper_ids)
                print(f"\n[{processed}/{to_retry + new_to_dl}] [{acronym}] {title[:70]}...")

                # Fetch full metadata from OpenAlex
                full = self._api_request(f"works/{paper_id}")
                if not full:
                    print("  Could not fetch metadata, using CSV data")
                    metadata = {k: row[k] for k in CSV_COLUMNS if k != "keep"}
                    metadata["local_pdf_path"] = None
                else:
                    metadata = self._extract_paper_metadata(full)

                pdf_url = row.get("pdf_url") or metadata.get("pdf_url") or ""

            # Common: download PDF
            if pdf_url:
                pdf_path, dl_status, dl_detail = self._download_pdf(pdf_url, paper_id)
                metadata["local_pdf_path"] = pdf_path
                if pdf_path:
                    collection["papers_with_pdf"] += 1
            else:
                metadata["local_pdf_path"] = None
                dl_status = "NO_URL"
                dl_detail = "No PDF URL available in CSV or OpenAlex metadata"
                print(f"  No PDF URL available")

            log_writer.writerow({
                "openalex_id": paper_id,
                "university": acronym,
                "title": title,
                "keep": "yes",
                "pdf_url": pdf_url,
                "status": dl_status,
                "detail": dl_detail,
                "timestamp": datetime.now().isoformat(),
            })

            # Add new paper or update existing (retry case)
            if paper_id in existing_paper_ids:
                # Update existing paper's pdf path in place
                for p in collection["universities"][acronym]["papers"]:
                    if p.get("id") == paper_id:
                        p["local_pdf_path"] = metadata.get("local_pdf_path")
                        break
            else:
                collection["universities"][acronym]["papers"].append(metadata)
                collection["universities"][acronym]["papers_count"] += 1
                collection["total_papers"] += 1

            # Auto-save after each paper (crash recovery)
            self._save_papers_json(collection)
            with open(self.metadata_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(collection, f, indent=2, ensure_ascii=False)

        log_file.close()

        if skipped:
            print(f"\nSkipped {skipped} papers already in papers.json")

        # Final save
        self._save_papers_json(collection)

        # Save full collection metadata (includes counts and PDF stats)
        with open(self.metadata_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(collection, f, indent=2, ensure_ascii=False)

        # Summary
        print(f"\n{'=' * 60}")
        print("DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"Total papers: {collection['total_papers']}")
        print(f"Papers with PDF: {collection['papers_with_pdf']}")
        for acronym, data in collection["universities"].items():
            print(f"  {acronym}: {data['papers_count']} papers")
        print(f"\nOutput files:")
        print(f"  papers.json:   {self.metadata_dir / 'papers.json'}")
        print(f"  metadata.json: {self.metadata_dir / 'metadata.json'}")
        print(f"  Download log:  {log_path}")

        return collection

    def _save_papers_json(self, collection: dict):
        """Save consolidated papers.json (same structure as agent's data/papers.json)."""
        papers_json = {"universities": {}}
        for acronym, data in collection["universities"].items():
            papers_json["universities"][acronym] = {
                "name": data["name"],
                "papers": data["papers"],
            }
        with open(self.metadata_dir / "papers.json", "w", encoding="utf-8") as f:
            json.dump(papers_json, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Internal helpers used by download()
    # ------------------------------------------------------------------

    def _extract_paper_metadata(self, paper: dict) -> dict:
        """Extract relevant metadata from a full OpenAlex work object."""
        authors = []
        affiliations = set()
        for authorship in paper.get("authorships", []):
            author = authorship.get("author", {})
            author_institutions = [
                inst.get("display_name") for inst in authorship.get("institutions", [])
                if inst.get("display_name")
            ]
            authors.append({
                "name": author.get("display_name"),
                "orcid": author.get("orcid"),
                "institutions": author_institutions,
            })
            for inst_name in author_institutions:
                affiliations.add(inst_name)

        oa_info = paper.get("open_access", {})
        pdf_url = oa_info.get("oa_url") or (paper.get("primary_location") or {}).get("pdf_url")

        concepts = [
            {"name": c.get("display_name"), "score": c.get("score")}
            for c in paper.get("concepts", [])[:10]
        ]

        abstract = self._reconstruct_abstract(paper.get("abstract_inverted_index"))

        return {
            "id": paper.get("id", "").replace("https://openalex.org/", ""),
            "doi": paper.get("doi"),
            "title": paper.get("title"),
            "abstract": abstract,
            "publication_date": paper.get("publication_date"),
            "publication_year": paper.get("publication_year"),
            "type": paper.get("type"),
            "cited_by_count": paper.get("cited_by_count", 0),
            "authors": authors,
            "affiliations": list(affiliations),
            "concepts": concepts,
            "is_open_access": oa_info.get("is_oa", False),
            "pdf_url": pdf_url,
            "source": ((paper.get("primary_location") or {}).get("source") or {}).get("display_name"),
            "language": paper.get("language"),
        }

    @staticmethod
    def _resolve_pdf_url(url: str) -> str:
        """Convert landing page URLs to direct PDF download URLs for known platforms."""
        import re
        # Zenodo landing page: /record/ID or /records/ID
        m = re.match(r"https?://zenodo\.org/records?/(\d+)/?$", url)
        if m:
            return f"https://zenodo.org/api/records/{m.group(1)}"
        # Zenodo DOI: https://doi.org/10.5281/zenodo.ID
        m = re.match(r"https?://doi\.org/10\.5281/zenodo\.(\d+)/?$", url)
        if m:
            return f"https://zenodo.org/api/records/{m.group(1)}"
        return url

    def _download_pdf(self, pdf_url: str, paper_id: str) -> tuple[Optional[str], str, str]:
        """Download PDF if available. Returns (path, status, detail)."""
        if not pdf_url:
            return None, "NO_URL", "No PDF URL provided"

        filename = f"{paper_id.replace('/', '_')}.pdf"
        filepath = self.papers_dir / filename

        if filepath.exists():
            print(f"  PDF already exists: {filename}")
            return str(filepath), "EXISTS", f"Already downloaded: {filename}"

        # Handle Zenodo: resolve landing page to actual PDF file
        resolved_url = self._resolve_pdf_url(pdf_url)
        if resolved_url != pdf_url and "zenodo.org/api/records" in resolved_url:
            try:
                resp = self.session.get(resolved_url, timeout=15)
                if resp.status_code == 200:
                    record = resp.json()
                    for f in record.get("files", []):
                        if f.get("key", "").lower().endswith(".pdf"):
                            pdf_url = f.get("links", {}).get("self", "") or f"https://zenodo.org/records/{record['id']}/files/{f['key']}"
                            print(f"  Zenodo resolved: {f['key']}")
                            break
            except Exception:
                pass  # Fall through to normal download with original URL

        try:
            # Use browser-like headers to avoid being blocked by publishers
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/pdf,*/*",
            }
            response = self.session.get(pdf_url, timeout=30, allow_redirects=True, headers=headers)
            content_type = response.headers.get("Content-Type", "")
            # Accept if Content-Type says PDF or if the content starts with PDF magic bytes
            is_pdf = "application/pdf" in content_type or response.content[:5] == b"%PDF-"
            if response.status_code == 200 and is_pdf:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print(f"  Downloaded: {filename}")
                return str(filepath), "OK", f"Downloaded: {filename}"
            else:
                detail = f"HTTP {response.status_code}, Content-Type: {content_type}"
                print(f"  Not a PDF or access denied: {pdf_url}")
                return None, "FAILED", detail
        except Exception as e:
            print(f"  Download failed: {e}")
            return None, "ERROR", str(e)


# ======================================================================
# Project collection — funded research grouped by grant/project
# ======================================================================

PROJECT_CSV_COLUMNS = [
    "keep",
    "project_key",
    "funder",
    "funder_id",
    "award_id",
    "paper_count",
    "universities",
    "paper_ids",
    "paper_titles",
    "first_year",
    "last_year",
    "topics",
    "collected_on",
]


class ProjectCollector:
    """Extends OpenAlexCollector to find funded research and group by project."""

    def __init__(self, base_collector: OpenAlexCollector):
        self.base = base_collector

    def collect_projects(self, max_per_institution: int = 0,
                         funder_filter: str = None,
                         only_university: str = None) -> Path:
        """Search for funded papers, group by grant, and write projects CSV.

        Args:
            max_per_institution: Max papers per institution (0 = unlimited).
            funder_filter: Only include grants from funders matching this
                           substring (case-insensitive), e.g. "European".
            only_university: Restrict to a single university acronym.
        """
        print("=" * 60)
        print("COLLECT PROJECTS — Funded research grouped by grant")
        print("=" * 60)

        institutions = self.base._load_institutions()
        if only_university:
            key = only_university.upper()
            if key not in institutions:
                raise ValueError(f"University '{key}' not found. Available: {', '.join(institutions.keys())}")
            institutions = {key: institutions[key]}
            print(f"Restricting collection to: {key}")

        if funder_filter:
            print(f"Funder filter: '{funder_filter}'")

        # Collect all funded papers
        all_funded_papers = []  # (acronym, paper_dict)
        seen_ids = set()

        for acronym, inst_info in institutions.items():
            if not inst_info or not inst_info.get("openalex_id"):
                continue

            inst_id = inst_info["openalex_id"]
            inst_name = inst_info["display_name"]
            print(f"\n--- {inst_name} ({acronym}) ---")

            inst_papers = []
            for query in self.base.queries:
                if max_per_institution > 0 and len(inst_papers) >= max_per_institution:
                    break

                print(f"  Query: {query}")

                # Search for papers — filter for funded ones client-side
                # (OpenAlex has no boolean has_award filter; we use
                #  awards.funder_display_name.search when a funder is specified,
                #  otherwise we fetch all and filter for papers with awards)
                cursor = "*"
                while cursor:
                    base_filter = f"authorships.institutions.id:{inst_id}"
                    if funder_filter:
                        base_filter += f",awards.funder_display_name.search:{funder_filter}"
                    params = {
                        "filter": base_filter,
                        "search": query,
                        "per_page": 50,
                        "sort": "cited_by_count:desc",
                        "cursor": cursor,
                    }
                    result = self.base._api_request("works", params)
                    if not result or "results" not in result:
                        break
                    results = result["results"]
                    if not results:
                        break

                    # Diagnostic: on first batch, detect the funding field name
                    if results and cursor == "*":
                        sample = results[0]
                        has_awards = any(bool(p.get("awards")) for p in results[:10])
                        has_grants = any(bool(p.get("grants")) for p in results[:10])
                        total_results = result.get("meta", {}).get("count", "?")
                        print(f"    API returned {len(results)} results (total: {total_results}), "
                              f"awards field: {has_awards}, grants field: {has_grants}")

                    for paper in results:
                        if max_per_institution > 0 and len(inst_papers) >= max_per_institution:
                            break
                        pid = paper.get("id", "")
                        if pid in seen_ids:
                            continue
                        if not self.base._has_uninovis_affiliation(paper, inst_id):
                            continue
                        if not self.base._is_relevant(paper):
                            continue

                        # Must have awards (OpenAlex may use "awards" or "grants")
                        awards = paper.get("awards") or paper.get("grants") or []
                        if not awards:
                            continue

                        # Apply funder filter (client-side double-check)
                        if funder_filter:
                            fl = funder_filter.lower()
                            awards = [a for a in awards
                                      if fl in (a.get("funder_display_name") or "").lower()
                                      or fl in (a.get("funder_id") or "").lower()]
                            if not awards:
                                continue

                        seen_ids.add(pid)
                        inst_papers.append(paper)

                    cursor = result.get("meta", {}).get("next_cursor")

            print(f"  {len(inst_papers)} funded papers after filtering")

            for paper in inst_papers:
                all_funded_papers.append((acronym, paper))

        # Group by project (funder + award_id)
        projects = {}  # project_key → {funder, funder_id, award_id, papers: [(acronym, paper)], ...}
        papers_without_award = []

        for acronym, paper in all_funded_papers:
            awards = paper.get("awards") or paper.get("grants") or []
            if funder_filter:
                fl = funder_filter.lower()
                awards = [a for a in awards
                          if fl in (a.get("funder_display_name") or "").lower()
                          or fl in (a.get("funder_id") or a.get("funder") or "").lower()]

            for award in awards:
                funder_name = award.get("funder_display_name", "Unknown")
                funder_id = (award.get("funder_id") or award.get("funder") or "").replace("https://openalex.org/", "")
                award_id = award.get("funder_award_id") or award.get("award_id") or ""

                if not award_id:
                    papers_without_award.append((acronym, paper, funder_name))
                    continue

                project_key = f"{funder_id}:{award_id}"
                if project_key not in projects:
                    projects[project_key] = {
                        "funder": funder_name,
                        "funder_id": funder_id,
                        "award_id": award_id,
                        "papers": [],
                    }
                projects[project_key]["papers"].append((acronym, paper))

        # Write projects CSV
        batch_date = datetime.now().strftime("%Y-%m-%d")
        csv_path = self.base.output_dir / "projects_to_review.csv"
        rows = []

        for project_key, proj in sorted(projects.items(), key=lambda x: len(x[1]["papers"]), reverse=True):
            unis = sorted({a for a, _ in proj["papers"]})
            years = [p.get("publication_year") for _, p in proj["papers"] if p.get("publication_year")]
            paper_ids = [p.get("id", "").replace("https://openalex.org/", "") for _, p in proj["papers"]]
            paper_titles = [p.get("title", "") for _, p in proj["papers"]]

            # Collect top concepts across all papers in this project
            concept_counts = {}
            for _, paper in proj["papers"]:
                for c in paper.get("concepts", []):
                    name = c.get("display_name", "")
                    score = c.get("score", 0)
                    if name and score > 0.3:
                        concept_counts[name] = concept_counts.get(name, 0) + 1
            top_topics = sorted(concept_counts.keys(), key=lambda x: concept_counts[x], reverse=True)[:10]

            rows.append({
                "keep": "yes",
                "project_key": project_key,
                "funder": proj["funder"],
                "funder_id": proj["funder_id"],
                "award_id": proj["award_id"],
                "paper_count": len(proj["papers"]),
                "universities": "; ".join(unis),
                "paper_ids": "; ".join(paper_ids),
                "paper_titles": "; ".join(paper_titles),
                "first_year": min(years) if years else "",
                "last_year": max(years) if years else "",
                "topics": "; ".join(top_topics),
                "collected_on": batch_date,
            })

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=PROJECT_CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        # Also write the individual papers CSV for reference
        papers_csv_path = self.base.output_dir / "project_papers.csv"
        paper_rows = []
        for acronym, paper in all_funded_papers:
            awards = paper.get("awards") or paper.get("grants") or []
            grant_strs = [
                f"{a.get('funder_display_name', '?')}:{a.get('funder_award_id') or a.get('award_id') or '?'}"
                for a in awards
            ]
            authors = "; ".join(
                a.get("author", {}).get("display_name", "")
                for a in paper.get("authorships", [])
            )
            oa = paper.get("open_access", {})
            abstract = self.base._reconstruct_abstract(paper.get("abstract_inverted_index"))

            paper_rows.append({
                "keep": "yes",
                "university": acronym,
                "openalex_id": paper.get("id", "").replace("https://openalex.org/", ""),
                "doi": paper.get("doi") or "",
                "title": paper.get("title") or "",
                "authors": authors,
                "publication_year": paper.get("publication_year") or "",
                "cited_by_count": paper.get("cited_by_count", 0),
                "grants": "; ".join(grant_strs),
                "is_open_access": oa.get("is_oa", False),
                "pdf_url": oa.get("oa_url") or (paper.get("primary_location") or {}).get("pdf_url") or "",
                "abstract": abstract,
                "collected_on": batch_date,
            })

        paper_csv_cols = [
            "keep", "university", "openalex_id", "doi", "title", "authors",
            "publication_year", "cited_by_count", "grants", "is_open_access",
            "pdf_url", "abstract", "collected_on",
        ]
        with open(papers_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=paper_csv_cols)
            writer.writeheader()
            writer.writerows(paper_rows)

        # Summary
        print(f"\n{'=' * 60}")
        print("PROJECT COLLECTION SUMMARY")
        print("=" * 60)
        print(f"Funded papers found: {len(all_funded_papers)}")
        print(f"Projects identified: {len(projects)}")
        print(f"Papers without award ID: {len(papers_without_award)}")
        print(f"\nTop funders:")
        funder_counts = {}
        for proj in projects.values():
            funder_counts[proj["funder"]] = funder_counts.get(proj["funder"], 0) + 1
        for funder, count in sorted(funder_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {funder}: {count} projects")
        print(f"\nOutput files:")
        print(f"  {csv_path}         — projects grouped by grant (review & set keep=yes/no)")
        print(f"  {papers_csv_path}  — individual papers with grant info")
        print(f"\nReview the CSVs, then use 'download --csv {papers_csv_path}' to download PDFs.")
        print("=" * 60)

        return csv_path


# ======================================================================
# CLI
# ======================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect AI & Responsibility papers from UNINOVIS universities (two-step workflow)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- collect ---
    p_collect = subparsers.add_parser(
        "collect", help="Step 1: query OpenAlex and produce a CSV for review"
    )
    p_collect.add_argument("--output", "-o", default=None, help="Output directory")
    p_collect.add_argument(
        "--topics", "-t", required=True,
        help="Path to a text file with search queries (one per line)",
    )
    p_collect.add_argument(
        "--max-papers", "-m", type=int, default=0,
        help="Max papers per institution (0 = unlimited, default)",
    )
    p_collect.add_argument(
        "--continue", dest="continue_csv", action="store_true",
        help="Continue from existing CSV: skip already-collected papers and append new ones",
    )
    p_collect.add_argument(
        "--university", "-u", default=None,
        help="Restrict collection to a single university by acronym (e.g. THUAS)",
    )
    p_collect.add_argument(
        "--relevance", "-r", default=None,
        help="Path to a relevance filter file with [ai_terms] and [domain_terms] sections. "
             "If not provided, no relevance filtering is applied (all search results are kept).",
    )

    # --- collect-projects ---
    p_projects = subparsers.add_parser(
        "collect-projects",
        help="Collect funded papers and group by research project/grant",
    )
    p_projects.add_argument("--output", "-o", default=None, help="Output directory")
    p_projects.add_argument(
        "--topics", "-t", required=True,
        help="Path to a text file with search queries (one per line)",
    )
    p_projects.add_argument(
        "--max-papers", "-m", type=int, default=0,
        help="Max papers per institution (0 = unlimited, default)",
    )
    p_projects.add_argument(
        "--funder", "-f", default=None,
        help="Only include grants from funders matching this substring "
             '(case-insensitive), e.g. "European" for EU-funded projects',
    )
    p_projects.add_argument(
        "--university", "-u", default=None,
        help="Restrict collection to a single university by acronym",
    )
    p_projects.add_argument(
        "--relevance", "-r", default=None,
        help="Path to a relevance filter file",
    )

    # --- download ---
    p_download = subparsers.add_parser(
        "download", help="Step 2: download PDFs for papers kept in the CSV"
    )
    p_download.add_argument("--output", "-o", default=None, help="Output directory")
    p_download.add_argument("--csv", default=None, help="Path to the reviewed CSV")

    # --- discover ---
    p_discover = subparsers.add_parser(
        "discover", help="Only discover/cache institution IDs"
    )
    p_discover.add_argument("--output", "-o", default=None, help="Output directory")

    args = parser.parse_args()

    queries = load_queries(args.topics) if hasattr(args, "topics") and args.topics else []
    relevance = load_relevance_filter(args.relevance) if hasattr(args, "relevance") and args.relevance else None
    collector = OpenAlexCollector(output_dir=args.output, queries=queries, relevance_filter=relevance)

    if args.command == "collect":
        collector.collect(
            max_per_institution=args.max_papers,
            continue_from_csv=args.continue_csv,
            only_university=args.university,
        )
    elif args.command == "collect-projects":
        pc = ProjectCollector(collector)
        pc.collect_projects(
            max_per_institution=args.max_papers,
            funder_filter=args.funder,
            only_university=args.university,
        )
    elif args.command == "download":
        csv_path = Path(args.csv) if args.csv else None
        collector.download(csv_path=csv_path)
    elif args.command == "discover":
        collector.discover_institution_ids()


if __name__ == "__main__":
    main()
