"""Desktop-side browser guard.

Three jobs, all running from the JustGivenUp daemon (root or the desktop user):

1. Extension required (3 minutes)
   Every browser that is running without a fresh heartbeat from the
   JustGivenUp extension is closed after ``EXTENSION_KILL_SECONDS``.
   Each browser family is tracked separately: Chrome being protected does
   not excuse Firefox running without the extension.

2. Incognito / private browsing
   * The extension is forced to "allow in incognito" in every Chromium
     profile when that browser is closed (Preferences patch).
   * ``IncognitoModeAvailability`` / ``PrivateBrowsingModeAvailability``
     policies disable incognito/private mode whenever the extension has not
     proved that it is allowed there.
   * A lightweight X11 watcher notices newly opened incognito/private
     windows (window title) and closes the browser immediately when the
     extension is not active in that browser.
   * Launches with ``--incognito`` / ``-private-window`` are killed too.

3. VPN extension policies
   Delegated to :mod:`justgivenup.vpnblock` (generic ``proxy`` permission
   block on Chromium + dynamic ID scan for Chromium/Firefox).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Iterable, Optional

from . import log, stats
from .config import extension_dir
from . import vpnblock

EXTENSION_KILL_SECONDS = 180
INCOGNITO_PROOF_SECONDS = 30
VPN_SCAN_SECONDS = 60
PREF_PATCH_SECONDS = 60
KILL_COOLDOWN_SECONDS = 15

_KNOWN_EXTENSION_ID = "jkfbcbkoeokcpkkdcedbdampnifgobka"

_BROWSERS = ("chrome", "chromium", "firefox", "brave", "msedge", "edge", "opera",
             "vivaldi", "opera_gx", "librewolf", "waterfox", "floorp", "tor")

_CHROMIUM_COMMS = ("chrome", "chromium", "brave", "msedge", "edge", "opera",
                   "vivaldi", "opera_gx")
_FIREFOX_COMMS = ("firefox", "librewolf", "waterfox", "floorp")

_INCOGNITO_MARKERS = (
    "incognito", "inprivate", "private browsing", "private window",
    "private tab", "التصفح المخفي", "تصفح خاص", "نافذة خاصة", "تصفح متخفي",
    "تصفح خفي", "الوضع الخاص", "privée", "incógnito", "inkognito", "privado",
)
_BROWSER_TITLE_HINTS = (
    "google chrome", "chromium", "brave", "microsoft edge", "opera",
    "vivaldi", "mozilla firefox", "firefox", "librewolf", "waterfox",
    "floorp",
)

_PROFILE_ROOTS = (
    (".config/google-chrome", "chrome"),
    (".config/chromium", "chromium"),
    (".config/chromium-browser", "chromium"),
    (".config/BraveSoftware/Brave-Browser", "brave"),
    (".config/microsoft-edge", "edge"),
    (".config/vivaldi", "vivaldi"),
    (".config/opera", "opera"),
    (".config/opera-beta", "opera"),
)

_FAMILY_COMMS = {
    "chrome": ("chrome",),
    "chromium": ("chromium",),
    "brave": ("brave",),
    "edge": ("msedge", "edge"),
    "vivaldi": ("vivaldi",),
    "opera": ("opera",),
}

_kill_lock = threading.Lock()
_last_pref_patch = 0.0
_last_incognito_log: Optional[bool] = None
_watcher_logged = False


# ---------------------------------------------------------------------------
# Process discovery
# ---------------------------------------------------------------------------

def process_family(comm: str) -> str:
    low = (comm or "").lower()
    if any(low.startswith(x) for x in _FIREFOX_COMMS):
        return "firefox"
    if any(low.startswith(x) for x in _CHROMIUM_COMMS):
        return "chromium"
    if low.startswith("tor"):
        return "tor"
    return "other"


def heartbeat_family(browser_label: str) -> str:
    """Map the heartbeat's ``browser`` string (Chrome 157, Firefox 128...)."""
    low = (browser_label or "").lower()
    if "firefox" in low:
        return "firefox"
    if any(x in low for x in ("chrome", "chromium", "edge", "brave", "opera", "vivaldi")):
        return "chromium"
    return "other"


_BRAND_COMMS = {
    "chrome": ("chrome",),
    "chromium": ("chromium",),
    "brave": ("brave",),
    "edge": ("msedge", "edge"),
    "opera": ("opera",),
    "vivaldi": ("vivaldi",),
    "firefox": ("firefox",),
    "librewolf": ("librewolf",),
    "waterfox": ("waterfox",),
    "floorp": ("floorp",),
    "tor": ("tor",),
}

_FIREFOX_BRANDS = ("firefox", "librewolf", "waterfox", "floorp")


def brand_for_comm(comm: str) -> str:
    low = (comm or "").lower()
    if "crashpad" in low:
        return "other"
    for brand in ("librewolf", "waterfox", "floorp", "firefox",
                  "msedge", "edge", "brave", "vivaldi", "opera",
                  "chromium", "chrome", "tor"):
        if low.startswith(brand):
            return "edge" if brand == "msedge" else brand
    return "other"


def brand_for_label(label: str) -> str:
    """Map a heartbeat browser label to a browser brand."""
    low = (label or "").lower()
    for brand, tokens in (
        ("librewolf", ("librewolf",)),
        ("waterfox", ("waterfox",)),
        ("floorp", ("floorp",)),
        ("firefox", ("firefox",)),
        ("edge", ("edge",)),
        ("brave", ("brave",)),
        ("opera", ("opera",)),
        ("vivaldi", ("vivaldi",)),
        ("chromium", ("chromium",)),
        ("chrome", ("chrome",)),
    ):
        if any(token in low for token in tokens):
            return brand
    return "unknown"


def engine_for_brand(brand: str) -> str:
    if brand in _FIREFOX_BRANDS:
        return "firefox"
    if brand == "tor":
        return "tor"
    return "chromium"


def brand_from_title(title: str) -> Optional[str]:
    low = (title or "").lower()
    if not any(hint in low for hint in _BROWSER_TITLE_HINTS):
        return None
    for brand, tokens in (
        ("librewolf", ("librewolf",)),
        ("waterfox", ("waterfox",)),
        ("floorp", ("floorp",)),
        ("edge", ("microsoft edge", "msedge")),
        ("brave", ("brave",)),
        ("opera", ("opera",)),
        ("vivaldi", ("vivaldi",)),
        ("chromium", ("chromium",)),
        ("chrome", ("google chrome",)),
        ("firefox", ("firefox", "mozilla firefox")),
    ):
        if any(token in low for token in tokens):
            return brand
    return None


def _read_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _proc_is_main(comm: str, argv: list[str]) -> bool:
    low = (comm or "").lower()
    if low.startswith(("chrome_crashpad", "crashpad")):
        return False
    joined = " ".join(argv)
    if any(token in joined for token in (
            "--type=", "-contentproc", "--content-process", "--crashpad-handler",
            "-crashhelper", "--utility-sub-type")):
        return False
    return True


def browser_processes() -> list[dict]:
    if os.name != "posix":
        return _windows_browser_processes()
    procs: list[dict] = []
    try:
        entries = list(Path("/proc").glob("[0-9]*"))
    except OSError:
        return procs
    for entry in entries:
        try:
            comm = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        low = comm.lower()
        # Crashpad handlers (Chrome's, Edge's, and other Electron apps such
        # as OpenCode) start with a browser name but are not browsers.
        if "crashpad" in low:
            continue
        if not any(low.startswith(b) for b in _BROWSERS):
            continue
        try:
            pid = int(entry.name)
        except ValueError:
            continue
        argv = _read_cmdline(pid)
        procs.append({
            "pid": pid,
            "comm": comm,
            "args": " ".join(argv),
            "argv": argv,
            "is_main": _proc_is_main(comm, argv),
        })
    return procs


def _windows_browser_processes() -> list[dict]:
    # Windows: only names and PIDs; kill via taskkill is sufficient.
    import csv

    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    procs = []
    for line in out.stdout.splitlines():
        try:
            parts = next(csv.reader([line]))
        except (ValueError, StopIteration):
            continue
        if len(parts) < 2:
            continue
        name = parts[0].lower()
        stem = name[:-4] if name.endswith(".exe") else name
        if not any(stem.startswith(b) for b in _BROWSERS):
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        procs.append({"pid": pid, "comm": stem, "args": "", "argv": [],
                      "is_main": True})
    return procs


def browsers_running() -> bool:
    return bool(browser_processes())


def incognito_launches(procs: Iterable[dict]) -> dict[str, set[int]]:
    """Map browser brand -> main PIDs launched with an incognito flag."""
    markers = {"--incognito", "--inprivate", "--private-window", "-private-window"}
    out: dict[str, set[int]] = {}
    for proc in procs:
        argv = proc.get("argv") or []
        if not markers.intersection(argv):
            continue
        brand = brand_for_comm(proc.get("comm", ""))
        if brand == "other" or not proc.get("is_main"):
            continue
        out.setdefault(brand, set()).add(int(proc["pid"]))
    return out


def _hard_kill_later(pids: set[int], families: set[str]) -> None:
    time.sleep(4)
    for proc in browser_processes():
        if proc["pid"] in pids or process_family(proc["comm"]) in families:
            try:
                os.kill(proc["pid"], signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass


def kill_browsers(reason: str, ctx=None, families: Optional[Iterable[str]] = None,
                  pids: Optional[Iterable[int]] = None,
                  brands: Optional[Iterable[str]] = None) -> list[str]:
    """Close browser processes.

    ``brands`` closes every process of those browser brands (the 3-minute
    extension rule), ``families`` closes whole engines, and ``pids`` closes
    only those browser main processes (the incognito watcher).  A targeted
    kill never falls back to the whole family in the SIGKILL retry, so a
    second Chrome profile is not collateral damage.

    SIGTERM first (Chrome/Firefox exit cleanly); still-alive processes are
    SIGKILLed a few seconds later.  The daemon never matches command-line
    patterns with pkill, so it can never kill the shell that started it.
    """
    want = set(families) if families else None
    want_pids = {int(pid) for pid in pids} if pids else None
    want_brands = set(brands) if brands else None
    with _kill_lock:
        now = time.time()
        if ctx is not None and now - float(getattr(ctx, "last_browser_kill", 0.0)) < KILL_COOLDOWN_SECONDS:
            return []
        procs = [p for p in browser_processes()
                 if "crashpad" not in p["comm"].lower()]
        if want_pids is not None:
            procs = [p for p in procs if p["pid"] in want_pids]
        elif want_brands is not None:
            procs = [p for p in procs if brand_for_comm(p["comm"]) in want_brands]
        elif want is not None:
            procs = [p for p in procs if process_family(p["comm"]) in want]
        if not procs:
            return []
        names = sorted({p["comm"] for p in procs})
        main_pids = {p["pid"] for p in procs if p["is_main"]}
        all_pids = {p["pid"] for p in procs}
        # A targeted kill must not turn into an engine-wide SIGKILL.
        target_families = (set() if (want_pids is not None or want_brands is not None)
                           else {process_family(p["comm"]) for p in procs})
        if ctx is not None:
            ctx.last_browser_kill = now
            ctx.last_browser_kill_reason = reason

        log.warn(f"[GUARD] closing browsers ({reason}): {', '.join(names)}")
        if os.name == "posix":
            for pid in (main_pids or all_pids):
                try:
                    os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
            threading.Thread(target=_hard_kill_later,
                             args=(all_pids, target_families),
                             name="jgu-hard-kill", daemon=True).start()
        else:
            for name in names:
                try:
                    subprocess.run(["taskkill", "/F", "/IM", name + ".exe"],
                                   capture_output=True, timeout=10)
                except Exception:
                    pass
        try:
            stats.record_event("browser_guard_kill", {
                "reason": reason,
                "browsers": names,
            })
        except Exception:
            pass
        return names


# ---------------------------------------------------------------------------
# X11 incognito window watcher
# ---------------------------------------------------------------------------

def _x_environments(procs: Iterable[dict]) -> list[dict]:
    envs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for proc in procs:
        try:
            raw = Path(f"/proc/{proc['pid']}/environ").read_bytes()
        except OSError:
            continue
        values = {}
        for item in raw.split(b"\0"):
            if b"=" not in item:
                continue
            key, _, value = item.partition(b"=")
            values[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
        display = values.get("DISPLAY")
        if not display:
            continue
        xauth = values.get("XAUTHORITY")
        home = values.get("HOME")
        candidates = []
        if xauth:
            candidates.append(xauth)
        if home:
            candidates.append(str(Path(home) / ".Xauthority"))
        uid = values.get("UID")
        if uid:
            candidates.append(f"/run/user/{uid}/gdm/Xauthority")
            candidates.append(f"/run/user/{uid}/Xauthority")
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                xauth = candidate
                break
        key = (display, xauth or "")
        if key in seen:
            continue
        seen.add(key)
        env = dict(os.environ)
        env["DISPLAY"] = display
        if xauth:
            env["XAUTHORITY"] = xauth
        envs.append(env)

    # Chrome 157 clears /proc/<pid>/environ (size 0).  As root (or the
    # desktop user) the standard X sockets + ~/.Xauthority are enough.
    for home in _home_dirs():
        try:
            uid = home.stat().st_uid
        except OSError:
            continue
        xauth = None
        for candidate in (home / ".Xauthority",
                          Path(f"/run/user/{uid}/gdm/Xauthority"),
                          Path(f"/run/user/{uid}/Xauthority")):
            try:
                if candidate.is_file():
                    xauth = candidate
                    break
            except OSError:
                continue
        if xauth is None:
            continue
        for display in (":0", ":1"):
            try:
                if not Path(f"/tmp/.X11-unix/X{display[1:]}").exists():
                    continue
            except OSError:
                continue
            key = (display, str(xauth))
            if key in seen:
                continue
            seen.add(key)
            env = dict(os.environ)
            env["DISPLAY"] = display
            env["XAUTHORITY"] = str(xauth)
            envs.append(env)
    return envs


def _xdotool(exe: str, args: list[str], env: dict) -> str:
    try:
        out = subprocess.run([exe, *args], env=env, capture_output=True,
                             text=True, timeout=3)
    except Exception:
        return ""
    return out.stdout


def find_incognito_windows(procs: Optional[Iterable[dict]] = None) -> list[tuple[str, str, int]]:
    """Return ``(title, brand, pid)`` for visible incognito/private windows.

    ``xdotool search`` and the two getters enumerate the same windows in the
    same order, so the listings are paired by index.  The PID lets the caller
    close only the browser instance that owns the window (a second Chrome
    profile with the extension is left alone).
    """
    if os.name != "posix":
        return []
    exe = shutil.which("xdotool")
    if not exe:
        return []
    procs = list(procs) if procs is not None else browser_processes()
    if not procs:
        return []
    hits: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    search = ["search", "--onlyvisible", "--name", "."]
    for env in _x_environments(procs):
        ids = _xdotool(exe, search, env).split()
        names_raw = _xdotool(exe, search + ["getwindowname", "%@"], env)
        pids_raw = _xdotool(exe, search + ["getwindowpid", "%@"], env)
        names = names_raw.rstrip("\n").split("\n") if names_raw else []
        pids = pids_raw.rstrip("\n").split("\n") if pids_raw else []
        if len(names) != len(ids) or len(pids) != len(ids):
            # The three listings must stay aligned; without PIDs the caller
            # falls back to closing the whole brand.
            pids = []
        for index, raw_title in enumerate(names):
            title = raw_title.strip()
            if not title:
                continue
            low = title.lower()
            if not any(marker in low for marker in _INCOGNITO_MARKERS):
                continue
            brand = brand_from_title(title)
            if not brand:
                continue
            pid = 0
            if index < len(pids):
                try:
                    pid = int(pids[index].strip())
                except ValueError:
                    pid = 0
            key = (brand, title, pid)
            if key in seen:
                continue
            seen.add(key)
            hits.append((title, brand, pid))
    return hits


def _brand_record(ext: dict, brand: str) -> dict:
    browsers = ext.get("browsers")
    if isinstance(browsers, dict):
        rec = browsers.get(brand)
        if isinstance(rec, dict) and rec:
            return rec
        # Transitional: an earlier 3.2 test build stored engine-level keys.
        engine = engine_for_brand(brand)
        rec = browsers.get(engine)
        if isinstance(rec, dict) and rec:
            if brand_for_label(str(rec.get("browser") or "")) == brand:
                return rec
    # Legacy 3.1.x heartbeat: only global fields exist.
    if not browsers and brand_for_label(ext.get("browser", "")) == brand:
        return ext
    return {}


def _brand_connected(ext: dict, brand: str) -> bool:
    return bool(_brand_record(ext, brand).get("connected"))


def _brand_ok(ext: dict, brand: str) -> bool:
    rec = _brand_record(ext, brand)
    return bool(rec.get("connected") and rec.get("incognito_access") is True)


_PROFILE_READY_TTL = 10.0
_profile_ready_cache: dict[str, tuple[float, bool]] = {}


def _profile_incognito_ready(brand: str) -> bool:
    """Chromium: read the profile's user-scoped "Allow in incognito" pref.

    Chrome 157 service workers do not reliably expose
    ``chrome.extension.isAllowedIncognitoAccess`` (it can resolve to null),
    while the preference written by the toggle is authoritative and readable
    by the daemon.  A brand is ready when the extension is installed in at
    least one of its profiles and every profile that has it also has the
    incognito preference enabled.  Profiles without the extension are ignored
    so unused Chrome profiles do not lock the main one.
    """
    now = time.time()
    cached = _profile_ready_cache.get(brand)
    if cached and now - cached[0] < _PROFILE_READY_TTL:
        return cached[1]
    try:
        target = extension_dir().resolve()
    except OSError:
        target = extension_dir()
    found = False
    for pref, family in _chromium_preferences():
        if family != brand:
            continue
        data = _read_json(pref)
        if not data:
            continue
        settings = (data.get("extensions") or {}).get("settings") or {}
        if not isinstance(settings, dict):
            continue
        for ext_id, info in settings.items():
            if not isinstance(info, dict):
                continue
            raw_path = info.get("path")
            same_path = False
            if raw_path:
                try:
                    same_path = Path(raw_path).resolve() == target
                except OSError:
                    same_path = (str(raw_path).rstrip("/")
                                 == str(target).rstrip("/"))
            if str(ext_id) != _KNOWN_EXTENSION_ID and not same_path:
                continue
            found = True
            if info.get("incognito") is not True:
                _profile_ready_cache[brand] = (now, False)
                return False
    _profile_ready_cache[brand] = (now, found)
    return found


def _brand_allowed(ext: dict, brand: str) -> bool:
    """Is incognito/private browsing allowed for this browser brand now?"""
    if not _brand_connected(ext, brand):
        return False
    if engine_for_brand(brand) == "chromium":
        return _profile_incognito_ready(brand)
    return bool(_brand_record(ext, brand).get("incognito_access") is True)


def _incognito_protected(ctx, brand: str) -> bool:
    try:
        return _brand_allowed(ctx.extension_info(), brand)
    except Exception:
        return False


def start_watcher(ctx, stop_event) -> Optional[threading.Thread]:
    """Poll visible X11 window titles for new incognito/private windows."""
    global _watcher_logged
    if os.name != "posix":
        return None
    if not shutil.which("xdotool"):
        if not _watcher_logged:
            _watcher_logged = True
            log.info("[GUARD] xdotool not installed — incognito window title watcher disabled")
        return None

    def loop() -> None:
        while stop_event.is_set():
            try:
                procs = browser_processes()
                hits = find_incognito_windows(procs) if procs else []
                if hits:
                    main_pids = {p["pid"] for p in procs if p["is_main"]}
                    by_brand: dict[str, dict] = {}
                    for title, brand, pid in hits:
                        entry = by_brand.setdefault(
                            brand, {"titles": [], "pids": set()})
                        entry["titles"].append(title)
                        if pid in main_pids:
                            entry["pids"].add(pid)
                    for brand, entry in by_brand.items():
                        target_pids = entry["pids"]
                        if _incognito_protected(ctx, brand):
                            hint = ctx.incognito_hints.get(brand)
                            if not isinstance(hint, dict):
                                hint = {"at": time.time(), "pids": set(),
                                        "titles": []}
                                ctx.incognito_hints[brand] = hint
                            hint["at"] = time.time()
                            hint["pids"] |= target_pids
                            hint["titles"] = entry["titles"]
                        else:
                            log.warn(f"[GUARD] incognito/private window without the "
                                     f"extension: {entry['titles'][0][:120]}")
                            if target_pids:
                                kill_browsers("incognito_without_extension", ctx,
                                              pids=target_pids)
                            else:
                                kill_browsers("incognito_without_extension", ctx,
                                              brands={brand})
            except Exception as exc:  # never let the watcher die
                log.warn(f"[GUARD] incognito watcher error: {exc}")
            stop_event.wait(2.0)

    thread = threading.Thread(target=loop, name="jgu-incognito-watcher",
                              daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Policies (incognito / private browsing)
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: dict) -> bool:
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    try:
        if path.is_file() and path.read_text(encoding="utf-8", errors="replace") == text:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def set_incognito_policies(chromium_allowed: dict[str, bool], firefox_allowed: bool) -> None:
    """Keep each browser's policy in sync with its own extension heartbeat.

    Chrome and Edge (etc.) have separate policy directories; allowing
    incognito in Chrome must never allow it in Edge where the extension is
    not installed.
    """
    global _last_incognito_log
    for brand, directory in vpnblock.chrome_policy_dirs_by_brand().items():
        value = 0 if chromium_allowed.get(brand) else 1
        _write_json(Path(directory) / "justgivenup-incognito.json",
                    {"IncognitoModeAvailability": value})

    firefox_value = 0 if firefox_allowed else 1
    for path in vpnblock.FIREFOX_POLICY_FILES:
        if not path.is_file():
            continue
        data = _read_json(path) or {}
        policies = data.setdefault("policies", {})
        if not isinstance(policies, dict):
            continue
        if policies.get("PrivateBrowsingModeAvailability") != firefox_value:
            policies["PrivateBrowsingModeAvailability"] = firefox_value
            _write_json(path, data)

    state = (tuple(sorted(chromium_allowed.items())), firefox_allowed)
    if state != _last_incognito_log:
        _last_incognito_log = state
        allowed = ", ".join(f"{brand}={'yes' if value else 'no'}"
                            for brand, value in sorted(chromium_allowed.items())) or "none"
        log.info("[GUARD] incognito allowed: %s; private browsing (firefox)=%s"
                 % (allowed, firefox_allowed))


# ---------------------------------------------------------------------------
# Chromium "allow in incognito" preference patch
# ---------------------------------------------------------------------------

def _home_dirs() -> list[Path]:
    homes: list[Path] = []
    try:
        homes.extend(p for p in Path("/home").iterdir() if p.is_dir())
    except OSError:
        pass
    if Path("/root").is_dir():
        homes.append(Path("/root"))
    return homes


def _chromium_preferences() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for home in _home_dirs():
        for rel, family in _PROFILE_ROOTS:
            base = home / rel
            try:
                if not base.is_dir():
                    continue
                direct = base / "Preferences"
                if direct.is_file():
                    out.append((direct, family))
                for pref in base.glob("*/Preferences"):
                    if pref.is_file():
                        out.append((pref, family))
            except OSError:
                continue
    # de-duplicate (Opera has Preferences directly and maybe also a subdir)
    seen: set[Path] = set()
    unique: list[tuple[Path, str]] = []
    for pref, family in out:
        if pref in seen:
            continue
        seen.add(pref)
        unique.append((pref, family))
    return unique


def _profile_family_running(family: str, procs: Iterable[dict]) -> bool:
    prefixes = _FAMILY_COMMS.get(family, ())
    for proc in procs:
        if not proc.get("is_main"):
            continue
        low = proc["comm"].lower()
        if any(low.startswith(prefix) for prefix in prefixes):
            return True
    return False


def _patch_preferences_file(pref: Path) -> bool:
    data = _read_json(pref)
    if not data:
        return False
    settings = (data.get("extensions") or {}).get("settings") or {}
    if not isinstance(settings, dict):
        return False
    try:
        target = extension_dir().resolve()
    except OSError:
        target = extension_dir()
    changed = False
    for ext_id, info in settings.items():
        if not isinstance(info, dict):
            continue
        raw_path = info.get("path")
        same_path = False
        if raw_path:
            try:
                same_path = Path(raw_path).resolve() == target
            except OSError:
                same_path = str(raw_path).rstrip("/") == str(target).rstrip("/")
        if str(ext_id) != _KNOWN_EXTENSION_ID and not same_path:
            continue
        if info.get("incognito") is not True:
            info["incognito"] = True
            changed = True
    if not changed:
        return False
    try:
        st = pref.stat()
        tmp = pref.with_name(pref.name + ".jgu-tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
        try:
            os.chmod(tmp, st.st_mode & 0o7777)
        except OSError:
            pass
        try:
            os.chown(tmp, st.st_uid, st.st_gid)
        except OSError:
            pass
        tmp.replace(pref)
    except OSError as exc:
        log.warn(f"[GUARD] could not patch {pref}: {exc}")
        return False
    log.info(f"[GUARD] enabled incognito access for the extension in {pref}")
    return True


def patch_incognito_prefs(force: bool = False) -> int:
    """Enable "Allow in Incognito" for the extension when a browser is closed.

    Chrome overwrites Preferences while it is running, so this is done only
    for browser profiles whose process is not running.  Ownership/mode are
    preserved (the daemon is usually root, the profile belongs to the user).
    """
    global _last_pref_patch
    now = time.time()
    if not force and now - _last_pref_patch < PREF_PATCH_SECONDS:
        return 0
    _last_pref_patch = now
    procs = browser_processes()
    patched = 0
    for pref, family in _chromium_preferences():
        if _profile_family_running(family, procs):
            continue
        if _patch_preferences_file(pref):
            patched += 1
    if patched:
        log.info(f"[GUARD] incognito access patched in {patched} profile(s)")
    return patched


# ---------------------------------------------------------------------------
# Periodic maintenance + enforcement
# ---------------------------------------------------------------------------

def maintain(ctx) -> None:
    patch_incognito_prefs()
    now = time.time()
    if now - float(getattr(ctx, "last_vpn_scan", 0.0)) < VPN_SCAN_SECONDS:
        return
    ctx.last_vpn_scan = now
    try:
        extra: set[str] = set()
        try:
            extra |= vpnblock.scan_installed_chrome_ids(
                exclude_paths=(extension_dir(),))
        except Exception as exc:
            log.warn(f"[GUARD] Chromium VPN scan failed: {exc}")
        try:
            extra |= vpnblock.scan_installed_firefox_ids()
        except Exception as exc:
            log.warn(f"[GUARD] Firefox VPN scan failed: {exc}")
        if vpnblock.apply_chrome_extension_policy(
                vpnblock.chrome_policy_dirs(), extra):
            log.info("[GUARD] blocked VPN/proxy extensions in Chromium policy")
        if vpnblock.apply_firefox_extension_policy(extra):
            log.info("[GUARD] blocked VPN/proxy add-ons in Firefox policy")
    except Exception as exc:
        log.warn(f"[GUARD] VPN policy update failed: {exc}")


def enforce(ctx) -> None:
    now = time.time()
    last = float(getattr(ctx, "last_guard_tick", 0.0))
    dt = 60.0 if last <= 0 else max(0.0, min(now - last, 60.0))
    ctx.last_guard_tick = now

    ext = ctx.extension_info()
    procs = browser_processes()
    running_brands = {brand_for_comm(p["comm"])
                      for p in procs if p.get("is_main")}
    running_brands.discard("other")

    # Per-brand incognito policy: Chrome's extension must not enable
    # incognito in Edge/Brave/... where it is not installed.
    policy_dirs = vpnblock.chrome_policy_dirs_by_brand()
    incognito_allowed: dict[str, bool] = {
        brand: _brand_allowed(ext, brand) for brand in policy_dirs
    }
    for brand in _FIREFOX_BRANDS:
        rec = _brand_record(ext, brand)
        if rec or brand in running_brands:
            incognito_allowed[brand] = _brand_allowed(ext, brand)
    firefox_allowed = any(_brand_allowed(ext, brand) for brand in _FIREFOX_BRANDS)
    set_incognito_policies(incognito_allowed, firefox_allowed)
    patch_incognito_prefs()

    # 1) close every brand that has no fresh extension heartbeat
    due: set[str] = set()
    for brand in running_brands:
        if _brand_connected(ext, brand):
            ctx.extension_kill_since.pop(brand, None)
            continue
        since = ctx.extension_kill_since.get(brand)
        if since is None:
            ctx.extension_kill_since[brand] = now
            continue
        if now - since >= EXTENSION_KILL_SECONDS:
            due.add(brand)
            ctx.extension_kill_since[brand] = now
    for brand in list(ctx.extension_kill_since):
        if brand not in running_brands:
            ctx.extension_kill_since.pop(brand, None)
    if due:
        kill_browsers("extension_not_installed_or_disabled", ctx, brands=due)
        stats.record_event("extension_required_kill", {
            "brands": sorted(due),
            "grace_seconds": EXTENSION_KILL_SECONDS,
        })

    # 2) command-line incognito/private launches
    main_pids = {p["pid"] for p in procs if p["is_main"]}
    for brand, launch_pids in incognito_launches(procs).items():
        if _brand_allowed(ext, brand):
            continue
        target = launch_pids & main_pids
        if target:
            kill_browsers("incognito_without_extension", ctx, pids=target)
        else:
            kill_browsers("incognito_without_extension", ctx, brands={brand})
        stats.record_event("incognito_blocked", {"brand": brand,
                                                  "via": "cmdline"})

    # 3) window-title hints recorded by the X11 watcher
    for brand, raw_hint in list(ctx.incognito_hints.items()):
        hint_pids: set[int] = set()
        if isinstance(raw_hint, dict):
            hinted = float(raw_hint.get("at") or 0.0)
            for value in raw_hint.get("pids") or ():
                try:
                    pid = int(value)
                except (TypeError, ValueError):
                    continue
                if pid in main_pids:
                    hint_pids.add(pid)
        else:
            hinted = float(raw_hint or 0.0)
        if not _brand_allowed(ext, brand):
            if hint_pids:
                kill_browsers("incognito_without_extension", ctx, pids=hint_pids)
            else:
                kill_browsers("incognito_without_extension", ctx, brands={brand})
            ctx.incognito_hints.pop(brand, None)
            stats.record_event("incognito_blocked", {"brand": brand,
                                                      "via": "window"})
            continue
        rec = _brand_record(ext, brand)
        # Either the extension loaded in an incognito context (split mode) or
        # it can see the incognito window from its normal context (spanning
        # mode).  Both prove it really has access; the latter is what Chrome
        # MV3 extensions normally report.
        proof = max(float(rec.get("incognito_context_at") or 0.0),
                    float(rec.get("incognito_seen_at") or 0.0))
        if proof >= hinted:
            ctx.incognito_hints.pop(brand, None)
        elif now - hinted >= INCOGNITO_PROOF_SECONDS:
            if hint_pids:
                kill_browsers("incognito_extension_not_running_there", ctx,
                              pids=hint_pids)
            else:
                kill_browsers("incognito_extension_not_running_there", ctx,
                              brands={brand})
            ctx.incognito_hints.pop(brand, None)
            stats.record_event("incognito_blocked", {
                "brand": brand, "via": "no_incognito_heartbeat"})

    # 4) an incognito window was seen recently, then the extension went away
    for brand in running_brands:
        rec = _brand_record(ext, brand)
        seen = float(rec.get("incognito_seen_at") or 0.0)
        if seen and now - seen < 300 and not _brand_connected(ext, brand):
            kill_browsers("incognito_extension_stopped", ctx, brands={brand})
            stats.record_event("incognito_blocked", {
                "brand": brand, "via": "heartbeat_stopped"})

    # 5) accumulate unprotected browser time for the 15-minute tamper penalty
    if (ext.get("ever_seen") and not ext.get("connected")
            and not ext.get("miss_flag") and procs):
        ctx.extension_missing_accum += dt
    elif ext.get("connected"):
        ctx.extension_missing_accum = 0.0

    chromium_all_allowed = all(
        incognito_allowed.get(brand, False)
        for brand in policy_dirs) if policy_dirs else False
    ctx.guard_state = {
        "browsers_running": sorted(running_brands),
        "chromium_running": any(engine_for_brand(brand) == "chromium"
                                for brand in running_brands),
        "firefox_running": any(engine_for_brand(brand) == "firefox"
                               for brand in running_brands),
        "incognito_allowed": incognito_allowed,
        "incognito_allowed_by_engine": {
            "chromium": chromium_all_allowed,
            "firefox": firefox_allowed,
        },
        "extension_required_seconds": EXTENSION_KILL_SECONDS,
        "extension_missing_seconds": int(ctx.extension_missing_accum),
        "last_kill_at": int(float(getattr(ctx, "last_browser_kill", 0.0))),
        "last_kill_reason": getattr(ctx, "last_browser_kill_reason", ""),
    }
