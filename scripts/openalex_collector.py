#!/usr/bin/env python3
"""
OpenAlex Data Collector for UNINOVIS Alliance
Collects papers on AI & Responsibility from alliance universities.

Two-step workflow:
  Step 1 (collect): Query OpenAlex and produce a CSV table for manual review.
  Step 2 (download): Read the reviewed CSV and download PDFs + metadata for
                     papers that were kept (column "keep" == "yes").

Usage:
  python openalex_collector.py collect  [-o DIR] [-m N]
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
        "search_names": ["Kauno Kolegija", "Kaunas College"],
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

# Focused search queries — each one already combines AI + Responsibility/Ethics
FOCUSED_QUERIES = [
    '"responsible AI"',
    '"ethical AI"',
    '"trustworthy AI"',
    '"AI ethics"',
    '"AI governance"',
    '"AI accountability"',
    '"AI fairness"',
    '"AI bias"',
    '"algorithmic fairness"',
    '"algorithmic bias"',
    '"algorithmic accountability"',
    '"explainable AI"',
    '"explainable artificial intelligence"',
    '"XAI"',
    '"artificial intelligence" AND ethics',
    '"artificial intelligence" AND responsibility',
    '"artificial intelligence" AND governance',
    '"artificial intelligence" AND fairness',
    '"artificial intelligence" AND transparency',
    '"machine learning" AND ethics',
    '"machine learning" AND bias',
    '"machine learning" AND fairness',
    '"deep learning" AND ethics',
    '"AI" AND "social responsibility"',
    '"AI" AND "human rights"',
    '"AI regulation"',
    '"AI policy"',
]

# OpenAlex API
OPENALEX_BASE_URL = "https://api.openalex.org"
POLITE_EMAIL = "imoreno@uma.es"

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
    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_DATA_DIR
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

    def _api_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to OpenAlex API with rate limiting."""
        url = f"{OPENALEX_BASE_URL}/{endpoint}"
        if params is None:
            params = {}
        params["mailto"] = POLITE_EMAIL

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            time.sleep(0.1)  # Polite rate limiting
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  API request error: {e}")
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

    @staticmethod
    def _is_relevant(paper: dict) -> bool:
        """Check that the paper is actually about AI AND responsibility/ethics."""
        title = (paper.get("title") or "").lower()
        abstract_inv = paper.get("abstract_inverted_index")
        abstract = ""
        if abstract_inv:
            abstract = " ".join(abstract_inv.keys()).lower()
        text = title + " " + abstract

        ai_terms = [
            "artificial intelligence", " ai ", "machine learning",
            "deep learning", "algorithm", "neural network", "automated decision",
        ]
        ethics_terms = [
            "ethic", "responsib", "bias", "fair", "accountab",
            "transparen", "explain", "trust", "governance", "regulat",
            "privacy", "discriminat", "right", "safe",
        ]
        return any(t in text for t in ai_terms) and any(t in text for t in ethics_terms)

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

    def collect(self, max_per_institution: int = 0, continue_from_csv: bool = False) -> Path:
        """Query OpenAlex and write a CSV table for manual review.

        Args:
            max_per_institution: Max papers per institution (0 = unlimited).
            continue_from_csv: If True, skip papers already in the existing CSV
                               and append new papers to it.
        """
        print("=" * 60)
        print("STEP 1 — Collect paper metadata for review")
        print("=" * 60)

        institutions = self._load_institutions()
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

            for query in FOCUSED_QUERIES:
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
                        inst.get("display_name", "")
                        for auth in paper.get("authorships", [])
                        for inst in auth.get("institutions", [])
                    }
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

        # Write CSV (existing + new rows if continuing)
        all_rows = existing_rows + rows
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(all_rows)

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

        # Prepare download log
        log_dir = self.output_dir / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tsv"
        log_columns = [
            "openalex_id", "university", "title", "keep",
            "pdf_url", "status", "detail",
        ]
        log_file = open(log_path, "w", newline="", encoding="utf-8")
        log_writer = csv.DictWriter(log_file, fieldnames=log_columns, delimiter="\t")
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
                })

        collection = {
            "collection_date": datetime.now().isoformat(),
            "universities": {},
            "total_papers": 0,
            "papers_with_pdf": 0,
        }

        for row in kept:
            acronym = row["university"]
            paper_id = row["openalex_id"]
            title = row["title"]
            pdf_url_csv = row.get("pdf_url", "")

            if acronym not in collection["universities"]:
                collection["universities"][acronym] = {
                    "name": UNINOVIS_UNIVERSITIES.get(acronym, {}).get("name", acronym),
                    "papers_count": 0,
                    "papers": [],
                }

            print(f"\n[{acronym}] {title[:70]}...")

            # Fetch full metadata from OpenAlex
            full = self._api_request(f"works/{paper_id}")
            if not full:
                print("  Could not fetch metadata, using CSV data")
                metadata = {k: row[k] for k in CSV_COLUMNS if k != "keep"}
                metadata["local_pdf_path"] = None
            else:
                metadata = self._extract_paper_metadata(full)

            # Download PDF
            pdf_url = row.get("pdf_url") or metadata.get("pdf_url") or ""
            if pdf_url:
                pdf_path, dl_status, dl_detail = self._download_pdf(pdf_url, paper_id)
                metadata["local_pdf_path"] = pdf_path
                if pdf_path:
                    collection["papers_with_pdf"] += 1
            else:
                metadata["local_pdf_path"] = None
                dl_status = "NO_URL"
                dl_detail = "No PDF URL available in CSV or OpenAlex metadata"

            log_writer.writerow({
                "openalex_id": paper_id,
                "university": acronym,
                "title": title,
                "keep": "yes",
                "pdf_url": pdf_url,
                "status": dl_status,
                "detail": dl_detail,
            })

            collection["universities"][acronym]["papers"].append(metadata)
            collection["universities"][acronym]["papers_count"] += 1
            collection["total_papers"] += 1

        log_file.close()

        # Save per-university JSON files
        for acronym, data in collection["universities"].items():
            with open(self.metadata_dir / f"{acronym}_papers.json", "w", encoding="utf-8") as f:
                json.dump(data["papers"], f, indent=2, ensure_ascii=False)

        # Save full collection
        with open(self.metadata_dir / "full_collection.json", "w", encoding="utf-8") as f:
            json.dump(collection, f, indent=2, ensure_ascii=False)

        # Summary
        print(f"\n{'=' * 60}")
        print("DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"Total papers: {collection['total_papers']}")
        print(f"Papers with PDF: {collection['papers_with_pdf']}")
        for acronym, data in collection["universities"].items():
            print(f"  {acronym}: {data['papers_count']} papers")
        print(f"\nDownload log: {log_path}")

        return collection

    # ------------------------------------------------------------------
    # Internal helpers used by download()
    # ------------------------------------------------------------------

    def _extract_paper_metadata(self, paper: dict) -> dict:
        """Extract relevant metadata from a full OpenAlex work object."""
        authors = []
        affiliations = set()
        for authorship in paper.get("authorships", []):
            author = authorship.get("author", {})
            authors.append({"name": author.get("display_name"), "orcid": author.get("orcid")})
            for inst in authorship.get("institutions", []):
                affiliations.add(inst.get("display_name"))

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

    def _download_pdf(self, pdf_url: str, paper_id: str) -> tuple[Optional[str], str, str]:
        """Download PDF if available. Returns (path, status, detail)."""
        if not pdf_url:
            return None, "NO_URL", "No PDF URL provided"

        filename = f"{paper_id.replace('/', '_')}.pdf"
        filepath = self.papers_dir / filename

        if filepath.exists():
            print(f"  PDF already exists: {filename}")
            return str(filepath), "EXISTS", f"Already downloaded: {filename}"

        try:
            response = self.session.get(pdf_url, timeout=30, allow_redirects=True)
            content_type = response.headers.get("Content-Type", "")
            if response.status_code == 200 and "application/pdf" in content_type:
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
        "--max-papers", "-m", type=int, default=0,
        help="Max papers per institution (0 = unlimited, default)",
    )
    p_collect.add_argument(
        "--continue", dest="continue_csv", action="store_true",
        help="Continue from existing CSV: skip already-collected papers and append new ones",
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
    collector = OpenAlexCollector(output_dir=args.output)

    if args.command == "collect":
        collector.collect(
            max_per_institution=args.max_papers,
            continue_from_csv=args.continue_csv,
        )
    elif args.command == "download":
        csv_path = Path(args.csv) if args.csv else None
        collector.download(csv_path=csv_path)
    elif args.command == "discover":
        collector.discover_institution_ids()


if __name__ == "__main__":
    main()
