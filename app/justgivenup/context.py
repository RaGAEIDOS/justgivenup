"""Shared application context passed to the dashboard server and the loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .autostart import status as autostart_status
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
        return {
            "last_seen": last_seen,
            "age_seconds": int(now - last_seen) if last_seen else None,
            "version": ext.get("version", ""),
            "browser": ext.get("browser", ""),
            "ever_seen": bool(ext.get("ever_seen")),
            "miss_flag": bool(ext.get("miss_flag")),
            "connected": bool(last_seen and now - last_seen < 180),
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
