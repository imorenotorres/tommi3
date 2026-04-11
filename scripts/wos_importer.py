#!/usr/bin/env python3
"""WOS Importer — Parse Web of Science exports and prepare data for TOMMI agents.

Workflow:
  1. Export from WOS web interface as "Tab delimited" with "Full Record" fields
  2. Run this script to filter by UNINOVIS affiliations, download open-access PDFs,
     and produce papers.json / researchers.json compatible with TOMMI agents

Usage:
    python wos_importer.py <wos_export.txt> --agent responsible_ai2
    python wos_importer.py <wos_export.txt> --agent nlp_eh --no-pdf
    python wos_importer.py <wos_export.txt> --output-dir ./my_output --email user@uma.es

WOS Export Instructions:
    1. Go to webofscience.com and search your topic
    2. Click "Export" → "Tab delimited file"
    3. Select "Full Record" (includes authors, affiliations, DOI, abstract)
    4. Download (max 500 records per file, repeat for more)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# UNINOVIS partner universities — same keywords as rag_metadata_mixin.py
# ---------------------------------------------------------------------------
UNINOVIS_AFFILIATION_KEYWORDS = {
    "USPN":  ["sorbonne paris nord", "paris 13", "universite sorbonne paris nord"],
    "UDCLV": ["vanvitelli", "university of campania"],
    "UMA":   ["universidad de malaga", "malaga university", "universidad de málaga"],
    "KK":    ["kauno kolegija", "kaunas kolegija"],
    "UT":    ["universiteti i tiranes", "university of tirana"],
    "THWS":  ["technical university of applied sciences wurzburg",
              "hochschule fur angewandte wissenschaften wurzburg",
              "thws", "fhws"],
    "TAMK":  ["tampere university of applied sciences", "tampereen ammattikorkeakoulu"],
    "THUAS": ["hague university of applied sciences", "haagse hogeschool"],
}

UNINOVIS_NAMES = {
    "USPN":  "Université Sorbonne Paris Nord",
    "UDCLV": "University of Campania \"Luigi Vanvitelli\"",
    "UMA":   "Universidad de Málaga",
    "KK":    "Kauno Kolegija Higher Education Institution",
    "UT":    "University of Tirana",
    "THWS":  "Technical University of Applied Sciences Würzburg-Schweinfurt",
    "TAMK":  "Tampere University of Applied Sciences",
    "THUAS": "The Hague University of Applied Sciences",
}


def match_uninovis(affiliation_str: str) -> list:
    """Return list of UNINOVIS acronyms matching the affiliation string."""
    aff_lower = affiliation_str.lower()
    # Normalize special characters for matching
    aff_norm = (aff_lower
                .replace("á", "a").replace("é", "e").replace("ü", "u")
                .replace("ö", "o").replace("ä", "a"))
    matched = []
    for acronym, keywords in UNINOVIS_AFFILIATION_KEYWORDS.items():
        for kw in keywords:
            if kw in aff_lower or kw in aff_norm:
                matched.append(acronym)
                break
    return matched


# ---------------------------------------------------------------------------
# WOS field mapping
# ---------------------------------------------------------------------------
# WOS tab-delimited exports use 2-letter field tags as column headers.
# See: https://images.webofknowledge.com/images/help/WOS/hs_wos_fieldtags.html
WOS_FIELDS = {
    "PT": "pub_type",      # Publication type (J=Journal, B=Book, etc.)
    "AU": "authors",       # Authors (semicolon-separated)
    "AF": "authors_full",  # Authors full name
    "TI": "title",         # Title
    "SO": "source",        # Journal / source name
    "AB": "abstract",      # Abstract
    "DE": "keywords_author",  # Author keywords
    "ID": "keywords_plus",    # Keywords Plus (WOS-generated)
    "C1": "affiliations",    # Author affiliations
    "RP": "reprint_addr",    # Reprint address
    "OI": "orcid",           # ORCID
    "DI": "doi",             # DOI
    "PY": "year",            # Publication year
    "PD": "pub_date",        # Publication date
    "DT": "doc_type",        # Document type
    "TC": "cited_by",        # Times cited
    "UT": "wos_id",          # WOS unique ID
    "OA": "open_access",     # Open access status
    "LA": "language",        # Language
    "DA": "export_date",     # Export date (added by WOS)
}


def parse_wos_file(filepath: str) -> list:
    """Parse a WOS tab-delimited export file into a list of record dicts."""
    records = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        # WOS exports are tab-delimited with header row
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            record = {}
            for wos_tag, field_name in WOS_FIELDS.items():
                value = row.get(wos_tag, "").strip()
                if value:
                    record[field_name] = value
            if record.get("title"):
                records.append(record)

    print(f"Parsed {len(records)} records from {os.path.basename(filepath)}")
    return records


def parse_authors(record: dict) -> list:
    """Extract author list with names from a WOS record."""
    authors_str = record.get("authors_full") or record.get("authors", "")
    if not authors_str:
        return []

    authors = []
    for name in authors_str.split(";"):
        name = name.strip()
        if not name:
            continue
        authors.append({"name": name, "orcid": None})

    # Try to parse ORCIDs if available (format: "Name/ORCID-ID; Name/ORCID-ID")
    orcid_str = record.get("orcid", "")
    if orcid_str:
        for entry in orcid_str.split(";"):
            entry = entry.strip()
            if "/" in entry:
                parts = entry.rsplit("/", 1)
                orcid_name = parts[0].strip()
                orcid_id = parts[1].strip()
                if orcid_id and len(orcid_id) >= 15:
                    orcid_url = f"https://orcid.org/{orcid_id}"
                    # Match to author by last name
                    for author in authors:
                        if _last_name_match(author["name"], orcid_name):
                            author["orcid"] = orcid_url
                            break

    return authors


def _last_name_match(full_name: str, orcid_name: str) -> bool:
    """Check if two name strings refer to the same person (by last name)."""
    def get_last(n):
        parts = n.split(",")
        return parts[0].strip().lower() if parts else n.strip().lower()
    return get_last(full_name) == get_last(orcid_name)


def parse_affiliations(record: dict) -> list:
    """Extract unique affiliation strings from a WOS record."""
    aff_str = record.get("affiliations", "")
    if not aff_str:
        return []

    # WOS C1 format: "[Author1; Author2] Institution, City, Country; [Author3] Institution2, ..."
    affiliations = set()
    for part in re.split(r";\s*(?=\[)", aff_str):
        # Remove the [Author] prefix
        clean = re.sub(r"^\[.*?\]\s*", "", part).strip()
        if clean:
            affiliations.add(clean)

    return list(affiliations)


def parse_keywords(record: dict) -> list:
    """Extract concepts/keywords from WOS record."""
    concepts = []
    seen = set()

    for field in ["keywords_author", "keywords_plus"]:
        kw_str = record.get(field, "")
        if kw_str:
            for kw in kw_str.split(";"):
                kw = kw.strip()
                if kw and kw.lower() not in seen:
                    seen.add(kw.lower())
                    concepts.append({"name": kw, "score": 0.5})

    return concepts


def filter_by_uninovis(records: list) -> list:
    """Filter records: keep only those with at least one UNINOVIS-affiliated author."""
    filtered = []
    for record in records:
        affiliations = parse_affiliations(record)
        all_matches = set()
        for aff in affiliations:
            matches = match_uninovis(aff)
            all_matches.update(matches)

        if all_matches:
            record["_uninovis_matches"] = list(all_matches)
            record["_affiliations_parsed"] = affiliations
            filtered.append(record)

    print(f"Filtered to {len(filtered)} records with UNINOVIS affiliations")
    for acronym in sorted(set(a for r in filtered for a in r["_uninovis_matches"])):
        count = sum(1 for r in filtered if acronym in r["_uninovis_matches"])
        print(f"  {acronym} ({UNINOVIS_NAMES[acronym]}): {count} papers")

    return filtered


# ---------------------------------------------------------------------------
# PDF download via Unpaywall (free, no API key)
# ---------------------------------------------------------------------------

def get_pdf_url_unpaywall(doi: str, email: str) -> str | None:
    """Query Unpaywall API for an open-access PDF URL."""
    if not doi:
        return None

    # Clean DOI
    doi_clean = doi.strip()
    if doi_clean.startswith("http"):
        doi_clean = re.sub(r"^https?://doi\.org/", "", doi_clean)

    url = f"https://api.unpaywall.org/v2/{doi_clean}?email={email}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TOMMI-WOS-Importer/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Try best open-access location first
        best_oa = data.get("best_oa_location")
        if best_oa:
            pdf_url = best_oa.get("url_for_pdf") or best_oa.get("url")
            if pdf_url:
                return pdf_url

        # Try other OA locations
        for loc in data.get("oa_locations", []):
            pdf_url = loc.get("url_for_pdf") or loc.get("url")
            if pdf_url:
                return pdf_url

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        pass

    return None


def download_pdf(url: str, output_path: str) -> bool:
    """Download a PDF file from URL."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "TOMMI-WOS-Importer/1.0",
            "Accept": "application/pdf,*/*",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()

            # Basic check: PDF files start with %PDF
            if not content[:5].startswith(b"%PDF"):
                return False

            with open(output_path, "wb") as f:
                f.write(content)
            return True

    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


# ---------------------------------------------------------------------------
# Build output in TOMMI agent format
# ---------------------------------------------------------------------------

def build_papers_json(records: list) -> dict:
    """Build papers.json structure grouped by UNINOVIS university."""
    universities = defaultdict(lambda: {"name": "", "papers": []})

    for record in records:
        authors = parse_authors(record)
        affiliations = record.get("_affiliations_parsed", parse_affiliations(record))
        concepts = parse_keywords(record)
        doi = record.get("doi", "")
        doi_url = f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi

        year_str = record.get("year", "")
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            year = None

        paper = {
            "id": record.get("wos_id", ""),
            "doi": doi_url,
            "title": record.get("title", ""),
            "abstract": record.get("abstract", ""),
            "publication_date": record.get("pub_date", ""),
            "publication_year": year,
            "type": (record.get("doc_type") or "article").lower(),
            "cited_by_count": int(record.get("cited_by", 0) or 0),
            "authors": authors,
            "affiliations": affiliations,
            "concepts": concepts,
            "is_open_access": "gold" in (record.get("open_access", "")).lower()
                              or "green" in (record.get("open_access", "")).lower()
                              or "bronze" in (record.get("open_access", "")).lower(),
            "pdf_url": None,
            "source": record.get("source", ""),
            "language": record.get("language", "en").lower()[:2],
            "local_pdf_path": record.get("_local_pdf_path"),
            "wos_source": True,  # Flag to distinguish from OpenAlex data
        }

        for acronym in record["_uninovis_matches"]:
            universities[acronym]["name"] = UNINOVIS_NAMES[acronym]
            universities[acronym]["papers"].append(paper)

    return {"universities": dict(universities)}


def build_researchers_json(records: list) -> dict:
    """Build researchers.json structure grouped by UNINOVIS university."""
    # Track researchers per university
    researcher_map = defaultdict(lambda: defaultdict(lambda: {
        "name": "",
        "paper_count": 0,
        "topics": set(),
        "papers": [],
        "affiliations": [],
        "affiliation_status": "wos_import",
    }))

    for record in records:
        authors = parse_authors(record)
        concepts = parse_keywords(record)
        topic_names = [c["name"] for c in concepts[:8]]

        year_str = record.get("year", "")
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            year = None

        paper_ref = {
            "id": record.get("wos_id", ""),
            "title": record.get("title", ""),
            "year": year,
        }

        # For each UNINOVIS match, try to identify which authors belong
        affiliations = record.get("_affiliations_parsed", [])
        aff_str = record.get("affiliations", "")

        for acronym in record["_uninovis_matches"]:
            # Try to match specific authors to this university via C1 field
            # WOS C1 format: [LastName, FirstName; ...] Institution
            matched_authors = _match_authors_to_uni(aff_str, acronym, authors)

            if not matched_authors:
                # Fallback: attribute to all authors (imprecise but avoids losing data)
                matched_authors = authors

            for author in matched_authors:
                name = author["name"]
                r = researcher_map[acronym][name]
                r["name"] = name
                r["paper_count"] += 1
                r["topics"].update(topic_names)
                # Avoid duplicate papers
                existing_ids = {p["id"] for p in r["papers"]}
                if paper_ref["id"] not in existing_ids:
                    r["papers"].append(paper_ref)

    # Convert sets to lists and build final structure
    result = {}
    for acronym, researchers in researcher_map.items():
        result[acronym] = []
        for name, data in sorted(researchers.items(), key=lambda x: -x[1]["paper_count"]):
            data["topics"] = sorted(data["topics"])
            result[acronym].append(data)

    return result


def _match_authors_to_uni(c1_field: str, acronym: str, all_authors: list) -> list:
    """Try to identify which authors belong to a specific UNINOVIS university
    based on the WOS C1 (affiliations) field.

    C1 format: [LastName, F.; LastName2, G.] University of X, City, Country
    """
    if not c1_field:
        return []

    keywords = UNINOVIS_AFFILIATION_KEYWORDS[acronym]
    matched_names = set()

    for part in re.split(r";\s*(?=\[)", c1_field):
        part_lower = part.lower().replace("á", "a").replace("é", "e").replace("ü", "u")
        is_uni = any(kw in part_lower for kw in keywords)
        if not is_uni:
            continue

        # Extract author names from brackets
        bracket_match = re.match(r"\[([^\]]+)\]", part)
        if bracket_match:
            names_str = bracket_match.group(1)
            for name in names_str.split(";"):
                name = name.strip()
                if name:
                    matched_names.add(name.lower())

    if not matched_names:
        return []

    # Match back to full author list
    result = []
    for author in all_authors:
        author_lower = author["name"].lower()
        # Try matching by last name
        author_last = author_lower.split(",")[0].strip()
        for mn in matched_names:
            mn_last = mn.split(",")[0].strip()
            if author_last == mn_last:
                result.append(author)
                break

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import WOS exports into TOMMI agent data format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("wos_file", nargs="+",
                        help="WOS tab-delimited export file(s)")
    parser.add_argument("--agent", default=None,
                        help="Target agent name (e.g. responsible_ai2). "
                             "Outputs directly to agents/<name>/data/")
    parser.add_argument("--output-dir", default=None,
                        help="Custom output directory (overrides --agent)")
    parser.add_argument("--email", default="tommi@uma.es",
                        help="Email for Unpaywall API (default: tommi@uma.es)")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF downloads")
    parser.add_argument("--merge", action="store_true",
                        help="Merge with existing papers.json/researchers.json "
                             "instead of overwriting")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and filter only, don't write files or download PDFs")

    args = parser.parse_args()

    # Determine output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tommi_root = os.path.dirname(script_dir)

    if args.output_dir:
        output_dir = args.output_dir
    elif args.agent:
        output_dir = os.path.join(tommi_root, "agents", args.agent, "data")
    else:
        output_dir = os.path.join(script_dir, "wos_output")

    if not args.dry_run:
        os.makedirs(output_dir, exist_ok=True)
        docs_dir = os.path.join(output_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

    # Parse all input files
    all_records = []
    for filepath in args.wos_file:
        if not os.path.isfile(filepath):
            print(f"ERROR: File not found: {filepath}")
            sys.exit(1)
        records = parse_wos_file(filepath)
        all_records.extend(records)

    # Deduplicate by DOI or title
    seen = set()
    unique_records = []
    for r in all_records:
        key = r.get("doi") or r.get("title", "").lower()
        if key and key not in seen:
            seen.add(key)
            unique_records.append(r)
    if len(unique_records) < len(all_records):
        print(f"Deduplicated: {len(all_records)} → {len(unique_records)} records")
    all_records = unique_records

    # Filter by UNINOVIS affiliations
    filtered = filter_by_uninovis(all_records)

    if not filtered:
        print("\nNo records matched UNINOVIS partner universities.")
        print("Check that the WOS export includes the C1 (affiliations) field.")
        sys.exit(0)

    if args.dry_run:
        print(f"\n[Dry run] Would output {len(filtered)} papers to {output_dir}")
        return

    # Download PDFs via Unpaywall
    if not args.no_pdf:
        print(f"\nDownloading open-access PDFs via Unpaywall (email: {args.email})...")
        downloaded = 0
        skipped = 0
        for i, record in enumerate(filtered):
            doi = record.get("doi", "")
            if not doi:
                continue

            # Create safe filename from DOI
            doi_clean = re.sub(r"^https?://doi\.org/", "", doi)
            safe_name = re.sub(r"[^\w\-.]", "_", doi_clean)[:80]
            pdf_path = os.path.join(docs_dir, f"{safe_name}.pdf")

            if os.path.exists(pdf_path):
                record["_local_pdf_path"] = pdf_path
                skipped += 1
                continue

            pdf_url = get_pdf_url_unpaywall(doi, args.email)
            if pdf_url:
                record["_pdf_url"] = pdf_url
                if download_pdf(pdf_url, pdf_path):
                    record["_local_pdf_path"] = pdf_path
                    downloaded += 1
                    print(f"  [{downloaded}] Downloaded: {record.get('title', '')[:60]}")

            # Rate limit: 1 request per second (Unpaywall policy)
            if i < len(filtered) - 1:
                time.sleep(1.0)

        print(f"PDFs: {downloaded} downloaded, {skipped} already existed, "
              f"{len(filtered) - downloaded - skipped} not available as open access")

    # Build output files
    papers_data = build_papers_json(filtered)
    researchers_data = build_researchers_json(filtered)

    # Optionally merge with existing data
    if args.merge:
        papers_path = os.path.join(output_dir, "papers.json")
        researchers_path = os.path.join(output_dir, "researchers.json")

        if os.path.isfile(papers_path):
            with open(papers_path, "r", encoding="utf-8") as f:
                existing_papers = json.load(f)
            papers_data = _merge_papers(existing_papers, papers_data)
            print("Merged with existing papers.json")

        if os.path.isfile(researchers_path):
            with open(researchers_path, "r", encoding="utf-8") as f:
                existing_researchers = json.load(f)
            researchers_data = _merge_researchers(existing_researchers, researchers_data)
            print("Merged with existing researchers.json")

    # Write output
    papers_out = os.path.join(output_dir, "papers_wos.json")
    researchers_out = os.path.join(output_dir, "researchers_wos.json")

    if args.merge:
        papers_out = os.path.join(output_dir, "papers.json")
        researchers_out = os.path.join(output_dir, "researchers.json")

    with open(papers_out, "w", encoding="utf-8") as f:
        json.dump(papers_data, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {papers_out}")

    with open(researchers_out, "w", encoding="utf-8") as f:
        json.dump(researchers_data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {researchers_out}")

    # Summary
    total_papers = sum(len(u["papers"]) for u in papers_data["universities"].values())
    total_researchers = sum(len(r) for r in researchers_data.values())
    print(f"\nSummary: {total_papers} papers, {total_researchers} researchers "
          f"across {len(papers_data['universities'])} universities")


def _merge_papers(existing: dict, new: dict) -> dict:
    """Merge new papers into existing papers.json, avoiding duplicates by DOI/title."""
    unis = existing.get("universities", {})
    for acronym, uni_data in new.get("universities", {}).items():
        if acronym not in unis:
            unis[acronym] = uni_data
        else:
            existing_ids = {p.get("doi") or p.get("title", "").lower()
                           for p in unis[acronym]["papers"]}
            for paper in uni_data["papers"]:
                key = paper.get("doi") or paper.get("title", "").lower()
                if key not in existing_ids:
                    unis[acronym]["papers"].append(paper)
                    existing_ids.add(key)
    return {"universities": unis}


def _merge_researchers(existing: dict, new: dict) -> dict:
    """Merge new researchers into existing researchers.json."""
    for acronym, researchers in new.items():
        if acronym not in existing:
            existing[acronym] = researchers
        else:
            existing_names = {r["name"].lower() for r in existing[acronym]}
            for researcher in researchers:
                if researcher["name"].lower() not in existing_names:
                    existing[acronym].append(researcher)
                    existing_names.add(researcher["name"].lower())
                else:
                    # Merge papers for existing researcher
                    for er in existing[acronym]:
                        if er["name"].lower() == researcher["name"].lower():
                            existing_ids = {p["id"] for p in er["papers"]}
                            for p in researcher["papers"]:
                                if p["id"] not in existing_ids:
                                    er["papers"].append(p)
                                    er["paper_count"] += 1
                            er["topics"] = sorted(
                                set(er.get("topics", [])) | set(researcher.get("topics", []))
                            )
                            break
    return existing


if __name__ == "__main__":
    main()
