#!/usr/bin/env python3
"""
Typo Robustness Study — 3 approaches tested on llm_A_std
Base agent: llm_A_std (74.0% on typo set, baseline)

Approach 1 — Explicit noise instruction in prompt
Approach 2 — Preprocessing: LLM spell-correction before classification
Approach 3 — Few-shot examples of typo queries in prompt

Evaluation: evaluation_set_typo.json (77 queries) only.
python3.13 typo_robustness.py
"""

import os, re, json, time, urllib.request
from collections import Counter

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
STUDY_DIR   = os.path.dirname(SCRIPT_DIR)
BENCH_DIR   = os.path.join(STUDY_DIR, "benchmark")
AGENT_PY    = os.path.join(STUDY_DIR, "agents", "llm_A_std", "agent.py")
OUT_DIR     = os.path.join(SCRIPT_DIR, "typo_robustness")
MATERIALS   = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-UniversidaddeMálaga/DatosTrabajo/Invest/"
    "LineasTrabajo/AIAgents/AIAgents_Reliability_Samuel/Paper/Version3/Materials"
)
os.makedirs(OUT_DIR, exist_ok=True)

API_KEY = "5csuTcL2eHvm98DvHzrjALMMgqJTiat3"
MODEL   = "mistral-small-latest"

CATEGORIES = ["meta","organization","out_of_scope","general",
               "papers","researcher","project","topic","glossary"]

# ── Mistral helper ────────────────────────────────────────────────────────────
def mistral(messages, max_tokens=200, temperature=0.0):
    payload = json.dumps({
        "model": MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
    }).encode()
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {API_KEY}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  [API ERROR] {e}"); time.sleep(3); return None

# ── Load base prompt ──────────────────────────────────────────────────────────
PROMPT_RE = re.compile(r'CLASSIFY_PROMPT\s*=\s*"""(.*?)"""', re.DOTALL)

def load_base_prompt():
    with open(AGENT_PY, encoding="utf-8") as f:
        src = f.read()
    m = PROMPT_RE.search(src)
    if not m: raise ValueError("CLASSIFY_PROMPT not found")
    return m.group(1)

BASE_PROMPT = load_base_prompt()

# ── Approach 1 — Explicit noise instruction ───────────────────────────────────
PROMPT_V1 = BASE_PROMPT.replace(
    "DISAMBIGUATION NOTES:",
    """NOISE HANDLING:
- The query may contain spelling errors (e.g., "reserch", "lerning", "abaut", "peipers") \
or grammatical interference from Spanish L1 speakers.
- Focus on the apparent INTENT of the query, not its exact wording.
- Queries about non-Responsible-AI topics (even with typos) → "general", NOT "glossary".
- "machin lerning", "deep lerning", "imig recognition", "kuantun computing" → category "general".
- Queries mentioning fairness, explainability, bias, ethics (even misspelled) → "topic" or "glossary".

DISAMBIGUATION NOTES:"""
)

# ── Approach 2 — Preprocessing: spell correction ─────────────────────────────
CORRECT_PROMPT = """Fix ONLY spelling errors in this query. Do not rephrase or add words.
Return ONLY the corrected query, nothing else. If there are no errors, return it as-is.

QUERY: {query}"""

def preprocess(query):
    corrected = mistral(
        [{"role": "user", "content": CORRECT_PROMPT.format(query=query)}],
        max_tokens=100, temperature=0.0
    )
    return corrected.strip() if corrected else query

# ── Approach 3 — Few-shot examples from dev typo set ─────────────────────────
FEW_SHOT_BLOCK = """
EXAMPLES (queries may contain spelling errors — classify by intent):
Q: "What are your capabilitis?" → {"category": "meta", "topic": "", "researcher": "", "university": "", "project": "", "output_format": "text"}
Q: "What is machin learning?" → {"category": "general", "topic": "", "researcher": "", "university": "", "project": "", "output_format": "text"}
Q: "Papers on deep lerning for imig recognition" → {"category": "general", "topic": "", "researcher": "", "university": "", "project": "", "output_format": "text"}
Q: "Reserch on machine lerning fearness" → {"category": "topic", "topic": "AI fairness", "researcher": "", "university": "", "project": "", "output_format": "text"}
Q: "What is explanable IA?" → {"category": "glossary", "topic": "explainability", "researcher": "", "university": "", "project": "", "output_format": "text"}
Q: "List all papers from THUAS reserchers" → {"category": "papers", "topic": "", "researcher": "", "university": "THUAS", "project": "", "output_format": "text"}
Q: "Who are the main reserchers at UMA?" → {"category": "researcher", "topic": "", "researcher": "", "university": "UMA", "project": "", "output_format": "text"}
Q: "Tell me abaut de IntelliMan proyect" → {"category": "project", "topic": "", "researcher": "", "university": "", "project": "IntelliMan", "output_format": "text"}
Q: "Write me an esay about AI" → {"category": "out_of_scope", "topic": "", "researcher": "", "university": "", "project": "", "output_format": "text"}
Q: "Which universitis belon to UNINOVIS?" → {"category": "organization", "topic": "", "researcher": "", "university": "", "project": "", "output_format": "text"}

"""

PROMPT_V3 = BASE_PROMPT.replace(
    "Respond with ONLY a JSON object:",
    FEW_SHOT_BLOCK + "Respond with ONLY a JSON object:"
)

# ── Parse JSON from LLM response ──────────────────────────────────────────────
def parse_json(text):
    if not text: return {"category": "out_of_scope"}
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        text = m.group(1).strip() if m else text
    jm = re.search(r"\{[^{}]*\}", text)
    try: return json.loads(jm.group() if jm else text)
    except: return {"category": "out_of_scope"}

# ── Classify functions per approach ──────────────────────────────────────────
def classify_v0(query):  # baseline
    text = mistral([{"role":"user","content": BASE_PROMPT.replace("{query}", query)}])
    return parse_json(text)

def classify_v1(query):  # explicit instruction
    text = mistral([{"role":"user","content": PROMPT_V1.replace("{query}", query)}])
    return parse_json(text)

def classify_v2(query):  # preprocessing
    clean = preprocess(query)
    text  = mistral([{"role":"user","content": BASE_PROMPT.replace("{query}", clean)}])
    result = parse_json(text)
    result["_preprocessed"] = clean
    return result

def classify_v3(query):  # few-shot
    text = mistral([{"role":"user","content": PROMPT_V3.replace("{query}", query)}])
    return parse_json(text)

# ── Evaluate one approach ─────────────────────────────────────────────────────
def evaluate(classify_fn, queries, label):
    print(f"\n  --- {label} ---")
    correct, failures = 0, []
    by_cat = Counter(q["expected"] for q in queries)
    ok_cat = Counter()
    for entry in queries:
        res = classify_fn(entry["query"])
        cat = res.get("category", "out_of_scope")
        if cat == entry["expected"]:
            correct += 1
            ok_cat[cat] += 1
        else:
            failures.append({
                "query": entry["query"],
                "expected": entry["expected"],
                "got": cat,
                "extra": res.get("_preprocessed", ""),
            })
            print(f"    [!!] {entry['query'][:55]:55s}  {entry['expected']} → {cat}")
    total = len(queries)
    print(f"  Accuracy: {correct}/{total} ({correct/total:.1%})")
    print(f"  Per-category:")
    for cat in CATEGORIES:
        t = by_cat.get(cat,0)
        c = ok_cat.get(cat,0)
        if t: print(f"    {cat:18s}: {c}/{t} ({c/t:.0%})")
    return {
        "label": label, "total": total, "correct": correct,
        "rate": round(correct/total, 4),
        "by_category": dict(by_cat),
        "correct_by_category": dict(ok_cat),
        "failures": failures,
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    with open(os.path.join(BENCH_DIR, "evaluation_set_typo.json"), encoding="utf-8") as f:
        typo_qs = json.load(f)["queries"]

    print(f"\n{'='*70}")
    print(f"  Typo Robustness Study — base: llm_A_std")
    print(f"  Evaluation set: {len(typo_qs)} typo queries")
    print(f"{'='*70}")

    # Baseline already known: llm_A_std = 57/77 (74.0%)
    BASELINE = {"label": "Baseline (llm_A_std)", "total": 77, "correct": 57,
                "rate": 0.7403,
                "by_category": {"meta":6,"organization":5,"out_of_scope":8,"general":8,
                                 "papers":10,"researcher":10,"project":10,"topic":10,"glossary":10},
                "correct_by_category": {"meta":5,"organization":4,"out_of_scope":7,"general":3,
                                        "papers":6,"researcher":10,"project":7,"topic":5,"glossary":10},
                "failures": []}

    approaches = [
        ("V1 — Explicit noise instruction", classify_v1),
        ("V2 — Preprocessing (spell corr)", classify_v2),
        ("V3 — Few-shot examples",          classify_v3),
    ]

    all_results = {"Baseline (llm_A_std)": BASELINE}
    for label, fn in approaches:
        r = evaluate(fn, typo_qs, label)
        all_results[label] = r

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  SUMMARY — Typo Set (77 queries)")
    print(f"{'='*70}")
    print(f"  {'Approach':40s} Accuracy   Δ vs baseline")
    baseline_rate = all_results["Baseline (llm_A_std)"]["rate"]
    for label, r in all_results.items():
        delta = r["rate"] - baseline_rate
        delta_str = f"{delta:+.1%}" if delta != 0 else "—"
        print(f"  {label:40s} {r['correct']}/{r['total']} ({r['rate']:.1%})   {delta_str}")

    print(f"\n  Per-category breakdown:")
    header = f"  {'Category':18s}" + "".join(f" {k[:8]:>8s}" for k in all_results)
    print(header)
    for cat in CATEGORIES:
        row = f"  {cat:18s}"
        for r in all_results.values():
            t = r["by_category"].get(cat,0)
            c = r["correct_by_category"].get(cat,0)
            row += f" {c}/{t}({c/t:.0%})" if t else "   —   "
        print(row)

    # ── Save results ──────────────────────────────────────────────────────────
    ts = time.strftime("%Y%m%d_%H%M%S")
    result_path = os.path.join(OUT_DIR, f"typo_robustness_{ts}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved: {result_path}")

    # Build markdown report
    lines = [
        "# Typo Robustness — 3 Approaches",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M')}  |  Base: llm_A_std  |  Set: evaluation_set_typo.json (77 q)",
        "",
        "## Approaches",
        "- **Baseline**: llm_A_std — 57/77 (74.0%), from prior evaluation (not re-run)",
        "- **V1 — Explicit instruction**: noise-handling note added to prompt",
        "- **V2 — Preprocessing**: LLM spell-correction before classification (2 API calls/query)",
        "- **V3 — Few-shot**: 10 typo examples (1 per category) from dev set added to prompt",
        "",
        "## Overall Accuracy",
        "| Approach | Correct/Total | Accuracy | Δ baseline |",
        "|----------|--------------|----------|------------|",
    ]
    for label, r in all_results.items():
        delta = r["rate"] - baseline_rate
        ds = f"{delta:+.1%}" if delta != 0 else "—"
        lines.append(f"| {label} | {r['correct']}/{r['total']} | {r['rate']:.1%} | {ds} |")

    lines += ["", "## Per-category Accuracy",
              "| Category | Baseline | V1 Explicit | V2 Preprocess | V3 Few-shot |",
              "|----------|---------|-------------|---------------|-------------|"]
    for cat in CATEGORIES:
        row = f"| {cat} |"
        for r in all_results.values():
            t = r["by_category"].get(cat,0)
            c = r["correct_by_category"].get(cat,0)
            row += f" {c}/{t} ({c/t:.0%}) |" if t else " — |"
        lines.append(row)

    lines += ["", "## Failures per Approach", ""]
    for label, r in all_results.items():
        lines.append(f"### {label} ({len(r['failures'])} failures)")
        for f2 in r["failures"]:
            pre = f" [corrected: '{f2['extra']}']" if f2.get("extra") else ""
            lines.append(f"- `{f2['query']}`{pre}  →  expected **{f2['expected']}**, got **{f2['got']}**")
        lines.append("")

    report = "\n".join(lines)
    rpt_path = os.path.join(OUT_DIR, f"typo_robustness_{ts}.md")
    with open(rpt_path, "w", encoding="utf-8") as f: f.write(report)
    print(f"  Report saved: {rpt_path}")

    if os.path.isdir(MATERIALS):
        mat_path = os.path.join(MATERIALS, f"typo_robustness_10Oct_{ts}.md")
        with open(mat_path, "w", encoding="utf-8") as f: f.write(report)
        print(f"  Report also saved: {mat_path}")

if __name__ == "__main__":
    main()
