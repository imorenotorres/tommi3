"""
Sonic Pi Tools for TOMMI Lite
==============================

Herramientas para integrar Sonic Pi con agentes de TOMMI Lite.
Compatible con Sonic Pi 4.x (Spider Server).

Los puertos y token se detectan automáticamente desde ~/.sonic-pi/log/gui.log.
Si la autodetección falla, se pueden configurar manualmente en env.txt:
SONIC_PI_HOST=127.0.0.1
SONIC_PI_TOKEN=<token>
SONIC_PI_GUI_PORT=<port>
SONIC_PI_OSC_PORT=<port>
"""

import os
import re
import random
import subprocess
from pathlib import Path
from psonic import set_server_parameter, run, stop


def _extract_from_gui_log(text: str) -> dict:
    """Extract port/token values from gui.log (Sonic Pi 4.5+).

    The daemon prints values as 'daemon_stdout: <number>'.
    Order: daemon_port, gui_port, spider_port, ?, osc_cues_port, tau_port, tau_web_port, token.
    """
    values = []
    for line in text.splitlines():
        m = re.search(r"daemon_stdout:\s*(-?\d+)", line)
        if m:
            values.append(int(m.group(1)))
    if len(values) >= 8:
        return {
            "gui_port": values[1],
            "osc_port": values[2],
            "token": values[7],
        }
    return {}


def _extract_from_spider_log(text: str) -> dict:
    """Extract port/token values from spider.log (Sonic Pi 4.3–4.4).

    Format: 'Token: <number>' and 'Ports: {:server_port=>N, ...}'
    """
    token = None
    server_port = None
    osc_port = None

    m = re.search(r"Token:\s*(-?\d+)", text)
    if m:
        token = int(m.group(1))
    m = re.search(r":server_port=>(\d+)", text)
    if m:
        server_port = int(m.group(1))
    m = re.search(r":osc_cues_port=>(\d+)", text)
    if m:
        osc_port = int(m.group(1))

    if token and server_port:
        return {
            "gui_port": osc_port or 4560,
            "osc_port": server_port,
            "token": token,
        }
    return {}


def _read_log_file(path: Path) -> str:
    """Read a log file, handling both binary and text formats."""
    # Method 1: 'strings' command (macOS/Linux — handles binary logs)
    try:
        result = subprocess.run(
            ["strings", str(path)],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, OSError):
        pass

    # Method 2: read directly (Windows, or text-format logs)
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass

    return ""


def _autodetect_sonic_pi_params() -> dict:
    """Read Sonic Pi 4.x boot params automatically.

    Supports:
    - Sonic Pi 4.5+ (reads gui.log, 'daemon_stdout' format)
    - Sonic Pi 4.3–4.4 (reads spider.log, 'Token:' and 'Ports:' format)
    - Also tries psonic's built-in set_server_parameter_from_log as fallback

    Works on macOS, Linux and Windows.
    """
    log_dir = Path.home() / ".sonic-pi" / "log"

    # Try gui.log first (Sonic Pi 4.5+)
    gui_log = log_dir / "gui.log"
    if gui_log.exists():
        text = _read_log_file(gui_log)
        params = _extract_from_gui_log(text)
        if params:
            return params

    # Try spider.log (Sonic Pi 4.3–4.4)
    spider_log = log_dir / "spider.log"
    if spider_log.exists():
        text = _read_log_file(spider_log)
        params = _extract_from_spider_log(text)
        if params:
            return params

    return {}


class SonicPiTools:
    def __init__(self):
        host = os.getenv("SONIC_PI_HOST", "127.0.0.1")

        # Try autodetection first, fall back to env vars
        auto = _autodetect_sonic_pi_params()
        token = int(os.getenv("SONIC_PI_TOKEN", str(auto.get("token", 0))))
        gui_port = int(os.getenv("SONIC_PI_GUI_PORT", str(auto.get("gui_port", 0))))
        osc_port = int(os.getenv("SONIC_PI_OSC_PORT", str(auto.get("osc_port", 0))))

        if not token or not gui_port or not osc_port:
            raise RuntimeError(
                "No se pudieron detectar los parámetros de Sonic Pi. "
                "¿Está Sonic Pi abierto? Reinícialo e inténtalo de nuevo."
            )

        set_server_parameter(host, token, osc_port, gui_port)
        self._params = {"host": host, "token": token, "gui_port": gui_port, "osc_port": osc_port}

    def play_code(self, code: str) -> str:
        try:
            run(code)
            return "✅ Código ejecutado en Sonic Pi"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def stop_all(self) -> str:
        try:
            stop()
            return "⏹️ Todos los sonidos detenidos"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def generate_melody(self, scale="c4", bpm=120, length=8, instrument="piano") -> str:
        scales = {
            "c4": ["c4", "d4", "e4", "f4", "g4", "a4", "b4"],
            "a4": ["a4", "b4", "c5", "d5", "e5", "f5", "g5"],
            "pentatonic": ["c4", "d4", "f4", "g4", "a4"],
            "blues": ["c4", "eb4", "f4", "fb4", "g4", "bb4"],
        }
        notes = scales.get(scale.lower(), scales["c4"])
        melody = [random.choice(notes) for _ in range(length)]
        return f"""use_bpm {bpm}
use_synth :{instrument}
live_loop :melody do
  {' '.join([f'play :{note}, release: 0.2; sleep 0.25;' for note in melody])}
end"""

    def generate_beat(self, style="techno", bpm=120) -> str:
        beats = {
            "techno": {"kick": "bd_haus", "snare": "sn_dolf", "hihat": "hihat",
                      "pattern": ["kick", "hihat", "kick", "snare", "hihat", "kick", "hihat", "snare"]},
            "hiphop": {"kick": "bd_ada", "snare": "sn_dolf", "hihat": "hihat",
                      "pattern": ["kick", "hihat", "kick", "hihat", "snare", "hihat", "kick", "hihat"]},
            "dubstep": {"kick": "bd_ada", "snare": "sn_dolf", "hihat": "hihat",
                       "pattern": ["kick", "sleep", "kick", "sleep", "snare", "sleep", "kick", "snare"]},
            "house": {"kick": "bd_haus", "snare": "sn_dolf", "hihat": "hihat",
                     "pattern": ["kick", "hihat", "kick", "hihat", "kick", "hihat", "snare", "hihat"]}
        }
        beat = beats.get(style.lower(), beats["techno"])
        pattern_code = []
        for sound in beat["pattern"]:
            if sound == "sleep":
                pattern_code.append("sleep 0.25")
            else:
                pattern_code.append(f"sample :{beat[sound]}; sleep 0.25")
        return f"""use_bpm {bpm}
live_loop :beat do
  {' '.join(pattern_code)}
end"""

    def generate_chord_progression(self, chords=None, bpm=80, instrument="piano") -> str:
        if chords is None:
            chords = ["c4", "f4", "g4", "c4"]
        return f"""use_bpm {bpm}
use_synth :{instrument}
live_loop :chords do
  {' '.join([f'play chord(:{chord}, :m7), release: 2; sleep 2;' for chord in chords])}
end"""

    def generate_full_song(self, style="chill", bpm=120) -> str:
        styles = {
            "chill": {"melody_instrument": "piano", "bass_instrument": "fm",
                     "beat_style": "hiphop", "melody_scale": "c4", "bass_notes": ["c2", "f2", "g2", "c2"]},
            "techno": {"melody_instrument": "pluck", "bass_instrument": "tb303",
                      "beat_style": "techno", "melody_scale": "a4", "bass_notes": ["a2", "c3", "e3", "a2"]},
            "ambient": {"melody_instrument": "hollow", "bass_instrument": "dsaw",
                       "beat_style": None, "melody_scale": "pentatonic", "bass_notes": ["c2", "g2", "a2", "f2"]}
        }
        config = styles.get(style.lower(), styles["chill"])
        melody_code = self.generate_melody(
            scale=config["melody_scale"], bpm=bpm, length=16, instrument=config["melody_instrument"]
        )
        bass_code = f"""use_bpm {bpm}
use_synth :{config["bass_instrument"]}
live_loop :bass do
  {' '.join([f'play :{note}, release: 1.5; sleep 2;' for note in config["bass_notes"]])}
end"""
        beat_code = self.generate_beat(config["beat_style"], bpm) if config["beat_style"] else ""
        return f"""# Canción en estilo {style}
use_bpm {bpm}

{beat_code}

{bass_code}

{melody_code}"""