"""Local dashboard HTTP server (127.0.0.1 only) + JSON API.

Security notes
--------------
* Binds to loopback; never exposed to the network.
* Mutating endpoints (POST) validate ``Origin``/``Referer``: only the
  dashboard itself and browser extensions may call them.  This stops any
  random web page from trying to unlock the guardian through the user's
  browser.
* While a time-lock is active there is NO endpoint that can shorten or
  remove it — /api/unlock answers 403 and records the attempt.
"""

from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import DASHBOARD_PORT, VERSION, log
from . import motivation, stats
from .blocklist import core_domains, full_domains, summary as blocklist_summary
from .config import extension_dir, web_root
from .context import AppContext
from .lock import LockActiveError

CHANGELOG = [
    {
        "version": "3.1.0",
        "title_en": "Auto-update + extension removal auto-lock + Google unblocked",
        "title_ar": "تحديث تلقائي + قفل تلقائي عند حذف الإضافة + فك حظر جوجل",
        "changes_en": [
            "Dashboard checks GitHub for new extension version and offers one-click update",
            "Extension self-reloads when a newer version is detected",
            "Auto-lock (90 days) if the browser extension is removed while running",
            "Google and all legitimate sites removed from Chrome/Firefox enterprise policies",
            "Version bumped to 3.1.0 across all components",
        ],
        "changes_ar": [
            "الداشبورد يفحص GitHub بحثاً عن إصدار جديد من الإضافة ويعرض زر تحديث بنقرة واحدة",
            "الإضافة تعيد تحميل نفسها تلقائياً عند اكتشاف إصدار أحدث",
            "قفل تلقائي (90 يوماً) عند حذف الإضافة من المتصفح أثناء التشغيل",
            "إزالة جوجل وكل المواقع الشرعية من سياسات Chrome/Firefox المؤسسية",
            "تحديث الإصدار إلى 3.1.0 في جميع المكونات",
        ],
        "date": "2026-11-07",
    },
    {
        "version": "3.0.0",
        "title_en": "Total rebuild: extension + cross-platform daemon",
        "title_ar": "إعادة بناء كاملة: إكستنشن + خدمة عابرة للمنصات",
        "changes_en": [
            "Browser extension for Chrome and Firefox (Manifest V3) with declarativeNetRequest blocking",
            "Sealed time-lock (HMAC-SHA256) with tamper penalty: +90 days",
            "System-level DNS blocking through /etc/hosts while locked",
            "Enterprise browser policies (URLBlocklist) shipped with the package",
            "systemd service + watchdog timer: starts at boot, restarts if killed",
            "Recovery dashboard: streaks, relapses, ranks, motivation (AR/EN)",
            "Debian package installable from the GitHub Pages apt repository",
        ],
        "changes_ar": [
            "إكستنشن للمتصفحات (Chrome وFirefox) بـ Manifest V3 وحجب declarativeNetRequest",
            "قفل زمني مختوم (HMAC-SHA256) مع عقوبة العبث: +90 يوماً",
            "حجب DNS على مستوى النظام عبر /etc/hosts أثناء القفل",
            "سياسات متصفحات مؤسسية (URLBlocklist) داخل الحزمة",
            "خدمة systemd + مؤقت حارس: يبدأ مع الإقلاع ويعيد التشغيل عند القتل",
            "لوحة تعافي: أيام نظيفة، انتكاسات، رتب، تحفيز (عربي/إنجليزي)",
            "حزمة Debian قابلة للتثبيت من مستودع apt على GitHub Pages",
        ],
        "date": "2026-11-06",
    },
    {
        "version": "2.3",
        "title_en": "Legacy Windows screen guardian",
        "title_ar": "حارس شاشة ويندوز (النسخة القديمة)",
        "changes_en": ["Moved to legacy/ — ONNX screen detection, tray, NSIS installer"],
        "changes_ar": ["انتقل إلى legacy/ — كشف شاشة ONNX، علبة نظام، مثبت NSIS"],
        "date": "2026-07-19",
    },
]

_EXT_ORIGINS = ("chrome-extension://", "moz-extension://", "safari-web-extension://")
_PENALTY_MISS_SECONDS = 600      # browsers running this long w/o extension => tamper
_BROWSER_REQUIRED = ("chrome", "chromium", "firefox", "brave", "edge", "opera",
                     "vivaldi", "opera-gx", "librewolf", "waterfox", "floorp", "tor")


# ---------------------------------------------------------------------------
# Server + handler
# ---------------------------------------------------------------------------

class _AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, ctx: AppContext, port: int) -> None:
        self.ctx = ctx
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = f"JustGivenUp/{VERSION}"
    protocol_version = "HTTP/1.1"

    # -- plumbing --------------------------------------------------------
    @property
    def ctx(self) -> AppContext:
        return self.server.ctx  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        if os.environ.get("JGU_HTTP_LOG"):
            log.info("[HTTP] " + (fmt % args))

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin") or ""
        referer = self.headers.get("Referer") or ""
        if not origin and not referer:
            return True  # curl / CLI / local process (not a browser)
        port = self.ctx.config.port
        for value in (origin, referer):
            if not value:
                continue
            if value.startswith(_EXT_ORIGINS):
                return True
            if value.startswith(f"http://127.0.0.1:{port}") or \
               value.startswith(f"http://localhost:{port}"):
                return True
        return False

    def _send(self, code: int, body: bytes, ctype: str,
              extra: dict | None = None, cors_origin: str | None = None) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "content-type")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code: int = 200, cors: str | None = None) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8",
                   extra={"Cache-Control": "no-store"}, cors_origin=cors)

    def _err(self, code: int, message: str) -> None:
        self._json({"ok": False, "error": message}, code)

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 2_000_000:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def _cors_hint(self) -> str | None:
        origin = self.headers.get("Origin") or ""
        if origin.startswith(_EXT_ORIGINS):
            return origin
        return None

    # -- verbs -----------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain",
                   cors_origin=self.headers.get("Origin") or "*")

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if path.startswith("/api/"):
            self._api_get(path)
        else:
            self._static(path)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._err(403, "origin not allowed")
            return
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if not path.startswith("/api/"):
            self._err(404, "not found")
            return
        try:
            self._api_post(path, self._read_body())
        except LockActiveError as exc:
            self._err(403, str(exc))
        except ValueError as exc:
            self._err(400, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            log.error(f"[HTTP] POST {path} failed: {exc}")
            self._err(500, "internal error")

    # -- static files ----------------------------------------------------
    def _static(self, path: str) -> None:
        root = web_root().resolve()
        rel = path.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        target = (root / rel).resolve()
        if not str(target).startswith(str(root)) or not target.is_file():
            target = root / "index.html"
            if not target.is_file():
                self._err(404, "not found")
                return
        try:
            body = target.read_bytes()
        except OSError:
            self._err(504, "read error")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        cache = "no-store" if target.suffix in (".html", ".js", ".css") else "public, max-age=3600"
        self._send(200, body, ctype, extra={"Cache-Control": cache})

    # -- API: GET --------------------------------------------------------
    def _api_get(self, path: str) -> None:
        cors = self._cors_hint()
        if path == "/api/status":
            self._json(self._status_payload(), cors=cors)
        elif path == "/api/lock":
            st = self.ctx.lock.status()
            self._json({
                "locked": st.locked,
                "until": st.until,
                "created_at": st.created_at,
                "duration_days": st.duration_days,
                "remaining_seconds": st.remaining_seconds,
                "expires_label": st.expires_label,
                "penalties": len(st.penalties),
                "confirm_phrase": "LOCK",
            }, cors=cors)
        elif path == "/api/stats":
            self._json(stats.instance().snapshot(), cors=cors)
        elif path == "/api/ranks":
            self._json(stats.instance().ranks_payload(), cors=cors)
        elif path == "/api/motivation":
            self._json(motivation.payload(self.ctx.config.language), cors=cors)
        elif path == "/api/settings":
            self._json(self.ctx.settings_payload(), cors=cors)
        elif path == "/api/setup-status":
            self._json({"setup_complete": bool(self.ctx.config.data.get("setup_complete"))},
                       cors=cors)
        elif path == "/api/events":
            self._json({"events": stats.recent_events(80)}, cors=cors)
        elif path == "/api/blocklist":
            self._json({"core": core_domains(), "summary": blocklist_summary()}, cors=cors)
        elif path == "/api/extension":
            self._json({
                "dir": str(extension_dir()),
                "manifest": str(extension_dir() / "manifest.json"),
                "info": self.ctx.extension_info(),
            }, cors=cors)
        elif path == "/api/changelog":
            self._json({"current_version": VERSION, "entries": CHANGELOG}, cors=cors)
        elif path == "/api/version":
            self._json({"version": VERSION}, cors=cors)
        elif path == "/api/hosts":
            self._json(self.ctx.enforcer.status(), cors=cors)
        else:
            self._err(404, "unknown api endpoint")

    # -- API: POST -------------------------------------------------------
    def _api_post(self, path: str, body: dict) -> None:
        if path == "/api/lock":
            self._post_lock(body)
        elif path == "/api/unlock":
            self._post_unlock(body)
        elif path == "/api/relapse":
            self._post_relapse(body)
        elif path == "/api/setup":
            self._post_setup(body)
        elif path == "/api/settings":
            self._post_settings(body)
        elif path == "/api/heartbeat":
            self._post_heartbeat(body)
        elif path == "/api/report":
            self._post_report(body)
        elif path == "/api/custom-domains":
            self._post_custom_domains(body)
        else:
            self._err(404, "unknown api endpoint")

    # -- POST handlers ---------------------------------------------------
    @staticmethod
    def _confirm_ok(body: dict, language: str) -> bool:
        expected = "اقفل" if language == "ar" else "LOCK"
        return str(body.get("confirm") or "") in (expected, "LOCK", "اقفل")

    def _post_lock(self, body: dict) -> None:
        if not self._confirm_ok(body, self.ctx.config.language):
            self._err(400, "confirmation phrase required")
            return
        days = int(body.get("days") or 0)
        if days < 1 or days > 3650:
            self._err(400, "days must be 1..3650")
            return
        status = self.ctx.lock.set_lock(days)
        stats.record_lock_taken()
        stats.record_event("lock_created", {"days": days, "until": status.until})
        self.ctx.enforcer.apply(full_domains(), force=True)
        self._json({"ok": True, "lock": {
            "locked": status.locked,
            "until": status.until,
            "remaining_seconds": status.remaining_seconds,
            "expires_label": status.expires_label,
        }})

    def _post_unlock(self, body: dict) -> None:
        if self.ctx.lock.is_locked():
            stats.record_event("unlock_refused", {"until": self.ctx.lock.until()})
            log.warn("[API] /api/unlock refused -- lock active")
            self._err(403,
                      "The time-lock cannot be removed before "
                      f"{self.ctx.lock.status().expires_label}.")
            return
        self._json({"ok": True, "note": "no lock was active"})

    def _post_relapse(self, body: dict) -> None:
        kind = str(body.get("kind") or "both")
        stats.instance().record_relapse(kind)
        self._json({"ok": True, "stats": stats.instance().snapshot()})

    def _post_setup(self, body: dict) -> None:
        cfg = self.ctx.config
        if not self._confirm_ok(body, cfg.language) and int(body.get("lock_days") or 0) > 0:
            self._err(400, "confirmation phrase required")
            return
        profile = cfg.data.setdefault("profile", {"name": "", "goal": ""})
        if "name" in body:
            profile["name"] = str(body.get("name") or "")[:80]
        if "goal" in body:
            profile["goal"] = str(body.get("goal") or "")[:200]
        if str(body.get("language") or "") in ("ar", "en"):
            cfg.data["language"] = body["language"]
        cfg.data["setup_complete"] = True
        if body.get("autostart"):
            from . import autostart as autostart_mod

            ok, detail = autostart_mod.enable()
            log.info(f"[SETUP] autostart enable -> {ok}: {detail}")
        days = int(body.get("lock_days") or 0)
        lock_info = None
        if days > 0:
            status = self.ctx.lock.set_lock(days)
            stats.record_lock_taken()
            stats.record_event("lock_created", {"days": days, "until": status.until})
            lock_info = {"until": status.until, "expires_label": status.expires_label}
            self.ctx.enforcer.apply(full_domains(), force=True)
        cfg.save()
        self._json({"ok": True, "lock": lock_info})

    def _post_settings(self, body: dict) -> None:
        cfg = self.ctx.config
        if str(body.get("language") or "") in ("ar", "en"):
            cfg.data["language"] = body["language"]
        profile = cfg.data.setdefault("profile", {"name": "", "goal": ""})
        if "name" in body:
            profile["name"] = str(body.get("name") or "")[:80]
        if "goal" in body:
            profile["goal"] = str(body.get("goal") or "")[:200]
        if "hosts_block" in body:
            if self.ctx.lock.is_locked() and not body.get("hosts_block"):
                self._err(403, "DNS blocking cannot be disabled while locked")
                return
            cfg.data["hosts_block"] = bool(body.get("hosts_block"))
        if "autostart" in body:
            from . import autostart as autostart_mod

            ok, detail = (autostart_mod.enable() if body.get("autostart")
                          else autostart_mod.disable())
            log.info(f"[SETTINGS] autostart -> {ok}: {detail}")
        cfg.save()
        self._json({"ok": True, "settings": self.ctx.settings_payload()})

    def _post_heartbeat(self, body: dict) -> None:
        cfg = self.ctx.config
        ext = cfg.data.setdefault("extension", {})
        ext["last_seen"] = time.time()
        ext["ever_seen"] = True
        ext["version"] = str(body.get("version") or "")[:20]
        ext["browser"] = str(body.get("browser") or "")[:40]
        ext["miss_flag"] = False
        cfg.save()
        self._json({"ok": True,
                    "locked": self.ctx.lock.is_locked(),
                    "until": self.ctx.lock.until(),
                    "penalty_days": cfg.penalty_days,
                    "confirm_phrase": "LOCK"})

    def _post_report(self, body: dict) -> None:
        try:
            count = max(1, min(50, int(body.get("count") or 1)))
        except (TypeError, ValueError):
            count = 1
        stats.instance().record_block(count)
        stats.record_event("block", {"from": str(body.get("from") or "")[:100]})
        self._json({"ok": True,
                    "total_blocked": stats.instance().snapshot()["total_blocked"]})

    def _post_custom_domains(self, body: dict) -> None:
        cfg = self.ctx.config
        current = list(cfg.data.get("custom_domains") or [])
        if body.get("action") == "remove":
            domain = str(body.get("domain") or "").lower()
            current = [d for d in current if d != domain]
        else:
            domain = str(body.get("domain") or "").strip().lower().lstrip("*.")
            if "." not in domain or " " in domain or len(domain) > 253:
                self._err(400, "invalid domain")
                return
            if domain not in current:
                current.append(domain)
        cfg.data["custom_domains"] = current[:500]
        cfg.save()
        self._json({"ok": True, "custom_domains": cfg.data["custom_domains"]})

    # -- combined payload ------------------------------------------------
    def _status_payload(self) -> dict:
        ctx = self.ctx
        st = ctx.lock.status()
        payload = {
            "version": VERSION,
            "now": int(time.time()),
            "setup_complete": bool(ctx.config.data.get("setup_complete")),
            "lang": ctx.config.language,
            "lock": {
                "locked": st.locked,
                "until": st.until,
                "created_at": st.created_at,
                "duration_days": st.duration_days,
                "remaining_seconds": st.remaining_seconds,
                "expires_label": st.expires_label,
                "penalties": st.penalties,
                "tampered": st.tampered,
                "source": st.source,
            },
            "stats": stats.instance().snapshot(),
            "ranks": stats.instance().ranks_payload(),
            "settings": ctx.settings_payload(),
            "extension": ctx.extension_info(),
            "hosts": ctx.enforcer.status(),
            "motivation": motivation.payload(ctx.config.language),
            "events": stats.recent_events(60),
        }
        return payload


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class DashboardServer:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.port = ctx.config.port or DASHBOARD_PORT
        self._httpd: _AppServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        try:
            self._httpd = _AppServer(self.ctx, self.port)
        except OSError as exc:
            log.error(f"[DASHBOARD] Cannot bind 127.0.0.1:{self.port} -- {exc}")
            return False
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name="jgu-dashboard", daemon=True)
        self._thread.start()
        log.info(f"[DASHBOARD] http://127.0.0.1:{self.port}")
        return True

    def stop(self) -> None:
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
