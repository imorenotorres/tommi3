#!/bin/bash
# Text Style Benchmarking: tests 4 questions x 4 conditions
# Conditions: (reliability_display: both/visual) x (prompt_level: stringent/lax)

SERVER="http://localhost:8000"
TOKEN="f142a495c0786b95a6bbe93e7182b68efeec25c8a6e405f28e46c4b6051f8402"
AGENT="responsible_ai3"
CONFIG="/Users/ignaciomoreno-torres/tommi3/agents/responsible_ai3/config.json"
RESULTS_DIR="/Users/ignaciomoreno-torres/tommi3/agents/responsible_ai3/benchmark_results"

mkdir -p "$RESULTS_DIR"

# 4 questions that trigger yellow or red banners
QUESTIONS=(
  "What is Responsible AI?"
  "List any topics related with responsible AI that have not been studied"
  "What do you know of Enrique Alba"
  "What are the main challenges for trustworthy AI in healthcare?"
)
Q_IDS=("Q1_conceptual" "Q2_gap_analysis" "Q3_researcher" "Q4_interpretation")

# 4 conditions
DISPLAYS=("both" "visual")
PROMPTS=("stringent" "lax")

update_config() {
  local display="$1"
  local prompt="$2"
  /usr/bin/python3 -c "
import json
with open('$CONFIG', 'r') as f:
    cfg = json.load(f)
cfg['reliability_display'] = '$display'
cfg['prompt_level'] = '$prompt'
with open('$CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print(f'Config set: reliability_display={cfg[\"reliability_display\"]}, prompt_level={cfg[\"prompt_level\"]}')
"
}

reload_agent() {
  curl -s -X POST "$SERVER/api/agents/$AGENT/init" \
    -H "Authorization: Bearer $TOKEN" > /dev/null 2>&1
  echo "Agent reloaded"
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
    --max-time 180 \
    > "$outfile" 2>&1
}

echo "=== Text Style Benchmark ==="
echo "Questions: ${#QUESTIONS[@]}"
echo "Conditions: ${#DISPLAYS[@]} x ${#PROMPTS[@]} = $(( ${#DISPLAYS[@]} * ${#PROMPTS[@]} ))"
echo "Total runs: $(( ${#QUESTIONS[@]} * ${#DISPLAYS[@]} * ${#PROMPTS[@]} ))"
echo ""

for display in "${DISPLAYS[@]}"; do
  for prompt in "${PROMPTS[@]}"; do
    condition="${display}_${prompt}"
    echo "--- Condition: display=$display, prompt=$prompt ---"
    update_config "$display" "$prompt"
    reload_agent

    for i in "${!QUESTIONS[@]}"; do
      qid="${Q_IDS[$i]}"
      question="${QUESTIONS[$i]}"
      outfile="$RESULTS_DIR/${condition}_${qid}.json"
      echo "  [$qid] $question"
      run_query "$question" "$outfile"

      # Quick check
      if [ -s "$outfile" ]; then
        resp_len=$(/usr/bin/python3 -c "import json; d=json.load(open('$outfile')); print(len(d.get('response','')))" 2>/dev/null)
        echo "    -> Response length: $resp_len chars"
      else
        echo "    -> ERROR: empty response"
      fi
      sleep 1
    done
    echo ""
  done
done

# Restore original config
update_config "both" "stringent"
reload_agent
echo "Config restored to original (both/stringent)"

echo ""
echo "=== All results saved to $RESULTS_DIR ==="
echo "Run the analysis script next."
