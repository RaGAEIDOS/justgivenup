"""Recovery statistics: streaks, relapses, blocked counts, activity feed.

Everything lives in the state directory:
  stats.json   counters & dates
  events.jsonl append-only activity feed (lock changes, tamper, blocks...)
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import VERSION, log
from .config import state_dir

_lock = threading.Lock()

RANKS = [
    (7, "Bronze", "برونز", "🥉"),
    (14, "Silver", "فضة", "🥈"),
    (21, "Gold", "ذهب", "🥇"),
    (30, "Platinum", "بلاتين", "💎"),
    (60, "Diamond", "الماس", "💠"),
    (90, "Master", "الخبير", "🧠"),
    (120, "Grandmaster", "الأستاذ الكبير", "🏆"),
    (240, "Legend", "الأسطورة", "🏕️"),
    (300, "Mythic", "الأسطوري", "🌟"),
    (365, "Immortal", "الخالد", "♾️"),
    (680, "Transcendent", "المتعالي", "🔥"),
    (1220, "Ascended", "الصاعد", "☀️"),
    (2550, "Enlightened", "المستنير", "📜"),
]

DEFAULT = {
    "start_date": "",
    "clean_since": "",            # ISO date of last relapse (or start)
    "total_blocked": 0,
    "total_relapses": 0,
    "relapse_kinds": {"porn": 0, "masturbation": 0, "both": 0},
    "longest_streak_days": 0,
    "last_relapse_at": 0,
    "warnings_shown": 0,
    "locks_taken": 0,
}


def _today() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def _stats_file() -> Path:
    return state_dir() / "stats.json"


def _events_file() -> Path:
    return state_dir() / "events.jsonl"


class Stats:
    def __init__(self) -> None:
        self.data = dict(DEFAULT)
        self._load()

    def _load(self) -> None:
        try:
            on_disk = json.loads(_stats_file().read_text(encoding="utf-8"))
            if isinstance(on_disk, dict):
                for key, value in on_disk.items():
                    if key == "relapse_kinds" and isinstance(value, dict):
                        merged = dict(DEFAULT["relapse_kinds"])
                        merged.update(value)
                        self.data["relapse_kinds"] = merged
                    else:
                        self.data[key] = value
        except (OSError, json.JSONDecodeError):
            pass
        if not self.data.get("start_date"):
            self.data["start_date"] = _today()
        if not self.data.get("clean_since"):
            self.data["clean_since"] = self.data["start_date"]

    def save(self) -> None:
        try:
            path = _stats_file()
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
            try:
                os.chmod(path, 0o644)
            except OSError:
                pass
        except OSError as exc:
            log.warn(f"[STATS] save failed: {exc}")

    # ------------------------------------------------------------------
    def _days_since(self, iso_date: str) -> int:
        if not iso_date:
            return 0
        try:
            then = datetime.strptime(iso_date, "%Y-%m-%d").astimezone()
        except ValueError:
            return 0
        now = datetime.now(timezone.utc).astimezone()
        return max(0, (now.date() - then.date()).days)

    @property
    def clean_days(self) -> int:
        return self._days_since(self.data.get("clean_since") or self.data.get("start_date", ""))

    def record_block(self, count: int = 1) -> None:
        with _lock:
            self.data["total_blocked"] = int(self.data.get("total_blocked", 0)) + count
            self.save()

    def record_relapse(self, kind: str = "both") -> None:
        with _lock:
            kind = kind if kind in ("porn", "masturbation", "both") else "both"
            today = _today()
            # count a relapse once per day
            if self.data.get("last_relapse_iso") != today:
                self.data["total_relapses"] = int(self.data.get("total_relapses", 0)) + 1
                self.data["locks_taken"] = int(self.data.get("locks_taken", 0))
            self.data["relapse_kinds"][kind] = int(self.data["relapse_kinds"].get(kind, 0)) + 1
            self.data["clean_since"] = today
            self.data["last_relapse_at"] = int(time.time())
            self.data["last_relapse_iso"] = today
            streak = self._days_since(today)
            self.data["longest_streak_days"] = max(
                int(self.data.get("longest_streak_days", 0)), streak
            )
            self.save()
            record_event("relapse", {"kind": kind})

    def record_lock_taken(self) -> None:
        with _lock:
            self.data["locks_taken"] = int(self.data.get("locks_taken", 0)) + 1
            if not self.data.get("start_date"):
                self.data["start_date"] = _today()
            self.save()

    def refresh_streak(self) -> int:
        with _lock:
            days = self.clean_days
            self.data["longest_streak_days"] = max(
                int(self.data.get("longest_streak_days", 0)), days
            )
            self.save()
            return days

    # ------------------------------------------------------------------
    def ranks_payload(self) -> dict:
        clean = self.clean_days
        longest = max(clean, int(self.data.get("longest_streak_days", 0)))
        current_idx = -1
        for i, (days, *_rest) in enumerate(RANKS):
            if longest >= days:
                current_idx = i
        payload = {
            "ranks": [
                {"days": d, "name_en": en, "name_ar": ar, "icon": icon,
                 "unlocked": longest >= d}
                for d, en, ar, icon in RANKS
            ],
            "current_streak": clean,
            "longest_streak": longest,
            "current_rank": None,
            "next_rank": None,
            "max_rank_reached": current_idx == len(RANKS) - 1,
        }
        if current_idx >= 0:
            d, en, ar, icon = RANKS[current_idx]
            payload["current_rank"] = {"days": d, "name_en": en, "name_ar": ar, "icon": icon}
        if current_idx + 1 < len(RANKS):
            d, en, ar, icon = RANKS[current_idx + 1]
            cur_days = RANKS[current_idx][0] if current_idx >= 0 else 0
            span = d - cur_days
            progress = 0 if span <= 0 else min(100, int((longest - cur_days) / span * 100))
            payload["next_rank"] = {
                "days": d, "name_en": en, "name_ar": ar, "icon": icon,
                "progress": progress, "remaining": d - longest,
            }
        return payload

    def snapshot(self) -> dict:
        with _lock:
            return {
                "start_date": self.data.get("start_date", ""),
                "clean_since": self.data.get("clean_since", ""),
                "clean_days": self.clean_days,
                "total_blocked": int(self.data.get("total_blocked", 0)),
                "total_relapses": int(self.data.get("total_relapses", 0)),
                "relapse_kinds": dict(self.data.get("relapse_kinds", {})),
                "longest_streak_days": int(self.data.get("longest_streak_days", 0)),
                "locks_taken": int(self.data.get("locks_taken", 0)),
                "warnings_shown": int(self.data.get("warnings_shown", 0)),
            }


_stats: Stats | None = None
_stats_lock = threading.Lock()


def instance() -> Stats:
    global _stats
    with _stats_lock:
        if _stats is None:
            _stats = Stats()
        return _stats


def record_lock_taken() -> None:
    instance().record_lock_taken()


def record_event(kind: str, detail: dict | None = None) -> None:
    entry = {"ts": int(time.time()), "type": kind, "detail": detail or {}}
    try:
        with open(_events_file(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def recent_events(limit: int = 60) -> list[dict]:
    path = _events_file()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = deque(fh, maxlen=max(1, limit))
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out.reverse()
    return out
