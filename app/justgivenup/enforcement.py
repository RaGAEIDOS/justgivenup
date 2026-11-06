"""System-level enforcement: the managed block inside the hosts file.

While a lock is active the daemon rewrites a marker-delimited section of
the hosts file with one ``0.0.0.0``/``::`` line per blocked domain, and
re-applies it every loop iteration — if someone deletes or edits the
section it is restored immediately (and the lock module records the
tamper attempt).

The hosts file carries a third copy of the sealed lock record, so
deleting both lock JSON files does not lose the lock.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from . import log
from .config import hosts_path
from .lock import BEGIN_MARK, END_MARK, TimeLock

__all__ = ["HostsEnforcer", "BEGIN_MARK", "END_MARK"]


class HostsEnforcer:
    def __init__(self, lock: TimeLock) -> None:
        self.lock = lock
        self.path = hosts_path()
        self._last_apply = 0.0
        self._last_status = ""

    # ------------------------------------------------------------------
    @property
    def writable(self) -> bool:
        try:
            if not self.path.exists():
                return os.access(self.path.parent, os.W_OK)
            return os.access(self.path, os.W_OK)
        except OSError:
            return False

    def _strip(self, text: str) -> str:
        out_lines = []
        skipping = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(BEGIN_MARK):
                skipping = True
                continue
            if s.startswith(END_MARK):
                skipping = False
                continue
            if not skipping:
                out_lines.append(line)
        # drop trailing blank lines the block may have left behind
        while out_lines and not out_lines[-1].strip():
            out_lines.pop()
        return "\n".join(out_lines) + "\n"

    def _read(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return "# Managed by JustGivenUp\n"
        except OSError as exc:
            log.warn(f"[HOSTS] Cannot read {self.path}: {exc}")
            return ""

    def _write(self, text: str) -> bool:
        try:
            tmp = self.path.with_suffix(".jgu.tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError as exc:
            log.warn(f"[HOSTS] Cannot write {self.path}: {exc}")
            return False

    # ------------------------------------------------------------------
    def current_block_present(self) -> bool:
        try:
            return BEGIN_MARK in self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

    @staticmethod
    def _block_domains(text: str) -> list[str]:
        """Domain names from the managed block, in order (for change detection)."""
        out = []
        inside = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(BEGIN_MARK):
                inside = True
                continue
            if s.startswith(END_MARK):
                inside = False
                continue
            if inside and (s.startswith("0.0.0.0 ") or s.startswith(":: ")):
                out.append(s.split(" ", 1)[1].strip())
        # entries come in 0.0.0.0/:: pairs; keep unique in first-seen order
        seen: set[str] = set()
        uniq = []
        for d in out:
            if d not in seen:
                seen.add(d)
                uniq.append(d)
        return uniq

    def apply(self, domains: list[str], force: bool = False) -> bool:
        """Ensure the managed block matches the current lock state."""
        now = time.time()
        locked = self.lock.is_locked()
        if not force and now - self._last_apply < 10:
            # throttle only when the desired state is already in effect
            satisfied = (self._last_status == "blocked") if locked else \
                        (self._last_status in ("clean", "cleared"))
            if satisfied:
                return True
        self._last_apply = now

        if not self.writable:
            if self._last_status != "readonly":
                log.warn(f"[HOSTS] {self.path} not writable -- DNS layer disabled "
                         "(run as root / install the .deb service)")
                self._last_status = "readonly"
            return False

        original = self._read()
        stripped = self._strip(original)
        locked = self.lock.is_locked()

        if not locked:
            if BEGIN_MARK in original:
                if self._write(stripped):
                    log.info("[HOSTS] Lock released -- managed block removed")
                    self._last_status = "cleared"
                    return True
            self._last_status = "clean"
            return True

        # build the block
        marker = self.lock.hosts_marker_line()
        lines = [BEGIN_MARK, "# Remove this section and the lock will punish you."]
        if marker:
            lines.append(marker.strip())
        for d in domains:
            lines.append(f"0.0.0.0 {d}")
            lines.append(f":: {d}")
        lines.append(END_MARK)
        block = "\n".join(lines) + "\n"

        desired = stripped.rstrip("\n") + "\n\n" + block
        if original == desired:
            self._last_status = "blocked"
            return True

        had_block = BEGIN_MARK in original
        vanished = (not had_block and self._last_status == "blocked")
        if self._write(desired):
            if vanished:
                log.warn("[HOSTS] Managed block vanished while locked -- "
                         "re-applied (tamper attempt)")
                from . import stats

                stats.record_event("tamper", {"reason": "hosts block removed"})
            elif not had_block:
                log.info(f"[HOSTS] Lock active -- blocked {len(domains)} domains")
            elif self._block_domains(original) == domains:
                # only the marker line changed (new seal / penalty): quiet update
                log.info("[HOSTS] Managed block refreshed (seal updated)")
            else:
                log.warn("[HOSTS] Managed block was altered -- restored (tamper attempt)")
                from . import stats

                stats.record_event("tamper", {"reason": "hosts block edited"})
            self._last_status = "blocked"
            return True
        return False

    def status(self) -> dict:
        return {
            "path": str(self.path),
            "writable": self.writable,
            "active": self.current_block_present(),
            "state": self._last_status,
        }
