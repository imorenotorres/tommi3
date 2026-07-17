"""
Sonic Pi Bridge — HTTP-to-OSC bridge for browser-based Sonic Pi control.

Run this script alongside Sonic Pi to allow TOMMI's Sonic Composer
to send code to your local Sonic Pi instance from the browser.

Usage:
    python sonic_bridge.py

Requirements:
    pip install python-sonic

The bridge auto-detects Sonic Pi's connection parameters.
"""

import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add base directory to path for sonic_pi_tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "base"))
from sonic_pi_tools import SonicPiTools

BRIDGE_PORT = 8001
sp = None


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
            self._json(200, {"status": "ok", "sonic_pi": sp is not None})
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
                result = sp.play_code(code)
                self._json(200, {"status": result})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == "/stop":
            try:
                result = sp.stop_all()
                self._json(200, {"status": result})
            except Exception as e:
                self._json(500, {"error": str(e)})

        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print(f"  {args[0]}")


def main():
    global sp
    print("=" * 50)
    print("  Sonic Pi Bridge")
    print("=" * 50)
    print()

    try:
        sp = SonicPiTools()
        print(f"  Connected to Sonic Pi: {sp._params}")
    except Exception as e:
        print(f"  ERROR: Cannot connect to Sonic Pi: {e}")
        print("  Make sure Sonic Pi is open and try again.")
        sys.exit(1)

    print(f"  Bridge running at http://localhost:{BRIDGE_PORT}")
    print()
    print("  Ready! Open Sonic Composer in your browser.")
    print("  Press Ctrl+C to stop.")
    print()

    server = HTTPServer(("127.0.0.1", BRIDGE_PORT), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Bridge stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
