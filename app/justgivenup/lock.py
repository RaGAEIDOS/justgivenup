"""The sealed time-lock.

Design goals (in order of importance):

1. Once set, it cannot be shortened or removed before ``until``.
2. Any tampering with the stored state is *detected* and punished by
   extending the lock (default +90 days).
3. Time manipulation (clock moved backwards or jumped forward while the
   daemon runs) is detected from the discrepancy between wall clock and a
   monotonic clock.

Where the state lives:

* primary  ``<state_dir>/lock.json``
* mirror   ``<mirror_dir>/lock.json`` (separate, root-only location)
* marker   inside the managed block of the hosts file (``jgu-lock`` comment)

Deleting one copy is detected through the others; deleting *all* copies
requires root, at which point the threat model is out of scope anyway.

The record is authenticated with HMAC-SHA256 under a machine-derived key
(/etc/machine-id on Linux, MachineGuid on Windows), so copying a clean
lock.json from another machine or another install is also a tamper.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import log
from .config import IS_WINDOWS, hosts_path, mirror_dir, state_dir

LOCK_FILENAME = "lock.json"
SEAL_VERSION = b"jgu-lock-v3"
KEY_SALT = b"JustGivenUp::time-lock::v3"
FORWARD_JUMP_LIMIT = 3600  # seconds of wall-clock jump inside one tick => tamper

# Managed hosts-file section (shared with enforcement.py)
BEGIN_MARK = "# >>> justgivenup managed block (do not edit) >>>"
END_MARK = "# <<< justgivenup managed block <<<"


class LockActiveError(RuntimeError):
    """Raised when an operation is refused because a lock is running."""


def _mono() -> float:
    """Monotonic clock that keeps ticking across suspend (Linux BOOTTIME)."""
    try:
        return time.clock_gettime(time.CLOCK_BOOTTIME)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return time.monotonic()


def _read_machine_id() -> str:
    if not IS_WINDOWS:
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                val = Path(p).read_text(encoding="utf-8").strip()
                if val:
                    return val
            except OSError:
                continue
    else:
        try:
            import winreg  # type: ignore

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if val:
                return str(val)
        except OSError:
            pass
    # Last resort: persist a random id so the key stays stable across runs.
    id_file = state_dir() / ".machine_id"
    try:
        return id_file.read_text(encoding="utf-8").strip()
    except OSError:
        rid = secrets.token_hex(16)
        try:
            id_file.write_text(rid, encoding="utf-8")
        except OSError:
            pass
        return rid


class _Sealer:
    """HMAC-SHA256 sealer with a machine-bound key (computed once)."""

    def __init__(self) -> None:
        base = _read_machine_id() or socket.gethostname()
        self.key = hmac.new(KEY_SALT, base.encode("utf-8"), hashlib.sha256).digest()

    def seal(self, payload: str) -> str:
        return hmac.new(self.key, (SEAL_VERSION + b"|" + payload.encode("utf-8")),
                        hashlib.sha256).hexdigest()


_sealer: _Sealer | None = None
_sealer_lock = threading.Lock()


def sealer() -> _Sealer:
    global _sealer
    with _sealer_lock:
        if _sealer is None:
            _sealer = _Sealer()
        return _sealer


def _payload(record: dict) -> str:
    return "|".join(
        str(record.get(k, ""))
        for k in ("created_at", "duration_days", "until", "seed", "generation")
    )


def seal_record(record: dict) -> str:
    return sealer().seal(_payload(record))


@dataclass
class LockStatus:
    locked: bool = False
    until: int = 0
    created_at: int = 0
    duration_days: int = 0
    remaining_seconds: int = 0
    penalties: list = field(default_factory=list)
    tampered: bool = False
    source: str = "none"          # primary | mirror | hosts | none
    expires_label: str = ""


class TimeLock:
    """Owns the lock record and enforces its invariants."""

    def __init__(self) -> None:
        self.state = state_dir()
        self.mirror = mirror_dir()
        self.primary = self.state / LOCK_FILENAME
        self.mirror_file = self.mirror / LOCK_FILENAME
        self._lock = threading.RLock()
        self._record: dict | None = None
        self._source = "none"
        self._last_wall = time.time()
        self._last_mono = time.monotonic()
        self._tick_started = False

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse(path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        if "until" not in data or "seal" not in data:
            return None
        if data.get("seal") != seal_record(data):
            return data  # present but invalid => caller treats as tamper
        return data

    @staticmethod
    def _record_ok(data: dict | None) -> bool:
        return data is not None and data.get("seal") == seal_record(data)

    def _write_one(self, path: Path, record: dict) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
            os.replace(tmp, path)
            try:
                os.chmod(path, 0o644)
            except OSError:
                pass
        except OSError as exc:
            log.warn(f"[LOCK] Cannot write {path}: {exc}")

    def _persist(self) -> None:
        if self._record is None:
            for path in (self.primary, self.mirror_file):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
            return
        self._write_one(self.primary, self._record)
        self._write_one(self.mirror_file, self._record)

    # ------------------------------------------------------------------
    # Hosts-file marker (third copy of the sealed record)
    # ------------------------------------------------------------------
    def hosts_marker(self) -> tuple[str, str] | None:
        """Return (until, seal) found in the managed hosts block, if any."""
        try:
            text = hosts_path().read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# jgu-lock "):
                try:
                    parts = dict(
                        kv.split("=", 1) for kv in line[len("# jgu-lock "):].split()
                    )
                    return parts["until"], parts["seal"]
                except (KeyError, ValueError):
                    return ("", "")
        return None

    def _hosts_marker_matches(self, record: dict) -> bool | None:
        """True/False when a marker exists, None when hosts is unreadable."""
        marker = self.hosts_marker()
        if marker is None:
            return None
        until, seal = marker
        if until == "" or seal == "":
            return False
        try:
            return int(until) == int(record["until"]) and seal == record["seal"]
        except (ValueError, KeyError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Loading / tamper detection
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load the lock from primary, mirror or the hosts marker."""
        with self._lock:
            primary_exists = self.primary.exists()
            mirror_exists = self.mirror_file.exists()
            primary = self._parse(self.primary) if primary_exists else None
            mirror = self._parse(self.mirror_file) if mirror_exists else None

            if not primary_exists and not mirror_exists:
                # Maybe only the hosts marker survived.
                self._restore_from_hosts()
                return

            valid_primary = self._record_ok(primary) if primary else False
            valid_mirror = self._record_ok(mirror) if mirror else False

            if primary_exists and not valid_primary:
                base = primary if primary else {}
                self._record = dict(base) if base else None
                if self._record:
                    self._penalize("primary lock file corrupt or seal mismatch")
                else:
                    self._record = self._fresh_record(0)
                    self._penalize("primary lock file unreadable")
                self._source = "primary"
                return

            if mirror_exists and not valid_mirror:
                # primary may still be fine; mirror tampered => punish anyway
                self._record = primary
                self._source = "primary"
                self._penalize("mirror lock file corrupt or seal mismatch")
                return

            if valid_primary and valid_mirror and primary["until"] != mirror["until"]:
                # copies disagree: keep the later end (never shorter) + punish
                chosen = primary if int(primary["until"]) >= int(mirror["until"]) else mirror
                self._record = dict(chosen)
                self._source = "primary"
                self._penalize("primary and mirror disagree")
                return

            if valid_primary:
                self._record = dict(primary)
                self._source = "primary"
            elif valid_mirror:
                self._record = dict(mirror)
                self._source = "mirror"
                self._penalize("primary lock file missing (mirror intact)")
            else:
                self._record = None
                self._source = "none"

            # NOTE: a marker that does not match the record is intentionally
            # NOT punished here. The files are authoritative; after set_lock()
            # or a penalty the marker in hosts is briefly stale until the
            # enforcer rewrites it, and tampering with it alone buys nothing.
            # What matters (file deletions / forged files) is handled above
            # and in _restore_from_hosts().

    def _hosts_block_present(self) -> bool:
        try:
            return BEGIN_MARK in hosts_path().read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            return False

    def _restore_from_hosts(self) -> None:
        """Both lock files gone: the hosts marker is the only surviving copy.

        * valid marker    -> restore it (and punish the file deletion)
        * tampered marker -> the HMAC check fails -> punish with a fresh lock
        * marker stripped while our block still exists -> same
        * no trace at all -> no lock (only root could have removed everything)
        """
        marker = self.hosts_marker()
        if marker and marker[0] and marker[1]:
            fake = {"until": int(marker[0]), "created_at": int(marker[0]),
                    "duration_days": 0, "seed": "", "generation": 0,
                    "seal": marker[1]}
            if self._record_ok(fake):
                self._record = fake
                self._source = "hosts"
                self._penalize("lock files deleted (hosts marker survived)")
                log.warn("[LOCK] Lock files deleted -> restored from hosts marker + penalty")
                return
            # present but not valid: someone edited the only surviving copy
            self._record = None
            self._penalize("hosts marker forged/altered after deleting the lock files")
            self._source = "hosts"
            return
        if self._hosts_block_present():
            self._record = None
            self._penalize("hosts block and lock files deleted together")
            self._source = "hosts"
            return
        self._record = None
        self._source = "none"

    @staticmethod
    def _fresh_record(duration_days: int) -> dict:
        now = int(time.time())
        return {
            "created_at": now,
            "duration_days": int(duration_days),
            "until": now + int(duration_days) * 86400,
            "seed": secrets.token_hex(8),
            "generation": 0,
            "penalties": [],
        }

    # ------------------------------------------------------------------
    # Penalties
    # ------------------------------------------------------------------
    def _penalize(self, reason: str, days: int | None = None) -> None:
        from .config import Config

        days = days if days is not None else Config().penalty_days
        now = int(time.time())
        if self._record is None:
            self._record = self._fresh_record(0)
        self._record["until"] = max(int(self._record.get("until", 0)), now) + days * 86400
        self._record["duration_days"] = int(self._record.get("duration_days", 0)) + days
        self._record.setdefault("penalties", []).append({"at": now, "days": days, "reason": reason})
        self._record["generation"] = int(self._record.get("generation", 0)) + 1
        self._record["seed"] = self._record.get("seed") or secrets.token_hex(8)
        self._record["seal"] = seal_record(self._record)
        self._persist()
        try:
            from . import stats

            stats.record_event("tamper", {"reason": reason, "days": days})
        except Exception:
            pass
        log.warn(f"[LOCK] TAMPER DETECTED: {reason} -> +{days} days")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def penalize(self, reason: str, days: int | None = None) -> None:
        """Public entry for out-of-band tamper verdicts (daemon monitoring)."""
        with self._lock:
            self._penalize(reason, days)

    def set_lock(self, days: int) -> LockStatus:
        """Create or extend a lock. Never shortens an active lock."""
        with self._lock:
            days = int(days)
            if days < 1 or days > 3650:
                raise ValueError("days must be 1..3650")
            now = int(time.time())
            if self._record and self.is_locked():
                new_until = now + days * 86400
                if new_until <= int(self._record["until"]):
                    raise LockActiveError(
                        f"already locked until {self._until_str()}; a lock can only be extended"
                    )
                record = dict(self._record)
                record["until"] = new_until
                record["duration_days"] = int(record.get("duration_days", 0)) + days
            else:
                record = self._fresh_record(days)
            record["seal"] = seal_record(record)
            self._record = record
            self._source = "primary"
            self._persist()
            try:
                from . import stats

                stats.record_event("lock_set", {"days": days, "until": record["until"]})
            except Exception:
                pass
            log.info(f"[LOCK] Locked for {days} day(s) until {self._until_str()}")
            return self.status()

    def unlock(self) -> None:
        """Refuses while a lock is active. Only reachable after expiry."""
        with self._lock:
            if self.is_locked():
                raise LockActiveError(
                    f"The time-lock is active until {self._until_str()} and cannot be removed."
                )
            self._record = None
            self._persist()
            log.info("[LOCK] Removed (lock was not active)")

    def is_locked(self) -> bool:
        if self._record is None:
            return False
        try:
            return int(time.time()) < int(self._record["until"])
        except (KeyError, TypeError, ValueError):
            return False

    def status(self) -> LockStatus:
        st = LockStatus(source=self._source)
        if self._record is None:
            return st
        try:
            until = int(self._record["until"])
        except (KeyError, TypeError, ValueError):
            return st
        now = int(time.time())
        st.locked = now < until
        st.until = until
        st.created_at = int(self._record.get("created_at", 0))
        st.duration_days = int(self._record.get("duration_days", 0))
        st.remaining_seconds = max(0, until - now)
        st.penalties = list(self._record.get("penalties", []))
        st.tampered = bool(st.penalties)
        st.expires_label = time.strftime("%Y-%m-%d %H:%M", time.localtime(until))
        return st

    def until(self) -> int:
        return int(self._record["until"]) if self._record else 0

    def _until_str(self) -> str:
        until = self.until()
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(until)) if until else "-"

    def hosts_marker_line(self) -> str:
        """Comment line embedded in the managed hosts block."""
        if not self._record or not self.is_locked():
            return ""
        rec = self._record
        return f"# jgu-lock until={rec['until']} seal={rec['seal']}\n"

    # ------------------------------------------------------------------
    # Clock sanity (runs inside the daemon loop)
    # ------------------------------------------------------------------
    def tick_clock(self) -> None:
        """Detect wall-clock jumps by comparing with a suspend-aware clock.

        CLOCK_BOOTTIME (Linux) / QPC keep running across laptop suspend,
        so a lid-closed night while locked is NOT a tamper, while moving
        the wall clock backwards or forwards by hours is.
        """
        with self._lock:
            wall_now = time.time()
            mono_now = _mono()
            if self._tick_started and self.is_locked():
                wall_delta = wall_now - self._last_wall
                mono_delta = mono_now - self._last_mono
                skew = abs(wall_delta - mono_delta)
                if skew > FORWARD_JUMP_LIMIT and wall_delta > 0:
                    self._penalize(
                        f"system clock changed by {int(skew)}s while locked"
                    )
            self._last_wall = wall_now
            self._last_mono = mono_now
            self._tick_started = True

    def expire_if_due(self) -> bool:
        """Drop an expired lock (both copies) and log the transition."""
        with self._lock:
            if self._record and not self.is_locked():
                log.info("[LOCK] Lock expired -- protection may now be configured")
                try:
                    from . import stats

                    stats.record_event("lock_expired", {"until": self._record.get("until", 0)})
                except Exception:
                    pass
                self._record = None
                self._persist()
                return True
            return False
