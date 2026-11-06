"""Tiny logging helper: stdout (journal) + guardian.log inside the state dir."""

import sys
import threading
import time
from pathlib import Path

_lock = threading.Lock()
_state_dir: Path | None = None


def set_state_dir(path: Path) -> None:
    global _state_dir
    _state_dir = path


def _write(level: str, msg: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp} [{level}] {msg}"
    with _lock:
        try:
            sys.stderr.write(line + "\n")
            sys.stderr.flush()
        except Exception:
            pass
        if _state_dir is not None:
            try:
                with open(_state_dir / "guardian.log", "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except Exception:
                pass


def info(msg: str) -> None:
    _write("INFO", msg)


def warn(msg: str) -> None:
    _write("WARN", msg)


def error(msg: str) -> None:
    _write("ERROR", msg)
