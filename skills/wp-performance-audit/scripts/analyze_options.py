#!/usr/bin/env python3
"""Analyze WordPress autoloaded options from `wp option list` output.

Every autoloaded option is loaded on every request (and stored in one
`alloptions` cache entry). Bloated autoload data is one of the most common
causes of slow TTFB and object-cache churn.

Produce the input with WP-CLI (read-only):

    wp option list --fields=option_name,size_bytes,autoload --format=json > options.json

Then:

    python3 analyze_options.py options.json
    wp option list --fields=option_name,size_bytes,autoload --format=json | \
        python3 analyze_options.py -

CSV (`--format=csv`) is accepted too. If `size_bytes` is missing but
`option_value` is present, the size is computed from the value. Option values
are never printed.

Exit codes: 0 healthy, 1 autoload total over --threshold or an option over
--large, 2 bad input.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import shlex
import sys

VERSION = "0.1.0"
# WordPress 6.6+ stores 'on'/'off'/'auto'/'auto-on'/'auto-off'; older sites use yes/no.
# wp_autoload_values_to_autoload() returns yes, on, auto-on and auto by default.
AUTOLOAD_VALUES = {"yes", "on", "auto-on", "auto"}
# Site Health ("Autoloaded options could affect performance") warns above 800 KB.
DEFAULT_THRESHOLD = 800_000
DEFAULT_LARGE = 100_000
CORE_KEEP = {
    "siteurl",
    "home",
    "active_plugins",
    "template",
    "stylesheet",
    "cron",
    "rewrite_rules",
    "wp_user_roles",
    "sidebars_widgets",
    "widget_block",
    "can_compress_scripts",
}


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n} B"


def parse_rows(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        raise ValueError("empty input")
    if text[0] in "[{":
        data = json.loads(text)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            raise ValueError("JSON input must be an array of objects")
        rows = data
    else:
        rows = list(csv.DictReader(io.StringIO(text)))
    out = []
    for r in rows:
        if not isinstance(r, dict) or "option_name" not in r:
            raise ValueError("each row needs an option_name field")
        size = r.get("size_bytes")
        if size in (None, ""):
            value = r.get("option_value")
            if value is None:
                raise ValueError(
                    "rows need size_bytes (use --fields=option_name,size_bytes,autoload)"
                )
            size = len(str(value).encode("utf-8"))
        autoload = str(r.get("autoload", "yes")).strip().lower()
        out.append({"name": str(r["option_name"]), "size": int(size), "autoload": autoload})
    return out


def owner_prefix(name: str) -> str:
    for p in ("_site_transient_", "_transient_"):
        if name.startswith(p):
            return p.rstrip("_")
    head = name.lstrip("_").split("_", 1)[0]
    return head or name


def analyze(rows: list[dict], threshold: int, large: int, top: int) -> dict:
    auto = [r for r in rows if r["autoload"] in AUTOLOAD_VALUES]
    total = sum(r["size"] for r in auto)
    auto_sorted = sorted(auto, key=lambda r: r["size"], reverse=True)
    groups: dict[str, dict] = {}
    for r in auto:
        g = groups.setdefault(owner_prefix(r["name"]), {"count": 0, "bytes": 0})
        g["count"] += 1
        g["bytes"] += r["size"]
    group_list = sorted(
        ({"prefix": k, **v} for k, v in groups.items()), key=lambda g: g["bytes"], reverse=True
    )
    issues = []
    if total > threshold:
        issues.append(
            {
                "type": "autoload_total",
                "severity": "high",
                "message": f"Autoloaded options total {human(total)} (threshold {human(threshold)})",
            }
        )
    large_opts = [r for r in auto_sorted if r["size"] >= large]
    for r in large_opts:
        issues.append(
            {
                "type": "large_option",
                "severity": "medium",
                "option": r["name"],
                "bytes": r["size"],
                "message": f"{r['name']} is {human(r['size'])} and autoloaded",
            }
        )
    transients = [r for r in auto if r["name"].startswith(("_transient_", "_site_transient_"))]
    if transients:
        issues.append(
            {
                "type": "autoloaded_transients",
                "severity": "low",
                "count": len(transients),
                "bytes": sum(r["size"] for r in transients),
                "message": f"{len(transients)} transient(s) autoloaded "
                f"({human(sum(r['size'] for r in transients))}); usually set without expiry",
            }
        )
    candidates = [r for r in large_opts if r["name"] not in CORE_KEEP]
    commands = [
        "wp db export before-autoload-change.sql  # back up first",
        *[f"wp option get-autoload {shlex.quote(r['name'])}" for r in candidates],
        *[f"wp option set-autoload {shlex.quote(r['name'])} off" for r in candidates],
    ]
    if transients:
        commands.append("wp transient delete --expired")
    return {
        "version": VERSION,
        "options_total": len(rows),
        "autoload_count": len(auto),
        "autoload_bytes": total,
        "autoload_human": human(total),
        "threshold_bytes": threshold,
        "top": [{"option": r["name"], "bytes": r["size"]} for r in auto_sorted[:top]],
        "by_prefix": group_list[:top],
        "issues": issues,
        "suggested_commands": commands if candidates or transients else [],
        "core_options_skipped": [r["name"] for r in large_opts if r["name"] in CORE_KEEP],
    }


def render_text(rep: dict) -> str:
    lines = [
        f"Autoloaded: {rep['autoload_count']} of {rep['options_total']} options, "
        f"{rep['autoload_human']} (threshold {human(rep['threshold_bytes'])})",
        "",
        "Largest autoloaded options:",
    ]
    lines += [f"  {human(t['bytes']):>10}  {t['option']}" for t in rep["top"]]
    lines += ["", "By prefix (likely owner plugin/theme):"]
    lines += [
        f"  {human(g['bytes']):>10}  {g['prefix']} ({g['count']} options)" for g in rep["by_prefix"]
    ]
    lines.append("")
    if rep["issues"]:
        lines.append("Issues:")
        lines += [f"  [{i['severity'].upper()}] {i['message']}" for i in rep["issues"]]
    else:
        lines.append("No issues: autoload size looks healthy.")
    if rep["core_options_skipped"]:
        lines.append(
            "  Note: large core option(s) kept autoloaded: "
            + ", ".join(rep["core_options_skipped"])
            + " (investigate the cause instead, e.g. cron or rewrite_rules bloat)"
        )
    if rep["suggested_commands"]:
        lines += ["", "Review, then run (confirm each option's owner is not needed on every page):"]
        lines += [f"  {c}" for c in rep["suggested_commands"]]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="analyze_options.py",
        description="Report autoloaded option size from `wp option list` JSON/CSV output.",
        epilog="Input: wp option list --fields=option_name,size_bytes,autoload --format=json",
    )
    p.add_argument("input", help="file with wp option list output, or - for stdin")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help="bytes (800000)")
    p.add_argument("--large", type=int, default=DEFAULT_LARGE, help="per-option bytes (100000)")
    p.add_argument("--top", type=int, default=15, help="rows to show (15)")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.input == "-":
            text = sys.stdin.read()
        else:
            with open(args.input, encoding="utf-8") as fh:
                text = fh.read()
        rows = parse_rows(text)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rep = analyze(rows, args.threshold, args.large, args.top)
    print(json.dumps(rep, indent=2) if args.json else render_text(rep))
    return 1 if any(i["severity"] in ("high", "medium") for i in rep["issues"]) else 0


if __name__ == "__main__":
    sys.exit(main())
