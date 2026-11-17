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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:  # shared-hosting suffixes (one-time cleanup of legacy whole-platform rules)
    from justgivenup.blocklist import PRIVATE_SUFFIXES
except Exception:  # pragma: no cover - hook must never fail to import
    PRIVATE_SUFFIXES = set()
try:  # VPN / proxy extension policies + shared target lists
    from justgivenup import vpnblock
except Exception:  # pragma: no cover
    vpnblock = None

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
        # Private browsing is only re-enabled by the daemon once the
        # extension proves that it runs in private windows.
        "PrivateBrowsingModeAvailability": 1,
    }


def write_policy(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)
    print(f"  wrote {path}")


def _managed_sidecar(path: Path) -> Path:
    return path.with_name(path.name + ".justgivenup-managed.json")


def _load_managed(path: Path) -> list[str]:
    """Patterns we added on the previous run (so stale ones can be removed)."""
    try:
        data = json.loads(_managed_sidecar(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [p for p in data if isinstance(p, str)] if isinstance(data, list) else []


def _save_managed(path: Path, patterns: list[str]) -> None:
    try:
        _managed_sidecar(path).write_text(
            json.dumps(sorted(set(patterns))), encoding="utf-8")
    except OSError:
        pass


def _legacy_platform_patterns() -> set[str]:
    """Old builds collapsed *.vercel.app porn hosts into vercel.app and
    blocked the whole platform.  Those base patterns must be dropped so
    legitimate sites on shared hosting work again."""
    out: set[str] = set()
    for base in PRIVATE_SUFFIXES:
        out.add(f"*://*.{base}/*")
        out.add(f"*://{base}/*")
    return out


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
    # replace the patterns we manage instead of appending forever:
    stale = set(_load_managed(path)) | _legacy_platform_patterns()
    blocklist = [p for p in blocklist if p not in stale]
    for p in ours["URLBlocklist"]:
        if p not in blocklist:
            blocklist.append(p)
    policies["URLBlocklist"] = blocklist
    policies["DNSOverHTTPS"] = ours["DNSOverHTTPS"]
    if "PrivateBrowsingModeAvailability" not in policies:
        policies["PrivateBrowsingModeAvailability"] = ours["PrivateBrowsingModeAvailability"]
    existing["policies"] = policies
    write_policy(path, existing)
    _save_managed(path, ours["URLBlocklist"])


def install(data_dir: Path) -> int:
    domains = load_core(data_dir)
    print(f"core domains: {len(domains)} -> {len(url_patterns(domains))} patterns")

    chrome_dirs: list[Path] = []
    for binary, directory in CHROME_TARGETS:
        if not which(binary):
            continue
        target = Path(directory) / "justgivenup.json"
        print(f"{binary}: {target}")
        write_policy(target, chrome_policy(domains))
        chrome_dirs.append(Path(directory))
        # Incognito stays disabled until the extension reports that it is
        # allowed in incognito; the daemon flips this to 0 dynamically.
        write_policy(Path(directory) / "justgivenup-incognito.json",
                     {"IncognitoModeAvailability": 1})

    if vpnblock is not None:
        if chrome_dirs:
            vpnblock.apply_chrome_extension_policy(chrome_dirs, set())
            print(f"  wrote VPN extension policy in {len(chrome_dirs)} Chrome target(s)")

    existing_firefox = [p for p in FIREFOX_CANDIDATES if p.is_file()]
    if not existing_firefox and (which("firefox") or which("firefox-esr")):
        existing_firefox = [FIREFOX_CANDIDATES[0]]
    for path in existing_firefox:
        print(f"firefox: {path}")
        merge_firefox_file(path, domains)
    if vpnblock is not None and existing_firefox:
        vpnblock.apply_firefox_extension_policy(set())
        print(f"  wrote VPN add-on policy in {len(existing_firefox)} Firefox target(s)")

    if not any(which(b) for b, _ in CHROME_TARGETS) and not existing_firefox:
        print("no supported browser detected; nothing installed")
    return 0


def remove(data_dir: Path) -> int:
    for _, directory in CHROME_TARGETS:
        base = Path(directory)
        for name in ("justgivenup.json", "justgivenup-extensions.json",
                     "justgivenup-incognito.json"):
            path = base / name
            if path.is_file():
                path.unlink()
                print(f"  removed {path}")
    if vpnblock is not None:
        vpnblock.remove_firefox_extension_policy()
    for path in FIREFOX_CANDIDATES:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        policies = data.get("policies") or {}
        blocklist = policies.get("URLBlocklist") or []
        # drop exactly the patterns we manage for our blocklist (plus any
        # recorded from a previous install and legacy whole-platform rules)
        domains = load_core(data_dir) if data_dir else []
        drop = set(url_patterns(domains)) | set(_load_managed(path)) \
            | _legacy_platform_patterns()
        new_blocklist = [p for p in blocklist if p not in drop]
        if len(new_blocklist) != len(blocklist):
            policies["URLBlocklist"] = new_blocklist
            print(f"  cleaned URLBlocklist in {path}")
        if policies.get("DNSOverHTTPS") == {"Enabled": False, "Locked": True}:
            policies.pop("DNSOverHTTPS", None)
        if policies.get("PrivateBrowsingModeAvailability") in (0, 1):
            policies.pop("PrivateBrowsingModeAvailability", None)
        if policies:
            data["policies"] = policies
        else:
            data = {k: v for k, v in data.items() if k != "policies"}
        if data:
            write_policy(path, data)
        else:
            path.unlink(missing_ok=True)
            print(f"  removed {path}")
        _managed_sidecar(path).unlink(missing_ok=True)
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
