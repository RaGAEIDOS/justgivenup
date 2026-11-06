#!/usr/bin/env python3
"""Decisive Firefox ESR check: block-only rule, fresh profile."""

import json
import shutil
import subprocess
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = Path("/tmp/jgu-fnx2-profile")
EXT = Path("/tmp/jgu-fnx2-ext")

shutil.rmtree(PROFILE, ignore_errors=True)
shutil.rmtree(EXT, ignore_errors=True)
PROFILE.mkdir(parents=True)

shutil.copytree(ROOT / "extension", EXT)
# block-only: no redirect, no transform, single rule for example.com
rules = [{
    "id": 1, "priority": 1,
    "action": {"type": "block"},
    "condition": {
        "requestDomains": ["example.com"],
        "resourceTypes": ["main_frame", "sub_frame", "stylesheet", "script",
                          "image", "font", "xmlhttprequest", "media",
                          "websocket", "ping", "other"],
    },
}]
(EXT / "rules.json").write_text(json.dumps(rules))

ext_dir = PROFILE / "extensions" / "justgivenup@ragaeidos.github.io"
ext_dir.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(EXT, ext_dir)
shutil.copy(ROOT / "extension" / "manifest.firefox.json", ext_dir / "manifest.json")
(PROFILE / "user.js").write_text(
    'user_pref("xpinstall.signatures.required", false);\n'
    'user_pref("extensions.autoDisableScopes", 0);\n')

shot = Path("/tmp/jgu-fnx2-shot.png")
ff = subprocess.Popen(
    ["firefox-esr", "--headless", "--profile", str(PROFILE),
     "--window-size=1280,900", "--screenshot", str(shot),
     "http://example.com/"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ff.wait(timeout=60)
except subprocess.TimeoutExpired:
    ff.kill()

if shot.exists():
    print(f"screenshot: {shot.stat().st_size} bytes md5={hashlib.md5(shot.read_bytes()).hexdigest()}")
else:
    print("screenshot: MISSING")

d = json.loads((PROFILE / "extensions.json").read_text())
for a in d.get("addons", []):
    if "justgivenup" in a.get("id", ""):
        print("addon active:", a.get("active"), "version:", a.get("version"))

print("done")
