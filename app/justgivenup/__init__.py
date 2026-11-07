"""JustGivenUp! Guardian — cross-platform porn blocker with an irreversible time-lock.

Two cooperating layers:
  1. Browser extension (Chrome / Firefox) — in-browser blocking + dashboard UX.
  2. Local daemon (this package) — dashboard server, sealed time-lock,
     /etc/hosts DNS enforcement, browser enterprise policies, streak stats.

Both are useless alone against a determined user; together (plus the
systemd watchdog and the deb package's removal guard) they make the
lock effectively unbreakable for its whole duration.
"""

VERSION = "3.1.0"
APP_NAME = "JustGivenUp"
APP_SLUG = "justgivenup"
DASHBOARD_PORT = 8081
