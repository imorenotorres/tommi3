#!/usr/bin/env python3
"""
Reconcile orphan PDFs: find PDFs in data/docs/ that are not in
papers.json/metadata.json and fetch their metadata from OpenAlex.

Usage:
  python reconcile_orphan_pdfs.py <agent_dir>

Example:
  python reconcile_orphan_pdfs.py agents/responsible_ai
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

OPENALEX_BASE_URL = "https://api.openalex.org"
POLITE_EMAIL = "imoreno@uma.es"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_paper_ids_from_metadata(meta):
    """Extract all paper IDs from metadata.json."""
    ids = set()
    for uni_data in meta.get("universities", {}).values():
        for p in uni_data.get("papers", []):
            ids.add(p["id"])
    return ids


def get_pdf_ids(docs_dir):
    """Get paper IDs from PDF filenames in docs/."""
    ids = set()
    for f in os.listdir(docs_dir):
        if f.endswith(".pdf") and f.startswith("W"):
            ids.add(f.replace(".pdf", ""))
    return ids


def fetch_openalex_work(work_id):
    """Fetch a single work from OpenAlex API."""
    url = f"{OPENALEX_BASE_URL}/works/{work_id}?mailto={POLITE_EMAIL}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception as e:
        print(f"  Error fetching {work_id}: {e}")
        return None


def work_to_paper(work, institution_ids):
    """Convert an OpenAlex work to our papers.json format."""
    authors = []
    for authorship in work.get("authorships", []):
        author_info = authorship.get("author", {})
        institutions = [
            inst.get("display_name", "")
            for inst in authorship.get("institutions", [])
        ]
        authors.append({
            "name": author_info.get("display_name", ""),
            "orcid": author_info.get("orcid", ""),
            "institutions": institutions,
        })

    affiliations = list({
        inst.get("display_name", "")
        for a in work.get("authorships", [])
        for inst in a.get("institutions", [])
        if inst.get("display_name")
    })

    concepts = [
        {"name": c.get("display_name", ""), "score": c.get("score", 0)}
        for c in work.get("concepts", [])
    ]

    # Determine which university this paper belongs to
    university = None
    inst_display_names = {v["display_name"].lower(): k for k, v in institution_ids.items()}
    for a in work.get("authorships", []):
        for inst in a.get("institutions", []):
            name_lower = inst.get("display_name", "").lower()
            if name_lower in inst_display_names:
                university = inst_display_names[name_lower]
                break
        if university:
            break

    oa_url = work.get("open_access", {}).get("oa_url", "")
    pdf_url = work.get("primary_location", {}).get("pdf_url", "") or oa_url

    return {
        "id": work.get("id", "").replace("https://openalex.org/", ""),
        "doi": work.get("doi", ""),
        "title": work.get("title", ""),
        "abstract": work.get("abstract", "") or "",
        "publication_date": work.get("publication_date", ""),
        "publication_year": work.get("publication_year"),
        "type": work.get("type", ""),
        "cited_by_count": work.get("cited_by_count", 0),
        "authors": authors,
        "affiliations": affiliations,
        "concepts": concepts,
        "pdf_url": pdf_url,
        "university": university,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    agent_dir = sys.argv[1]
    data_dir = os.path.join(agent_dir, "data")
    docs_dir = os.path.join(data_dir, "docs")

    metadata_path = os.path.join(data_dir, "metadata.json")
    papers_path = os.path.join(data_dir, "papers.json")
    inst_path = os.path.join(data_dir, "institution_ids.json")

    if not os.path.exists(docs_dir):
        print(f"Error: {docs_dir} not found")
        sys.exit(1)

    metadata = load_json(metadata_path)
    papers = load_json(papers_path) if os.path.exists(papers_path) else {}
    institution_ids = load_json(inst_path) if os.path.exists(inst_path) else {}

    meta_ids = get_paper_ids_from_metadata(metadata)
    pdf_ids = get_pdf_ids(docs_dir)
    orphans = sorted(pdf_ids - meta_ids)

    if not orphans:
        print("No orphan PDFs found — all PDFs are in metadata.")
        return

    print(f"Found {len(orphans)} orphan PDFs. Fetching metadata from OpenAlex...\n")

    added = 0
    failed = []
    no_uni = []

    for i, pid in enumerate(orphans):
        print(f"  [{i+1}/{len(orphans)}] {pid}...", end=" ", flush=True)
        work = fetch_openalex_work(pid)
        if not work:
            print("NOT FOUND in OpenAlex")
            failed.append(pid)
            continue

        paper = work_to_paper(work, institution_ids)
        uni = paper.pop("university", None)

        if not uni:
            print(f"WARNING: no matching university found for '{paper.get('title', '')[:60]}'")
            no_uni.append(pid)
            continue

        # Add to metadata.json
        if uni not in metadata.get("universities", {}):
            metadata["universities"][uni] = {"name": institution_ids.get(uni, {}).get("display_name", uni), "papers_count": 0, "papers": []}
        uni_meta = metadata["universities"][uni]
        uni_meta["papers"].append(paper)
        uni_meta["papers_count"] = len(uni_meta["papers"])

        # Add to papers.json
        if "universities" not in papers:
            papers["universities"] = {}
        if uni not in papers["universities"]:
            papers["universities"][uni] = {"name": institution_ids.get(uni, {}).get("display_name", uni), "papers": []}
        papers["universities"][uni]["papers"].append(paper)

        added += 1
        print(f"OK → {uni} | {paper['title'][:60]}")

        # Rate limiting
        time.sleep(0.1)

    # Save
    save_json(metadata_path, metadata)
    save_json(papers_path, papers)

    print(f"\nDone!")
    print(f"  Added: {added}")
    print(f"  Not found in OpenAlex: {len(failed)}")
    if failed:
        print(f"    {', '.join(failed[:10])}")
    print(f"  No matching university: {len(no_uni)}")
    if no_uni:
        print(f"    {', '.join(no_uni[:10])}")


if __name__ == "__main__":
    main()
