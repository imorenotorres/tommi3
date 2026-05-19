#!/bin/bash
# Text Style Benchmark (20 questions x 4 conditions = 80 API calls)

SERVER="http://localhost:8000"
AGENT="responsible_ai3"
CONFIG="/Users/ignaciomoreno-torres/tommi3/agents/responsible_ai3/config.json"
RESULTS_DIR="/Users/ignaciomoreno-torres/tommi3/agents/responsible_ai3/benchmark_results20"

# Login to get fresh token
TOKEN=$(curl -s -X POST "$SERVER/api/auth/login" -H "Content-Type: application/json" \
  -d '{"username":"imts1965@gmail.com","password":"Sol191712@"}' | \
  /usr/bin/python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
echo "Token: ${TOKEN:0:20}..."

mkdir -p "$RESULTS_DIR"

# 20 questions across 7 categories
# Each triggers yellow or red banners (AI-generated content)
QUESTIONS=(
  # Conceptual (yellow) — general knowledge, not from DB
  "What is Responsible AI?"
  "What is explainable artificial intelligence?"
  "What is the difference between AI ethics and AI governance?"
  # Gap analysis (red) — reasoning about absence
  "List any topics related with responsible AI that have not been studied"
  "Are there any gaps in UNINOVIS research on AI fairness?"
  "Which responsible AI subtopics are missing from the UNINOVIS database?"
  # Researcher lookup (yellow) — DB data + AI interpretation
  "What do you know of Enrique Alba"
  "Tell me about Liliya Terzieva"
  # Topic search with commentary (green+yellow)
  "List researchers that have interest in AI and Ethics"
  "What research exists on explainable artificial intelligence?"
  "List researchers interested in Bias and Fairness"
  "What papers discuss trustworthy AI and accountability?"
  # Cross-university interpretation (yellow)
  "Which UNINOVIS partners have published on Explainable AI?"
  "Are there collaborations between UMA and UT on AI ethics?"
  # Interpretation / opinion (yellow)
  "What are the main challenges for trustworthy AI in healthcare?"
  "How does UNINOVIS research compare across universities?"
  "What trends do you see in UNINOVIS responsible AI research?"
  # Off-topic / scope boundary (red)
  "What is the recipe for chocolate cake?"
  "What is machine learning?"
  # Projects (yellow)
  "What projects on Trustworthy AI involve UNINOVIS partners?"
)

Q_IDS=(
  "Q01_conceptual1"
  "Q02_conceptual2"
  "Q03_conceptual3"
  "Q04_gap1"
  "Q05_gap2"
  "Q06_gap3"
  "Q07_researcher1"
  "Q08_researcher2"
  "Q09_topic1"
  "Q10_topic2"
  "Q11_topic3"
  "Q12_topic4"
  "Q13_crossuni1"
  "Q14_crossuni2"
  "Q15_interpret1"
  "Q16_interpret2"
  "Q17_interpret3"
  "Q18_offtopic1"
  "Q19_boundary1"
  "Q20_projects1"
)

DISPLAYS=("both" "visual")
PROMPTS=("stringent" "lax")

update_config() {
  /usr/bin/python3 -c "
import json
with open('$CONFIG', 'r') as f:
    cfg = json.load(f)
cfg['reliability_display'] = '$1'
cfg['prompt_level'] = '$2'
with open('$CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print(f'  Config: display=$1, prompt=$2')
"
}

reload_agent() {
  curl -s -X POST "$SERVER/api/agents/$AGENT/init" \
    -H "Authorization: Bearer $TOKEN" > /dev/null 2>&1
  sleep 1
}

run_query() {
  local question="$1"
  local outfile="$2"
  local escaped=$(echo "$question" | /usr/bin/python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
  curl -s -X POST "$SERVER/api/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"agent_id\":\"$AGENT\",\"message\":$escaped}" \
    --max-time 180 > "$outfile" 2>&1
}

echo "=== Text Style Benchmark (20 questions) ==="
echo "Conditions: ${#DISPLAYS[@]} x ${#PROMPTS[@]} = $(( ${#DISPLAYS[@]} * ${#PROMPTS[@]} ))"
echo "Total runs: $(( ${#QUESTIONS[@]} * ${#DISPLAYS[@]} * ${#PROMPTS[@]} ))"
echo ""

COUNT=0
TOTAL=$(( ${#QUESTIONS[@]} * ${#DISPLAYS[@]} * ${#PROMPTS[@]} ))

for display in "${DISPLAYS[@]}"; do
  for prompt in "${PROMPTS[@]}"; do
    condition="${display}_${prompt}"
    echo "--- Condition: $condition ---"
    update_config "$display" "$prompt"
    reload_agent

    for i in "${!QUESTIONS[@]}"; do
      qid="${Q_IDS[$i]}"
      question="${QUESTIONS[$i]}"
      outfile="$RESULTS_DIR/${condition}_${qid}.json"
      COUNT=$((COUNT + 1))
      echo "  [$COUNT/$TOTAL] $qid"
      run_query "$question" "$outfile"

      if [ -s "$outfile" ]; then
        resp_len=$(/usr/bin/python3 -c "import json; d=json.load(open('$outfile')); print(len(d.get('response','')))" 2>/dev/null)
        echo "    -> $resp_len chars"
      else
        echo "    -> ERROR: empty"
      fi
      sleep 1
    done
    echo ""
  done
done

# Restore original
update_config "both" "stringent"
reload_agent
echo "Config restored. All results in $RESULTS_DIR"
