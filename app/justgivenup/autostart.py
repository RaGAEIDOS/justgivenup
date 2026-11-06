"""Start-with-the-system handling.

Linux (packaged): the .deb ships a systemd unit + timer; this module
reports/toggles them via systemctl when available.

Linux (manual/dev): XDG autostart desktop entry in ~/.config/autostart.

Windows: HKCU Run value (works without admin) plus, when elevated, a
scheduled task that starts the daemon with highest privileges so the
hosts layer is available.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import log
from .config import IS_WINDOWS

SYSTEMD_UNIT = "justgivenup.service"
SYSTEMD_TIMER = "justgivenup-watchdog.timer"


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def _has_systemctl() -> bool:
    from shutil import which

    return (not IS_WINDOWS) and which("systemctl") is not None


def is_installed_package() -> bool:
    return Path("/usr/lib/justgivenup").is_dir() and Path(
        "/lib/systemd/system/" + SYSTEMD_UNIT
    ).exists() or Path("/usr/lib/systemd/system/" + SYSTEMD_UNIT).exists()


# ---------------------------------------------------------------------------
# Linux / systemd
# ---------------------------------------------------------------------------

def systemd_status() -> dict:
    if not _has_systemctl():
        return {"available": False}
    code, out = _run(["systemctl", "is-enabled", SYSTEMD_UNIT])
    enabled = code == 0 and out.strip() == "enabled"
    code2, out2 = _run(["systemctl", "is-active", SYSTEMD_UNIT])
    active = code2 == 0 and out2.strip() == "active"
    return {"available": True, "enabled": enabled, "active": active, "detail": out}


def systemd_enable() -> tuple[bool, str]:
    if not _has_systemctl():
        return False, "systemctl not available"
    rc1, out1 = _run(["systemctl", "enable", "--now", SYSTEMD_UNIT])
    rc2, out2 = _run(["systemctl", "enable", "--now", SYSTEMD_TIMER])
    ok = rc1 == 0 or rc2 == 0
    return ok, (out1 + "\n" + out2).strip()


def systemd_disable() -> tuple[bool, str]:
    if not _has_systemctl():
        return False, "systemctl not available"
    rc1, out1 = _run(["systemctl", "disable", "--now", SYSTEMD_TIMER])
    rc2, out2 = _run(["systemctl", "disable", "--now", SYSTEMD_UNIT])
    ok = rc1 == 0 or rc2 == 0
    return ok, (out1 + "\n" + out2).strip()


# ---------------------------------------------------------------------------
# XDG autostart (fallback without systemd, e.g. dev mode)
# ---------------------------------------------------------------------------

def _xdg_entry_path() -> Path:
    return Path.home() / ".config" / "autostart" / "justgivenup.desktop"


def _xdg_is_installed() -> bool:
    return _xdg_entry_path().exists()


def _xdg_install() -> bool:
    path = _xdg_entry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        exe = _daemon_invocation()
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=JustGivenUp! Guardian\n"
            "Comment=Porn blocker with time-lock\n"
            f"Exec={exe}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "NoDisplay=true\n",
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        log.warn(f"[AUTOSTART] XDG install failed: {exc}")
        return False


def _xdg_remove() -> bool:
    try:
        _xdg_entry_path().unlink()
        return True
    except OSError:
        return False


def _daemon_invocation() -> str:
    # prefer the packaged wrapper, fall back to module invocation
    if Path("/usr/bin/justgivenup").exists():
        return "/usr/bin/justgivenup run"
    return f"{sys.executable} -m justgivenup run"


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _win_run_key():
    import winreg  # type: ignore

    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
    )


def windows_status() -> dict:
    if not IS_WINDOWS:
        return {"available": False}
    try:
        key = _win_run_key()
        winreg = __import__("winreg")
        try:
            winreg.QueryValueEx(key, "JustGivenUp")
            present = True
        except OSError:
            present = False
        finally:
            winreg.CloseKey(key)
        return {"available": True, "enabled": present}
    except Exception:
        return {"available": False}


def windows_enable() -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "Windows only"
    try:
        import winreg  # type: ignore

        key = _win_run_key()
        cmd = f'"{sys.executable}" -m justgivenup run'
        wrapper = Path(os.environ.get("PROGRAMDATA", "")) / "JustGivenUp" / "run.bat"
        if wrapper.exists():
            cmd = f'"{wrapper}"'
        winreg.SetValueEx(key, "JustGivenUp", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True, "Run key set"
    except Exception as exc:
        return False, str(exc)


def windows_disable() -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "Windows only"
    try:
        import winreg  # type: ignore

        key = _win_run_key()
        try:
            winreg.DeleteValue(key, "JustGivenUp")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return True, "Run key removed"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def status() -> dict:
    if IS_WINDOWS:
        st = windows_status()
        st["mode"] = "windows-run"
        return st
    if _has_systemctl() and (is_installed_package() or _unit_files_exist()):
        st = systemd_status()
        st["mode"] = "systemd"
        return st
    return {
        "available": True,
        "enabled": _xdg_is_installed(),
        "mode": "xdg-autostart",
    }


def _unit_files_exist() -> bool:
    from shutil import which

    if which("systemctl") is None:
        return False
    for d in ("/lib/systemd/system", "/usr/lib/systemd/system", "/etc/systemd/system"):
        if (Path(d) / SYSTEMD_UNIT).exists():
            return True
    return False


def enable() -> tuple[bool, str]:
    if IS_WINDOWS:
        return windows_enable()
    if _has_systemctl() and _unit_files_exist():
        return systemd_enable()
    return (True, "XDG autostart entry installed") if _xdg_install() else (False, "failed")


def disable() -> tuple[bool, str]:
    if IS_WINDOWS:
        return windows_disable()
    if _has_systemctl() and _unit_files_exist():
        return systemd_disable()
    return (True, "XDG autostart entry removed") if _xdg_remove() else (False, "failed")
