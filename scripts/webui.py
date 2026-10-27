#!/usr/bin/env python3
"""Visual admin panel for the daily greeting mail system.

Run:  python webui.py        -> open http://127.0.0.1:8765
Serves webui.html plus a small JSON API that reads/writes config.json.

Sharing:
  config.json "listen": "0.0.0.0"  -> LAN users can open http://<your-ip>:8765
  config.json "listen": "127.0.0.1"-> only this machine
  Access is protected by "admin_password" (login required).
"""
import hashlib
import json
import os
import shutil
import socket
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import daily_greeting as dg

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(ROOT, "config.json")
BACKUP = os.path.join(ROOT, "config.backup.json")
HTML = os.path.join(ROOT, "webui.html")
PORT = 8765
COOKIE = "gmauth"


def cfg_dict():
    return dg.load_config()


def auth_token():
    """Token derived from the current admin password."""
    pw = cfg_dict().get("admin_password", "")
    return hashlib.sha256(("greeting-mail|" + pw).encode()).hexdigest()


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8",
              cookie=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def _authed(self):
        cookies = self.headers.get("Cookie", "")
        for part in cookies.split(";"):
            if part.strip().startswith(COOKIE + "="):
                return part.strip().split("=", 1)[1] == auth_token()
        return False

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            with open(HTML, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")

        if not self._authed():
            return self._send(401, {"error": "unauthorized"})

        if path == "/api/config":
            try:
                return self._send(200, cfg_dict())
            except Exception as e:
                return self._send(500, {"error": str(e)})
        if path == "/api/info":
            return self._send(200, {"lan_ips": lan_ips(), "port": PORT,
                                    "listen": cfg_dict().get("listen", "0.0.0.0")})
        if path == "/api/logs":
            p = os.path.join(ROOT, "logs", "greeting.log")
            text = ""
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    text = "".join(f.readlines()[-80:])
            return self._send(200, {"log": text})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            data = self._body()

            if self.path == "/api/login":
                if data.get("password", "") == cfg_dict().get("admin_password", ""):
                    tok = auth_token()
                    return self._send(200, {"ok": True},
                                      cookie=f"{COOKIE}={tok}; Path=/; HttpOnly; SameSite=Lax")
                return self._send(403, {"error": "密码错误"})

            if not self._authed():
                return self._send(401, {"error": "unauthorized"})

            if self.path == "/api/save":
                cfg = data.get("config")
                if not isinstance(cfg, dict):
                    return self._send(400, {"error": "invalid config payload"})
                json.dumps(cfg)  # validate serializable
                if os.path.exists(CONFIG):
                    shutil.copy2(CONFIG, BACKUP)
                with open(CONFIG, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
                return self._send(200, {"ok": True, "backup": "config.backup.json"})

            if self.path == "/api/preview":
                slot = data.get("slot")
                if slot not in dg.SLOTS:
                    return self._send(400, {"error": "slot must be morning/midday/evening"})
                cfg = dg.load_config()
                r = dg.run_slot(cfg, slot, dry_run=True)
                return self._send(200, r)

            if self.path == "/api/send":
                slot = data.get("slot")
                if slot not in dg.SLOTS:
                    return self._send(400, {"error": "slot must be morning/midday/evening"})
                cfg = dg.load_config()
                r = dg.run_slot(cfg, slot)
                return self._send(200, r)

            return self._send(404, {"error": "not found"})
        except Exception as e:
            dg.log(f"WEBUI ERROR: {type(e).__name__}: {e}")
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        pass  # keep console quiet


if __name__ == "__main__":
    listen = cfg_dict().get("listen", "0.0.0.0")
    try:
        server = ThreadingHTTPServer((listen, PORT), Handler)
    except OSError:
        # port already taken -> another instance is running; exit quietly
        print(f"Port {PORT} already in use, admin panel likely already running.")
        raise SystemExit(0)
    scope = "LAN (0.0.0.0)" if listen == "0.0.0.0" else "local only (127.0.0.1)"
    print(f"Greeting Mail Admin [{scope}]: http://127.0.0.1:{PORT}")
    server.serve_forever()
