#!/usr/bin/env python3
"""
Sonic Pi Bridge — connects your browser to Sonic Pi.

This is a self-contained script. Place it anywhere and run:
    python3 sonic_bridge.py

It will:
1. Auto-detect Sonic Pi's connection parameters
2. Start a tiny HTTP server on localhost:8001
3. The browser sends code here, and this script forwards it to Sonic Pi

Requirements:
    pip3 install python-sonic
"""

import json
import os
import re
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ── Check dependencies ──

try:
    from psonic import set_server_parameter, run, stop, start_recording, stop_recording, save_recording
except ImportError:
    print()
    print("  ERROR: python-sonic is not installed.")
    print("  Use start_bridge.command (Mac) or start_bridge.bat (Windows)")
    print("  to set up automatically, or install manually:")
    print("    pip install python-sonic")
    print()
    input("  Press Enter to exit...")
    sys.exit(1)


# ── Sonic Pi auto-detection ──

def _extract_from_gui_log(text):
    """Sonic Pi 4.5+ (gui.log, 'daemon_stdout' format)."""
    values = []
    for line in text.splitlines():
        m = re.search(r"daemon_stdout:\s*(-?\d+)", line)
        if m:
            values.append(int(m.group(1)))
    if len(values) >= 8:
        return {"gui_port": values[1], "osc_port": values[2], "token": values[7]}
    return {}


def _extract_from_spider_log(text):
    """Sonic Pi 4.3–4.4 (spider.log, 'Token:' format)."""
    token = server_port = osc_port = None
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
        return {"gui_port": osc_port or 4560, "osc_port": server_port, "token": token}
    return {}


def _read_log(path):
    """Read a log file, handling both binary and text formats."""
    try:
        result = subprocess.run(
            ["strings", str(path)], capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, OSError):
        pass
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return ""


def detect_sonic_pi():
    """Auto-detect Sonic Pi connection parameters."""
    log_dir = Path.home() / ".sonic-pi" / "log"

    gui_log = log_dir / "gui.log"
    if gui_log.exists():
        params = _extract_from_gui_log(_read_log(gui_log))
        if params:
            return params

    spider_log = log_dir / "spider.log"
    if spider_log.exists():
        params = _extract_from_spider_log(_read_log(spider_log))
        if params:
            return params

    return {}


# ── HTTP Bridge Server ──

BRIDGE_PORT = 8001
RECORDING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
sp_connected = False
is_recording = False


def play_code(code):
    run(code)
    return "Code sent to Sonic Pi"


def stop_all():
    stop()
    return "All sounds stopped"


def rec_start():
    global is_recording
    start_recording()
    is_recording = True
    return "Recording started"


def rec_stop():
    global is_recording
    os.makedirs(RECORDING_DIR, exist_ok=True)
    filepath = os.path.join(RECORDING_DIR, "composition.wav")
    stop_recording()
    import time
    time.sleep(0.5)
    save_recording(filepath)
    is_recording = False
    return filepath


class BridgeHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self, *_):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/ping":
            self._json(200, {"status": "ok", "sonic_pi": sp_connected, "recording": is_recording})
        elif self.path == "/record/download":
            filepath = os.path.join(RECORDING_DIR, "composition.wav")
            if os.path.exists(filepath):
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Disposition", "attachment; filename=composition.wav")
                size = os.path.getsize(filepath)
                self.send_header("Content-Length", str(size))
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._json(404, {"error": "No recording found. Record something first."})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""

        if self.path == "/play":
            try:
                data = json.loads(body)
                code = data.get("code", "")
                if not code:
                    self._json(400, {"error": "no code"})
                    return
                result = play_code(code)
                self._json(200, {"status": result})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == "/stop":
            try:
                result = stop_all()
                self._json(200, {"status": result})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == "/record/start":
            try:
                result = rec_start()
                self._json(200, {"status": result})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == "/record/stop":
            try:
                filepath = rec_stop()
                self._json(200, {"status": "Recording saved", "file": filepath})
            except Exception as e:
                self._json(500, {"error": str(e)})

        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print(f"  {args[0]}")


# ── Main ──

def main():
    global sp_connected

    print()
    print("=" * 50)
    print("  Sonic Pi Bridge")
    print("=" * 50)
    print()

    # Detect Sonic Pi
    params = detect_sonic_pi()
    if not params:
        print("  ERROR: Cannot detect Sonic Pi.")
        print("  Make sure Sonic Pi is open and try again.")
        print()
        input("  Press Enter to exit...")
        sys.exit(1)

    # Connect
    try:
        set_server_parameter("127.0.0.1", params["token"], params["osc_port"], params["gui_port"])
        sp_connected = True
        print(f"  Connected to Sonic Pi")
        print(f"    Token: {params['token']}")
        print(f"    Port:  {params['osc_port']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        input("  Press Enter to exit...")
        sys.exit(1)

    # Test with a silent command
    try:
        run("# bridge connected")
        print("  Connection verified!")
    except Exception:
        pass

    print()
    print(f"  Bridge running at http://localhost:{BRIDGE_PORT}")
    print()
    print("  Ready! Open Sonic Composer in your browser.")
    print("  Press Ctrl+C to stop.")
    print("=" * 50)
    print()

    server = HTTPServer(("127.0.0.1", BRIDGE_PORT), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Bridge stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
