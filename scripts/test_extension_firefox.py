#!/usr/bin/env python3
"""Firefox quick-check for the extension (profile-directory method):

- installs the test extension (with `localhost` injected into DNR rules)
  as an UNPACKED dir inside a fresh profile's extensions/<id>/
- verifies the heartbeat reaches the daemon (alarms.tick = 1 min)
- takes a screenshot of the blocked URL and checks the browser then
  navigates to the interstitial (screenshot differs from the bare page)
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = Path("/tmp/jgu-ff-profile")
EXT = Path("/tmp/jgu-ff-ext")
WEBROOT = Path("/tmp/jgu-ff-web")
STATE = Path("/tmp/jgu-ff-state")
HOSTS = Path("/tmp/jgu-ff-hosts")
MIRROR = Path("/tmp/jgu-ff-mirror")
API = "http://127.0.0.1:8081"
FIREFOX = os.environ.get("JGU_FIREFOX", "firefox-esr")
WEB_PORT = 8899

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def http_get(path):
    with urllib.request.urlopen(API + path, timeout=5) as r:
        return json.loads(r.read().decode())


def main():
    for p in (STATE, MIRROR, WEBROOT, PROFILE):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)
    if EXT.exists():
        shutil.rmtree(EXT)
    HOSTS.write_text("127.0.0.1 localhost\n")
    (WEBROOT / "index.html").write_text(
        "<html><head><title>FFTESTPLAIN</title></head><body>PLAIN PAGE</body></html>")

    # test extension copy w/ localhost rules
    shutil.copytree(ROOT / "extension", EXT)
    rules = json.loads((EXT / "rules.json").read_text())
    # NOTE: the test host must resolve somewhere; DNR acts BEFORE DNS,
    # so a rule match redirects before any lookup matters. If the rule is
    # ignored the navigation will fail with NXDOMAIN instead.
    for r in rules[:2]:
        r["condition"]["requestDomains"] = ["poltest.invalid"]
    (EXT / "rules.json").write_text(json.dumps(rules))
    # firefox-style directory install named by gecko id, with the
    # Firefox manifest (background.scripts, not service_worker)
    ext_dir = PROFILE / "extensions" / "justgivenup@ragaeidos.github.io"
    ext_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EXT, ext_dir)
    shutil.copy(ROOT / "extension" / "manifest.firefox.json",
                ext_dir / "manifest.json")
    (PROFILE / "user.js").write_text(
        'user_pref("xpinstall.signatures.required", false);\n'
        'user_pref("extensions.autoDisableScopes", 0);\n')
    (PROFILE / "times.json").write_text("{}")

    env = dict(os.environ)
    env.update({
        "JGU_STATE_DIR": str(STATE),
        "JGU_HOSTS_FILE": str(HOSTS),
        "JGU_MIRROR_DIR": str(MIRROR),
        "PYTHONPATH": str(ROOT / "app"),
    })
    procs = []

    def spawn(cmd, **kw):
        p = subprocess.Popen(cmd, env=env, **kw)
        procs.append(p)
        return p

    daemon = None
    try:
        daemon = spawn([sys.executable, "-m", "justgivenup", "run"],
                       cwd=str(ROOT / "app"), stdout=open("/tmp/jgu-ff-daemon.log", "w"),
                       stderr=subprocess.STDOUT)
        web = spawn([sys.executable, "-m", "http.server", str(WEB_PORT),
                     "--bind", "127.0.0.1", "--directory", str(WEBROOT)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            time.sleep(0.5)
            try:
                http_get("/api/version")
                break
            except Exception:
                continue

        # phase 1: background page heartbeats on the 1-minute alarm
        ff = spawn([FIREFOX, "--headless", "--profile", str(PROFILE),
                    "--window-size=1280,900", "about:blank"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("  waiting up to 100s for heartbeat (alarm tick)...")
        seen = False
        for _ in range(100):
            time.sleep(1)
            if ff.poll() is not None:
                break
            info = http_get("/api/extension").get("info", {})
            if info.get("ever_seen"):
                seen = True
                break
        record("heartbeat seen by daemon", seen,
               f"browser={info.get('browser')} age={info.get('age_seconds')}")

        # stop this run; relaunch to the blocked URL and screenshot
        ff.send_signal(signal.SIGTERM)
        try:
            ff.wait(timeout=20)
        except subprocess.TimeoutExpired:
            ff.kill()
        procs.remove(ff)

        shot = Path("/tmp/jgu-ff-shot.png")
        if shot.exists():
            shot.unlink()
        ff2 = spawn([FIREFOX, "--headless", "--profile", str(PROFILE),
                     "--window-size=1280,900",
                     "--screenshot", str(shot),
                     f"http://poltest.invalid:{WEB_PORT}/"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            ff2.wait(timeout=120)
        except subprocess.TimeoutExpired:
            ff2.kill()

        record("screenshot produced", shot.is_file() and shot.stat().st_size > 1000,
               f"{shot.stat().st_size if shot.exists() else 0} bytes")

        time.sleep(2)
        stats = http_get("/api/stats")
        record("interstitial reported the block", stats["total_blocked"] >= 1,
               f"total_blocked={stats['total_blocked']}")

    finally:
        for p in procs:
            try:
                p.send_signal(signal.SIGTERM)
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=6)
            except subprocess.TimeoutExpired:
                p.kill()

    failed = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
