#!/usr/bin/env python3
"""E2E test: load the extension in Chrome, verify DNR redirects a blocked
navigation to the extension interstitial (blocked.html).

- serves a local page on 127.0.0.1:8899
- rules.json (test copy) contains `localhost`
- expects the tab URL to become chrome-extension://.../blocked.html
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PORT_DEBUG = 9333
PORT_WEB = 8899
EXT = "/tmp/jgu-ext-test"
PROFILE = "/tmp/jgu-chrome-prof"
CHROME_BIN = os.environ.get("JGU_CHROME", "/tmp/chrome-linux64/chrome")


def get(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def main() -> int:
    Path("/tmp/jgu-webroot").mkdir(exist_ok=True)
    (Path("/tmp/jgu-webroot") / "index.html").write_text(
        "<html><body>LOCAL PAGE OK</body></html>")

    web = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT_WEB), "--bind", "127.0.0.1",
         "--directory", "/tmp/jgu-webroot"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run(["pkill", "-f", "user-data-dir=" + PROFILE], stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    try:
        Path(PROFILE).rename(Path(PROFILE + ".old"))
    except OSError:
        pass

    chrome = subprocess.Popen(
        [CHROME_BIN,
         "--headless=new",
         "--disable-gpu",
         "--no-first-run",
         "--no-default-browser-check",
         f"--user-data-dir={PROFILE}",
         f"--load-extension={EXT}",
         f"--remote-debugging-port={PORT_DEBUG}",
         "--remote-allow-origins=*",
         "about:blank"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    ok = False
    try:
        # wait for devtools
        tabs = None
        for _ in range(40):
            time.sleep(0.5)
            if chrome.poll() is not None:
                print("chrome exited early:")
                print(chrome.stdout.read()[-3000:])
                return 2
            try:
                tabs = get(f"http://127.0.0.1:{PORT_DEBUG}/json/list")
                break
            except Exception:
                continue
        if tabs is None:
            print("devtools never came up")
            return 2

        # is the extension loaded?
        targets = get(f"http://127.0.0.1:{PORT_DEBUG}/json/list")
        ext_targets = [t for t in targets if t.get("type") == "service_worker"
                       and "jgu-ext-test" in t.get("url", "")]
        print("extension service_worker targets:", len(ext_targets))
        for t in ext_targets:
            print("  ", t["url"])

        # open the local test page (blocked by our injected rule)
        try:
            tab = get(f"http://127.0.0.1:{PORT_DEBUG}/json/new?"
                      f"http://localhost:{PORT_WEB}/", method="PUT")
        except urllib.error.HTTPError as e:
            # older Chrome wants GET for json/new
            tab = get(f"http://127.0.0.1:{PORT_DEBUG}/json/new?"
                      f"http://localhost:{PORT_WEB}/")
            print("PUT failed, GET ok?", e.code)

        final_url = ""
        for _ in range(30):
            time.sleep(0.5)
            tabs = get(f"http://127.0.0.1:{PORT_DEBUG}/json/list")
            for t in tabs:
                if t.get("id") == tab.get("id"):
                    final_url = t.get("url", "")
                    break
            if "blocked.html" in final_url or final_url.startswith(
                    ("http://localhost", "http://127.0.0.1")) and "blocked" not in final_url:
                if "blocked.html" in final_url:
                    break

        print("final tab url:", final_url)
        if "blocked.html" in final_url:
            print("PASS: navigation redirected to the interstitial")
            ok = True
        elif final_url.startswith("http://localhost"):
            print("FAIL: page loaded normally -- DNR redirect did not apply")
        else:
            print("FAIL: unexpected url:", final_url)

        # check extension errors surface
        for t in get(f"http://127.0.0.1:{PORT_DEBUG}/json/list"):
            if t.get("type") == "service_worker" and "jgu-ext-test" in t.get("url", ""):
                print("SW url:", t["url"])
    finally:
        subprocess.run(["pkill", "-f", "user-data-dir=" + PROFILE],
                       stderr=subprocess.DEVNULL)
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        web.terminate()

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
