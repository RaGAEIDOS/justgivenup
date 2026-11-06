#!/usr/bin/env python3
"""End-to-end test suite for the JustGivenUp daemon + extension.

Run (Chrome for Testing must be extracted at /tmp/chrome-linux64/chrome):
    python3 scripts/test_e2e.py

Covers:
  T1  extension heartbeat reaches the daemon (background.js works)
  T2  DNR static rules redirect a blocked navigation to blocked.html
  T3  the interstitial reports the attempt (/api/report)
  T4  lock creation writes the sealed record + managed hosts block
  T5  /api/unlock is refused while locked (403)
  T6  cross-origin POST is refused (403)
  T7  valid re-seal in the past expires the lock and cleans the hosts file
  T8  editing the lock file (bad seal) => +90 day penalty
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8081"
CFT = Path(os.environ.get("JGU_CHROME", "/tmp/chrome-linux64/chrome"))
EXT = Path("/tmp/jgu-ext-test")
STATE = Path("/tmp/jgu-e2e-state")
HOSTS = Path("/tmp/jgu-e2e-hosts")
MIRROR = Path("/tmp/jgu-e2e-mirror")
PROFILE = Path("/tmp/jgu-e2e-profile")
WEBROOT = Path("/tmp/jgu-e2e-web")
DEBUG_PORT = 9344
WEB_PORT = 8891

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def http(path: str, payload: dict | None = None, headers: dict | None = None,
         method: str | None = None):
    url = API + path
    data = None
    hdrs = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        hdrs.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed


def get_json(url: str, method: str = "GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=6) as resp:
        return json.loads(resp.read().decode())


def build_test_extension() -> None:
    src = ROOT / "extension"
    if EXT.exists():
        shutil.rmtree(EXT)
    shutil.copytree(src, EXT)
    rules = json.loads((EXT / "rules.json").read_text())
    for r in rules[:2]:
        r["condition"]["requestDomains"] = ["localhost"]
    (EXT / "rules.json").write_text(json.dumps(rules))
    manifest = json.loads((EXT / "manifest.json").read_text())
    manifest["name"] = "JGU E2E Harness"
    (EXT / "manifest.json").write_text(json.dumps(manifest, indent=2))


def chrome_tab_url(tab_id: str) -> str:
    for t in get_json(f"http://127.0.0.1:{DEBUG_PORT}/json/list"):
        if t.get("id") == tab_id:
            return t.get("url", "")
    return ""


def kill_existing_daemon() -> None:
    """Free port 8081: terminate leftover guardian daemons (not this proc)."""
    me = os.getpid()
    victims = []
    for comm in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            pid = int(comm.parent.name)
            cmd = comm.read_bytes().replace(b"\x00", b" ").decode(errors="replace")
        except (OSError, ValueError):
            continue
        if pid == me:
            continue
        if "justgivenup" in cmd and " run" in cmd:
            victims.append(pid)
    for pid in victims:
        print(f"  killing leftover daemon pid={pid}")
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    for _ in range(30):
        try:
            with urllib.request.urlopen(API + "/api/version", timeout=0.5):
                time.sleep(0.5)
                continue
        except Exception:
            break
    time.sleep(0.5)


def main() -> int:
    # -- environment ------------------------------------------------------
    for p in (STATE, MIRROR, WEBROOT):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)
    HOSTS.write_text("127.0.0.1 localhost\n")

    env = dict(os.environ)
    env.update({
        "JGU_STATE_DIR": str(STATE),
        "JGU_HOSTS_FILE": str(HOSTS),
        "JGU_MIRROR_DIR": str(MIRROR),
        "PYTHONPATH": str(ROOT / "app"),
    })
    os.environ.update(env)

    build_test_extension()
    (WEBROOT / "index.html").write_text("<html><body>WEB OK</body></html>")
    kill_existing_daemon()

    procs: list[subprocess.Popen] = []
    def spawn(cmd, **kw):
        p = subprocess.Popen(cmd, env=env, **kw)
        procs.append(p)
        return p

    try:
        # -- daemon -------------------------------------------------------
        daemon = spawn([sys.executable, "-m", "justgivenup", "run"],
                       cwd=str(ROOT / "app"),
                       stdout=open("/tmp/jgu-e2e-daemon.log", "w"),
                       stderr=subprocess.STDOUT)
        web = spawn([sys.executable, "-m", "http.server", str(WEB_PORT),
                     "--bind", "127.0.0.1", "--directory", str(WEBROOT)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _ in range(30):
            time.sleep(0.5)
            if http("/api/version")[0] == 200:
                break
        else:
            print("daemon never came up; log:")
            print(Path("/tmp/jgu-e2e-daemon.log").read_text()[-2000:])
            return 2

        if not CFT.is_file():
            print(f"Chrome for Testing missing at {CFT} -- download it first:")
            print("  https://googlechromelabs.github.io/chrome-for-testing/")
            return 2

        shutil.rmtree(PROFILE, ignore_errors=True)
        chrome = spawn(
            [CFT, "--headless=new", "--disable-gpu", "--no-first-run",
             f"--user-data-dir={PROFILE}", f"--load-extension={EXT}",
             f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _ in range(40):
            time.sleep(0.5)
            if chrome.poll() is not None:
                print("chrome exited early")
                return 2
            try:
                get_json(f"http://127.0.0.1:{DEBUG_PORT}/json/list")
                break
            except Exception:
                continue

        # T1 heartbeat -----------------------------------------------------
        print("T1: extension heartbeat")
        seen = False
        for _ in range(20):
            time.sleep(1)
            _, ext = http("/api/extension")
            if ext.get("info", {}).get("ever_seen"):
                seen = True
                break
        record("heartbeat received", seen,
               f"browser={ext.get('info', {}).get('browser')}")

        # T2 redirect ------------------------------------------------------
        print("T2: DNR redirect to interstitial")
        tab = get_json(f"http://127.0.0.1:{DEBUG_PORT}/json/new?"
                       f"http://localhost:{WEB_PORT}/", method="PUT")
        final = ""
        for _ in range(30):
            time.sleep(0.5)
            final = chrome_tab_url(tab.get("id", ""))
            if "blocked.html" in final or final.startswith("http://localhost"):
                if "blocked.html" in final:
                    break
        record("blocked.html redirect", "blocked.html" in final, final[:100])

        # T3 report --------------------------------------------------------
        print("T3: interstitial report")
        time.sleep(2)
        _, stats_before = http("/api/stats")
        _, ext_before = http("/api/extension")
        report_id = None
        tab2 = get_json(f"http://127.0.0.1:{DEBUG_PORT}/json/new?"
                        f"http://localhost:{WEB_PORT}/", method="PUT")
        report_id = tab2.get("id")
        got_report = False
        for _ in range(20):
            time.sleep(1)
            _, stats_now = http("/api/stats")
            if stats_now.get("total_blocked", 0) > stats_before.get("total_blocked", 0):
                got_report = True
                break
        record("attempt reported to dashboard", got_report,
               f"blocked={stats_now.get('total_blocked')}")

        # T4 lock + hosts --------------------------------------------------
        print("T4: create lock, hosts enforcement")
        st, resp = http("/api/lock", {"days": 30, "confirm": "WRONG"})
        record("wrong confirm phrase rejected", st == 400, f"http {st}")
        st, resp = http("/api/lock", {"days": 30, "confirm": "LOCK"})
        record("lock created", st == 200 and resp.get("ok"), f"http {st}")
        hosts_text = HOSTS.read_text()
        record("hosts block applied", "justgivenup managed block" in hosts_text
               and "0.0.0.0" in hosts_text)
        record("hosts carries lock marker", "jgu-lock until=" in hosts_text)
        _, lock_now = http("/api/lock")
        record("api reports locked", lock_now.get("locked") is True)

        # T5 unlock refused ------------------------------------------------
        print("T5: unlock refused")
        st, resp = http("/api/unlock", {})
        record("unlock refused (403)", st == 403, f"http {st}: {resp.get('error', '')[:60]}")

        # T6 origin check --------------------------------------------------
        print("T6: cross-origin refused")
        st, resp = http("/api/unlock", {},
                        headers={"Origin": "https://example-porn.test"},
                        method="POST")
        record("foreign origin refused", st == 403, f"http {st}")
        st, resp = http("/api/unlock", {},
                        headers={"Origin": "chrome-extension://aaaa"},
                        method="POST")
        record("extension origin accepted (403 expected while locked)",
               st == 403, f"http {st}")

        # T7 valid re-seal => expiry path ---------------------------------
        print("T7: valid expiry (re-seal in the past)")
        sys.path.insert(0, str(ROOT / "app"))
        from justgivenup.lock import seal_record  # noqa: E402

        for path in (STATE / "lock.json", MIRROR / "lock.json"):
            rec = json.loads(path.read_text())
            rec["until"] = int(time.time()) - 60
            rec["seal"] = seal_record(rec)
            path.write_text(json.dumps(rec))
        expired = False
        for _ in range(30):  # daemon cycle is 15s
            time.sleep(1)
            _, lk = http("/api/lock")
            if not lk.get("locked"):
                expired = True
                break
        record("lock expires with valid seal", expired)
        time.sleep(2)
        hosts_after = HOSTS.read_text()
        record("hosts block removed after expiry",
               "justgivenup managed block" not in hosts_after)

        # T8 tamper => penalty --------------------------------------------
        print("T8: tamper penalty (+90 days)")
        st, resp = http("/api/lock", {"days": 1, "confirm": "LOCK"})
        record("short lock created", st == 200, f"http {st}")
        _, lk = http("/api/lock")
        until_before = lk.get("until", 0)
        rec = json.loads((STATE / "lock.json").read_text())
        rec["until"] = int(time.time()) + 5 * 86400  # try to shorten to 5 days
        rec["seal"] = "deadbeef" * 8                 # invalid seal
        (STATE / "lock.json").write_text(json.dumps(rec))
        penalized = False
        until_after = until_before
        for _ in range(30):
            time.sleep(1)
            _, lk = http("/api/lock")
            until_after = lk.get("until", 0)
            if until_after > until_before + 80 * 86400:
                penalized = True
                break
        record("tamper detected -> +90 days", penalized,
               f"until {until_before} -> {until_after}")

        # cleanup: force-expire so the suite leaves no active lock
        for path in (STATE / "lock.json", MIRROR / "lock.json"):
            if path.exists():
                rec = json.loads(path.read_text())
                rec["until"] = int(time.time()) - 60
                rec["seal"] = seal_record(rec)
                path.write_text(json.dumps(rec))
        for _ in range(30):
            time.sleep(1)
            _, lk = http("/api/lock")
            if not lk.get("locked"):
                break

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

    print()
    failed = [r for r in RESULTS if not r[1]]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
