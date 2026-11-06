#!/usr/bin/env python3
"""Watchdog: started by justgivenup-watchdog.timer every 30s.

Guarantee: while a time-lock is ACTIVE the main service keeps running.
If it is not active (killed, crashed, stopped), restart it. When no lock
is active (or expired) the watchdog does nothing.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, "/usr/lib/justgivenup")  # packaged layout


def _run(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=20).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 127


def main() -> int:
    try:
        from justgivenup.lock import TimeLock
    except Exception:
        return 0  # package not importable -> nothing to guard

    lock = TimeLock()
    lock.load()
    if not lock.is_locked():
        return 0  # no active lock -> hands off

    active = _run(["systemctl", "is-active", "--quiet", "justgivenup.service"])
    if active != 0:
        rc = _run(["systemctl", "start", "justgivenup.service"])
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{stamp} [WATCHDOG] service was down while locked -> "
              f"start requested (rc={rc})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
