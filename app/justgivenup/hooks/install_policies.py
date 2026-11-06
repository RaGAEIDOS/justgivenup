#!/usr/bin/env python3
"""Install / remove the enterprise browser policies for JustGivenUp!.

Google Chrome / Chromium / Edge / Brave:
  /etc/opt/chrome/policies/managed/justgivenup.json
  /etc/opt/microsoft-edge/policies/managed/justgivenup.json
  /etc/chromium/policies/managed/justgivenup.json
  /etc/opt/brave.com/brave/policies/managed/justgivenup.json
  -> URLBlocklist (untouchable by the user) + DnsOverHttpsMode off,
     only for browsers actually detected.

Firefox / Firefox ESR:
  merges into every candidate policies.json:
    /etc/firefox/policies/policies.json
    /etc/firefox-esr/policies/policies.json
    /usr/lib/firefox-esr/distribution/policies.json
    /usr/lib/firefox/distribution/policies.json
  -> URLBlocklist + DNSOverHTTPS disabled.

Usage (run by postinst / postrm):
  install_policies.py [install|remove] [--data-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

CHROME_TARGETS = [
    ("google-chrome", "/etc/opt/chrome/policies/managed"),
    ("chromium", "/etc/chromium/policies/managed"),
    ("chromium-browser", "/etc/chromium/policies/managed"),
    ("microsoft-edge", "/etc/opt/microsoft-edge/policies/managed"),
    ("brave-browser", "/etc/opt/brave.com/brave/policies/managed"),
    ("vivaldi", "/etc/opt/vivaldi/policies/managed"),
]

FIREFOX_CANDIDATES = [
    Path("/etc/firefox/policies/policies.json"),
    Path("/etc/firefox-esr/policies/policies.json"),
    Path("/usr/lib/firefox-esr/distribution/policies.json"),
    Path("/usr/lib/firefox/distribution/policies.json"),
]


def which(name: str) -> bool:
    return shutil.which(name) is not None


def load_core(data_dir: Path) -> list[str]:
    path = data_dir / "blocklist_core.txt"
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l and not l.startswith("#")]


def url_patterns(domains: list[str]) -> list[str]:
    """Documented Chrome/Firefox URLBlocklist forms:
    two patterns per domain so bare domains and every subdomain match."""
    out: list[str] = []
    for d in domains:
        out.append(f"*://*.{d}/*")
        out.append(f"*://{d}/*")
    return sorted(set(out))


def chrome_policy(domains: list[str]) -> dict:
    return {
        "URLBlocklist": url_patterns(domains),
        "DnsOverHttpsMode": "off",
        "SafeBrowsingEnabled": True,
    }


def firefox_policy(domains: list[str]) -> dict:
    return {
        "URLBlocklist": url_patterns(domains),
        "DNSOverHTTPS": {"Enabled": False, "Locked": True},
    }


def write_policy(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)
    print(f"  wrote {path}")


def merge_firefox_file(path: Path, domains: list[str]) -> None:
    """Merge our policies into an existing policies.json (idempotent)."""
    existing: dict = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    policies = existing.setdefault("policies", {})
    ours = firefox_policy(domains)
    blocklist = policies.setdefault("URLBlocklist", [])
    for p in ours["URLBlocklist"]:
        if p not in blocklist:
            blocklist.append(p)
    policies["DNSOverHTTPS"] = ours["DNSOverHTTPS"]
    existing["policies"] = policies
    write_policy(path, existing)


def install(data_dir: Path) -> int:
    domains = load_core(data_dir)
    print(f"core domains: {len(domains)} -> {len(url_patterns(domains))} patterns")

    for binary, directory in CHROME_TARGETS:
        if not which(binary):
            continue
        target = Path(directory) / "justgivenup.json"
        print(f"{binary}: {target}")
        write_policy(target, chrome_policy(domains))

    existing_firefox = [p for p in FIREFOX_CANDIDATES if p.is_file()]
    if not existing_firefox and (which("firefox") or which("firefox-esr")):
        existing_firefox = [FIREFOX_CANDIDATES[0]]
    for path in existing_firefox:
        print(f"firefox: {path}")
        merge_firefox_file(path, domains)

    if not any(which(b) for b, _ in CHROME_TARGETS) and not existing_firefox:
        print("no supported browser detected; nothing installed")
    return 0


def remove(data_dir: Path) -> int:
    for _, directory in CHROME_TARGETS:
        path = Path(directory) / "justgivenup.json"
        if path.is_file():
            path.unlink()
            print(f"  removed {path}")
    for path in FIREFOX_CANDIDATES:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        policies = data.get("policies") or {}
        blocklist = policies.get("URLBlocklist") or []
        # drop exactly the patterns we manage for our blocklist
        domains = load_core(data_dir) if data_dir else []
        drop = set(url_patterns(domains))
        new_blocklist = [p for p in blocklist if p not in drop]
        if len(new_blocklist) != len(blocklist):
            policies["URLBlocklist"] = new_blocklist
            print(f"  cleaned URLBlocklist in {path}")
        if policies.get("DNSOverHTTPS") == {"Enabled": False, "Locked": True}:
            policies.pop("DNSOverHTTPS", None)
        if policies:
            data["policies"] = policies
        else:
            data = {k: v for k, v in data.items() if k != "policies"}
        if data:
            write_policy(path, data)
        else:
            path.unlink(missing_ok=True)
            print(f"  removed {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["install", "remove"])
    ap.add_argument("--data-dir", default="/usr/lib/justgivenup/justgivenup/data")
    args = ap.parse_args()
    return install(Path(args.data_dir)) if args.action == "install" else \
        remove(Path(args.data_dir))


if __name__ == "__main__":
    raise SystemExit(main())
