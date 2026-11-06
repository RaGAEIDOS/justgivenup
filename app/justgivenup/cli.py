"""``justgivenup`` command line interface."""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser


def _ctx():
    from .context import AppContext

    return AppContext.build()


def _daemon_alive() -> bool:
    import urllib.request

    from .config import Config

    port = Config().port
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _api_status() -> dict | None:
    import urllib.request

    from .config import Config

    port = Config().port
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_run(args) -> int:
    from .daemon import run

    return run(port=args.port)


def cmd_status(args) -> int:
    payload = _api_status()
    daemon_up = payload is not None
    if payload is None:
        # daemon not running: read local state
        from . import VERSION, stats as stats_mod

        ctx = _ctx()
        st = ctx.lock.status()
        payload = {
            "version": VERSION,
            "lock": {
                "locked": st.locked, "until": st.until,
                "remaining_seconds": st.remaining_seconds,
                "expires_label": st.expires_label,
            },
            "stats": stats_mod.instance().snapshot(),
        }
    payload["daemon_running"] = daemon_up
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    lock = payload.get("lock", {})
    stats_data = payload.get("stats", {})
    print(f"JustGivenUp! v{payload.get('version', '?')}")
    print(f"  daemon   : {'running' if payload.get('daemon_running') else 'stopped'}")
    if lock.get("locked"):
        remain = int(lock.get("remaining_seconds", 0))
        days, rem = divmod(remain, 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        print(f"  lock     : LOCKED until {lock.get('expires_label')} "
              f"({days}d {hours}h {mins}m left)")
    else:
        print("  lock     : not active")
    print(f"  clean    : {stats_data.get('clean_days', 0)} day(s) "
          f"(longest {stats_data.get('longest_streak_days', 0)})")
    print(f"  blocked  : {stats_data.get('total_blocked', 0)}")
    print(f"  relapses : {stats_data.get('total_relapses', 0)}")
    print(f"  dashboard: http://127.0.0.1:8081")
    return 0


def cmd_lock(args) -> int:
    ctx = _ctx()
    st = ctx.lock.status()
    if st.locked:
        print(f"[LOCK] Already locked until {st.expires_label}. "
              "An active lock can only be extended, never shortened.")
        if args.days <= 0:
            return 1

    days = args.days
    if days < 1 or days > 3650:
        print("[FAIL] Use --days 1..3650")
        return 1

    print(f"!! You are about to lock protection for {days} day(s).")
    print("!! Once set, NOBODY (not you, not the CLI, not the dashboard)")
    print("!! can remove or shorten it before it expires.")
    print("!! Tampering with the files adds 90 extra days.\n")

    phrase = args.confirm or "LOCK"
    if not args.yes:
        for attempt in range(1, 4):
            typed = input(f"Type {phrase} to confirm ({attempt}/3): ").strip()
            if typed != phrase:
                print("Confirmation did not match.")
                if attempt == 3:
                    print("Aborted.")
                    return 1
            else:
                break

    from . import stats
    from .blocklist import full_domains

    status = ctx.lock.set_lock(days)
    stats.record_lock_taken()
    stats.record_event("lock_created", {"days": days, "until": status.until,
                                        "via": "cli"})
    ctx.enforcer.apply(full_domains(), force=True)
    print(f"[LOCK] Active until {status.expires_label}")
    return 0


def cmd_unlock(args) -> int:
    ctx = _ctx()
    try:
        ctx.lock.unlock()
        print("[OK] No lock was active; nothing to remove.")
        return 0
    except Exception as exc:
        print(f"[BLOCKED] {exc}")
        from . import stats

        stats.record_event("unlock_refused", {"via": "cli"})
        return 1


def cmd_relapse(args) -> int:
    from . import stats

    stats.instance().record_relapse(args.kind)
    snap = stats.instance().snapshot()
    print(f"[OK] Relapse logged ({args.kind}). Streak reset to {snap['clean_days']} day(s).")
    print("     The lock (if any) stays in place — that is the point.")
    return 0


def cmd_autostart(args) -> int:
    from . import autostart

    if args.action == "status":
        print(json.dumps(autostart.status(), ensure_ascii=False, indent=2))
        return 0
    if args.action == "enable":
        ok, detail = autostart.enable()
    else:
        ok, detail = autostart.disable()
    print(("[OK] " if ok else "[FAIL] ") + detail)
    return 0 if ok else 1


def cmd_extension(args) -> int:
    from .config import extension_dir

    ext = extension_dir()
    if args.action == "path":
        print(ext)
        return 0
    print(f"Extension directory: {ext}")
    info = _api_status() or {}
    ext_info = info.get("extension", {})
    if ext_info.get("connected"):
        print(f"  status   : connected ({ext_info.get('browser', '?')} "
              f"v{ext_info.get('version', '?')})")
    elif ext_info.get("ever_seen"):
        age = ext_info.get("age_seconds")
        print(f"  status   : last seen {age}s ago")
    else:
        print("  status   : not connected yet")
    print()
    print("Chrome / Edge / Brave : chrome://extensions -> Developer mode ON ->")
    print("                        Load unpacked -> pick the directory above")
    print("Firefox                : about:addons -> gear -> Install Add-on From File")
    print(f"                        -> {ext}/justgivenup.xpi")
    return 0


def cmd_dashboard(args) -> int:
    from .config import Config

    url = f"http://127.0.0.1:{Config().port}"
    print(url)
    if args.open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return 0


def cmd_blocklist(args) -> int:
    from .blocklist import summary

    print(json.dumps(summary(), ensure_ascii=False, indent=2))
    return 0


def cmd_version(_args) -> int:
    from . import VERSION

    print(f"justgivenup {VERSION}")
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="justgivenup",
        description="JustGivenUp! — porn blocker with an irreversible time-lock.",
    )
    sub = p.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="run the guardian daemon (used by systemd)")
    run_p.add_argument("--port", type=int, default=None)
    run_p.set_defaults(func=cmd_run)

    st = sub.add_parser("status", help="show lock + recovery status")
    st.add_argument("--json", action="store_true")
    st.set_defaults(func=cmd_status)

    lk = sub.add_parser("lock", help="lock protection for N days (irreversible)")
    lk.add_argument("--days", type=int, required=True)
    lk.add_argument("--confirm", default=None, help="confirmation phrase (default: LOCK)")
    lk.add_argument("--yes", action="store_true",
                    help="skip interactive confirmation (scripts only)")
    lk.set_defaults(func=cmd_lock)

    un = sub.add_parser("unlock", help="refused while a lock is active")
    un.set_defaults(func=cmd_unlock)

    rl = sub.add_parser("relapse", help="log a relapse and reset the streak")
    rl.add_argument("--kind", choices=["porn", "masturbation", "both"], default="both")
    rl.set_defaults(func=cmd_relapse)

    au = sub.add_parser("autostart", help="start automatically at boot/login")
    au.add_argument("action", choices=["enable", "disable", "status"])
    au.set_defaults(func=cmd_autostart)

    ex = sub.add_parser("extension", help="browser extension info")
    ex.add_argument("action", choices=["info", "path"], nargs="?", default="info")
    ex.set_defaults(func=cmd_extension)

    db = sub.add_parser("dashboard", help="print (and optionally open) the dashboard URL")
    db.add_argument("--open", action="store_true")
    db.set_defaults(func=cmd_dashboard)

    bl = sub.add_parser("blocklist", help="show blocklist statistics")
    bl.set_defaults(func=cmd_blocklist)

    ver = sub.add_parser("version", help="print version")
    ver.set_defaults(func=cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    from . import log
    from .config import state_dir

    log.set_state_dir(state_dir())
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        if getattr(args, "command", None) is None:
            # no subcommand: friendly default = status
            args = parser.parse_args(["status"])
        else:
            parser.print_help()
            return 1
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
