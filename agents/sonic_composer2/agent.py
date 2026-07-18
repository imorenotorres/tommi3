"""Sonic Composer v2 — classified music agent with style awareness."""
import html as html_mod
import json, os, re, sys, difflib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "base"))
from llm_client import LLMClient

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Try Sonic Pi tools
try:
    from sonic_pi_tools import SonicPiTools
    _SONIC_AVAILABLE = True
except ImportError:
    _SONIC_AVAILABLE = False


# ── Import code generator from sonic_composer ──

sys.path.insert(0, os.path.join(AGENT_DIR, "..", "sonic_composer"))
from agent import (
    state_to_code, scale_notes,
    VALID_SYNTHS, VALID_FX, VALID_SAMPLES, VALID_LOOPS,
    SCALE_INTERVALS, NOTE_TO_MIDI,
)


# ── Validation ──

VALID_SYNTH_NAMES = {
    "beep", "sine", "saw", "pulse", "square", "triangle",
    "dull_bell", "pretty_bell", "fm", "tb303", "prophet", "zawa",
    "supersaw", "hoover", "dark_ambience", "growl", "hollow",
    "piano", "pluck", "dsaw", "dpulse", "dtri",
    "mod_saw", "mod_dsaw", "mod_sine", "mod_tri", "mod_pulse",
    "noise", "pnoise", "bnoise",
}
VALID_SCALE_NAMES = set(SCALE_INTERVALS.keys()) | {
    "pentatonic", "major_pentatonic", "minor_pentatonic",
    "phrygian", "lydian", "locrian", "whole", "chromatic",
    "hungarian_minor", "hirajoshi", "iwato", "kumoi", "pelog", "egyptian",
    "melodic_minor_asc",
}
VALID_FX_NAMES = {
    "reverb", "echo", "distortion", "lpf", "hpf", "bpf",
    "flanger", "wobble", "slicer", "panslicer", "krush",
    "bitcrusher", "compressor", "whammy", "pitch_shift",
}
VALID_SAMPLE_NAMES = {
    "bd_pure", "bd_808", "bd_zum", "bd_gas", "bd_sone", "bd_haus",
    "bd_zome", "bd_boom", "bd_klub", "bd_fat", "bd_tek", "bd_ada",
    "sn_dub", "sn_dolf", "sn_zome", "sn_generic",
    "hat_snap", "hat_cab", "hat_gem", "hat_metal", "hat_raw", "hat_bdu", "hat_psych",
    "drum_heavy_kick", "drum_bass_soft", "drum_bass_hard",
    "drum_snare_soft", "drum_snare_hard",
    "drum_cymbal_soft", "drum_cymbal_hard", "drum_cymbal_open",
    "drum_cymbal_closed", "drum_cymbal_pedal",
    "drum_tom_lo_soft", "drum_tom_lo_hard",
    "drum_tom_mid_soft", "drum_tom_mid_hard",
    "drum_tom_hi_soft", "drum_tom_hi_hard",
    "drum_splash_soft", "drum_splash_hard", "drum_cowbell", "drum_roll",
    "elec_triangle", "elec_snare", "elec_lo_snare", "elec_hi_snare",
    "elec_mid_snare", "elec_cymbal", "elec_soft_kick", "elec_filt_snare",
    "elec_fuzz_tom", "elec_chime", "elec_bong", "elec_twang", "elec_wood",
    "elec_pop", "elec_beep", "elec_blip", "elec_blip2", "elec_ping",
    "elec_bell", "elec_flip", "elec_tick", "elec_hollow_kick",
    "perc_bell", "perc_snap", "perc_snap2", "perc_swash", "perc_till",
    "bass_hit_c", "bass_hard_c", "bass_thick_c", "bass_drop_c",
    "bass_woodsy_c", "bass_voxy_c", "bass_dnb_f",
    "guit_harmonics", "guit_e_fifths", "guit_e_slide", "guit_em9",
    "ambi_soft_buzz", "ambi_swoosh", "ambi_drone", "ambi_glass_hum",
    "ambi_glass_rub", "ambi_haunted_hum", "ambi_piano", "ambi_lunar_land",
    "ambi_dark_woosh", "ambi_choir", "ambi_sauna",
    "vinyl_backspin", "vinyl_rewind", "vinyl_scratch", "vinyl_hiss",
    "loop_industrial", "loop_compus", "loop_amen", "loop_amen_full",
    "loop_garzul", "loop_mika", "loop_breakbeat", "loop_safari",
    "loop_tabla", "loop_3dprinter", "loop_drone_g_97", "loop_electric",
    "loop_perc_1", "loop_perc_2", "loop_weirdo",
    "rest",
}


def validate_state(state: dict) -> dict:
    """Validate and fix a musical state, replacing invalid values."""
    state["bpm"] = max(40, min(200, state.get("bpm", 120)))
    for name, loop in state.get("loops", {}).items():
        # Validate synth
        synth = loop.get("synth", "piano")
        if synth not in VALID_SYNTH_NAMES:
            loop["synth"] = "piano"
            print(f"[Validate] Invalid synth '{synth}' → 'piano'")
        # Validate fx
        if "fx" in loop:
            valid_fx = [f for f in loop["fx"] if f in VALID_FX_NAMES]
            if len(valid_fx) != len(loop["fx"]):
                removed = set(loop["fx"]) - set(valid_fx)
                print(f"[Validate] Removed invalid fx: {removed}")
            loop["fx"] = valid_fx
        # Validate volume and pan
        loop["volume"] = max(0.0, min(1.0, loop.get("volume", 0.8)))
        loop["pan"] = max(-1.0, min(1.0, loop.get("pan", 0.0)))
        # Validate beat samples
        if loop.get("type") == "beat" and "beat_pattern" in loop:
            for step in loop["beat_pattern"]:
                sample = step.get("sample", "bd_haus")
                if sample not in VALID_SAMPLE_NAMES:
                    step["sample"] = "bd_haus"
                    print(f"[Validate] Invalid sample '{sample}' → 'bd_haus'")
        # Validate sample_loop
        if loop.get("type") == "sample_loop":
            sample = loop.get("sample_name", "loop_amen")
            if sample not in VALID_SAMPLE_NAMES:
                loop["sample_name"] = "loop_amen"
                print(f"[Validate] Invalid loop sample '{sample}' → 'loop_amen'")
        # Validate chord names (fix common LLM hallucinations like "Caj3", "Faj3")
        if loop.get("type") == "chords" and "chord_names" in loop:
            fixed = []
            for ch in loop["chord_names"]:
                # Remove "aj" hallucination and octave numbers from chord names
                clean = re.sub(r"aj\d*", "", ch)  # Caj3 → C, Faj3 → F
                clean = re.sub(r"\d+$", "", clean)  # C3 → C (octave handled by generator)
                if not clean:
                    clean = "C"
                fixed.append(clean)
                if clean != ch:
                    print(f"[Validate] Fixed chord name '{ch}' → '{clean}'")
            loop["chord_names"] = fixed
    return state


# ── JSON/prompt helpers ──

def _load_json(filename):
    path = os.path.join(AGENT_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_text(filename):
    path = os.path.join(AGENT_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _build_system_prompt(config, prompts):
    level = config.get("prompt_level", "stringent")
    tvars = {
        "agent_name": config.get("agent_name", "Sonic Composer"),
        "description": config.get("description", ""),
    }
    def render(section):
        text = prompts.get(section, "")
        if not text:
            return ""
        try:
            return text.format(**tvars)
        except KeyError:
            return text

    parts = [render("identity")]
    if level in ("tolerant", "stringent"):
        r = render("rules")
        if r:
            parts.append(r)
    if level == "stringent":
        s = render("strict")
        if s:
            parts.append(s)
    return "\n\n".join(parts)


def _extract_state_json(text: str) -> dict | None:
    m = re.search(r"<estado>\s*(.*?)\s*</estado>", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"```json?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _extract_description(text: str) -> str:
    cleaned = re.sub(r"<estado>.*?</estado>", "", text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL).strip()
    return cleaned or "Estado musical actualizado."


def _diff_code(old_code: str, new_code: str) -> str:
    old_lines = old_code.splitlines() if old_code else []
    new_lines = new_code.splitlines()

    def esc(line):
        return line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if not old_lines:
        return "\n".join(esc(l) for l in new_lines)

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    if matcher.ratio() < 0.3:
        return "\n".join(esc(l) for l in new_lines)

    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in new_lines[j1:j2]:
                result.append(esc(line))
        elif tag == "replace":
            for line in old_lines[i1:i2]:
                result.append('<span style="color:#e74c3c;">\u25cf # ' + esc(line.strip()) + '</span>')
            for line in new_lines[j1:j2]:
                result.append('<span style="color:#2ecc71;">\u25cf</span> ' + esc(line))
        elif tag == "delete":
            for line in old_lines[i1:i2]:
                result.append('<span style="color:#e74c3c;">\u25cf # ' + esc(line.strip()) + '</span>')
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                result.append('<span style="color:#2ecc71;">\u25cf</span> ' + esc(line))
    return "\n".join(result)


# ── Intent classification ──

def classify_intent(message: str, config: dict, client, model: str) -> str:
    """Use LLM to classify the user's intent."""
    classification = config.get("classification", {})
    if not classification:
        return "new_composition"

    # Quick keyword-based pre-classification for obvious cases
    msg_lower = message.lower().strip()
    if msg_lower in ("stop", "para", "para la música", "silence", "quiet"):
        return "stop"

    # Build classification prompt
    categories = []
    for intent, data in classification.items():
        examples = ", ".join(f'"{e}"' for e in data.get("examples", [])[:3])
        categories.append(f"- {intent}: {data['description']}. Examples: {examples}")

    prompt = (
        "Classify the following user message into EXACTLY ONE of these categories. "
        "Respond with ONLY the category name, nothing else.\n\n"
        "Categories:\n" + "\n".join(categories) + "\n\n"
        f'User message: "{message}"\n\nCategory:'
    )

    try:
        response = client.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        intent = response.choices[0].message.content.strip().lower().replace(" ", "_")
        if intent in classification:
            return intent
    except Exception as e:
        print(f"[Classify] Error: {e}")

    return "new_composition"


# ── Agent ──

class Agent:
    def __init__(self, system_prompt=None, **kwargs):
        self.client = LLMClient()
        self.model = os.getenv(
            "MISTRAL_MODEL",
            os.getenv("OLLAMA_MODEL", os.getenv("VLLM_MODEL", "mistral-small-latest")),
        )
        self._config = _load_json("config.json")
        self._prompts = _load_json("prompts.json")
        self._presets = _load_json("presets.json")
        self._reference = _load_text("data/sonic_pi_reference.md")
        self._base_prompt = system_prompt or _build_system_prompt(self._config, self._prompts)

        self.musical_state = {"bpm": 120, "loops": {}}
        self._previous_code = ""

        # Sonic Pi connection
        self._sonic = None
        if _SONIC_AVAILABLE:
            try:
                self._sonic = SonicPiTools()
                print(f"[SonicComposer2] Connected to Sonic Pi: {self._sonic._params}")
            except Exception as e:
                print(f"[SonicComposer2] Sonic Pi not available: {e}")

    def _send_to_sonic_pi(self, code: str) -> str:
        if not code:
            if self._sonic:
                return self._sonic.stop_all()
            return ""
        if self._sonic:
            return self._sonic.play_code(code)
        return ""

    def _find_preset(self, message: str) -> dict | None:
        """Find a matching preset for the user's message."""
        if not self._presets:
            return None
        msg_lower = message.lower()
        for name, preset in self._presets.items():
            keywords = name.replace("_", " ").split()
            if all(k in msg_lower for k in keywords):
                return preset
        # Try partial matches
        style_aliases = {
            "rock": "rock_and_roll", "blues": "blues", "jazz": "jazz",
            "techno": "techno", "house": "house", "ambient": "ambient",
            "bossa": "bossa_nova", "reggae": "reggae", "hiphop": "hiphop",
            "hip-hop": "hiphop", "hip hop": "hiphop", "chill": "chill",
            "lo-fi": "chill", "lofi": "chill", "funk": "hiphop",
        }
        for keyword, preset_name in style_aliases.items():
            if keyword in msg_lower and preset_name in self._presets:
                return self._presets[preset_name]
        return None

    def _build_intent_prompt(self, intent: str, message: str) -> str:
        """Build the full prompt for a specific intent."""
        parts = [self._base_prompt]

        # Add intent-specific instructions
        intent_prompts = self._prompts.get("intent_prompts", {})
        if intent in intent_prompts:
            parts.append(f"\nINSTRUCCIÓN PARA ESTE TIPO DE PETICIÓN:\n{intent_prompts[intent]}")

        # Add style reference for composition/add intents
        if intent in ("new_composition", "add_element"):
            # Find relevant section of reference
            preset = self._find_preset(message)
            if preset:
                parts.append(
                    f"\nPRESET SUGERIDO (usa como base, adapta según la instrucción):\n"
                    f"{json.dumps(preset, ensure_ascii=False, indent=2)}"
                )
            # Add relevant style reference
            if self._reference:
                # Extract the relevant style section
                msg_lower = message.lower()
                style_sections = re.split(r"### ", self._reference)
                relevant = []
                for section in style_sections:
                    section_name = section.split("\n")[0].lower()
                    # Check if any word from the message matches the section
                    for word in msg_lower.split():
                        if len(word) > 3 and word in section_name:
                            relevant.append("### " + section)
                            break
                if relevant:
                    parts.append("\nREFERENCIA DE ESTILO:\n" + "\n".join(relevant))

            # Always include available resources summary
            parts.append(
                "\nRECURSOS VÁLIDOS DE SONIC PI (usa SOLO estos):\n"
                "Synths: piano, saw, square, tb303, fm, prophet, hollow, pluck, "
                "supersaw, dsaw, dark_ambience, growl, hoover, beep, zawa\n"
                "Drum samples: bd_haus, bd_808, bd_ada, bd_boom, sn_dolf, sn_dub, "
                "hat_snap, hat_cab, drum_cymbal_open, drum_cymbal_closed, drum_cowbell\n"
                "FX: reverb, echo, distortion, lpf, hpf, flanger, wobble, slicer"
            )

        return "\n\n".join(parts)

    def _build_response(self, description: str) -> str:
        """Build the standard HTML response with code block and state."""
        code = state_to_code(self.musical_state)
        self._send_to_sonic_pi(code)

        parts = [description]
        if not code:
            self._previous_code = ""
        if code:
            code_html = _diff_code(self._previous_code, code)
            self._previous_code = code
            parts.append("")
            parts.append(
                '<div class="sp-code-block" style="border:2px solid #4250b3;border-radius:8px;overflow:hidden;margin:8px 0;">'
                '<div style="background:#4250b3;color:#fff;padding:6px 12px;font-size:0.8em;font-weight:700;">'
                '&#9835; Now Playing'
                '<button onclick="spCopyCode(this)" style="float:right;background:rgba(255,255,255,0.2);border:none;color:#fff;padding:2px 10px;border-radius:4px;font-size:0.8em;cursor:pointer;">Copy</button>'
                '</div>'
                '<pre style="margin:0;border-radius:0;"><code>'
                + code_html
                + '</code></pre></div>'
            )

        state_escaped = html_mod.escape(
            json.dumps(self.musical_state, ensure_ascii=False)
        )
        parts.append(
            f'<div class="sp-state" style="display:none" '
            f'data-state="{state_escaped}"></div>'
        )
        return "\n".join(parts)

    def _try_programmatic_modify(self, message: str):
        """Handle simple modifications without LLM. Returns response string or None."""
        import copy
        msg = message.lower()
        state = copy.deepcopy(self.musical_state)
        changes = []

        # BPM change
        bpm_match = re.search(r'(\d{2,3})\s*bpm', msg)
        if not bpm_match:
            bpm_match = re.search(r'bpm\s*(?:a|to|=|:)?\s*(\d{2,3})', msg)
        if bpm_match:
            new_bpm = int(bpm_match.group(1))
            if 40 <= new_bpm <= 200:
                state["bpm"] = new_bpm
                changes.append(f"BPM → {new_bpm}")

        # Faster / slower with intensity
        if not bpm_match:
            delta = 0
            if any(w in msg for w in ["mucho más rápido", "much faster", "way faster", "doble"]):
                delta = 40
            elif any(w in msg for w in ["un poco más rápido", "poco más rápido", "slightly faster", "a bit faster", "algo más rápido"]):
                delta = 10
            elif any(w in msg for w in ["faster", "rápido", "más rápido", "speed up", "más velocidad", "sube el tempo", "sube tempo"]):
                delta = 20
            elif any(w in msg for w in ["mucho más lento", "much slower", "way slower", "mitad"]):
                delta = -40
            elif any(w in msg for w in ["un poco más lento", "poco más lento", "slightly slower", "a bit slower", "algo más lento"]):
                delta = -10
            elif any(w in msg for w in ["slower", "lento", "más lento", "slow down", "menos velocidad", "baja el tempo", "baja tempo"]):
                delta = -20
            if delta:
                state["bpm"] = max(40, min(200, state.get("bpm", 120) + delta))
                label = "faster" if delta > 0 else "slower"
                changes.append(f"BPM → {state['bpm']} ({label})")

        # Synth change (for all melodic loops)
        for synth_name in VALID_SYNTH_NAMES:
            if synth_name in msg and synth_name not in ("sine", "noise", "fm"):
                # Check it's mentioned as a synth, not just a random word
                if f"synth {synth_name}" in msg or f"sintetizador {synth_name}" in msg or f"con {synth_name}" in msg or f"to {synth_name}" in msg:
                    for loop in state.get("loops", {}).values():
                        if loop.get("type") in ("melody", "bass", "chords", "generative"):
                            loop["synth"] = synth_name
                    changes.append(f"Synth → {synth_name}")
                    break

        # Scale change
        for scale_name in ["major", "minor", "pentatonic", "blues", "dorian",
                           "mixolydian", "phrygian", "lydian", "harmonic_minor"]:
            if scale_name in msg and ("scale" in msg or "escala" in msg or "cambia" in msg or "change" in msg):
                for loop in state.get("loops", {}).values():
                    if loop.get("type") in ("melody", "generative"):
                        loop["scale"] = scale_name
                        # Regenerate notes for the new scale
                        root = loop.get("root", "C4")
                        loop["notes"] = scale_notes(root, scale_name)
                changes.append(f"Scale → {scale_name}")
                break

        # FX add/remove
        for fx_name in VALID_FX_NAMES:
            if fx_name in msg:
                if any(w in msg for w in ["add", "añade", "pon", "con"]):
                    for loop in state.get("loops", {}).values():
                        if fx_name not in loop.get("fx", []):
                            loop.setdefault("fx", []).append(fx_name)
                    changes.append(f"Added FX: {fx_name}")
                elif any(w in msg for w in ["remove", "quita", "elimina", "sin"]):
                    for loop in state.get("loops", {}).values():
                        if fx_name in loop.get("fx", []):
                            loop["fx"].remove(fx_name)
                    changes.append(f"Removed FX: {fx_name}")

        # Volume change
        vol_match = re.search(r'vol(?:ume|umen)?\s*(?:a|to|=|:)?\s*([\d.]+)', msg)
        if vol_match:
            new_vol = max(0.0, min(1.0, float(vol_match.group(1))))
            for loop in state.get("loops", {}).values():
                loop["volume"] = new_vol
            changes.append(f"Volume → {new_vol}")

        if not changes:
            return None  # Could not handle programmatically, fall through to LLM

        self.musical_state = state
        description = "Modificado: " + ", ".join(changes)
        print(f"[SonicComposer2] Programmatic modify: {changes}")
        return self._build_response(description)

    def _clean_history(self, history):
        """Clean history to remove HTML state divs that confuse the LLM."""
        cleaned = []
        for msg in history:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                # Remove hidden state divs and code blocks from assistant responses
                content = re.sub(r'<div class="sp-state"[^>]*>.*?</div>', '', content, flags=re.DOTALL)
                content = re.sub(r'<div class="sp-code-block"[^>]*>.*?</div>\s*</div>', '', content, flags=re.DOTALL)
                content = content.strip()
            cleaned.append({"role": msg.get("role", "user"), "content": content})
        return cleaned

    def chat(self, message, history, **kwargs):
        # Reset on new session
        if not history:
            self._previous_code = ""
            self.musical_state = {"bpm": 120, "loops": {}}

        # Clean history (remove HTML artifacts)
        clean_hist = self._clean_history(history)

        try:
            # Classify intent
            intent = classify_intent(message, self._config, self.client, self.model)
            print(f"[SonicComposer2] Intent: {intent}")
        except Exception as e:
            print(f"[SonicComposer2] Classification error: {e}")
            intent = "modify" if self.musical_state.get("loops") else "new_composition"

        # Handle info intent (no JSON needed)
        if intent == "info":
            prompt = self._build_intent_prompt(intent, message)
            if self._reference:
                prompt += "\n\nREFERENCIA COMPLETA:\n" + self._reference[:3000]
            messages = [{"role": "system", "content": prompt}]
            messages.extend(clean_hist)
            messages.append({"role": "user", "content": message})
            model = kwargs.get("model_override") or self.model
            response = self.client.complete(model=model, messages=messages)
            return response.choices[0].message.content

        # Handle stop intent
        if intent == "stop":
            self.musical_state = {"bpm": 120, "loops": {}}
            self._previous_code = ""
            self._send_to_sonic_pi("")
            state_escaped = html_mod.escape(json.dumps(self.musical_state))
            return (
                "Música detenida."
                f'\n<div class="sp-state" style="display:none" data-state="{state_escaped}"></div>'
            )

        # For "modify" intent, try programmatic changes first (no LLM needed)
        if intent == "modify" and self.musical_state.get("loops"):
            result = self._try_programmatic_modify(message)
            if result:
                return result

        # Build prompt with intent-specific context
        prompt = self._build_intent_prompt(intent, message)

        # Build user message with current state
        state_str = json.dumps(self.musical_state, ensure_ascii=False, indent=2)
        user_msg = f"<estado_actual>\n{state_str}\n</estado_actual>\n\nInstrucción del usuario: {message}"

        messages = [{"role": "system", "content": prompt}]
        messages.extend(clean_hist)
        messages.append({"role": "user", "content": user_msg})

        model = kwargs.get("model_override") or self.model
        response = self.client.complete(model=model, messages=messages)
        raw = response.choices[0].message.content
        print(f"[SonicComposer2] LLM response:\n{raw[:300]}")

        # Parse and validate
        new_state = _extract_state_json(raw)
        description = _extract_description(raw)

        if new_state:
            new_state = validate_state(new_state)
            self.musical_state = new_state
            return self._build_response(description)
        else:
            return raw

    async def chat_stream(self, message, history, **kwargs):
        try:
            result = self.chat(message, history, **kwargs)
        except Exception as e:
            print(f"[SonicComposer2] Error in chat: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            result = f"Error: {e}"
        chunk_size = 40
        for i in range(0, len(result), chunk_size):
            yield ("content", result[i : i + chunk_size])
