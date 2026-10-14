#!/usr/bin/env python3
"""
Rabanser L2 Reliability Analysis — 10Oct RAG Study
=======================================================
Metrics:
  - Consistency  C_traj  (K=5 repeated runs per query)
  - Robustness   R_prompt (accuracy + degradation std → typo/grammar/spanish)
  - Safety       L1 (wrong in-scope class) / L2 (domain-boundary error)

Evaluation sets:
  - Standard-77  : 77 queries  (baseline, clean English)
  - Typo-77      : 77 queries  (orthographic noise, L2 poor)
  - Grammar-77   : 77 queries  (grammatical noise, L2 poor)
  - Spanish-77   : 77 queries  (clean Spanish L1)

No T2/T3 — focus on L2 (noise) and L1 (Spanish) only.

Usage:
  python3.13 rabanser_l2.py                                   # all 6 agents
  python3.13 rabanser_l2.py --agents llm_A_std llm_B_std llm_C_std
  python3.13 rabanser_l2.py --agents llm_A_std --k 3          # quick test
  python3.13 rabanser_l2.py --agents llm_A_std --skip-consistency
"""

import os, re, json, time, argparse, urllib.request
from collections import Counter

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_DIR  = os.path.dirname(SCRIPT_DIR)
BENCH_DIR  = os.path.join(STUDY_DIR, "benchmark")
AGENTS_DIR = os.path.join(STUDY_DIR, "agents")
OUT_DIR    = os.path.join(SCRIPT_DIR, "rabanser_l2")
MATERIALS  = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-UniversidaddeMálaga/DatosTrabajo/Invest/"
    "LineasTrabajo/AIAgents/AIAgents_Reliability_Samuel/Paper/Version3/Materials"
)
os.makedirs(OUT_DIR, exist_ok=True)

API_KEY = "5csuTcL2eHvm98DvHzrjALMMgqJTiat3"
MODEL   = "mistral-small-latest"

ALL_AGENTS = ["llm_A_std", "llm_B_std", "llm_C_std", "llm_A", "llm_B", "llm_C"]

CATEGORIES = ["meta", "organization", "out_of_scope", "general",
              "papers", "researcher", "project", "topic", "glossary"]

IN_SCOPE   = {"meta", "organization", "papers", "researcher",
              "project", "topic", "glossary"}
# 'general' is research-but-out-of-domain; 'out_of_scope' is fully off-topic

# ── API ───────────────────────────────────────────────────────────────────────
def mistral(messages, max_tokens=200, temperature=0.0):
    payload = json.dumps({
        "model": MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
    }).encode()
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {API_KEY}"}, method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    [API ERROR attempt {attempt+1}] {e}")
            time.sleep(3 * (attempt + 1))
    return None

# ── Prompt helpers ────────────────────────────────────────────────────────────
PROMPT_RE = re.compile(r'CLASSIFY_PROMPT\s*=\s*"""(.*?)"""', re.DOTALL)

def load_prompt(agent_name):
    agent_py = os.path.join(AGENTS_DIR, agent_name, "agent.py")
    with open(agent_py, encoding="utf-8") as f:
        src = f.read()
    m = PROMPT_RE.search(src)
    if not m:
        raise ValueError(f"CLASSIFY_PROMPT not found in {agent_py}")
    return m.group(1)

def parse_json(text):
    if not text:
        return {"category": "out_of_scope"}
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        text = m.group(1).strip() if m else text
    jm = re.search(r"\{[^{}]*\}", text)
    try:
        return json.loads(jm.group() if jm else text)
    except Exception:
        return {"category": "out_of_scope"}

def classify_once(prompt_template, query):
    text = mistral([{"role": "user", "content": prompt_template.replace("{query}", query)}])
    return parse_json(text).get("category", "out_of_scope")

# ── Load evaluation sets ──────────────────────────────────────────────────────
def load_sets():
    """Return (standard_77, typo_77, grammar_77, spanish_77) — matched paired sets."""
    def load(name):
        with open(os.path.join(BENCH_DIR, name), encoding="utf-8") as f:
            return json.load(f)["queries"]

    std_q     = load("evaluation_set_standard_77.json")
    typo_q    = load("evaluation_set_typo_77.json")
    grammar_q = load("evaluation_set_grammar_77.json")
    spanish_q = load("evaluation_set_spanish_77.json")

    print(f"  Sets: Std={len(std_q)}, Typo={len(typo_q)}, Grammar={len(grammar_q)}, Spanish={len(spanish_q)}")
    return std_q, typo_q, grammar_q, spanish_q

# ── Core: run K classifications per query ─────────────────────────────────────
def run_set(prompt_template, queries, set_label, k=5):
    """
    Returns list of dicts:
      {query, expected, runs:[cat, ...], majority, consistent, correct_majority}
    """
    results = []
    n = len(queries)
    for i, entry in enumerate(queries):
        q   = entry["query"]
        exp = entry["expected"]
        runs = []
        for r in range(k):
            cat = classify_once(prompt_template, q)
            runs.append(cat)
        majority    = Counter(runs).most_common(1)[0][0]
        consistent  = (len(set(runs)) == 1)
        correct_maj = (majority == exp)
        results.append({
            "query":           q,
            "expected":        exp,
            "runs":            runs,
            "majority":        majority,
            "consistent":      consistent,
            "correct_majority": correct_maj,
        })
        tick = "." if consistent else "!"
        print(f"    [{set_label}] {i+1}/{n} {tick} {q[:45]:45s}  "
              f"exp={exp:12s} maj={majority:12s} "
              f"{'OK' if correct_maj else 'FAIL'}")
    return results

# ── Metric computations ────────────────────────────────────────────────────────
def compute_consistency(results, label):
    """C_traj = fraction of queries where all K runs agree."""
    total = len(results)
    consistent = sum(1 for r in results if r["consistent"])
    c_traj = consistent / total if total else 0.0

    by_cat = {}
    for cat in CATEGORIES:
        subset = [r for r in results if r["expected"] == cat]
        if subset:
            c = sum(1 for r in subset if r["consistent"])
            by_cat[cat] = {"consistent": c, "total": len(subset),
                           "c_traj": round(c / len(subset), 4)}
    return {
        "set": label,
        "total": total,
        "consistent": consistent,
        "c_traj": round(c_traj, 4),
        "by_category": by_cat,
    }

def compute_robustness(results, label):
    """Accuracy using majority vote per query."""
    total   = len(results)
    correct = sum(1 for r in results if r["correct_majority"])
    acc     = correct / total if total else 0.0

    by_cat = {}
    for cat in CATEGORIES:
        subset = [r for r in results if r["expected"] == cat]
        if subset:
            c = sum(1 for r in subset if r["correct_majority"])
            by_cat[cat] = {"correct": c, "total": len(subset),
                           "acc": round(c / len(subset), 4)}

    failures = [
        {"query": r["query"], "expected": r["expected"],
         "majority": r["majority"], "runs": r["runs"]}
        for r in results if not r["correct_majority"]
    ]
    return {
        "set": label,
        "total": total,
        "correct": correct,
        "accuracy": round(acc, 4),
        "by_category": by_cat,
        "failures": failures,
    }

def compute_safety(results_t1, results_typo, results_grammar, results_spanish):
    """
    L1: in-scope query misclassified into another in-scope class.
    L2: in-scope query misclassified into general/out_of_scope  (false rejection)
        OR general query misclassified into an in-scope class   (false acceptance).
    OOS_refusal: out_of_scope queries correctly refused (maj == out_of_scope).
    """
    def analyse(results, label):
        l1, l2_rejection, l2_acceptance, oos_refused = 0, 0, 0, 0
        oos_total = 0
        in_scope_total  = sum(1 for r in results if r["expected"] in IN_SCOPE)
        general_total   = sum(1 for r in results if r["expected"] == "general")

        for r in results:
            exp = r["expected"]
            maj = r["majority"]
            if exp in IN_SCOPE and not r["correct_majority"]:
                if maj in IN_SCOPE:
                    l1 += 1           # wrong in-scope class
                else:
                    l2_rejection += 1 # rejected from domain
            if exp == "general" and maj in IN_SCOPE:
                l2_acceptance += 1    # false domain acceptance
            if exp == "out_of_scope":
                oos_total += 1
                if maj == "out_of_scope":
                    oos_refused += 1

        return {
            "set": label,
            "in_scope_total": in_scope_total,
            "general_total": general_total,
            "oos_total": oos_total,
            "L1_wrong_class": l1,
            "L1_rate": round(l1 / in_scope_total, 4) if in_scope_total else 0.0,
            "L2_false_rejection": l2_rejection,
            "L2_false_rejection_rate": round(l2_rejection / in_scope_total, 4) if in_scope_total else 0.0,
            "L2_false_acceptance": l2_acceptance,
            "L2_false_acceptance_rate": round(l2_acceptance / general_total, 4) if general_total else 0.0,
            "oos_refusal_correct": oos_refused,
            "oos_refusal_rate": round(oos_refused / oos_total, 4) if oos_total else 0.0,
        }

    return {
        "standard": analyse(results_t1,      "standard"),
        "typo":     analyse(results_typo,    "typo"),
        "grammar":  analyse(results_grammar, "grammar"),
        "spanish":  analyse(results_spanish, "spanish"),
    }

# ── Print summaries ────────────────────────────────────────────────────────────
def print_consistency(c, label):
    print(f"\n  Consistency ({label}): C_traj = {c['consistent']}/{c['total']} = {c['c_traj']:.1%}")
    for cat in CATEGORIES:
        if cat in c["by_category"]:
            b = c["by_category"][cat]
            print(f"    {cat:18s}: {b['consistent']}/{b['total']} ({b['c_traj']:.0%})")

def print_robustness(r_std, r_typo, r_gram, r_es):
    print(f"\n  Robustness (R_prompt):")
    print(f"    Standard-77 (baseline): {r_std['correct']}/{r_std['total']} ({r_std['accuracy']:.1%})")
    for label, r in [("Typo    ", r_typo), ("Grammar ", r_gram), ("Spanish ", r_es)]:
        d = r['accuracy'] - r_std['accuracy']
        print(f"    {label}         : {r['correct']}/{r['total']} ({r['accuracy']:.1%})  Δ={d:+.1%}")

def print_safety(safety):
    print(f"\n  Safety:")
    print(f"    {'Metric':35s} {'Std':>7s} {'Typo':>7s} {'Grammar':>8s} {'Spanish':>8s}")
    metrics = [
        ("L1 (wrong in-scope class)",        "L1_rate"),
        ("L2 false rejection (in→out)",       "L2_false_rejection_rate"),
        ("L2 false acceptance (general→in)",  "L2_false_acceptance_rate"),
        ("OOS refusal rate",                  "oos_refusal_rate"),
    ]
    for label, key in metrics:
        vs = [safety[s][key] for s in ["standard","typo","grammar","spanish"]]
        print(f"    {label:35s}" + "".join(f" {v:>7.1%}" for v in vs))

# ── Markdown report ────────────────────────────────────────────────────────────
def build_report(all_agent_results, k):
    lines = [
        "# Rabanser L2 Reliability Analysis — 10Oct RAG Study",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M')}  |  K={k}  |  Sets: T1(116) + Typo(77) + Grammar(77)",
        "",
        "## 1. Consistency (C_traj)",
        f"C_traj = fraction of queries where all {k} runs produce the same label.",
        "",
        "| Agent | Std-77 C_traj | Typo C_traj | Grammar C_traj |",
        "|-------|-----------|-------------|----------------|",
    ]
    for ag, res in all_agent_results.items():
        ct1  = res["consistency"]["standard"]["c_traj"]
        ctyp = res["consistency"]["typo"]["c_traj"]
        cgr  = res["consistency"]["grammar"]["c_traj"]
        lines.append(f"| {ag} | {ct1:.1%} | {ctyp:.1%} | {cgr:.1%} |")

    lines += ["", "### Consistency by Category — Tier 1", ""]
    # header
    agents = list(all_agent_results.keys())
    lines.append("| Category | " + " | ".join(agents) + " |")
    lines.append("|----------|" + "|".join(["-------"] * len(agents)) + "|")
    for cat in CATEGORIES:
        row = f"| {cat} |"
        for ag in agents:
            bc = all_agent_results[ag]["consistency"]["standard"]["by_category"]
            if cat in bc:
                b = bc[cat]
                row += f" {b['consistent']}/{b['total']} ({b['c_traj']:.0%}) |"
            else:
                row += " — |"
        lines.append(row)

    lines += [
        "",
        "## 2. Robustness (R_prompt)",
        "Accuracy using majority-vote across K runs. Δ = degradation vs Standard-77 baseline.",
        "",
        "| Agent | Std-77 | Typo | Δ Typo | Grammar | Δ Grammar | Spanish | Δ Spanish |",
        "|-------|--------|------|--------|---------|-----------|---------|-----------|",
    ]
    for ag, res in all_agent_results.items():
        r1  = res["robustness"]["standard"]
        rt  = res["robustness"]["typo"]
        rg  = res["robustness"]["grammar"]
        res2 = res["robustness"]["spanish"]
        lines.append(
            f"| {ag} | {r1['accuracy']:.1%} "
            f"| {rt['accuracy']:.1%} | {rt['accuracy']-r1['accuracy']:+.1%} "
            f"| {rg['accuracy']:.1%} | {rg['accuracy']-r1['accuracy']:+.1%} "
            f"| {res2['accuracy']:.1%} | {res2['accuracy']-r1['accuracy']:+.1%} |"
        )

    lines += [
        "",
        "### Robustness by Category — Tier 1 baseline",
        "",
        "| Category | " + " | ".join(agents) + " |",
        "|----------|" + "|".join(["-------"] * len(agents)) + "|",
    ]
    for cat in CATEGORIES:
        row = f"| {cat} |"
        for ag in agents:
            bc = all_agent_results[ag]["robustness"]["standard"]["by_category"]
            if cat in bc:
                b = bc[cat]
                row += f" {b['correct']}/{b['total']} ({b['acc']:.0%}) |"
            else:
                row += " — |"
        lines.append(row)

    lines += [
        "",
        "## 3. Safety",
        "",
        "- **L1** (wrong in-scope class): in-scope query misclassified into another in-scope category.",
        "- **L2 false rejection**: in-scope query classified as `general` or `out_of_scope`.",
        "- **L2 false acceptance**: `general` query classified as an in-scope category.",
        "- **OOS refusal rate**: `out_of_scope` queries correctly classified.",
        "",
        "| Agent | Set | L1 rate | L2 reject | L2 accept | OOS refusal |",
        "|-------|-----|---------|-----------|-----------|-------------|",
    ]
    for ag, res in all_agent_results.items():
        for s_label in ["standard", "typo", "grammar", "spanish"]:
            s = res["safety"][s_label]
            lines.append(
                f"| {ag} | {s_label} "
                f"| {s['L1_rate']:.1%} "
                f"| {s['L2_false_rejection_rate']:.1%} "
                f"| {s['L2_false_acceptance_rate']:.1%} "
                f"| {s['oos_refusal_rate']:.1%} |"
            )

    lines += [
        "",
        "## 4. Impact of L2 Noise — Summary",
        "",
        "Mean across agents:",
        "",
        "| Metric | Std-77 | Typo | Grammar | Spanish | Δ Typo | Δ Grammar | Δ Spanish |",
        "|--------|--------|------|---------|---------|--------|-----------|-----------|",
    ]
    def avg(key, subkey, agents, all_res):
        vals = [all_res[ag][key][subkey] for ag in agents]
        return sum(v["accuracy"] if isinstance(v, dict) and "accuracy" in v else v
                   for v in vals) / len(vals)

    # robustness accuracy averages
    names = list(all_agent_results.keys())
    def means(vals_dict):
        return {k: sum(v)/len(v) for k, v in vals_dict.items()}

    for label, key, subkey in [
        ("Robustness accuracy", "robustness", "accuracy"),
        ("C_traj consistency",  "consistency", "c_traj"),
    ]:
        ms = means({s: [all_agent_results[ag][key][s][subkey] for ag in names]
                    for s in ["standard","typo","grammar","spanish"]})
        lines.append(
            f"| {label} | {ms['standard']:.1%} | {ms['typo']:.1%} | {ms['grammar']:.1%} | {ms['spanish']:.1%} "
            f"| {ms['typo']-ms['standard']:+.1%} | {ms['grammar']-ms['standard']:+.1%} | {ms['spanish']-ms['standard']:+.1%} |"
        )
    for safety_label, safety_key in [
        ("L1 rate",            "L1_rate"),
        ("L2 rejection rate",  "L2_false_rejection_rate"),
        ("L2 acceptance rate", "L2_false_acceptance_rate"),
        ("OOS refusal rate",   "oos_refusal_rate"),
    ]:
        ms = means({s: [all_agent_results[ag]["safety"][s][safety_key] for ag in names]
                    for s in ["standard","typo","grammar","spanish"]})
        lines.append(
            f"| {safety_label} | {ms['standard']:.1%} | {ms['typo']:.1%} | {ms['grammar']:.1%} | {ms['spanish']:.1%} "
            f"| {ms['typo']-ms['standard']:+.1%} | {ms['grammar']-ms['standard']:+.1%} | {ms['spanish']-ms['standard']:+.1%} |"
        )

    return "\n".join(lines)

# ── Per-agent analysis ─────────────────────────────────────────────────────────
def analyse_agent(agent_name, tier1, typo_q, grammar_q, spanish_q, k, skip_consistency):
    prompt = load_prompt(agent_name)
    print(f"\n{'='*65}")
    print(f"  Agent: {agent_name}  |  K={k}  |  skip_consistency={skip_consistency}")
    print(f"{'='*65}")

    effective_k = 1 if skip_consistency else k

    print(f"\n  [1/4] Standard-77 ({len(tier1)} queries) ...")
    res_t1 = run_set(prompt, tier1, "Std77", k=effective_k)

    print(f"\n  [2/4] Typo-77 ({len(typo_q)} queries) ...")
    res_typo = run_set(prompt, typo_q, "Typo", k=effective_k)

    print(f"\n  [3/4] Grammar-77 ({len(grammar_q)} queries) ...")
    res_grammar = run_set(prompt, grammar_q, "Grammar", k=effective_k)

    print(f"\n  [4/4] Spanish-77 ({len(spanish_q)} queries) ...")
    res_spanish = run_set(prompt, spanish_q, "ES", k=effective_k)

    # Metrics
    cons = {
        "standard": compute_consistency(res_t1,      "standard"),
        "typo":     compute_consistency(res_typo,    "typo"),
        "grammar":  compute_consistency(res_grammar, "grammar"),
        "spanish":  compute_consistency(res_spanish, "spanish"),
    }
    rob = {
        "standard": compute_robustness(res_t1,      "standard"),
        "typo":     compute_robustness(res_typo,    "typo"),
        "grammar":  compute_robustness(res_grammar, "grammar"),
        "spanish":  compute_robustness(res_spanish, "spanish"),
    }
    safety = compute_safety(res_t1, res_typo, res_grammar, res_spanish)

    print_consistency(cons["standard"], "Standard-77")
    print_consistency(cons["typo"],     "Typo-77")
    print_consistency(cons["grammar"],  "Grammar-77")
    print_consistency(cons["spanish"],  "Spanish-77")
    print_robustness(rob["standard"], rob["typo"], rob["grammar"], rob["spanish"])
    print_safety(safety)

    return {
        "agent": agent_name,
        "k": effective_k,
        "consistency": cons,
        "robustness": rob,
        "safety": safety,
        "raw_t1": res_t1,
        "raw_typo": res_typo,
        "raw_grammar": res_grammar,
        "raw_spanish": res_spanish,
    }

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", nargs="+", default=ALL_AGENTS)
    parser.add_argument("--k", type=int, default=5, help="Repetitions per query for consistency")
    parser.add_argument("--skip-consistency", action="store_true",
                        help="Use K=1 (fast mode) — robustness and safety only")
    args = parser.parse_args()

    tier1, typo_q, grammar_q, spanish_q = load_sets()

    all_results = {}
    for agent_name in args.agents:
        agent_py = os.path.join(AGENTS_DIR, agent_name, "agent.py")
        if not os.path.isfile(agent_py):
            print(f"  [SKIP] {agent_name} — agent.py not found")
            continue
        res = analyse_agent(agent_name, tier1, typo_q, grammar_q, spanish_q,
                            k=args.k, skip_consistency=args.skip_consistency)
        all_results[agent_name] = res

    if not all_results:
        print("No agents evaluated. Exiting.")
        return

    # Save JSON (without raw data to keep size manageable)
    ts = time.strftime("%Y%m%d_%H%M%S")
    compact = {
        ag: {
            "agent": res["agent"],
            "k": res["k"],
            "consistency": res["consistency"],
            "robustness": {s: {k2: v for k2, v in d.items() if k2 != "failures"}
                           for s, d in res["robustness"].items()},
            "safety": res["safety"],
        }
        for ag, res in all_results.items()
    }
    json_path = os.path.join(OUT_DIR, f"rabanser_l2_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(compact, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON saved: {json_path}")

    # Save full raw JSON (for debugging failures)
    raw_path = os.path.join(OUT_DIR, f"rabanser_l2_raw_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"  Raw JSON saved: {raw_path}")

    # Markdown report
    report = build_report(all_results, k=args.k)
    rpt_path = os.path.join(OUT_DIR, f"rabanser_l2_{ts}.md")
    with open(rpt_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Report saved: {rpt_path}")

    if os.path.isdir(MATERIALS):
        mat_path = os.path.join(MATERIALS, f"rabanser_l2_10Oct_{ts}.md")
        with open(mat_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  Report also saved: {mat_path}")

    print("\nDone.")

if __name__ == "__main__":
    main()
