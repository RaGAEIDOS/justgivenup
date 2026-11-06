"""Blocklist loading.

Two tiers ship with the package:

  blocklist_full.txt   every adult domain we know (~150k) -> /etc/hosts
  blocklist_core.txt   popular registrable domains (~8k)  -> browser policy
                                               + extension DNR rules

The user can append custom domains from the dashboard; they are merged
into both tiers (the extension picks them up live as dynamic DNR rules;
the enterprise policy file keeps the build-time list and is refreshed on
package update).
"""

from __future__ import annotations

import threading
from pathlib import Path

from .config import core_blocklist_path, state_dir

# Circumvention aids: web proxies / unblockers commonly used to reach
# blocked content.  Deliberately excludes corporate VPN vendors.
EXTRA_PROXY_DOMAINS = [
    "proxysite.com", "croxyproxy.com", "www.croxyproxy.com", "croxy.io",
    "free-proxy.cz", "hide.me", "proxify.com", "unblockweb.co",
    "unblocksource.com", "unblockplanet.com", "youtubeunblocked.live",
    "proxysite.one", "123unblock.com", "123unblock.pro", "unblock.video",
    "kproxy.com", "kproxy.site", "zend2.com", "vtunnel.com",
    "proxyium.com", "proxysium.com", "whoer.net", "vpnbook.com",
    "sitetounblock.com", "unblocknow.com", "bypasswebside.com",
    "winspec.net", "anonymox.net", "anonymouse.org", "hidemy.name",
    "freeproxy.co", "us-proxy.org", "sslproxies.org", "proxy-list.org",
    "spys.one", "hidester.com", "guardianvpn.net", "unblockyoutube.in",
    "proxTube.com", "proxTube.ru", "prox.dog", "windscribe.com/proxy",
    "chromefoxy.com", "proxysupport.com", "unblock-lite.com",
    "proxycopy.com", "proxyb.net", "proxysite.org", "video.unblock.la",
    "unblock.la", "unblockla.com", "youtubeproxy.net", "ytproxy.info",
    "unblock-youtube.com", "proxflow.com", "proxad.net", "unblockweb.in",
]

_cache: dict[str, list[str]] = {}
_cache_lock = threading.Lock()


def _read(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        # accept plain domains or "0.0.0.0 domain" lines
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            line = parts[1]
        if "." in line and " " not in line:
            out.append(line)
    return out


def _dedup(domains: list[str]) -> list[str]:
    return sorted(set(domains))


def custom_domains() -> list[str]:
    from .config import Config

    raw = Config().data.get("custom_domains") or []
    out = []
    for d in raw:
        d = str(d).strip().lower().lstrip("*.").rstrip("/")
        if "." in d and " " not in d:
            out.append(d)
    return _dedup(out)


def full_domains() -> list[str]:
    """Everything that goes into /etc/hosts (cached)."""
    with _cache_lock:
        if "full" in _cache:
            base = _cache["full"]
        else:
            base = _read(Path(_blocklist_file("full")))
            _cache["full"] = base
    return _dedup(base + EXTRA_PROXY_DOMAINS + custom_domains())


def core_domains() -> list[str]:
    """Popular domains used for browser policy + extension rules."""
    with _cache_lock:
        if "core" in _cache:
            base = _cache["core"]
        else:
            base = _read(Path(_blocklist_file("core")))
            _cache["core"] = base
    return _dedup(base + custom_domains())


def _blocklist_file(tier: str) -> str:
    from .config import blocklist_path, core_blocklist_path

    return str(blocklist_path() if tier == "full" else core_blocklist_path())


def summary() -> dict:
    return {
        "full_count": len(full_domains()),
        "core_count": len(core_domains()),
        "custom_count": len(custom_domains()),
        "state_dir": str(state_dir()),
    }
