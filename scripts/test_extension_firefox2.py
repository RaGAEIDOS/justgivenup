#!/usr/bin/env python3
"""Decisive Firefox ESR check of the SHIPPED rules.json:

fresh profile, uninstall previous state, single navigation to
http://example.com/ (injected into rules first). Verdict from the
screenshot bytes: identical to the plain page (no redirect) or different
(interstitial / blocked).
"""

import json
import os
import shutil
import subprocess
import sys
import time
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = Path("/tmp/jgu-fnx-profile")
EXT = Path("/tmp/jgu-fnx-ext")

def main():
    shutil.rmtree(EXT, ignore_errors=True)
    shutil.rmtree(PROFILE, ignore_errors=True)
    PROFILE.mkdir(parents=True)

    shutil.copytree(ROOT / "extension", EXT)
    rules = json.loads((EXT / "rules.json").read_text())
    for r in rules[:2]:
        r["condition"]["requestDomains"] = ["example.com"]
    (EXT / "rules.json").write_text(json.dumps(rules))

    ext_dir = PROFILE / "extensions" / "justgivenup@ragaeidos.github.io"
    ext_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EXT, ext_dir)
    shutil.copy(ROOT / "extension" / "manifest.firefox.json", ext_dir / "manifest.json")
    (PROFILE / "user.js").write_text(
        'user_pref("xpinstall.signatures.required", false);\n'
        'user_pref("extensions.autoDisableScopes", 0);\n')

    shot = Path("/tmp/jgu-fnx-shot.png")
    ff = subprocess.Popen(
        ["firefox-esr", "--headless", "--profile", str(PROFILE),
         "--window-size=1280,900", "--screenshot", str(shot),
         "http://example.com/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ff.wait(timeout=60)
    except subprocess.TimeoutExpired:
        ff.kill()

    addons = json.loads((PROFILE / "addons.json").read_text())
    ours = [a for a in addons.get("addons", []) if "justgivenup" in a.get("id", "")]
    print("registered:", bool(ours), "version:", ours[0].get("version") if ours else "-")
    if shot.exists():
        h = hashlib.md5(shot.read_bytes()).hexdigest()
        print(f"screenshot: {shot.stat().st_size} bytes md5={h}")
    else:
        print("screenshot: MISSING")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
