#!/usr/bin/env python3
"""Final, careful URLBlocklist syntax verdict — one chrome instance per
(port, policy) case, page served with a marker title, server-request and
title based verdict."""

import json
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CFT = Path(os.environ.get("JGU_CHROME", "/tmp/chrome-linux64/chrome"))
WEB_PORT = 8893
DOMAIN = "poltest.invalid"
SUB = "shop." + DOMAIN
POLICY_DIR = Path("/tmp/jgu-policy-final")

REQ: list[str] = []


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        REQ.append(self.path)
        body = b"<html><head><title>SPONGO_LOADED</title></head><body>hi</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def devtools(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
        return json.loads(r.read().decode())


def new_tab(port, url):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{url}", method="PUT")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def run(patterns, url, port):
    if POLICY_DIR.exists():
        shutil.rmtree(POLICY_DIR)
    POLICY_DIR.mkdir(parents=True)
    hdrs = {}
    if patterns is not None:
        (POLICY_DIR / "test.json").write_text(json.dumps({"URLBlocklist": patterns}))
    profile = Path(f"/tmp/jgu-final-prof-{port}")
    shutil.rmtree(profile, ignore_errors=True)
    proc = subprocess.Popen(
        [str(CFT), "--headless=new", "--disable-gpu", "--no-first-run",
         f"--user-data-dir={profile}", f"--load-policy={POLICY_DIR}",
         "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE localhost",
         f"--remote-debugging-port={port}", "--remote-allow-origins=*",
         "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            time.sleep(0.5)
            try:
                devtools(port)
                break
            except Exception:
                if proc.poll() is not None:
                    return "EXIT"
        before = len(REQ)
        time.sleep(2.0)  # let policies settle
        tab = new_tab(port, url)
        title = ""
        for _ in range(12):
            time.sleep(0.5)
            try:
                tabs = devtools(port)
                t = [x for x in tabs if x.get("id") == tab.get("id")]
                if t and t[0].get("title"):
                    title = t[0]["title"]
                    break
            except Exception:
                break
        time.sleep(0.8)
        got = len(REQ) > before
        if title == "SPONGO_LOADED" or got:
            return "LOADED" + (f" title={title!r}" if got else "")
        return f"BLOCKED title={title!r}"
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()
        for _ in range(20):
            time.sleep(0.3)
            try:
                devtools(port)
            except Exception:
                break


def main():
    server = ThreadingHTTPServer(("127.0.0.1", WEB_PORT), H)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = 9800
    cases = [
        ("CONTROL no-policy", None, SUB),
        ("CONTROL nomatch", ["*://*zzz-nomatch-000.com/*"], SUB),
        ("A *://*D/* bare", ["*://*" + DOMAIN + "/*"], DOMAIN),
        ("A sub", ["*://*" + DOMAIN + "/*"], SUB),
        ("B *.D bare", ["*://*." + DOMAIN + "/*"], DOMAIN),
        ("B sub", ["*://*." + DOMAIN + "/*"], SUB),
        ("D *://D/* bare", ["*://" + DOMAIN + "/*"], DOMAIN),
        ("D sub", ["*://" + DOMAIN + "/*"], SUB),
        ("E bareD bare", [DOMAIN], DOMAIN),
        ("E sub", [DOMAIN], SUB),
    ]
    for name, pats, host in cases:
        port += 1
        print(f"  {name:26s} -> {run(pats, f'http://{host}:{WEB_PORT}/', port)}")
    server.shutdown()


if __name__ == "__main__":
    main()
