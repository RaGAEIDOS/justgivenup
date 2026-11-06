#!/usr/bin/env python3
"""Build the canonical blocklists + the extension's DNR rules.

Inputs
  scripts/.cache/porn-hosts.txt   StevenBlack "porn" alternate (downloaded)
  justgivenup.blocklist.EXTRA_PROXY_DOMAINS   curated circumvention sites

Outputs
  data/blocklist_full.txt   every domain -> /etc/hosts tier (~150k)
  data/blocklist_core.txt   popular registrable domains -> browser policy
                            + extension rules.json
  extension/rules.json      declarativeNetRequest static rules (Chrome)
  extension/rules.firefox.json   Firefox DNR rules (no transform support)

Run:  python3 scripts/build_blocklist.py [--no-fetch]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from justgivenup.blocklist import EXTRA_PROXY_DOMAINS  # noqa: E402

SRC_URL = ("https://raw.githubusercontent.com/StevenBlack/hosts"
           "/master/alternates/porn/hosts")
CACHE = ROOT / "scripts" / ".cache" / "porn-hosts.txt"
DATA = ROOT / "data"
RULES_OUT = ROOT / "extension" / "rules.json"
RULES_OUT_FF = ROOT / "extension" / "rules.firefox.json"

MAX_CORE = 15_000          # safety cap for policy / DNR tiers
CORE_NAME_LEN = 6          # registrable label length heuristic (short = popular)

MULTI_TLDS = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "net.uk", "sch.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "id.au",
    "co.in", "net.in", "org.in", "firm.in", "gen.in", "ind.in",
    "com.br", "net.br", "org.br", "com.mx", "net.mx", "org.mx",
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp", "lg.jp",
    "co.za", "org.za", "net.za", "web.za", "com.ar", "net.ar", "org.ar",
    "com.tr", "net.tr", "org.tr", "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.hk", "net.hk", "org.hk", "com.tw", "net.tw", "org.tw",
    "co.kr", "ne.kr", "or.kr", "com.sg", "net.sg", "org.sg",
    "com.my", "net.my", "org.my", "com.ph", "net.ph", "org.ph",
    "com.vn", "net.vn", "org.vn", "co.id", "net.id", "org.id",
    "co.th", "net.th", "org.th", "com.ua", "net.ua", "org.ua",
    "com.ru", "net.ru", "org.ru", "msk.ru", "spb.ru",
    "com.pl", "net.pl", "org.pl", "com.es", "net.es", "org.es",
    "co.nz", "net.nz", "org.nz", "co.il", "net.il", "org.il",
    "com.sa", "net.sa", "org.sa", "com.eg", "net.eg", "org.eg",
    "com.pk", "net.pk", "org.pk", "com.bd", "com.np",
    "com.co", "net.co", "org.co", "com.ve", "com.pe", "com.ec",
    "com.uy", "com.bo", "com.py", "com.gt", "com.do", "com.pr",
    "eu.org",
}

# --- Legitimate sites that must NEVER be blocked (safety allowlist) ---
# These are collapsed from subdomains in the upstream list (e.g.
# www.google.com -> google.com) and would otherwise slip into core/full
# because of short first labels or other heuristics.
LEGIT_DOMAINS = [
    "google.com", "youtube.com", "facebook.com", "instagram.com", "twitter.com",
    "wikipedia.org", "reddit.com", "microsoft.com", "apple.com", "amazon.com",
    "netflix.com", "linkedin.com", "github.com", "stackoverflow.com",
    "discord.com", "twitch.tv", "spotify.com", "icloud.com", "adobe.com",
    "dropbox.com", "paypal.com", "ebay.com", "aliexpress.com", "walmart.com",
    "target.com", "samsung.com", "sony.com", "nintendo.com",
    "steampowered.com", "epicgames.com", "origin.com", "uplay.com",
    "battle.net", "riotgames.com", "mojang.com", "roblox.com",
    "cloudflare.com", "akamai.com", "fastly.com",
    "verizon.com", "att.com", "t-mobile.com", "vodafone.com",
    "orange.com", "telefonica.com", "dtag.com", "bt.com",
    "bbc.co.uk", "nytimes.com", "washingtonpost.com", "theguardian.com",
    "reuters.com", "apnews.com", "bloomberg.com", "wsj.com", "forbes.com",
    "cnn.com", "foxnews.com", "aljazeera.com", "dw.com", "france24.com",
    "google.co.uk", "google.ca", "google.co.in", "google.co.jp",
    "google.co.za", "google.com.au", "google.de", "google.fr", "google.it",
    "google.es", "google.nl", "google.se", "google.no", "google.dk",
    "google.fi", "google.pl", "google.cz", "google.hu", "google.ro",
    "google.hr", "google.ie", "google.pt", "google.gr", "google.tr",
    "google.com.br", "google.com.mx", "google.com.ar", "google.com.co",
    "google.com.pe", "google.com.ve", "google.com.cl", "google.com.uy",
    "google.com.py", "google.com.ec", "google.com.bo",
    "google.com.sv", "google.com.gt", "google.com.hn", "google.com.cr",
    "google.com.pa", "google.com.do", "google.com.pr",
    "google.be", "google.com.vn", "amazon.co.jp", "amazon.de",
    "amazon.dev", "amazon.it", "apple.com.cn", "cnn.cm", "cnn.io",
    "github.io", "reddit.rest", "sony.jp",
]

# Popular domains we always want in the core tier (short names usually
# catch them anyway; this is belt & braces for mirrors/CDN hosts).
KNOWN_MAJORS = [
    "pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "redtube.com",
    "youporn.com", "tube8.com", "spankbang.com", "eporner.com", "porntube.com",
    "motherless.com", "beeg.com", "daftsex.com", "hclips.com",
    "tktube.com", "porndoe.com", "porndig.com", "porndroids.com",
    "pornone.com", "missav.com", "javhd.com", "hanime.tv", "nhentai.net",
    "e621.net", "gelbooru.com", "rule34.xxx", "danbooru.donmai.us",
    "safebooru.org", "onlyfans.com", "fansly.com", "stripchat.com",
    "chaturbate.com", "cam4.com", "bongacams.com", "livejasmin.com",
    "myfreecams.com", "streamate.com", "flirt4free.com", "camcontacts.com",
    "livecam.com", "omegle.com", "chatroulette.com", "chatrandom.com",
    "cocochat.com", "adriendelvaux.com", "ashleymadison.com",
    "adultfriendfinder.com", "fling.com", "sex.com",
    "tnaflix.com", "empflix.com", "redtube.xxx", "tubeon.com",
    "sunporno.com", "zbporn.com", "fakeraptor.com", "4tube.com",
    "thumbzilla.com", "fuq.com", "www.xnxx.com", "sexytube.me",
    "txxx.com", "biguz.net", "porncorn.com", "hotmovs.com", "milfzr.com",
    "anyporn.com", "asspornxxx.com", "xcafe.com", "vikiporn.com",
    "proporn.com", "sundosex.com", "kysqxs.com", "myporntube.com",
    "freepornhere.com", "freepornhq.com", "freepornpics.net", "sexu.com",
    "pornhat.com", "pornpics.com", "icanw.com", "24videos.tv",
    "sweet-eva.com", "watchmygf.me", "porcore.com", "sexvideosporn.com",
    "ixxx.com", "hdzog.com", "tube-mix.com", "watchpornfree.info",
    "freeporn8.com", "gonzoxxx.com", "porndollars.com", "analporn.com",
    "eroprofile.com", "imagefap.com", "fapdu.com", "thisvid.com",
    "fux.com", "drtuber.com", "pornxs.com", "iceporn.com",
    "motherless.com", "youjizz.com", "eporner.com", "porn.com",
    "pornerbros.com", "pornomine.com", "xkeezmovies.com", "keezmovies.com",
    "wowporn.com", "bestjavporn.com", "javporn.tv", "avgle.com",
    "supjav.com", "njav.tv", "tokyomotion.net", "porndish.com",
    "pornbraze.com", "dansmovies.com", "beegporn.com", "xnxx.com",
    "redgifs.com", "gfycat.com", "xxxbunker.com",
]

LINE_RE = re.compile(r"^(?:0\.0\.0\.0|127\.0\.0\.1)\s+([A-Za-z0-9._-]+)\s*$")
SKIP_DOMAINS = {
    "localhost", "local", "broadcasthost", "0.0.0.0", "localhost.localdomain",
    "ip6-localhost", "ip6-loopback", "ip6-localnet", "ip6-mcastprefix",
    "ip6-allnodes", "ip6-allrouters", "ip6-allhosts",
}


def fetch_sources(no_fetch: bool) -> str:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if no_fetch and CACHE.is_file():
        return CACHE.read_text(encoding="utf-8", errors="replace")
    if CACHE.is_file() and _cache_is_fresh():
        return CACHE.read_text(encoding="utf-8", errors="replace")
    print(f"downloading {SRC_URL} ...")
    try:
        with urllib.request.urlopen(SRC_URL, timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        CACHE.write_text(text, encoding="utf-8")
        return text
    except Exception as exc:  # offline build: fall back to cache
        if CACHE.is_file():
            print(f"  download failed ({exc}); using cached copy")
            return CACHE.read_text(encoding="utf-8", errors="replace")
        raise SystemExit(f"no cached source available: {exc}")


def _cache_is_fresh() -> bool:
    age = time.time() - CACHE.stat().st_mtime
    return age < 30 * 86400


def registrable(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    if ".".join(parts[-2:]) in MULTI_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def valid_domain(d: str) -> bool:
    if not d or len(d) > 253 or " " in d or d in SKIP_DOMAINS:
        return False
    if ".." in d or d.startswith(".") or d.endswith("."):
        return False
    return "." in d and re.fullmatch(r"[a-z0-9._-]+", d) is not None


SAFE_SEARCH_RULES = [
    # Safe Search hardening (search engines only)
    {
        "id": 10,
        "priority": 2,
        "action": {"type": "redirect", "redirect": {"transform": {
            "queryTransform": {"addOrReplaceParams": [
                {"key": "safe", "value": "active"}]}}}},
        "condition": {"urlFilter": "||google.com/search",
                      "resourceTypes": ["main_frame"]},
    },
    {
        "id": 11,
        "priority": 2,
        "action": {"type": "redirect", "redirect": {"transform": {
            "queryTransform": {"addOrReplaceParams": [
                {"key": "safe", "value": "active"}]}}}},
        "condition": {"urlFilter": "||google.co.uk/search",
                      "resourceTypes": ["main_frame"]},
    },
    {
        "id": 12,
        "priority": 2,
        "action": {"type": "redirect", "redirect": {"transform": {
            "queryTransform": {"addOrReplaceParams": [
                {"key": "adlt", "value": "strict"}]}}}},
        "condition": {"urlFilter": "||bing.com/search",
                      "resourceTypes": ["main_frame"]},
    },
    {
        "id": 13,
        "priority": 2,
        "action": {"type": "redirect", "redirect": {"transform": {
            "queryTransform": {"addOrReplaceParams": [
                {"key": "kp", "value": "-1"}]}}}},
        "condition": {"urlFilter": "||duckduckgo.com/",
                      "resourceTypes": ["main_frame"]},
    },
]


def build_rules(core: list[str], for_firefox: bool = False) -> list[dict]:
    # NOTE: resource types must be valid in BOTH Chrome MV3 and Firefox MV3.
    # "webtransport"/"webbundle"/"object" are Chrome-only and made Firefox
    # reject the whole file (silently). Safe subset below.
    blocked_types = [
        "sub_frame", "stylesheet", "script", "image", "font",
        "xmlhttprequest", "media", "websocket", "ping", "other",
    ]
    rules = [
        {
            "id": 1,
            "priority": 1,
            "action": {"type": "redirect",
                       "redirect": {"extensionPath": "/blocked.html"}},
            "condition": {"requestDomains": core,
                          "resourceTypes": ["main_frame"]},
        },
        {
            "id": 2,
            "priority": 1,
            "action": {"type": "block"},
            "condition": {"requestDomains": core,
                          "resourceTypes": blocked_types},
        },
    ]
    # Firefox DNR rejects the whole SET if any rule uses `transform`
    # (unsupported) — dropping safe-search rules there lets core rules apply.
    if not for_firefox:
        rules += SAFE_SEARCH_RULES
    return rules


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true",
                    help="use the cached upstream list only")
    args = ap.parse_args()

    text = fetch_sources(args.no_fetch)

    full: set[str] = set()
    for line in text.splitlines():
        m = LINE_RE.match(line.strip())
        if m:
            d = m.group(1).lower()
            if valid_domain(d):
                full.add(d)

    extras = [d for d in EXTRA_PROXY_DOMAINS if valid_domain(d.lower())]
    majors = [d.lower() for d in KNOWN_MAJORS if valid_domain(d.lower())]
    full.update(extras)
    full.update(majors)

    regs = {registrable(d) for d in full if valid_domain(d)}
    # remove legitimate sites from the blocklist entirely (safety allowlist)
    regs -= set(LEGIT_DOMAINS)
    for d in extras + majors:
        regs.add(registrable(d))
    regs -= set(LEGIT_DOMAINS)  # also in case majors/extras overlap legit

    # heuristic: shorter first label ~= older/popular site
    core_list = sorted(
        regs,
        key=lambda d: (len(d.split(".")[0]), d),
    )
    core = [d for d in core_list
            if len(d.split(".")[0]) <= CORE_NAME_LEN
            or d in {registrable(x) for x in majors + extras}]
    core = sorted(set(core))[:MAX_CORE]
    core = sorted(core)

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "blocklist_full.txt").write_text(
        "# JustGivenUp! full blocklist -- generated by "
        "scripts/build_blocklist.py\n"
        "# source: StevenBlack/hosts alternates/porn + curated extras\n"
        f"# domains: {len(full)}\n"
        + "\n".join(sorted(full)) + "\n",
        encoding="utf-8",
    )
    (DATA / "blocklist_core.txt").write_text(
        "# JustGivenUp! core blocklist (policy + extension tier)\n"
        f"# registrable domains, heuristic: first label <= {CORE_NAME_LEN} chars\n"
        f"# domains: {len(core)}\n"
        + "\n".join(core) + "\n",
        encoding="utf-8",
    )

    rules = build_rules(core)
    rules_firefox = build_rules(core, for_firefox=True)
    RULES_OUT.parent.mkdir(parents=True, exist_ok=True)
    RULES_OUT.write_text(json.dumps(rules, ensure_ascii=False,
                                    separators=(",", ":")),
                         encoding="utf-8")
    RULES_OUT_FF.write_text(json.dumps(rules_firefox, ensure_ascii=False,
                                       separators=(",", ":")),
                            encoding="utf-8")

    print(f"full : {len(full)} domains -> data/blocklist_full.txt")
    print(f"core : {len(core)} domains -> data/blocklist_core.txt")
    print(f"rules: {len(rules)} DNR rules -> extension/rules.json "
          f"({RULES_OUT.stat().st_size // 1024} KB)")
    print(f"rules: {len(rules_firefox)} DNR rules -> "
          f"extension/rules.firefox.json "
          f"({RULES_OUT_FF.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
