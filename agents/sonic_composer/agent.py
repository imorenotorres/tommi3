"""Sonic Composer — interactive music agent for Sonic Pi and Strudel."""
import html as html_mod
import json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Try to import Sonic Pi tools; allow graceful fallback if psonic not installed
try:
    sys.path.insert(0, os.path.join(AGENT_DIR, "..", "base"))
    from sonic_pi_tools import SonicPiTools
    _SONIC_AVAILABLE = True
except ImportError:
    _SONIC_AVAILABLE = False


# --- MIDI/music helpers ---

SCALE_INTERVALS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "pentatonic": [0, 2, 4, 7, 9],
    "blues": [0, 3, 5, 6, 7, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
}

NOTE_TO_MIDI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

VALID_SYNTHS = {
    "piano", "tb303", "prophet", "blade", "pluck", "beep", "fm",
    "saw", "square", "hollow", "dsaw", "dpulse", "tech_saws",
}
VALID_FX = {"reverb", "echo", "distortion", "lpf", "hpf", "flanger", "wobble", "slicer"}
VALID_SAMPLES = {
    "bd_haus", "bd_ada", "bd_boom", "sn_dolf", "sn_dub", "hat_snap", "hat_cab", "hat_gem",
    "ambi_piano", "ambi_choir", "ambi_drone", "ambi_lunar_land", "ambi_dark_woosh",
    "ambi_glass_hum", "ambi_haunted_hum", "ambi_soft_buzz", "ambi_swoosh",
    "bass_hit_c", "bass_voxy_c", "bass_dnb_f", "bass_drop_c", "bass_thick_c", "bass_woodsy_c",
    "elec_ping", "elec_twang", "elec_cymbal", "elec_bell", "elec_blip", "elec_chime",
    "elec_flip", "elec_pop", "elec_wood",
    "guit_em9", "guit_e_fifths", "guit_e_slide", "guit_harmonics",
    "vinyl_scratch", "vinyl_rewind", "vinyl_hiss", "vinyl_backspin",
}
VALID_LOOPS = {
    "loop_amen", "loop_breakbeat", "loop_industrial", "loop_safari",
    "loop_tabla", "loop_compus", "loop_garzul", "loop_mika",
}


def root_to_midi(root: str) -> int:
    """Convert e.g. 'C4' to MIDI 60."""
    note = root[:-1].upper()
    octave = int(root[-1])
    return NOTE_TO_MIDI.get(note, 0) + (octave + 1) * 12


def scale_notes(root: str, scale: str, octaves: int = 1) -> list[int]:
    """Generate MIDI notes for a scale."""
    base = root_to_midi(root)
    intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["major"])
    notes = []
    for o in range(octaves):
        for i in intervals:
            notes.append(base + i + o * 12)
    return notes


# --- Code generator ---

def _pan_arg(loop: dict) -> str:
    """Return pan argument string if pan is set and non-zero."""
    pan = loop.get("pan", 0.0)
    if pan and pan != 0.0:
        return f", pan: {pan}"
    return ""


def _open_fx(lines: list, fx_list: list, indent: str = "  "):
    """Append with_fx opening lines and return the number opened."""
    count = 0
    for fx in fx_list:
        if fx in VALID_FX:
            lines.append(f"{indent}with_fx :{fx} do")
            count += 1
    return count


def _close_fx(lines: list, count: int, indent: str = "  "):
    """Append closing 'end' for each opened fx block."""
    for _ in range(count):
        lines.append(f"{indent}end")


def state_to_code(state: dict) -> str:
    """Convert musical state JSON to valid Sonic Pi code."""
    bpm = state.get("bpm", 120)
    loops = state.get("loops", {})
    if not loops:
        return ""

    lines = [f"use_bpm {bpm}", ""]

    for name, loop in loops.items():
        loop_type = loop.get("type", "melody")
        safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())
        pan = _pan_arg(loop)
        vol = loop.get("volume", 0.8)
        fx_list = loop.get("fx", [])

        if loop_type == "sample_loop":
            # Pregrabado loop sample
            sample_name = loop.get("sample_name", "loop_amen")
            rate = loop.get("rate", 1.0)
            lines.append(f"live_loop :{safe_name} do")
            fx_count = _open_fx(lines, fx_list)
            lines.append(f"  sample :{sample_name}, rate: {rate}, amp: {vol}{pan}")
            lines.append(f"  sleep sample_duration(:{sample_name}) / {abs(rate)}")
            _close_fx(lines, fx_count)
            lines.append("end")

        elif loop_type == "generative":
            # Generative / random notes from a scale
            synth = loop.get("synth", "piano")
            root = loop.get("root", "C4")
            sc = loop.get("scale", "pentatonic")
            num_octaves = loop.get("num_octaves", 2)
            density = loop.get("density", 8)
            sleep_range = loop.get("sleep_range", [0.1, 0.5])
            # Precalculate scale notes as MIDI array (avoids scale() Ring issues via psonic)
            notes = scale_notes(root, sc, num_octaves)
            lines.append(f"live_loop :{safe_name} do")
            lines.append(f"  use_synth :{synth}")
            fx_count = _open_fx(lines, fx_list)
            lines.append(f"  notes = {notes}")
            lines.append(f"  {density}.times do")
            lines.append(f"    play notes.choose, amp: {vol}, release: rrand({sleep_range[0]}, {sleep_range[1]}) * 1.5{pan}")
            lines.append(f"    sleep rrand({sleep_range[0]}, {sleep_range[1]})")
            lines.append("  end")
            _close_fx(lines, fx_count)
            lines.append("end")

        elif loop_type == "beat":
            pattern = loop.get("beat_pattern", [])
            if not pattern:
                pattern = [
                    {"sample": "bd_haus", "sleep": 0.25},
                    {"sample": "hat_snap", "sleep": 0.25},
                    {"sample": "bd_haus", "sleep": 0.25},
                    {"sample": "sn_dolf", "sleep": 0.25},
                ]
            lines.append(f"live_loop :{safe_name} do")
            fx_count = _open_fx(lines, fx_list)
            for step in pattern:
                sample = step.get("sample", "bd_haus")
                sl = step.get("sleep", 0.25)
                if sample == "rest":
                    lines.append(f"  sleep {sl}")
                else:
                    lines.append(f"  sample :{sample}, amp: {vol}{pan}")
                    lines.append(f"  sleep {sl}")
            _close_fx(lines, fx_count)
            lines.append("end")

        elif loop_type == "chords":
            synth = loop.get("synth", "piano")
            chord_names = loop.get("chord_names", ["C", "Am", "F", "G"])
            chord_type = loop.get("chord_type", "major")
            rhythm = loop.get("rhythm", [2])

            lines.append(f"live_loop :{safe_name} do")
            lines.append(f"  use_synth :{synth}")
            fx_count = _open_fx(lines, fx_list)
            for i, chord in enumerate(chord_names):
                root = chord.replace("m", "").replace("7", "")
                if "m7" in chord:
                    ct = "m7"
                elif "m" in chord and chord != root:
                    ct = "minor"
                elif "7" in chord:
                    ct = "dom7"
                else:
                    ct = chord_type
                sl = rhythm[i % len(rhythm)]
                lines.append(f"  play chord(:{root}3, :{ct}), release: {sl}, amp: {vol}{pan}")
                lines.append(f"  sleep {sl}")
            _close_fx(lines, fx_count)
            lines.append("end")

        else:
            # melody or bass
            synth = loop.get("synth", "piano")
            root = loop.get("root", "C4" if loop_type == "melody" else "C2")
            sc = loop.get("scale", "major")
            rhythm = loop.get("rhythm", [0.25, 0.25, 0.5, 0.25, 0.75])

            notes = loop.get("notes")
            if not notes:
                notes = scale_notes(root, sc)

            lines.append(f"live_loop :{safe_name} do")
            lines.append(f"  use_synth :{synth}")
            fx_count = _open_fx(lines, fx_list)
            lines.append(f"  notes = {notes}")
            lines.append(f"  durations = {rhythm}")
            lines.append("  notes.length.times do |i|")
            lines.append(f"    play notes[i % notes.length], release: durations[i % durations.length] * 0.9, amp: {vol}{pan}")
            lines.append("    sleep durations[i % durations.length]")
            lines.append("  end")
            _close_fx(lines, fx_count)
            lines.append("end")

        lines.append("")

    return "\n".join(lines)


# --- JSON helpers ---

def _load_json(filename):
    path = os.path.join(AGENT_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _build_system_prompt(config, prompts):
    level = config.get("prompt_level", "stringent")
    tvars = {
        "agent_name": config.get("agent_name", "Sonic Composer"),
        "description": config.get("description", "compositor musical"),
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
    """Extract JSON from <estado>...</estado> tags in LLM response."""
    m = re.search(r"<estado>\s*(.*?)\s*</estado>", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: try to find a JSON block
    m = re.search(r"```json?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _extract_description(text: str) -> str:
    """Extract the description part after the JSON block."""
    # Remove <estado>...</estado> block
    cleaned = re.sub(r"<estado>.*?</estado>", "", text, flags=re.DOTALL).strip()
    # Remove markdown code blocks
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL).strip()
    return cleaned or "Estado musical actualizado."


# --- Agent ---

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
        base_prompt = system_prompt or _build_system_prompt(self._config, self._prompts)
        # Append preset reference to system prompt
        if self._presets:
            preset_ref = "\n\nPRESETS DE ESTILOS MUSICALES:\nCuando el usuario pida un estilo musical específico, usa estos presets como BASE y adáptalos según la instrucción. Puedes modificar bpm, notas, instrumentos, etc. pero mantén la estructura rítmica del estilo.\n\n"
            for name, preset in self._presets.items():
                preset_ref += f"- {name}: {preset.get('description', '')} (bpm={preset.get('bpm', 120)})\n"
            preset_ref += "\nPara usar un preset, responde con su estado JSON completo. Puedes combinar elementos de varios presets."
            base_prompt += preset_ref
        self.system_prompt = base_prompt

        # Musical state persists across messages in the same session
        self.musical_state = {"bpm": 120, "loops": {}}
        self._previous_code = ""

        # Sonic Pi connection
        self._sonic = None
        if _SONIC_AVAILABLE:
            try:
                self._sonic = SonicPiTools()
                print(f"[SonicComposer] Connected to Sonic Pi: {self._sonic._params}")
            except Exception as e:
                print(f"[SonicComposer] Failed to connect to Sonic Pi: {e}")
        else:
            print("[SonicComposer] psonic not available")

    @staticmethod
    def _diff_code(old_code: str, new_code: str) -> str:
        """Compare old and new code, return HTML with changed/removed lines marked in place."""
        import difflib

        old_lines = old_code.splitlines() if old_code else []
        new_lines = new_code.splitlines()

        def esc_line(line):
            return line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if not old_lines:
            return "\n".join(esc_line(l) for l in new_lines)

        # If code is mostly different (< 30% match), show all as new — no diff
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        if matcher.ratio() < 0.3:
            return "\n".join(esc_line(l) for l in new_lines)

        result = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for line in new_lines[j1:j2]:
                    result.append(esc_line(line))
            elif tag == "replace":
                for line in old_lines[i1:i2]:
                    result.append(
                        '<span style="color:#e74c3c;">\u25cf # ' + esc_line(line.strip()) + '</span>'
                    )
                for line in new_lines[j1:j2]:
                    result.append(
                        '<span style="color:#2ecc71;">\u25cf</span> ' + esc_line(line)
                    )
            elif tag == "delete":
                for line in old_lines[i1:i2]:
                    result.append(
                        '<span style="color:#e74c3c;">\u25cf # ' + esc_line(line.strip()) + '</span>'
                    )
            elif tag == "insert":
                for line in new_lines[j1:j2]:
                    result.append(
                        '<span style="color:#2ecc71;">\u25cf</span> ' + esc_line(line)
                    )
        return "\n".join(result)

    def _send_to_sonic_pi(self, code: str) -> str:
        """Send code to Sonic Pi. Returns status message."""
        if not code:
            if self._sonic:
                return self._sonic.stop_all()
            return "Música detenida (Sonic Pi no conectado)."
        if self._sonic:
            return self._sonic.play_code(code)
        return "(Sonic Pi no conectado — instala psonic y abre Sonic Pi)"

    def chat(self, message, history, **kwargs):
        # Reset diff tracking when starting a new session (no history)
        if not history:
            self._previous_code = ""
            self.musical_state = {"bpm": 120, "loops": {}}

        # Check if a preset matches the user's request
        preset_hint = ""
        if self._presets:
            msg_lower = message.lower()
            for name, preset in self._presets.items():
                keywords = name.replace("_", " ").split()
                if all(k in msg_lower for k in keywords):
                    preset_hint = (
                        f"\n\nPRESET SUGERIDO para '{name}':\n"
                        f"{json.dumps(preset, ensure_ascii=False, indent=2)}\n"
                        f"Usa este preset como base y adáptalo según la instrucción del usuario."
                    )
                    break

        # Build messages with current state injected
        state_str = json.dumps(self.musical_state, ensure_ascii=False, indent=2)
        user_msg = f"<estado_actual>\n{state_str}\n</estado_actual>\n\nInstrucción del usuario: {message}{preset_hint}"

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_msg})

        model = kwargs.get("model_override") or self.model
        response = self.client.complete(model=model, messages=messages)
        raw = response.choices[0].message.content

        # Parse LLM response
        print(f"[SonicComposer] LLM raw response:\n{raw[:500]}")
        new_state = _extract_state_json(raw)
        description = _extract_description(raw)
        print(f"[SonicComposer] Parsed state: {new_state is not None}")

        if new_state:
            self.musical_state = new_state
            code = state_to_code(new_state)
            print(f"[SonicComposer] Generated code ({len(code)} chars)")

            # Try Sonic Pi (if connected)
            sonic_status = self._send_to_sonic_pi(code)
            print(f"[SonicComposer] Sonic Pi: {sonic_status}")

            # Build response for user
            parts = [description]

            # Sonic Pi code block (visible)
            if not code:
                self._previous_code = ""
            if code:
                code_html = self._diff_code(self._previous_code, code)
                self._previous_code = code
                parts.append("")
                parts.append(
                    '<div class="sp-code-block" style="border:2px solid #4250b3;border-radius:8px;overflow:hidden;margin:8px 0;">'
                    '<div style="background:#4250b3;color:#fff;padding:6px 12px;font-size:0.8em;font-weight:700;">'
                    '&#9835; Now Playing'
                    '<button onclick="spCopyCode(this)" style="float:right;background:rgba(255,255,255,0.2);border:none;color:#fff;padding:2px 10px;border-radius:4px;font-size:0.8em;cursor:pointer;">Copy</button>'
                    '</div>'
                    '<pre style="margin:0;border-radius:0;"><code>'
                    + code_html +
                    '</code></pre></div>'
                )

            # Embed state JSON for Strudel (hidden, frontend reads it)
            state_escaped = html_mod.escape(
                json.dumps(self.musical_state, ensure_ascii=False)
            )
            parts.append(
                f'<div class="sp-state" style="display:none" '
                f'data-state="{state_escaped}"></div>'
            )
            return "\n".join(parts)
        else:
            return raw

    async def chat_stream(self, message, history, **kwargs):
        # For streaming, collect full response first (need complete JSON)
        result = self.chat(message, history, **kwargs)
        # Yield in chunks for streaming compatibility
        chunk_size = 40
        for i in range(0, len(result), chunk_size):
            yield ("content", result[i : i + chunk_size])
