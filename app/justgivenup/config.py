"""Paths, configuration and shared helpers.

State directory resolution (first match wins):
  1. $JGU_STATE_DIR                      (tests / portable mode)
  2. Windows: %PROGRAMDATA%\JustGivenUp  (falls back to %LOCALAPPDATA%)
  3. Linux/macOS: /var/lib/justgivenup   (created by the .deb postinst, root)
     otherwise: ~/.local/share/justgivenup  (dev / manual run)

A mirror of the time-lock lives in a second, separately-protected location
so deleting the primary file is detected as tampering (see lock.py).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import DASHBOARD_PORT, VERSION

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

IS_WINDOWS = sys.platform == "win32"


def repo_root() -> Path:
    """Source tree root when running from a checkout, package root otherwise."""
    here = Path(__file__).resolve()
    # .../app/justgivenup/config.py -> repo root is two levels up
    cand = here.parent.parent.parent
    if (cand / "app" / "justgivenup").is_dir():
        return cand
    return here.parent


def state_dir() -> Path:
    env = os.environ.get("JGU_STATE_DIR")
    if env:
        p = Path(env)
    elif IS_WINDOWS:
        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        localappdata = os.environ.get("LOCALAPPDATA")
        p = Path(programdata) / "JustGivenUp"
        if localappdata and not _can_write(p) and not _can_write(p.parent):
            p = Path(localappdata) / "JustGivenUp"
    else:
        system = Path("/var/lib/justgivenup")
        p = system if system.exists() else Path.home() / ".local" / "share" / "justgivenup"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        p = Path.home() / ".local" / "share" / "justgivenup"
        p.mkdir(parents=True, exist_ok=True)
    return p


def mirror_dir() -> Path:
    """Second location holding a copy of the sealed lock."""
    env = os.environ.get("JGU_MIRROR_DIR")
    if env:
        p = Path(env)
    elif IS_WINDOWS:
        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        p = Path(programdata) / "JustGivenUpMirror"
    else:
        p = Path("/etc/justgivenup")
        if not _can_write(p.parent):  # dev mode without root
            p = state_dir() / ".mirror"
    try:
        p.mkdir(parents=True, exist_ok=True)
        if not IS_WINDOWS:
            os.chmod(p, 0o700)
    except OSError:
        p = state_dir() / ".mirror"
        p.mkdir(parents=True, exist_ok=True)
    return p


def _can_write(path: Path) -> bool:
    try:
        if not path.exists():
            return os.access(path.parent, os.W_OK)
        return os.access(path, os.W_OK)
    except OSError:
        return False


def hosts_path() -> Path:
    env = os.environ.get("JGU_HOSTS_FILE")
    if env:
        return Path(env)
    if IS_WINDOWS:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        return Path(windir) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def web_root() -> Path:
    env = os.environ.get("JGU_WEB_ROOT")
    if env:
        return Path(env)
    # installed layout: /usr/lib/justgivenup/web
    installed = Path(__file__).resolve().parent / "web"
    if installed.is_dir():
        return installed
    # source checkout: app/web
    dev = Path(__file__).resolve().parent.parent / "web"
    return dev


def extension_dir() -> Path:
    env = os.environ.get("JGU_EXTENSION_DIR")
    if env:
        return Path(env)
    installed = Path(__file__).resolve().parent / "extension"
    if installed.is_dir():
        return installed
    dev = repo_root() / "extension"
    return dev


def blocklist_path() -> Path:
    env = os.environ.get("JGU_BLOCKLIST")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    for cand in (here / "data" / "blocklist_full.txt", repo_root() / "data" / "blocklist_full.txt"):
        if cand.is_file():
            return cand
    return here / "data" / "blocklist_full.txt"


def core_blocklist_path() -> Path:
    here = Path(__file__).resolve().parent
    for cand in (here / "data" / "blocklist_core.txt", repo_root() / "data" / "blocklist_core.txt"):
        if cand.is_file():
            return cand
    return here / "data" / "blocklist_core.txt"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "language": "ar",           # "ar" | "en"
    "port": DASHBOARD_PORT,
    "hosts_block": True,        # enforce /etc/hosts while locked (needs root)
    "penalty_days": 90,         # extra days added on any tamper attempt
    "setup_complete": False,
    "app_version": VERSION,
    "profile": {"name": "", "goal": ""},
    "custom_domains": [],       # extra domains the user adds to the blocklist
    "extension": {"last_seen": 0.0, "version": "", "browser": "", "ever_seen": False},
}


def config_path() -> Path:
    return state_dir() / "config.json"


class Config:
    def __init__(self) -> None:
        self.path = config_path()
        self.data = dict(DEFAULT_CONFIG)
        if self.path.is_file():
            try:
                on_disk = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(on_disk, dict):
                    for key, value in on_disk.items():
                        if key == "profile" and isinstance(value, dict):
                            merged = dict(DEFAULT_CONFIG["profile"])
                            merged.update(value)
                            self.data["profile"] = merged
                        elif key == "extension" and isinstance(value, dict):
                            merged = dict(DEFAULT_CONFIG["extension"])
                            merged.update(value)
                            self.data["extension"] = merged
                        else:
                            self.data[key] = value
            except (OSError, json.JSONDecodeError):
                pass
        self.data["app_version"] = VERSION

    # -- helpers ------------------------------------------------------------
    def save(self) -> None:
        path = config_path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass

    @property
    def language(self) -> str:
        return "ar" if self.data.get("language") == "ar" else "en"

    @property
    def port(self) -> int:
        try:
            return int(self.data.get("port") or DASHBOARD_PORT)
        except (TypeError, ValueError):
            return DASHBOARD_PORT

    @property
    def penalty_days(self) -> int:
        try:
            return max(1, int(self.data.get("penalty_days") or 90))
        except (TypeError, ValueError):
            return 90

    @property
    def hosts_block(self) -> bool:
        return bool(self.data.get("hosts_block", True))
