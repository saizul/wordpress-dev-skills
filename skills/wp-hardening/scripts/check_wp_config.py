#!/usr/bin/env python3
"""Audit wp-config.php hardening constants and (optionally) a WordPress root.

Reads wp-config.php as text (it is never executed) and reports risky or
missing settings: salts, debug output, file editing, auto-updates, database
user, SSL admin, and more. Secret values (passwords, keys, salts) are never
printed: only whether they are set and whether they look like defaults.

With --wp-root it also checks file permissions and leftover files that leak
data (debug.log, *.sql dumps, .git, phpinfo files, wp-config backups).

Exit codes: 0 no findings at or above --fail-on, 1 findings, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys

VERSION = "0.1.0"
SEVERITIES = ["info", "low", "medium", "high"]
SALT_KEYS = [
    "AUTH_KEY",
    "SECURE_AUTH_KEY",
    "LOGGED_IN_KEY",
    "NONCE_KEY",
    "AUTH_SALT",
    "SECURE_AUTH_SALT",
    "LOGGED_IN_SALT",
    "NONCE_SALT",
]
DEFINE_RE = re.compile(
    r"""define\s*\(\s*['"]([A-Za-z0-9_]+)['"]\s*,\s*"""
    r"""('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|[^;]+?)\s*\)\s*;""",
    re.S,
)
PREFIX_RE = re.compile(r"""\$table_prefix\s*=\s*['"]([^'"]*)['"]\s*;""")
LEAK_PATTERNS = [
    (
        re.compile(
            r"^(?:wp-config\.php\.(?:bak|old|orig|save|swp|txt)|wp-config\.(?:bak|old|txt))$|~$"
        ),
        "high",
        "Backup copy of a config file is web-reachable",
    ),
    (re.compile(r"\.(?:sql|sql\.gz|sql\.zip)$"), "high", "Database dump inside the web root"),
    (re.compile(r"^(?:phpinfo|info|test)\.php$"), "high", "phpinfo/test script in the web root"),
    (
        re.compile(r"^debug\.log$"),
        "high",
        "debug.log is web-reachable and may contain paths, queries or user data",
    ),
    (
        re.compile(r"^(?:adminer|phpmyadmin)[\w.-]*\.php$", re.I),
        "high",
        "Database admin tool in the web root",
    ),
    (re.compile(r"^\.env$"), "high", ".env file in the web root"),
]


def strip_comments(src: str) -> str:
    """Blank out PHP comments, keeping strings (salts may contain '/*' or '#')."""
    out = []
    i, n = 0, len(src)
    state = None
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state is None:
            if c in ("'", '"'):
                state = c
                out.append(c)
            elif (c == "/" and nxt == "/") or c == "#":
                state = "line"
                out.append(" ")
            elif c == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 1
            else:
                out.append(c)
        elif state in ("'", '"'):
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(nxt)
                i += 1
            elif c == state:
                state = None
        elif state == "line":
            if c == "\n":
                state = None
            out.append("\n" if c == "\n" else " ")
        else:
            if c == "*" and nxt == "/":
                state = None
                out.append("  ")
                i += 1
            else:
                out.append("\n" if c == "\n" else " ")
        i += 1
    return "".join(out)


def parse_value(raw: str):
    raw = raw.strip()
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    m = re.fullmatch(r"""(['"])(.*)\1""", raw, re.S)
    if m:
        return m.group(2)
    return {"expr": raw}


def parse_config(src: str) -> tuple[dict, str | None]:
    code = strip_comments(src)
    consts = {m.group(1): parse_value(m.group(2)) for m in DEFINE_RE.finditer(code)}
    pm = PREFIX_RE.search(code)
    return consts, (pm.group(1) if pm else None)


def audit_config(consts: dict, prefix: str | None) -> list[dict]:
    out: list[dict] = []

    def add(sev: str, cid: str, msg: str, fix: str) -> None:
        out.append({"id": cid, "severity": sev, "message": msg, "fix": fix})

    salts = {k: consts.get(k) for k in SALT_KEYS}
    bad = [
        k
        for k, v in salts.items()
        if not isinstance(v, str) or len(v) < 32 or "put your unique phrase here" in v
    ]
    if bad:
        add(
            "high",
            "WPH001",
            f"{len(bad)} auth key/salt(s) missing, short or default: {', '.join(bad)}",
            "Generate fresh values with `wp config shuffle-salts` (logs everyone out).",
        )
    vals = [v for v in salts.values() if isinstance(v, str) and v]
    if len(vals) != len(set(vals)):
        add(
            "medium",
            "WPH002",
            "Some keys/salts share the same value",
            "Run `wp config shuffle-salts`.",
        )

    debug = consts.get("WP_DEBUG") is True
    if debug:
        add(
            "medium",
            "WPH010",
            "WP_DEBUG is true",
            "Set WP_DEBUG to false in production (or use WP_ENVIRONMENT_TYPE to switch).",
        )
        if consts.get("WP_DEBUG_DISPLAY") is not False:
            add(
                "high",
                "WPH011",
                "Debug output is displayed to visitors (WP_DEBUG on, WP_DEBUG_DISPLAY not false)",
                "define( 'WP_DEBUG_DISPLAY', false ); and @ini_set( 'display_errors', 0 );",
            )
    log = consts.get("WP_DEBUG_LOG")
    if log is True:
        add(
            "medium",
            "WPH012",
            "WP_DEBUG_LOG writes to wp-content/debug.log, which is web-reachable by default",
            "Log outside the web root: define( 'WP_DEBUG_LOG', '/var/log/wp/debug.log' );",
        )
    if consts.get("SAVEQUERIES") is True:
        add(
            "medium",
            "WPH013",
            "SAVEQUERIES is on (memory and speed cost)",
            "Remove it in production.",
        )
    if consts.get("SCRIPT_DEBUG") is True:
        add(
            "low", "WPH014", "SCRIPT_DEBUG loads unminified core assets", "Remove it in production."
        )

    if (
        consts.get("DISALLOW_FILE_EDIT") is not True
        and consts.get("DISALLOW_FILE_MODS") is not True
    ):
        add(
            "medium",
            "WPH020",
            "Theme/plugin file editor is enabled",
            "define( 'DISALLOW_FILE_EDIT', true );",
        )
    if "DISALLOW_FILE_MODS" not in consts:
        add(
            "info",
            "WPH021",
            "DISALLOW_FILE_MODS not set",
            "For git/CI-deployed sites define( 'DISALLOW_FILE_MODS', true ); "
            "(also blocks dashboard updates; keep updates in your pipeline).",
        )
    if consts.get("FORCE_SSL_ADMIN") is not True:
        add("low", "WPH030", "FORCE_SSL_ADMIN is not true", "define( 'FORCE_SSL_ADMIN', true );")
    if consts.get("AUTOMATIC_UPDATER_DISABLED") is True:
        add(
            "medium",
            "WPH040",
            "All automatic updates are disabled (including security releases)",
            "Remove AUTOMATIC_UPDATER_DISABLED or make sure updates run elsewhere.",
        )
    if consts.get("WP_AUTO_UPDATE_CORE") is False:
        add(
            "medium",
            "WPH041",
            "Core auto-updates are off (minor/security releases too)",
            "Use define( 'WP_AUTO_UPDATE_CORE', 'minor' ); unless updates are automated.",
        )
    if consts.get("DB_USER") == "root":
        add(
            "medium",
            "WPH050",
            "Database user is root",
            "Create a dedicated DB user with rights on one database.",
        )
    if "DB_PASSWORD" in consts and consts.get("DB_PASSWORD") == "":
        add("high", "WPH051", "Database password is empty", "Set a long random DB password.")
    if prefix == "wp_":
        add(
            "info",
            "WPH060",
            "Default table prefix wp_",
            "Not a real defence; only change it on new installs.",
        )
    if "WP_ENVIRONMENT_TYPE" not in consts:
        add(
            "info",
            "WPH070",
            "WP_ENVIRONMENT_TYPE not set",
            "define( 'WP_ENVIRONMENT_TYPE', 'production' ); lets plugins behave per environment.",
        )
    return out


def audit_files(config_path: str, wp_root: str | None) -> list[dict]:
    out: list[dict] = []

    def add(sev: str, cid: str, msg: str, fix: str, path: str = "") -> None:
        out.append({"id": cid, "severity": sev, "message": msg, "fix": fix, "path": path})

    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(config_path).st_mode)
        if mode & stat.S_IWOTH:
            add(
                "high",
                "WPH100",
                f"wp-config.php is world-writable ({oct(mode)})",
                "chmod 600 or 640 wp-config.php",
                config_path,
            )
        elif mode & stat.S_IROTH:
            add(
                "medium",
                "WPH101",
                f"wp-config.php is world-readable ({oct(mode)})",
                "chmod 640 (or 600/400 if PHP runs as the file owner)",
                config_path,
            )
    if not wp_root:
        return out
    world_writable: list[str] = []
    for root, dirs, files in os.walk(wp_root):
        dirs[:] = [d for d in dirs if d not in ("node_modules",)]
        rel_root = os.path.relpath(root, wp_root)
        if ".git" in dirs:
            add(
                "high",
                "WPH110",
                "A .git directory is inside the web root",
                "Deploy without .git or deny it in the web server.",
                os.path.join(root, ".git"),
            )
            dirs.remove(".git")
        for name in files:
            full = os.path.join(root, name)
            for rx, sev, msg in LEAK_PATTERNS:
                if rx.search(name):
                    add(sev, "WPH111", msg, "Delete it or move it outside the web root.", full)
                    break
        if os.name == "posix":
            for name in dirs + files:
                full = os.path.join(root, name)
                try:
                    st = os.lstat(full)
                except OSError:
                    continue
                if stat.S_ISLNK(st.st_mode):
                    continue
                if st.st_mode & stat.S_IWOTH:
                    world_writable.append(os.path.join(rel_root, name))
    if world_writable:
        add(
            "high",
            "WPH120",
            f"{len(world_writable)} world-writable file(s)/dir(s), e.g. {', '.join(sorted(world_writable)[:5])}",
            "find . -type d -exec chmod 755 {} + && find . -type f -exec chmod 644 {} + (then fix wp-config.php)",
        )
    return out


def find_config(wp_root: str) -> str | None:
    for cand in (
        os.path.join(wp_root, "wp-config.php"),
        os.path.join(os.path.dirname(os.path.abspath(wp_root)), "wp-config.php"),
    ):
        if os.path.isfile(cand):
            return cand
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_wp_config.py",
        description="Audit wp-config.php hardening constants (never prints secrets) and "
        "optionally permissions/leftover files in a WordPress root.",
        epilog="Example: python3 check_wp_config.py --wp-root /var/www/example.com/htdocs",
    )
    p.add_argument(
        "config", nargs="?", help="path to wp-config.php (default: found from --wp-root)"
    )
    p.add_argument("--wp-root", help="WordPress root to check permissions and leftover files")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = args.config or (find_config(args.wp_root) if args.wp_root else None)
    if not config or not os.path.isfile(config):
        print("error: wp-config.php not found; pass its path or --wp-root", file=sys.stderr)
        return 2
    if args.wp_root and not os.path.isdir(args.wp_root):
        print(f"error: not a directory: {args.wp_root}", file=sys.stderr)
        return 2
    with open(config, encoding="utf-8", errors="replace") as fh:
        consts, prefix = parse_config(fh.read())
    findings = audit_config(consts, prefix) + audit_files(config, args.wp_root)
    rank = SEVERITIES.index(args.fail_on)
    failing = [f for f in findings if SEVERITIES.index(f["severity"]) >= rank]
    summary = {
        "config": config,
        "constants_found": sorted(consts),
        "findings": findings,
    }
    if args.json:
        print(json.dumps({"version": VERSION, **summary}, indent=2))
    else:
        print(f"Checked {config} ({len(consts)} constants).")
        order = {s: i for i, s in enumerate(reversed(SEVERITIES))}
        for f in sorted(findings, key=lambda f: order[f["severity"]]):
            where = f" [{f['path']}]" if f.get("path") else ""
            print(f"[{f['severity'].upper()}] {f['id']} {f['message']}{where}")
            print(f"    fix: {f['fix']}")
        if not findings:
            print("No findings.")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
