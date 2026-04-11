#!/usr/bin/env python3
"""Enrich project markdown files with UNINOVIS researchers and project website URLs.

Strategy:
1. Load known UNINOVIS researchers from researchers.json
2. For each project, query OpenAIRE for linked publications
3. Match publication authors against UNINOVIS researchers
4. Scrape CORDIS project page for the project website URL
5. Update the project .md files with the new information

Usage:
    python enrich_projects.py [--dry-run] [--grant-id GRANT_ID]

Rate limits:
    - OpenAIRE unauthenticated: 60 requests/hour
    - CORDIS: no documented limits, but we add delays to be polite
"""

import os
import re
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
PROJECT_DOCS_DIR = os.path.join(DATA_DIR, "project_docs")
RESEARCHERS_PATH = os.path.join(DATA_DIR, "researchers.json")

OPENAIRE_PUB_URL = "https://api.openaire.eu/search/publications?projectID={grant_id}&funder=EC&format=json&size=200"
CORDIS_PROJECT_URL = "https://cordis.europa.eu/project/id/{grant_id}"

# Delay between API requests (seconds)
OPENAIRE_DELAY = 2.0
CORDIS_DELAY = 1.5


def load_uninovis_researchers():
    """Load all UNINOVIS researchers, indexed by normalized name for matching."""
    with open(RESEARCHERS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build lookup: normalized_name -> (original_name, university_acronym)
    lookup = {}
    for acronym, researchers in data.items():
        for r in researchers:
            name = r["name"]
            normalized = normalize_name(name)
            lookup[normalized] = (name, acronym)
            # Also add last-name-first variant
            parts = name.split()
            if len(parts) >= 2:
                # "First Last" -> also index "Last, First" and "Last First"
                last_first = f"{parts[-1]} {' '.join(parts[:-1])}"
                lookup[normalize_name(last_first)] = (name, acronym)
    return lookup


def normalize_name(name):
    """Normalize a name for fuzzy matching."""
    # Remove accents (simple approach), lowercase, strip punctuation
    import unicodedata
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().strip()
    name = re.sub(r"[^a-z\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def fetch_json(url, timeout=30):
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "UNINOVIS-ProjectEnricher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"  Warning: Failed to fetch {url}: {e}")
        return None


def fetch_html(url, timeout=30):
    """Fetch HTML from a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "UNINOVIS-ProjectEnricher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"  Warning: Failed to fetch {url}: {e}")
        return None


def get_openaire_authors(grant_id):
    """Get all unique author names from publications linked to a grant ID via OpenAIRE."""
    url = OPENAIRE_PUB_URL.format(grant_id=grant_id)
    data = fetch_json(url)
    if not data:
        return []

    authors = set()
    results_container = data.get("response", {}).get("results")
    if not results_container or not isinstance(results_container, dict):
        return []
    results = results_container.get("result", [])
    if not results:
        return []
    if not isinstance(results, list):
        results = [results]

    for r in results:
        meta = r.get("metadata", {}).get("oaf:entity", {}).get("oaf:result", {})
        creators = meta.get("creator", [])
        if isinstance(creators, dict):
            creators = [creators]
        for c in creators:
            name = c.get("$", c.get("content", "")) if isinstance(c, dict) else str(c)
            if name:
                authors.add(name)

    return list(authors)


def get_cordis_website(grant_id):
    """Scrape the CORDIS project page for the project website URL."""
    url = CORDIS_PROJECT_URL.format(grant_id=grant_id)
    html = fetch_html(url)
    if not html:
        return None

    # Look for the project website link
    match = re.search(r'data-url="(https?://[^"]+)"[^>]*>\s*Project website', html)
    if match:
        return match.group(1)

    # Alternative pattern
    match = re.search(r'class="[^"]*weblink[^"]*"[^>]*data-url="(https?://[^"]+)"', html)
    if match:
        return match.group(1)

    return None


def author_name_variants(raw_name):
    """Generate normalized name variants from an author string.

    Handles formats like:
    - "First Last"
    - "Last, First"
    - "Last, F."
    - "Last, First; Second, Author" (multi-author strings)
    """
    variants = set()
    # Split multi-author strings (semicolons, ampersands)
    parts_list = re.split(r"[;&]", raw_name)
    for part in parts_list:
        part = part.strip()
        if not part:
            continue
        normalized = normalize_name(part)
        if len(normalized) < 3:
            continue
        variants.add(normalized)
        # If "Last, First" format, also generate "First Last"
        if "," in part:
            comma_parts = part.split(",", 1)
            last = comma_parts[0].strip()
            first = comma_parts[1].strip()
            if first and last:
                variants.add(normalize_name(f"{first} {last}"))
        else:
            # "First Last" -> also try "Last First"
            words = normalized.split()
            if len(words) >= 2:
                variants.add(f"{words[-1]} {' '.join(words[:-1])}")
    return variants


def match_uninovis_researchers(author_names, researcher_lookup, project_partners):
    """Match a list of author names against UNINOVIS researchers.

    Only returns researchers from universities that are UNINOVIS partners in this project.
    Uses exact normalized name matching with multiple format variants.
    Returns list of (researcher_name, university_acronym).
    """
    matched = []
    seen = set()

    for author in author_names:
        for variant in author_name_variants(author):
            if variant in researcher_lookup:
                name, acronym = researcher_lookup[variant]
                if acronym in project_partners and name not in seen:
                    seen.add(name)
                    matched.append((name, acronym))
                break

    return sorted(matched, key=lambda x: (x[1], x[0]))


def parse_grant_id(filename):
    """Extract grant ID from filename like '101004130_CoRob-X.md'."""
    match = re.match(r"(\d+|NWA[.\d]+)", filename)
    return match.group(1) if match else None


def parse_project_md(filepath):
    """Parse a project .md file and return its content and metadata."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    grant_match = re.search(r"\*\*Grant ID:\*\*\s*(.+)", content)
    grant_id = grant_match.group(1).strip() if grant_match else None

    partners_match = re.search(r"\*\*UNINOVIS partners:\*\*\s*(.+)", content)
    partners = [p.strip() for p in partners_match.group(1).split(",")] if partners_match else []

    return content, grant_id, partners


def update_project_md(filepath, content, uninovis_researchers, website_url):
    """Update a project .md file with UNINOVIS researchers and website URL."""
    new_content = content

    # Add website URL after the Period/Status/Total cost block if not already present
    if website_url and "**Website:**" not in content:
        # Insert after Total cost line (or Status if no Total cost)
        for anchor in [r"(\*\*Total cost:\*\*[^\n]*\n)", r"(\*\*Status:\*\*[^\n]*\n)"]:
            match = re.search(anchor, content)
            if match:
                insert_pos = match.end()
                new_content = new_content[:insert_pos] + f"**Website:** {website_url}\n" + new_content[insert_pos:]
                break

    # Add/update UNINOVIS researchers section
    if uninovis_researchers:
        researchers_text = "\n## UNINOVIS Researchers\n\n"
        by_uni = defaultdict(list)
        for name, acronym in uninovis_researchers:
            by_uni[acronym].append(name)
        for acronym in sorted(by_uni.keys()):
            names = sorted(by_uni[acronym])
            researchers_text += f"**{acronym}:** {', '.join(names)}\n"

        # Replace existing section or add before UNINOVIS partners line
        existing = re.search(r"\n## UNINOVIS Researchers\n.*?(?=\n\*\*UNINOVIS partners|\Z)", new_content, re.DOTALL)
        if existing:
            new_content = new_content[:existing.start()] + researchers_text + new_content[existing.end():]
        else:
            # Insert before **UNINOVIS partners:** line
            partners_pos = new_content.find("**UNINOVIS partners:**")
            if partners_pos > 0:
                new_content = new_content[:partners_pos] + researchers_text + "\n" + new_content[partners_pos:]

    return new_content


def main():
    parser = argparse.ArgumentParser(description="Enrich project docs with UNINOVIS researchers and website URLs")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files")
    parser.add_argument("--grant-id", type=str, help="Only process a specific grant ID")
    parser.add_argument("--skip-openaire", action="store_true", help="Skip OpenAIRE API calls (only fetch CORDIS website)")
    args = parser.parse_args()

    print("Loading UNINOVIS researchers...")
    researcher_lookup = load_uninovis_researchers()
    print(f"  {len(researcher_lookup)} name variants indexed")

    md_files = sorted(f for f in os.listdir(PROJECT_DOCS_DIR) if f.endswith(".md"))
    print(f"Found {len(md_files)} project files\n")

    stats = {"processed": 0, "researchers_found": 0, "websites_found": 0, "updated": 0}

    for filename in md_files:
        filepath = os.path.join(PROJECT_DOCS_DIR, filename)
        content, grant_id, partners = parse_project_md(filepath)

        if not grant_id:
            print(f"  Skipping {filename}: no grant ID found")
            continue

        if args.grant_id and grant_id != args.grant_id:
            continue

        print(f"Processing {filename} (Grant: {grant_id}, Partners: {', '.join(partners)})...")
        stats["processed"] += 1

        # 1. Find UNINOVIS researchers via OpenAIRE publications
        uninovis_researchers = []
        if not args.skip_openaire:
            print(f"  Querying OpenAIRE for publications...")
            time.sleep(OPENAIRE_DELAY)
            authors = get_openaire_authors(grant_id)
            print(f"  Found {len(authors)} unique authors across publications")

            if authors:
                uninovis_researchers = match_uninovis_researchers(authors, researcher_lookup, set(partners))
                if uninovis_researchers:
                    print(f"  Matched {len(uninovis_researchers)} UNINOVIS researchers:")
                    for name, acr in uninovis_researchers:
                        print(f"    - {name} ({acr})")
                    stats["researchers_found"] += len(uninovis_researchers)
                else:
                    print(f"  No UNINOVIS researchers matched")

        # 2. Get project website from CORDIS
        website_url = None
        if "**Website:**" not in content:
            print(f"  Fetching CORDIS project page for website URL...")
            time.sleep(CORDIS_DELAY)
            website_url = get_cordis_website(grant_id)
            if website_url:
                print(f"  Website: {website_url}")
                stats["websites_found"] += 1
            else:
                # Fallback: use CORDIS project page as the link
                if grant_id and not grant_id.startswith("NWA"):
                    website_url = f"https://cordis.europa.eu/project/id/{grant_id}"
                    print(f"  No project website found — using CORDIS page: {website_url}")
                    stats["websites_found"] += 1
                else:
                    print(f"  No project website found on CORDIS")
        else:
            print(f"  Website already present, skipping CORDIS fetch")

        # 3. Update the file
        if uninovis_researchers or website_url:
            new_content = update_project_md(filepath, content, uninovis_researchers, website_url)
            if new_content != content:
                if args.dry_run:
                    print(f"  [DRY RUN] Would update {filename}")
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"  Updated {filename}")
                stats["updated"] += 1

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Projects processed: {stats['processed']}")
    print(f"  UNINOVIS researchers found: {stats['researchers_found']}")
    print(f"  Project websites found: {stats['websites_found']}")
    print(f"  Files {'that would be ' if args.dry_run else ''}updated: {stats['updated']}")
    if not args.dry_run and stats["updated"] > 0:
        print(f"\nProject .md files have been updated. Restart the agent to pick up changes.")


if __name__ == "__main__":
    main()
