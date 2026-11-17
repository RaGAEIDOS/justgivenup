"""Detect and block VPN / proxy browser extensions.

Layers
------
Chrome / Chromium / Edge / Brave / Vivaldi:
  * ``ExtensionSettings`` wildcard rule blocks the ``proxy`` API permission
    for every extension (this covers the vast majority of VPN add-ons).
  * A curated list of known VPN extension IDs is blocked explicitly.
  * A dynamic scan of every installed extension manifest adds any extension
    that requests ``proxy`` or has an obvious VPN/proxy name.
Firefox:
  * A curated list of known VPN add-on IDs is blocked.
  * A dynamic scan of the profile XPI files does the same job as above
    (Firefox has no permission-based default rule).

The written policies are idempotent; the daemon refreshes them periodically
so a VPN extension installed after boot is blocked within a minute.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Iterable, Optional

# Browsers that read /etc/<...>/policies/managed/*.json
CHROME_TARGETS = [
    ("google-chrome", "/etc/opt/chrome/policies/managed"),
    ("chromium", "/etc/chromium/policies/managed"),
    ("chromium-browser", "/etc/chromium/policies/managed"),
    ("microsoft-edge", "/etc/opt/microsoft-edge/policies/managed"),
    ("brave-browser", "/etc/opt/brave.com/brave/policies/managed"),
    ("vivaldi", "/etc/opt/vivaldi/policies/managed"),
    ("opera", "/etc/opera/policies/managed"),
]

# Brand -> policy directory.  Incognito is decided per brand: an extension
# installed in Chrome must not silently enable incognito in Edge.
CHROME_POLICY_DIRS_BY_BRAND = {
    "chrome": Path("/etc/opt/chrome/policies/managed"),
    "chromium": Path("/etc/chromium/policies/managed"),
    "edge": Path("/etc/opt/microsoft-edge/policies/managed"),
    "brave": Path("/etc/opt/brave.com/brave/policies/managed"),
    "vivaldi": Path("/etc/opt/vivaldi/policies/managed"),
    "opera": Path("/etc/opera/policies/managed"),
}

_BRAND_BINARIES = {
    "chrome": ("google-chrome",),
    "chromium": ("chromium", "chromium-browser"),
    "edge": ("microsoft-edge",),
    "brave": ("brave-browser", "brave"),
    "vivaldi": ("vivaldi",),
    "opera": ("opera",),
}

FIREFOX_POLICY_FILES = [
    Path("/etc/firefox/policies/policies.json"),
    Path("/etc/firefox-esr/policies/policies.json"),
    Path("/usr/lib/firefox-esr/distribution/policies.json"),
    Path("/usr/lib/firefox/distribution/policies.json"),
]

# Curated, verified Google Chrome Web Store IDs (November 2026).
CHROME_VPN_IDS = frozenset({
    # Browsec, Hola, Urban VPN, Proton VPN, NordVPN
    "omghfjlpggmjjaagoclmmobgdodcjboh",
    "gkojfkhlekighikafcpjkiklfbnlmeio",
    "eppiocemhmnlbhjplcgkofciiegomcon",
    "jplgfhpmjnbigmhklmmbgecoobifkmpa",
    "fjoaledfpmneenckfbpdfhkmimnjocfa",
    # DotVPN, SetupVPN, CyberGhost, ExpressVPN, Surfshark
    "kpiecbcckbofpmkkkdibbllpinceiihk",
    "oofgbpoabipfcfjapgnbbjjaenockbdp",
    "ffbkglfijbcbgblgflchnbphjdllaogb",
    "fgddmllnllkalaagkghckoinaemmogpe",
    "ailoabdmgclmfmhdagmlohpjlbpffblp",
    # Touch VPN, TunnelBear, Windscribe, Hotspot Shield, IPVanish, hide.me
    "bihmplhobchoageeokmgbdihknkjbknd",
    "omdakjcmkglenbhjadbccaookpfjihpa",
    "hnmpcagpplmpfojmgmnngilcnanddlhb",
    "fgcngeihbacfndglmmmdkkdlhgndkaaf",
    "nlbejmccbhkncgokjcmghpfloaajcffj",
    "ekeoaffihmbjndaoglobgjibjgcmjfpo",
    "ohjocgmpmlfahafbipehkhbaacoemojp",
    # VeePN variants (the first one is present on this machine)
    "majdfhpaihoncoakbjgbdhglocklcgno",
    "agnmhhebllipfgbjapeaokbmookepach",
    "jgdefbohamhjckdlhioadifmhfdahenl",
    "baglfifodllloppchbbpddiinccmignh",
    "mmflncbnfobfkblcnngkjfgncjaocckd",
    "pjjaekbbbfhnagmcffknohdoifagibpn",
    "fjnddclkfikoaonclkhkjnnmajagdmik",
    "hdhkbojcompocgnbgpcaoocgnbnpojgl",
    # Planet VPN regional builds
    "jpadbaildllggkcgibilkeacpcodailn",
    "emgljgblbgakbjamhfhdfnmlhdofljid",
    "hdfonibceclkpbbgheghddomkmkjpchh",
    "geecodjadodhllgoiahfhdpgfpamkofp",
    "hbjemocpeikmflpdcipppbhcmiliaohh",
    "jonfefokggbliacanjbaiejmbclccocp",
    "anojflfckeghbodjglfogdpgkmfinloi",
    "iibgamnboldgknjoighigjajflgcmfeh",
    "fhggeljlcambnphlgjbgnenndddhldkg",
    "eghnafjbdndehofookfnkfkogbnicgdb",
    # 1VPN / free VPN proxy family, FastestVPN, Link VPN, My IP Hider, Betternet
    "akcocjjpkmlniicdeemdceeajlmoabhg",
    "jaoafpkngncfpfggjefnekilbkcpjdgp",
    "hipncndjamdcmphkgngojegjblibadbe",
    "fcfhplploccackoneaefokcmbjfbkenj",
    "adlpodnneegcnbophopdmhedicjbcgco",
    "jcbiifklmgnkppebelchllpdbnibihel",
    "lneaocagcijjdpkcabeanfpdbmapcjjg",
    "cppljodbhecoilefippjhdbekghdigae",
    "jedieiamjmoflcknjdjhpieklepfglin",
    "jjblgeoaolomehjfhklmbbffgnhmgnfp",
    "keodbianoliadkoelloecbhllnpiocoi",
    "gjknjjomckknofjidppipffbpoekiipm",
})

# Curated Firefox Add-ons IDs (AMO, November 2026).
FIREFOX_VPN_IDS = frozenset({
    "{4bf7c817-a8ab-4d98-b84d-65f79f05415d}",  # fastproxy
    "nord-proxy@example.com",
    "adguard-vpn@adguard.com",
    "info@angelvpn.com",
    "client@anonymox.net",
    "browsec@browsec.com",
    "{585280b0-ee78-428a-92c5-3fb3c0b85460}",  # CyberGhost
    "firefox-addon@expressvpn.com",
    "admin@fastestvpn.com",
    "foxyproxy@eric.h.jung",
    "tuxler-ff@tuxler.com",
    "freevpn@actmobile.com",
    "{1935b298-ac62-11ec-b909-0242ac120002}",  # Planet VPN
    "@hoxx-vpn",
    "vpn@mozilla.com",                          # Mozilla VPN
    "nordvpnproxy@nordvpn.com",
    "{3e4d2037-d300-4e95-859d-3cba866f46d3}",  # Private Internet Access
    "vpn@proton.ch",
    "enquiry@purevpn.com",
    "@setupvpncom",
    "shieldbrowse@extension",
    "{732216ec-0dab-43bb-ac85-4b5e1977599d}",  # Surfshark
    "browser@tunnelbear.com",
    "1vpn@example.com",
    "sandvpn_@sandvpn.com",
    "vpnfirefox@softnour.com",
    "{98e5888b-e5f3-4321-a647-28bc617deda2}",  # VPN add-on
    "{a871656a-91f6-402c-912b-6291197b9c49}",  # Betternet
    "{94ed9bbf-a1e2-4e58-81ae-cd16dad818d8}",  # VeePN
    "vpncity@thinkhuge.net",
    "@windscribeff",
    "firefox-webext@zenmate.com",
    "suziwen1@gmail.com",                       # ZeroOmega / SwitchyOmega
})

_VPN_NAME_RE = None


def _vpn_name_re():
    """Compiled lazily so importing this module never costs much."""
    global _VPN_NAME_RE
    if _VPN_NAME_RE is None:
        import re

        _VPN_NAME_RE = re.compile(
            r"(?i)(?:\bvpn\b|\bproxy\b|proxies|hide\s*my\s*ip|ip\s*hider|"
            r"hotspot\s*shield|browsec|zenmate|\bhola\b|windscribe|tunnelbear|"
            r"cyberghost|nordvpn|surfshark|expressvpn|ipvanish|proton\s*vpn|"
            r"veepn|veezn|planet\s*vpn|urban\s*vpn|touch\s*vpn|setup\s*vpn|"
            r"setupvpn|1click\s*vpn|1vpn|betternet|dotvpn|hoxx|purevpn|"
            r"private\s*internet\s*access|mullvad|hide\.me|fastestvpn|"
            r"anonymox|foxyproxy|switchyomega|adguard\s*vpn|mozilla\s*vpn|"
            r"tuxler|angelvpn|vpncity|vpn\s*unlimited|free\s*vpn)"
        )
    return _VPN_NAME_RE


def is_vpn_name(name: str) -> bool:
    return bool(name and _vpn_name_re().search(name))


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _localized_name(manifest: dict, read_file) -> str:
    name = str(manifest.get("name") or "")
    if not (name.startswith("__MSG_") and name.endswith("__")):
        return name
    key = name[6:-2]
    default_locale = str(manifest.get("default_locale") or "en")
    for locale in (default_locale, "en", "en_US"):
        try:
            raw = read_file(f"_locales/{locale}/messages.json")
        except Exception:
            raw = None
        if not raw:
            continue
        try:
            messages = json.loads(raw)
            value = (messages.get(key) or {}).get("message")
        except (ValueError, TypeError):
            continue
        if value:
            return str(value)
    return name


def _manifest_is_vpn(manifest: dict, read_file) -> bool:
    permissions = manifest.get("permissions") or []
    if not isinstance(permissions, list):
        permissions = []
    if "proxy" in permissions:
        return True
    optional = manifest.get("optional_permissions") or []
    name = _localized_name(manifest, read_file)
    if isinstance(optional, list) and "proxy" in optional and is_vpn_name(name):
        return True
    return is_vpn_name(name)


def _home_dirs() -> list[Path]:
    homes: list[Path] = []
    try:
        homes.extend(p for p in Path("/home").iterdir() if p.is_dir())
    except OSError:
        pass
    if Path("/root").is_dir():
        homes.append(Path("/root"))
    return homes


_CHROMIUM_PROFILE_ROOTS = (
    ".config/google-chrome",
    ".config/chromium",
    ".config/chromium-browser",
    ".config/BraveSoftware/Brave-Browser",
    ".config/microsoft-edge",
    ".config/vivaldi",
    ".config/opera",
    ".config/opera-beta",
)


def _chromium_profiles() -> list[Path]:
    profiles: list[Path] = []
    for home in _home_dirs():
        for rel in _CHROMIUM_PROFILE_ROOTS:
            base = home / rel
            try:
                if not base.is_dir():
                    continue
                if (base / "Preferences").is_file():
                    profiles.append(base)
                profiles.extend(p.parent for p in base.glob("*/Preferences"))
            except OSError:
                continue
    return profiles


def scan_installed_chrome_ids(exclude_paths: Iterable[Path] = ()) -> set[str]:
    """Return IDs of installed Chromium extensions that look like VPN/proxy.

    Only IDs are returned; manifests are read from ``Extensions/<id>/<ver>``
    and from unpacked extensions referenced by the profile Preferences.
    """
    excluded = set()
    for p in exclude_paths:
        try:
            excluded.add(Path(p).resolve())
        except OSError:
            pass
    found: set[str] = set()

    for profile in _chromium_profiles():
        extensions_dir = profile / "Extensions"
        if extensions_dir.is_dir():
            try:
                id_dirs = list(extensions_dir.iterdir())
            except OSError:
                id_dirs = []
            for id_dir in id_dirs:
                if not id_dir.is_dir() or id_dir.name in {"Temp", "temp"}:
                    continue
                try:
                    versions = list(id_dir.iterdir())
                except OSError:
                    continue
                for version in versions:
                    manifest_path = version / "manifest.json"
                    if not manifest_path.is_file():
                        continue
                    manifest = _read_json(manifest_path)
                    if not manifest:
                        break
                    if _manifest_is_vpn(
                        manifest,
                        lambda rel, base=version: (
                            (base / rel).read_text(encoding="utf-8", errors="replace")
                            if (base / rel).is_file() else None
                        ),
                    ):
                        found.add(id_dir.name)
                    break

        # Unpacked extensions live outside Extensions/ and are recorded in
        # Preferences with an absolute ``path``.
        prefs = _read_json(profile / "Preferences")
        if not prefs:
            continue
        settings = (prefs.get("extensions") or {}).get("settings") or {}
        if not isinstance(settings, dict):
            continue
        for ext_id, info in settings.items():
            if not isinstance(info, dict):
                continue
            if info.get("location") == 5:  # component extension
                continue
            raw_path = info.get("path")
            if not raw_path:
                continue
            try:
                ext_path = Path(raw_path)
                if ext_path.resolve() in excluded:
                    continue
            except OSError:
                continue
            manifest_path = ext_path / "manifest.json"
            if not manifest_path.is_file():
                continue
            manifest = _read_json(manifest_path)
            if not manifest:
                continue
            name = _localized_name(
                manifest,
                lambda rel, base=ext_path: (
                    (base / rel).read_text(encoding="utf-8", errors="replace")
                    if (base / rel).is_file() else None
                ),
            )
            if is_vpn_name(name) or "proxy" in (manifest.get("permissions") or []):
                found.add(str(ext_id))
    return found


def scan_installed_firefox_ids(exclude_ids: Iterable[str] = ()) -> set[str]:
    """Return IDs of installed Firefox add-ons that look like VPN/proxy."""
    excluded = {str(x) for x in exclude_ids}
    found: set[str] = set()
    roots = (".config/mozilla/firefox", ".mozilla/firefox")
    for home in _home_dirs():
        for rel in roots:
            base = home / rel
            try:
                if not base.is_dir():
                    continue
                profiles = [p for p in base.iterdir() if p.is_dir()]
            except OSError:
                continue
            for profile in profiles:
                ext_dir = profile / "extensions"
                try:
                    if not ext_dir.is_dir():
                        continue
                    entries = list(ext_dir.iterdir())
                except OSError:
                    continue
                for entry in entries:
                    addon_id = entry.name[:-4] if entry.suffix == ".xpi" else entry.name
                    if addon_id in excluded:
                        continue
                    try:
                        if entry.suffix == ".xpi":
                            with zipfile.ZipFile(entry) as zf:
                                manifest = json.loads(zf.read("manifest.json"))
                                name = _localized_name(
                                    manifest,
                                    lambda rel: zf.read(rel).decode("utf-8", "replace"),
                                )
                        else:
                            manifest = _read_json(entry / "manifest.json")
                            if not manifest:
                                continue
                            name = _localized_name(
                                manifest,
                                lambda rel, base=entry: (
                                    (base / rel).read_text(encoding="utf-8", errors="replace")
                                    if (base / rel).is_file() else None
                                ),
                            )
                    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                        continue
                    if "proxy" in (manifest.get("permissions") or []) or is_vpn_name(name):
                        found.add(addon_id)
    return found


def chrome_extension_settings(extra_ids: Iterable[str] = ()) -> dict:
    settings: dict = {"*": {"blocked_permissions": ["proxy"]}}
    for ext_id in sorted(set(CHROME_VPN_IDS) | {str(i) for i in extra_ids}):
        settings[ext_id] = {"installation_mode": "blocked"}
    return settings


def _write_if_changed(path: Path, payload: dict) -> bool:
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    try:
        if path.is_file() and path.read_text(encoding="utf-8", errors="replace") == text:
            return False
    except OSError:
        pass
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return False
    return True


def chrome_policy_dirs(create: bool = False) -> list[Path]:
    dirs: list[Path] = []
    for binary, directory in CHROME_TARGETS:
        if not shutil.which(binary):
            continue
        path = Path(directory)
        if create:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue
        if path.is_dir() and path not in dirs:
            dirs.append(path)
    return dirs


def chrome_policy_dirs_by_brand(create: bool = False) -> dict[str, Path]:
    """Installed Chromium-family brands -> their managed-policy directory."""
    out: dict[str, Path] = {}
    for brand, directory in CHROME_POLICY_DIRS_BY_BRAND.items():
        if not any(shutil.which(binary) for binary in _BRAND_BINARIES.get(brand, ())):
            continue
        path = Path(directory)
        if create:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue
        if path.is_dir():
            out[brand] = path
    return out


def apply_chrome_extension_policy(dirs: Iterable[Path], extra_ids: Iterable[str] = ()) -> bool:
    payload = {"ExtensionSettings": chrome_extension_settings(extra_ids)}
    changed = False
    for directory in dirs:
        changed |= _write_if_changed(Path(directory) / "justgivenup-extensions.json", payload)
    return changed


def _ext_sidecar(path: Path) -> Path:
    return path.with_name(path.name + ".justgivenup-extensions.json")


def _load_managed_extensions(path: Path) -> set[str]:
    try:
        data = json.loads(_ext_sidecar(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(x) for x in data} if isinstance(data, list) else set()


def _save_managed_extensions(path: Path, ids: set[str]) -> None:
    try:
        _ext_sidecar(path).write_text(
            json.dumps(sorted(ids), indent=1), encoding="utf-8")
    except OSError:
        pass


def apply_firefox_extension_policy(extra_ids: Iterable[str] = ()) -> bool:
    want = set(FIREFOX_VPN_IDS) | {str(i) for i in extra_ids}
    changed = False
    for path in FIREFOX_POLICY_FILES:
        if not path.is_file():
            continue
        data = _read_json(path) or {}
        policies = data.setdefault("policies", {})
        if not isinstance(policies, dict):
            continue
        settings = policies.setdefault("ExtensionSettings", {})
        if not isinstance(settings, dict):
            continue
        managed = _load_managed_extensions(path)
        file_changed = False
        for ext_id in sorted(want):
            current = settings.get(ext_id)
            if isinstance(current, dict) and current.get("installation_mode") == "blocked":
                continue
            settings[ext_id] = {"installation_mode": "blocked"}
            managed.add(ext_id)
            file_changed = True
        if file_changed:
            _write_if_changed(path, data)
            changed = True
        if managed and (file_changed or not _ext_sidecar(path).is_file()):
            _save_managed_extensions(path, managed)
    return changed


def remove_firefox_extension_policy() -> bool:
    changed = False
    for path in FIREFOX_POLICY_FILES:
        if not path.is_file():
            continue
        managed = _load_managed_extensions(path)
        if not managed:
            continue
        data = _read_json(path) or {}
        policies = data.get("policies")
        if not isinstance(policies, dict):
            continue
        settings = policies.get("ExtensionSettings")
        if isinstance(settings, dict):
            for ext_id in managed:
                settings.pop(ext_id, None)
            if not settings:
                policies.pop("ExtensionSettings", None)
            _write_if_changed(path, data)
            changed = True
        _ext_sidecar(path).unlink(missing_ok=True)
    return changed
