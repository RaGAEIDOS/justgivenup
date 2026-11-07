"""The daemon loop: dashboard server + continuous enforcement.

Every cycle (15s):
  1. reload the lock if it changed on disk (CLI / other process)
  2. verify seals, detect clock jumps        -> +90 days on tamper
  3. drop an expired lock
  4. apply / clean the managed hosts block   (re-applied if edited)
  5. watch the extension heartbeat           -> penalty if removed while locked
  6. refresh streak counters periodically

A pidfile with an exclusive lock keeps a single instance; systemd's
Restart=always (plus the watchdog timer) brings it back if it is killed.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path

from . import VERSION, log
from . import stats
from .blocklist import full_domains
from .context import AppContext
from .server import DashboardServer

TICK_SECONDS = 15
EXTENSION_MISS_SECONDS = 900    # 15 min: browsers up, extension silent => tamper

_running = threading.Event()


def _mono() -> float:
    """Monotonic clock that also advances across system suspend (Linux)."""
    try:
        return time.clock_gettime(time.CLOCK_BOOTTIME)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return time.monotonic()


# ---------------------------------------------------------------------------
# Single instance
# ---------------------------------------------------------------------------

class _PidFile:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        try:
            self._fh = open(self.path, "a+", encoding="utf-8")
        except OSError as exc:
            log.warn(f"[DAEMON] pidfile open failed: {exc}")
            return True  # non-fatal
        if os.name == "posix":
            import fcntl

            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return False
        else:  # best effort on Windows
            self._fh.seek(0)
            old = self._fh.read().strip()
            if old and old.isdigit() and _pid_alive(int(old)):
                return False
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(str(os.getpid()))
        self._fh.flush()
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.close()
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
        self._fh = None


def _pid_alive(pid: int) -> bool:
    if os.name == "posix":
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Browser detection (for the extension heartbeat verdict)
# ---------------------------------------------------------------------------

_BROWSERS = ("chrome", "chromium", "firefox", "brave", "msedge", "edge", "opera",
             "vivaldi", "opera_gx", "librewolf", "waterfox", "floorp", "tor")


def _browsers_running() -> bool:
    if os.name == "posix":
        proc = Path("/proc")
        if not proc.is_dir():
            return False
        try:
            for comm in proc.glob("[0-9]*/comm"):
                try:
                    name = comm.read_text(encoding="utf-8", errors="replace").strip().lower()
                except OSError:
                    continue
                for browser in _BROWSERS:
                    if name.startswith(browser):
                        return True
        except OSError:
            return False
        return False
    # Windows
    try:
        import subprocess

        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=10)
        low = out.stdout.lower()
        return any(b in low for b in _BROWSERS)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# One enforcement cycle
# ---------------------------------------------------------------------------

def _reload_lock_if_changed(ctx: AppContext, cache: dict) -> None:
    stamp = {}
    for path in (ctx.lock.primary, ctx.lock.mirror_file):
        try:
            st = path.stat()
            stamp[str(path)] = (st.st_mtime_ns, st.st_size)
        except OSError:
            stamp[str(path)] = None
    if stamp != cache:
        ctx.lock.load()
        cache.clear()
        cache.update(stamp)


def _watch_extension(ctx: AppContext) -> None:
    ext = ctx.extension_info()
    now = time.time()
    if not ext["ever_seen"]:
        ctx.browser_seen_running_since = None
        return
    if ext["connected"] or ext["miss_flag"]:
        ctx.browser_seen_running_since = None
        return
    if not _browsers_running():
        ctx.browser_seen_running_since = None
        return
    if ctx.browser_seen_running_since is None:
        ctx.browser_seen_running_since = now
        return
    browser_uptime = now - ctx.browser_seen_running_since
    silence = now - (ext["last_seen"] or 0)
    if browser_uptime >= EXTENSION_MISS_SECONDS and silence >= EXTENSION_MISS_SECONDS:
        if ctx.lock.is_locked():
            # extension removed while locked => penalty
            ctx.lock.penalize("browser extension removed or disabled while locked")
        else:
            # extension removed and no lock => auto-lock for 90 days
            try:
                ctx.lock.set_lock(90)
                from . import stats
                stats.record_event("lock_set", {
                    "days": 90,
                    "reason": "extension_removed_auto_lock",
                })
                log.warn("[DAEMON] Extension removed -> auto-lock for 90 days")
            except Exception as exc:
                log.error(f"[DAEMON] auto-lock failed: {exc}")
        cfg_ext = ctx.config.data.setdefault("extension", {})
        cfg_ext["miss_flag"] = True
        ctx.config.save()
        ctx.browser_seen_running_since = now


def cycle(ctx: AppContext, lock_cache: dict, tick: int) -> None:
    _reload_lock_if_changed(ctx, lock_cache)
    ctx.lock.tick_clock()
    ctx.lock.expire_if_due()

    locked = ctx.lock.is_locked()
    if locked and ctx.config.hosts_block:
        ctx.enforcer.apply(full_domains())
    elif not locked:
        # removal must not be throttled (expiry -> release immediately);
        # when there is no block the call is just a cheap no-op read
        ctx.enforcer.apply([], force=True)

    _watch_extension(ctx)

    if tick % 4 == 0:  # once a minute
        stats.instance().refresh_streak()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(port: int | None = None) -> int:
    from .config import state_dir

    state = state_dir()
    try:
        from . import log as _log

        _log.set_state_dir(state)
    except Exception:
        pass

    pidfile = _PidFile(state / "daemon.pid")
    if not pidfile.acquire():
        log.info("[DAEMON] Already running -- exiting")
        return 0

    ctx = AppContext.build()
    if port:
        ctx.config.data["port"] = port

    def _shutdown(signum, _frame) -> None:
        log.info(f"[DAEMON] signal {signum} -- shutting down")
        _running.clear()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError):
            pass

    log.info(f"=== JustGivenUp! guardian v{VERSION} ({sys.platform}) ===")
    stats.record_event("service_start", {"version": VERSION})

    server = DashboardServer(ctx)
    if not server.start():
        pidfile.release()
        return 1

    # first enforcement pass
    lock_cache: dict = {}
    _reload_lock_if_changed(ctx, lock_cache)
    if ctx.lock.is_locked() and ctx.config.hosts_block:
        ctx.enforcer.apply(full_domains(), force=True)

    _running.set()
    tick = 0
    try:
        while _running.is_set():
            tick += 1
            try:
                cycle(ctx, lock_cache, tick)
            except Exception as exc:  # keep the loop alive no matter what
                log.error(f"[DAEMON] cycle failed: {exc}")
            # sleep in slices so SIGTERM stops us promptly (Event.wait()
            # returns immediately when the event is already set!)
            for _ in range(int(TICK_SECONDS * 10)):
                if not _running.is_set():
                    break
                time.sleep(0.1)
    finally:
        server.stop()
        stats.record_event("service_stop", {})
        pidfile.release()
        log.info("[DAEMON] stopped")
    return 0
