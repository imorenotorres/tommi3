#!/usr/bin/env python3
"""
Compute RAG similarity scores for a list of queries.

Usage:
    python similarity_test.py queries.txt
    python similarity_test.py queries.txt -o results.tsv
    python similarity_test.py queries.txt --threshold 0.5

Input file: one query per line (blank lines and lines starting with # are skipped).
Output: TSV with columns: similarity, status, query

Example input (queries.txt):
    List papers from THUAS
    What are the findings about bias?
    Any study about Donald Duck?
    Tell me about the weather

Example output:
    similarity	status	query
    0.62	Good	List papers from THUAS
    0.55	Good	What are the findings about bias?
    0.41	Poor	Any study about Donald Duck?
    0.38	Poor	Tell me about the weather
"""

import argparse
import json
import os
import sys
import warnings

# Suppress noisy warnings from dependencies
warnings.filterwarnings("ignore", message=".*position_ids.*")

def main():
    parser = argparse.ArgumentParser(
        description="Compute RAG similarity scores for a list of queries"
    )
    parser.add_argument("input", help="Text file with one query per line")
    parser.add_argument("-o", "--output", default=None,
                        help="Output file (default: print to stdout)")
    parser.add_argument("-t", "--threshold", type=float, default=None,
                        help="Similarity threshold (default: from config.json)")
    parser.add_argument("-n", "--n-results", type=int, default=3,
                        help="Number of ChromaDB results to retrieve (default: 3)")
    args = parser.parse_args()

    # Read queries
    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        queries = [
            line.strip() for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    if not queries:
        print("Error: no queries found in input file", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(queries)} queries from {args.input}", file=sys.stderr)

    # Initialize ChromaDB (same setup as the agent)
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(agent_dir, "data")
    db_path = os.path.join(data_dir, "chroma_db")

    # Load threshold from config if not specified
    config_path = os.path.join(agent_dir, "config.json")
    threshold = args.threshold
    domain_keywords = []
    boost_per_kw = 0.03
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if threshold is None:
            threshold = config.get("rag_similarity_threshold", 0.5)
        domain_keywords = config.get("rag_domain_keywords", [])
        boost_per_kw = config.get("rag_keyword_boost", 0.03)
    except Exception:
        if threshold is None:
            threshold = 0.5

    print(f"Similarity threshold: {threshold}", file=sys.stderr)
    print(f"Loading ChromaDB from {db_path}...", file=sys.stderr)

    try:
        import chromadb
        from chromadb.utils import embedding_functions

        client = chromadb.PersistentClient(path=db_path)
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.get_collection(
            name="documents",
            embedding_function=embedding_fn
        )
        doc_count = collection.count()
        print(f"ChromaDB ready: {doc_count} chunks indexed", file=sys.stderr)
    except Exception as e:
        print(f"Error initializing ChromaDB: {e}", file=sys.stderr)
        print("Make sure you run this from the agent directory with Python 3.12-3.13", file=sys.stderr)
        sys.exit(1)

    # Process queries
    results = []
    for i, query in enumerate(queries, 1):
        try:
            res = collection.query(
                query_texts=[query],
                n_results=args.n_results,
                include=["distances"],
            )
            distances = res.get("distances", [[]])[0]
            avg_raw = sum(distances) / len(distances) if distances else 2.0
            similarity = avg_raw / -2.0 + 1.0
            # Boost for domain keywords
            query_lower = query.lower()
            n_matches = sum(1 for kw in domain_keywords if kw in query_lower)
            similarity = min(similarity + boost_per_kw * n_matches, 1.0)
            similarity = round(similarity, 2)
        except Exception as e:
            print(f"  Error on query {i}: {e}", file=sys.stderr)
            similarity = 0.0

        status = "Good" if similarity >= threshold else "Poor"
        results.append((similarity, status, query))

        print(f"  [{i}/{len(queries)}] {similarity}\t{status}\t{query}", file=sys.stderr)

    # Output
    lines = ["similarity\tstatus\tquery"]
    for sim, status, query in results:
        lines.append(f"{sim}\t{status}\t{query}")

    output_text = "\n".join(lines) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"\nResults saved to {args.output}", file=sys.stderr)
    else:
        print()
        print(output_text)

    # Summary
    good = sum(1 for s, _, _ in results if s >= threshold)
    poor = len(results) - good
    avg_sim = sum(s for s, _, _ in results) / len(results) if results else 0
    print(f"\nSummary: {len(results)} queries, {good} Good, {poor} Poor, avg similarity: {avg_sim:.2f}", file=sys.stderr)


if __name__ == "__main__":
    main()
