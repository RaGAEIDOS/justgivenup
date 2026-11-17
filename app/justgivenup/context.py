"""Shared application context passed to the dashboard server and the loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .autostart import status as autostart_status
from .browser_guard import engine_for_brand
from .config import Config
from .enforcement import HostsEnforcer
from .lock import TimeLock


@dataclass
class AppContext:
    config: Config
    lock: TimeLock
    enforcer: HostsEnforcer
    last_ext_penalty: float = 0.0
    browser_seen_running_since: Optional[float] = None
    extension_missing_accum: float = 0.0
    extension_kill_since: dict = field(default_factory=dict)
    incognito_hints: dict = field(default_factory=dict)
    guard_state: dict = field(default_factory=dict)
    last_guard_tick: float = 0.0
    last_vpn_scan: float = 0.0
    last_browser_kill: float = 0.0
    last_browser_kill_reason: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def build(cls) -> "AppContext":
        config = Config()
        lock = TimeLock()
        lock.load()
        enforcer = HostsEnforcer(lock)
        return cls(config=config, lock=lock, enforcer=enforcer)

    def extension_info(self) -> dict:
        ext = dict(self.config.data.get("extension") or {})
        import time as _time

        now = _time.time()
        last_seen = float(ext.get("last_seen") or 0)
        browsers: dict = {}
        raw_browsers = ext.get("browsers")
        if isinstance(raw_browsers, dict):
            for family, rec in raw_browsers.items():
                if not isinstance(rec, dict):
                    continue
                rec_last = float(rec.get("last_seen") or 0)
                browsers[str(family)] = {
                    "brand": str(rec.get("brand") or family),
                    "engine": str(rec.get("engine") or engine_for_brand(str(family))),
                    "browser": str(rec.get("browser") or ""),
                    "version": str(rec.get("version") or ""),
                    "last_seen": rec_last,
                    "age_seconds": int(now - rec_last) if rec_last else None,
                    "connected": bool(rec_last and now - rec_last < 180),
                    "incognito_access": rec.get("incognito_access"),
                    "incognito_context": bool(rec.get("incognito_context")),
                    "incognito_context_at": float(rec.get("incognito_context_at") or 0),
                    "incognito_windows": int(rec.get("incognito_windows") or 0),
                    "incognito_seen_at": float(rec.get("incognito_seen_at") or 0),
                    "incognito_recent": bool(
                        rec.get("incognito_seen_at")
                        and now - float(rec.get("incognito_seen_at") or 0) < 300),
                    "vpn_blocked": int(rec.get("vpn_blocked") or 0),
                    "vpn_blocked_at": float(rec.get("vpn_blocked_at") or 0),
                }
        incognito_seen_at = float(ext.get("incognito_seen_at") or 0)
        if browsers:
            vpn_blocked_total = sum(int(rec.get("vpn_blocked") or 0)
                                    for rec in browsers.values())
            incognito_windows_total = max(
                (int(rec.get("incognito_windows") or 0)
                 for rec in browsers.values()), default=0)
            incognito_seen_at = max(
                [incognito_seen_at] +
                [float(rec.get("incognito_seen_at") or 0)
                 for rec in browsers.values()])
        else:
            vpn_blocked_total = int(ext.get("vpn_blocked") or 0)
            incognito_windows_total = int(ext.get("incognito_windows") or 0)
        return {
            "last_seen": last_seen,
            "age_seconds": int(now - last_seen) if last_seen else None,
            "version": ext.get("version", ""),
            "browser": ext.get("browser", ""),
            "ever_seen": bool(ext.get("ever_seen")),
            "miss_flag": bool(ext.get("miss_flag")),
            "connected": bool(last_seen and now - last_seen < 180),
            "incognito_access": ext.get("incognito_access"),
            "incognito_context": bool(ext.get("incognito_context")),
            "incognito_context_at": float(ext.get("incognito_context_at") or 0),
            "incognito_windows": incognito_windows_total,
            "incognito_seen_at": incognito_seen_at,
            "incognito_recent": bool(incognito_seen_at and now - incognito_seen_at < 300),
            "vpn_blocked": vpn_blocked_total,
            "vpn_blocked_at": float(ext.get("vpn_blocked_at") or 0),
            "browsers": browsers,
        }

    def settings_payload(self) -> dict:
        return {
            "language": self.config.language,
            "port": self.config.port,
            "hosts_block": self.config.hosts_block,
            "penalty_days": self.config.penalty_days,
            "setup_complete": bool(self.config.data.get("setup_complete")),
            "profile": dict(self.config.data.get("profile") or {"name": "", "goal": ""}),
            "custom_domains": list(self.config.data.get("custom_domains") or []),
            "auto_start": autostart_status(),
        }
