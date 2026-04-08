#!/usr/bin/env python3
"""
Convert between researchers.json and TSV (tab-separated) formats.

Usage:
  python researchers_tsv.py researchers.json              # JSON → TSV (writes .tsv)
  python researchers_tsv.py researchers.tsv               # TSV → JSON (writes .json)
  python researchers_tsv.py input.json output.tsv         # explicit output path
  python researchers_tsv.py input.tsv output.json         # explicit output path
"""

import csv
import json
import sys
from pathlib import Path

SEPARATOR = "; "

FIELDNAMES = [
    "university", "name", "paper_count", "affiliation_status",
    "affiliations", "topics", "paper_ids", "paper_titles", "paper_years",
]


def json_to_tsv(input_path: Path, output_path: Path):
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for uni_code, researchers in data.items():
        for r in researchers:
            papers = r.get("papers", [])
            rows.append({
                "university": uni_code,
                "name": r["name"],
                "paper_count": r["paper_count"],
                "affiliation_status": r.get("affiliation_status", ""),
                "affiliations": SEPARATOR.join(r.get("affiliations", [])),
                "topics": SEPARATOR.join(r.get("topics", [])),
                "paper_ids": SEPARATOR.join(p["id"] for p in papers),
                "paper_titles": SEPARATOR.join(p["title"] for p in papers),
                "paper_years": SEPARATOR.join(str(p.get("year", "")) for p in papers),
            })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"JSON → TSV: {len(rows)} researchers written to {output_path}")


def tsv_to_json(input_path: Path, output_path: Path):
    with open(input_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    data = {}
    for row in rows:
        uni = row["university"]
        if uni not in data:
            data[uni] = []

        ids = row.get("paper_ids", "").split(SEPARATOR) if row.get("paper_ids") else []
        titles = row.get("paper_titles", "").split(SEPARATOR) if row.get("paper_titles") else []
        years = row.get("paper_years", "").split(SEPARATOR) if row.get("paper_years") else []

        papers = []
        for pid, title, year in zip(ids, titles, years):
            pid, title, year = pid.strip(), title.strip(), year.strip()
            papers.append({
                "id": pid,
                "title": title,
                "year": int(year) if year.isdigit() else None,
            })

        affiliations = [a.strip() for a in row.get("affiliations", "").split(SEPARATOR) if a.strip()]
        topics = [t.strip() for t in row.get("topics", "").split(SEPARATOR) if t.strip()]

        data[uni].append({
            "name": row["name"],
            "paper_count": int(row.get("paper_count", len(papers))),
            "topics": topics,
            "papers": papers,
            "affiliations": affiliations,
            "affiliation_status": row.get("affiliation_status", "confirmed"),
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in data.values())
    print(f"TSV → JSON: {total} researchers written to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    input_path = Path(sys.argv[1])
    suffix = input_path.suffix.lower()

    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    elif suffix == ".json":
        output_path = input_path.with_suffix(".tsv")
    elif suffix in (".tsv", ".txt"):
        output_path = input_path.with_suffix(".json")
    else:
        print(f"Cannot infer direction from extension '{suffix}'. Use .json or .tsv")
        sys.exit(1)

    if suffix == ".json":
        json_to_tsv(input_path, output_path)
    else:
        tsv_to_json(input_path, output_path)
