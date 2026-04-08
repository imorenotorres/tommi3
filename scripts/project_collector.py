#!/usr/bin/env python3
"""
Research Project Collector for UNINOVIS Alliance.
Collects funded research projects from CORDIS (EU) and OpenAIRE (EU + national).

Two-step workflow:
  Step 1 (collect): Search APIs and produce a CSV table for manual review.
  Step 2 (export):  Read the reviewed CSV and produce agent-ready JSON files.

Usage:
  python project_collector.py collect -t TOPICS_FILE [-o DIR] [-s cordis|openaire|both]
  python project_collector.py collect -t TOPICS_FILE -u UMA -s openaire
  python project_collector.py export  [-o DIR] [--csv PATH] [--agent-dir PATH]

Examples:
  # Collect EU + national projects on responsible AI topics
  python project_collector.py collect -t topics_responsible_ai.txt -s both

  # Only CORDIS (EU-funded)
  python project_collector.py collect -t topics_responsible_ai.txt -s cordis

  # Only OpenAIRE, restricted to UMA
  python project_collector.py collect -t topics_responsible_ai.txt -s openaire -u UMA

  # Export reviewed CSV to agent data directory
  python project_collector.py export --agent-dir ../agents/responsible_ai
"""

import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = SCRIPT_DIR / "data"

# UNINOVIS universities — used for filtering by organization
UNINOVIS_UNIVERSITIES = {
    "USPN": {
        "name": "Université Sorbonne Paris Nord",
        "search_names": ["Sorbonne Paris Nord"],
        "country": "FR",
        "cordis_names": ["UNIVERSITE SORBONNE PARIS NORD", "UNIVERSITE PARIS XIII"],
    },
    "UDCLV": {
        "name": "University of Campania Luigi Vanvitelli",
        "search_names": ["Campania Luigi Vanvitelli", "Campania Vanvitelli"],
        "country": "IT",
        "cordis_names": ["UNIVERSITA DEGLI STUDI DELLA CAMPANIA LUIGI VANVITELLI",
                         "SECONDA UNIVERSITA DEGLI STUDI DI NAPOLI"],
    },
    "UMA": {
        "name": "Universidad de Málaga",
        "search_names": ["Universidad de Malaga", "University of Malaga"],
        "country": "ES",
        "cordis_names": ["UNIVERSIDAD DE MALAGA"],
    },
    "KK": {
        "name": "Kauno Kolegija",
        "search_names": ["Kauno Kolegija", "Kaunas College"],
        "country": "LT",
        "cordis_names": ["KAUNO KOLEGIJA"],
    },
    "UT": {
        "name": "University of Tirana",
        "search_names": ["University of Tirana"],
        "country": "AL",
        "cordis_names": ["UNIVERSITETI I TIRANES"],
    },
    "THWS": {
        "name": "Technical University of Applied Sciences Würzburg-Schweinfurt",
        "search_names": ["Würzburg-Schweinfurt", "THWS"],
        "country": "DE",
        "cordis_names": ["HOCHSCHULE FUR ANGEWANDTE WISSENSCHAFTEN WURZBURG-SCHWEINFURT",
                         "TECHNISCHE HOCHSCHULE WURZBURG-SCHWEINFURT"],
    },
    "TAMK": {
        "name": "Tampere University of Applied Sciences",
        "search_names": ["Tampere University of Applied Sciences", "TAMK"],
        "country": "FI",
        "cordis_names": ["TAMPEREEN AMMATTIKORKEAKOULU", "TAMK"],
    },
    "THUAS": {
        "name": "The Hague University of Applied Sciences",
        "search_names": ["Hague University of Applied Sciences", "Haagse Hogeschool"],
        "country": "NL",
        "cordis_names": ["DE HAAGSE HOGESCHOOL", "HAAGSE HOGESCHOOL"],
    },
}

CSV_COLUMNS = [
    "keep", "source", "project_id", "grant_id", "acronym", "title",
    "summary", "funder", "programme", "call_id",
    "start_date", "end_date", "status",
    "total_cost", "funded_amount", "currency",
    "universities", "all_participants",
    "keywords", "website_url", "collected_on",
]


def load_queries(topics_file: str) -> list[str]:
    path = Path(topics_file)
    if not path.exists():
        raise FileNotFoundError(f"Topics file not found: {topics_file}")
    return [
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _http_get_json(url: str, timeout: int = 30, max_retries: int = 3) -> Optional[dict]:
    """Simple HTTP GET returning parsed JSON, with retries."""
    headers = {"User-Agent": "UNINOVIS-ProjectCollector/1.0", "Accept": "application/json"}
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(2 ** attempt * 5, 60)
                print(f"    Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
                continue
            elif e.code >= 500:
                time.sleep(2)
                continue
            print(f"    HTTP error {e.code}: {url[:120]}")
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            print(f"    Request error: {e}")
            return None
    return None


# ======================================================================
# CORDIS collector (EU-funded projects)
# ======================================================================

class CORDISCollector:
    """Collect projects from the CORDIS search API."""

    BASE_URL = "https://cordis.europa.eu/search/en"

    def search(self, query: str, max_results: int = 100,
               only_university: str = None) -> list[dict]:
        """Search CORDIS for projects matching query."""
        projects = []
        page = 1
        per_page = 10  # CORDIS default

        # Build query with organization filter for specific UNINOVIS university
        q = f"'{query}'"
        if only_university:
            uni_info = UNINOVIS_UNIVERSITIES.get(only_university.upper())
            if uni_info:
                # Use CORDIS-specific names (uppercase legal names)
                cordis_names = uni_info.get("cordis_names", uni_info["search_names"])
                org_clauses = " OR ".join(
                    f"organization/legalName='{n}'" for n in cordis_names
                )
                q = f"({q}) AND ({org_clauses})"

        while len(projects) < max_results:
            params = urllib.parse.urlencode({
                "q": q,
                "type": "project",
                "p": page,
                "num": per_page,
                "srt": "Relevance:decreasing",
                "format": "json",
            })
            url = f"{self.BASE_URL}?{params}"
            data = _http_get_json(url)
            if not data:
                break

            # Navigate CORDIS response structure
            header = data.get("result", {}).get("header", {})
            total = int(header.get("totalHits", 0))
            records = data.get("hits", {}).get("hit", [])
            if isinstance(records, dict):
                records = [records]

            if page == 1:
                print(f"    CORDIS: {total} total results for '{query[:50]}'")

            if not records:
                break

            for record in records:
                project = self._parse_project(record)
                if project:
                    projects.append(project)

            if len(records) < per_page or len(projects) >= max_results:
                break
            page += 1
            time.sleep(1)  # Rate limiting

        return projects[:max_results]

    def _parse_project(self, record: dict) -> Optional[dict]:
        """Parse a CORDIS search result into our standard format."""
        proj = record.get("project") or record
        if isinstance(proj, str):
            return None

        # Extract participants
        relations = proj.get("relations") or {}
        associations = relations.get("associations") or {}
        org_list = associations.get("organization") or []
        if isinstance(org_list, dict):
            org_list = [org_list]
        participants = []
        for org in org_list:
            name = org.get("legalName") or org.get("name") or ""
            country = org.get("country") or ""
            if name:
                participants.append(f"{name} ({country})" if country else name)

        # Match UNINOVIS universities
        unis = []
        participant_names_lower = [p.lower() for p in participants]
        for acronym, info in UNINOVIS_UNIVERSITIES.items():
            for search_name in info["search_names"]:
                if any(search_name.lower() in p for p in participant_names_lower):
                    unis.append(acronym)
                    break

        # Extract programme info
        prog_list = associations.get("programme") or []
        if isinstance(prog_list, dict):
            prog_list = [prog_list]
        programme = ""
        if prog_list:
            programme = prog_list[0].get("title") or prog_list[0].get("code") or ""

        # Keywords
        kw = proj.get("keywords") or ""
        if isinstance(kw, dict):
            kw = kw.get("keyword", "")
        if isinstance(kw, list):
            kw = "; ".join(kw)

        return {
            "source": "CORDIS",
            "project_id": str(proj.get("rcn") or proj.get("id") or ""),
            "grant_id": str(proj.get("id") or ""),
            "acronym": proj.get("acronym") or "",
            "title": proj.get("title") or "",
            "summary": (proj.get("objective") or proj.get("teaser") or "")[:2000],
            "funder": "European Commission",
            "programme": programme,
            "call_id": "",
            "start_date": proj.get("startDate") or "",
            "end_date": proj.get("endDate") or "",
            "status": proj.get("status") or "",
            "total_cost": str(proj.get("totalCost") or ""),
            "funded_amount": str(proj.get("ecMaxContribution") or ""),
            "currency": "EUR",
            "universities": "; ".join(unis),
            "all_participants": "; ".join(participants[:30]),
            "keywords": kw,
            "website_url": "",
        }


# ======================================================================
# OpenAIRE Graph API v2 collector (EU + national funding)
# ======================================================================

class OpenAIRECollector:
    """Collect projects from the OpenAIRE Search API."""

    BASE_URL = "https://api.openaire.eu/search/projects"

    def search(self, query: str, max_results: int = 100,
               funder: str = None, only_university: str = None) -> list[dict]:
        """Search OpenAIRE for projects matching query."""
        projects = []
        page = 1
        page_size = 50

        while len(projects) < max_results:
            params = {
                "keywords": query,
                "format": "json",
                "size": str(page_size),
                "page": str(page),
            }
            if funder:
                params["funder"] = funder
            if only_university:
                uni_info = UNINOVIS_UNIVERSITIES.get(only_university.upper())
                if uni_info:
                    # Use country + acronym for better precision
                    params["participantCountries"] = uni_info["country"]
                    # Also add acronym if short and distinctive
                    if only_university.upper() not in ("UT",):  # UT is too generic
                        params["participantAcronyms"] = only_university.upper()

            qs = urllib.parse.urlencode(params)
            url = f"{self.BASE_URL}?{qs}"
            data = _http_get_json(url)
            if not data:
                break

            resp = data.get("response", {})
            header = resp.get("header", {})
            total = int(header.get("total", {}).get("$", 0))
            results_wrapper = resp.get("results") or {}
            results = results_wrapper.get("result") or []
            if isinstance(results, dict):
                results = [results]

            if page == 1:
                print(f"    OpenAIRE: {total} total results for '{query[:50]}'"
                      + (f" (funder={funder})" if funder else ""))

            if not results:
                break

            for record in results:
                project = self._parse_project(record)
                if project:
                    projects.append(project)

            if len(results) < page_size or len(projects) >= max_results:
                break
            page += 1
            time.sleep(0.5)

        return projects[:max_results]

    @staticmethod
    def _val(node, key="$"):
        """Extract text value from OpenAIRE's {\"$\": \"value\"} format."""
        if not node:
            return ""
        if isinstance(node, str):
            return node
        return node.get(key, "")

    def _parse_project(self, record: dict) -> Optional[dict]:
        """Parse an OpenAIRE Search API project result."""
        meta = record.get("metadata", {}).get("oaf:entity", {}).get("oaf:project", {})
        if not meta:
            return None

        v = self._val

        # Funding tree
        ft = meta.get("fundingtree") or {}
        if isinstance(ft, list):
            ft = ft[0] if ft else {}
        funder_node = ft.get("funder", {})
        funder_name = v(funder_node.get("name"))
        funder_short = v(funder_node.get("shortname"))

        # Programme / funding stream
        programme = ""
        funding_level = ft.get("funding_level_1") or ft.get("funding_level_0") or {}
        if funding_level:
            programme = v(funding_level.get("description")) or v(funding_level.get("name"))

        # Budget
        currency = v(meta.get("currency"))
        total_cost = v(meta.get("totalcost"))
        funded_amount = v(meta.get("fundedamount"))

        # Participants (from rels)
        rels = meta.get("rels") or {}
        rel_list = rels.get("rel") or []
        if isinstance(rel_list, dict):
            rel_list = [rel_list]
        participants = []
        for rel in rel_list:
            if v(rel.get("to", {}).get("@class")) == "hasParticipant":
                name = v(rel.get("legalname"))
                country = v(rel.get("country", {}).get("classname"))
                if name:
                    participants.append(f"{name} ({country})" if country else name)

        # Match UNINOVIS
        unis = []
        participant_names_lower = [p.lower() for p in participants]
        for acronym, info in UNINOVIS_UNIVERSITIES.items():
            for search_name in info["search_names"]:
                if any(search_name.lower() in p for p in participant_names_lower):
                    unis.append(acronym)
                    break

        # Keywords
        subjects = meta.get("subjects") or ""
        if isinstance(subjects, dict):
            subj_list = subjects.get("subject") or []
            if isinstance(subj_list, dict):
                subj_list = [subj_list]
            subjects = "; ".join(v(s) for s in subj_list if v(s))
        elif isinstance(subjects, list):
            subjects = "; ".join(v(s) for s in subjects if v(s))

        return {
            "source": "OpenAIRE",
            "project_id": v(meta.get("code")) or v(record.get("header", {}).get("dri:objIdentifier")),
            "grant_id": v(meta.get("code")),
            "acronym": v(meta.get("acronym")),
            "title": v(meta.get("title")),
            "summary": "",  # Search API doesn't return summaries
            "funder": funder_name or funder_short,
            "programme": programme,
            "call_id": v(meta.get("callidentifier")),
            "start_date": v(meta.get("startdate")),
            "end_date": v(meta.get("enddate")),
            "status": "",
            "total_cost": total_cost,
            "funded_amount": funded_amount,
            "currency": currency or "EUR",
            "universities": "; ".join(unis),
            "all_participants": "; ".join(participants[:30]),
            "keywords": subjects if isinstance(subjects, str) else "",
            "website_url": v(meta.get("websiteurl")),
        }


# ======================================================================
# Main collector orchestrator
# ======================================================================

class ProjectCollector:
    def __init__(self, output_dir: str = None, queries: list[str] = None):
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_DATA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.queries = queries or []
        self.cordis = CORDISCollector()
        self.openaire = OpenAIRECollector()

    def collect(self, source: str = "both", max_per_query: int = 100,
                only_university: str = None, funder: str = None) -> Path:
        """Collect projects for UNINOVIS universities and write a CSV.

        Iterates over each UNINOVIS university (or a single one if
        --university is set) and searches for projects where that
        university is a participant — same approach as the papers
        collector.
        """
        print("=" * 60)
        print("COLLECT RESEARCH PROJECTS (UNINOVIS partners only)")
        print("=" * 60)
        print(f"Source: {source}")
        print(f"Queries: {len(self.queries)}")
        if only_university:
            print(f"University filter: {only_university}")
        if funder:
            print(f"Funder filter: {funder}")
        print()

        # Determine which universities to search
        if only_university:
            key = only_university.upper()
            if key not in UNINOVIS_UNIVERSITIES:
                raise ValueError(f"Unknown university '{key}'. "
                                 f"Available: {', '.join(UNINOVIS_UNIVERSITIES.keys())}")
            universities = {key: UNINOVIS_UNIVERSITIES[key]}
        else:
            universities = UNINOVIS_UNIVERSITIES

        all_projects = []
        seen_keys = set()  # Deduplicate by (source, grant_id)

        for acronym, uni_info in universities.items():
            print(f"\n--- {uni_info['name']} ({acronym}) ---")

            for query in self.queries:
                print(f"  Query: {query}")

                # CORDIS (EU-funded) — filter by organization name
                if source in ("cordis", "both"):
                    cordis_results = self.cordis.search(
                        query, max_results=max_per_query,
                        only_university=acronym,
                    )
                    new = 0
                    for p in cordis_results:
                        key = ("CORDIS", p.get("grant_id") or p.get("title"))
                        if key not in seen_keys:
                            seen_keys.add(key)
                            # Ensure university is tagged
                            if acronym not in (p.get("universities") or ""):
                                existing = p.get("universities") or ""
                                p["universities"] = f"{existing}; {acronym}".strip("; ")
                            all_projects.append(p)
                            new += 1
                    if new:
                        print(f"    CORDIS: +{new} new projects")

                # OpenAIRE (EU + national) — filter by country
                if source in ("openaire", "both"):
                    funders_to_search = [funder] if funder else [None]
                    for f in funders_to_search:
                        openaire_results = self.openaire.search(
                            query, max_results=max_per_query,
                            funder=f, only_university=acronym,
                        )
                        new = 0
                        for p in openaire_results:
                            key = ("OpenAIRE", p.get("grant_id") or p.get("title"))
                            if key not in seen_keys:
                                seen_keys.add(key)
                                if acronym not in (p.get("universities") or ""):
                                    existing = p.get("universities") or ""
                                    p["universities"] = f"{existing}; {acronym}".strip("; ")
                                all_projects.append(p)
                                new += 1
                        if new:
                            print(f"    OpenAIRE: +{new} new projects"
                                  + (f" ({f})" if f else ""))

            uni_total = sum(1 for p in all_projects if acronym in (p.get("universities") or ""))
            print(f"  {acronym} total: {uni_total} projects")

        # Write CSV
        csv_path = self.output_dir / "projects_to_review.csv"
        batch_date = datetime.now().strftime("%Y-%m-%d")
        for p in all_projects:
            p["keep"] = "yes"
            p["collected_on"] = batch_date

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_projects)

        # Summary
        cordis_count = sum(1 for p in all_projects if p["source"] == "CORDIS")
        openaire_count = sum(1 for p in all_projects if p["source"] == "OpenAIRE")
        print(f"\n{'=' * 60}")
        print("COLLECTION SUMMARY")
        print("=" * 60)
        print(f"Total projects: {len(all_projects)}")
        print(f"  CORDIS:   {cordis_count}")
        print(f"  OpenAIRE: {openaire_count}")

        # Show top funders
        funder_counts = {}
        for p in all_projects:
            fn = p.get("funder") or "Unknown"
            funder_counts[fn] = funder_counts.get(fn, 0) + 1
        if funder_counts:
            print(f"\nTop funders:")
            for fn, count in sorted(funder_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {fn}: {count} projects")

        # Show UNINOVIS matches
        uni_matches = sum(1 for p in all_projects if p.get("universities"))
        if uni_matches:
            print(f"\nProjects involving UNINOVIS universities: {uni_matches}")

        print(f"\nCSV: {csv_path}")
        print("Review the CSV and set 'keep' to 'no' for projects to exclude.")
        print(f"Then run:  python {Path(__file__).name} export --agent-dir <agent>")
        print("=" * 60)

        return csv_path

    def export(self, csv_path: Path = None, agent_dir: str = None) -> None:
        """Read reviewed CSV and produce agent-ready JSON files."""
        if csv_path is None:
            csv_path = self.output_dir / "projects_to_review.csv"
        if not csv_path.exists():
            print(f"CSV not found: {csv_path}")
            print("Run 'collect' first.")
            return

        print("=" * 60)
        print("EXPORT PROJECTS TO AGENT DATA")
        print("=" * 60)

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        kept = [r for r in rows if r.get("keep", "").strip().lower() == "yes"]
        print(f"Total rows: {len(rows)}, kept: {len(kept)}")

        # Build projects.json
        projects = []
        for row in kept:
            projects.append({
                "source": row.get("source", ""),
                "project_id": row.get("project_id", ""),
                "grant_id": row.get("grant_id", ""),
                "acronym": row.get("acronym", ""),
                "title": row.get("title", ""),
                "summary": row.get("summary", ""),
                "funder": row.get("funder", ""),
                "programme": row.get("programme", ""),
                "call_id": row.get("call_id", ""),
                "start_date": row.get("start_date", ""),
                "end_date": row.get("end_date", ""),
                "status": row.get("status", ""),
                "total_cost": row.get("total_cost", ""),
                "funded_amount": row.get("funded_amount", ""),
                "currency": row.get("currency", ""),
                "universities": row.get("universities", ""),
                "all_participants": row.get("all_participants", ""),
                "keywords": row.get("keywords", ""),
                "website_url": row.get("website_url", ""),
            })

        output = {"collection_date": datetime.now().isoformat(), "projects": projects}

        # Save to output_dir
        out_path = self.output_dir / "projects.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Saved: {out_path} ({len(projects)} projects)")

        # Also save as markdown documents for RAG indexing
        docs_dir = self.output_dir / "project_docs"
        docs_dir.mkdir(exist_ok=True)
        for proj in projects:
            pid = proj.get("grant_id") or proj.get("project_id") or "unknown"
            pid_safe = pid.replace("/", "_").replace("\\", "_")
            acronym = proj.get("acronym") or "project"
            filename = f"{pid_safe}_{acronym}.md"
            content = self._project_to_markdown(proj)
            with open(docs_dir / filename, "w", encoding="utf-8") as f:
                f.write(content)

        print(f"Saved: {docs_dir}/ ({len(projects)} markdown docs for RAG indexing)")

        # Copy to agent data dir if specified
        if agent_dir:
            agent_data = Path(agent_dir) / "data"
            agent_docs = agent_data / "docs"
            agent_docs.mkdir(parents=True, exist_ok=True)

            import shutil
            # Copy projects.json
            shutil.copy2(out_path, agent_data / "projects.json")
            print(f"Copied projects.json → {agent_data / 'projects.json'}")

            # Copy markdown docs
            for md_file in docs_dir.glob("*.md"):
                shutil.copy2(md_file, agent_docs / md_file.name)
            print(f"Copied {len(projects)} docs → {agent_docs}/")

        print("\nDone!")

    @staticmethod
    def _project_to_markdown(proj: dict) -> str:
        """Convert a project to a markdown document for RAG indexing."""
        lines = []
        acronym = proj.get("acronym")
        title = proj.get("title", "Untitled Project")
        if acronym:
            lines.append(f"# {acronym}: {title}")
        else:
            lines.append(f"# {title}")

        lines.append("")

        meta = []
        if proj.get("grant_id"):
            meta.append(f"**Grant ID:** {proj['grant_id']}")
        if proj.get("funder"):
            meta.append(f"**Funder:** {proj['funder']}")
        if proj.get("programme"):
            meta.append(f"**Programme:** {proj['programme']}")
        if proj.get("call_id"):
            meta.append(f"**Call:** {proj['call_id']}")
        if proj.get("start_date"):
            dates = f"**Period:** {proj['start_date']}"
            if proj.get("end_date"):
                dates += f" — {proj['end_date']}"
            meta.append(dates)
        if proj.get("status"):
            meta.append(f"**Status:** {proj['status']}")
        if proj.get("total_cost"):
            budget = f"**Total cost:** {proj['total_cost']}"
            if proj.get("funded_amount"):
                budget += f" (funded: {proj['funded_amount']})"
            if proj.get("currency"):
                budget += f" {proj['currency']}"
            meta.append(budget)
        if proj.get("website_url"):
            meta.append(f"**Website:** {proj['website_url']}")
        if meta:
            lines.extend(meta)
            lines.append("")

        if proj.get("summary"):
            lines.append("## Summary")
            lines.append("")
            lines.append(proj["summary"])
            lines.append("")

        if proj.get("keywords"):
            lines.append(f"**Keywords:** {proj['keywords']}")
            lines.append("")

        if proj.get("all_participants"):
            lines.append("## Participants")
            lines.append("")
            for p in proj["all_participants"].split("; "):
                if p.strip():
                    lines.append(f"- {p.strip()}")
            lines.append("")

        if proj.get("universities"):
            lines.append(f"**UNINOVIS partners:** {proj['universities']}")
            lines.append("")

        return "\n".join(lines)


# ======================================================================
# CLI
# ======================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect funded research projects from CORDIS and OpenAIRE"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- collect ---
    p_collect = subparsers.add_parser(
        "collect", help="Search for projects and produce a CSV for review"
    )
    p_collect.add_argument("--output", "-o", default=None, help="Output directory")
    p_collect.add_argument(
        "--topics", "-t", required=True,
        help="Path to a text file with search queries (one per line)",
    )
    p_collect.add_argument(
        "--source", "-s", default="both", choices=["cordis", "openaire", "both"],
        help="Data source: cordis (EU only), openaire (EU + national), both (default)",
    )
    p_collect.add_argument(
        "--max-results", "-m", type=int, default=100,
        help="Max results per query per source (default: 100)",
    )
    p_collect.add_argument(
        "--university", "-u", default=None,
        help="Restrict to a UNINOVIS university by acronym (e.g. UMA)",
    )
    p_collect.add_argument(
        "--funder", "-f", default=None,
        help="OpenAIRE funder short name (e.g. EC, NSF, UKRI). Only for openaire source.",
    )

    # --- export ---
    p_export = subparsers.add_parser(
        "export", help="Export reviewed CSV to agent-ready JSON and markdown files"
    )
    p_export.add_argument("--output", "-o", default=None, help="Output directory")
    p_export.add_argument("--csv", default=None, help="Path to the reviewed CSV")
    p_export.add_argument(
        "--agent-dir", default=None,
        help="Agent directory to copy files into (e.g. agents/responsible_ai)",
    )

    args = parser.parse_args()

    queries = []
    if hasattr(args, "topics") and args.topics:
        queries = load_queries(args.topics)

    collector = ProjectCollector(output_dir=args.output, queries=queries)

    if args.command == "collect":
        collector.collect(
            source=args.source,
            max_per_query=args.max_results,
            only_university=args.university,
            funder=args.funder,
        )
    elif args.command == "export":
        csv_path = Path(args.csv) if args.csv else None
        collector.export(csv_path=csv_path, agent_dir=args.agent_dir)


if __name__ == "__main__":
    main()
