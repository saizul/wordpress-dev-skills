#!/usr/bin/env python3
"""Plan a safe `wp search-replace` for a domain or URL migration.

The script does not touch the database. It validates the old/new values, warns
about classic mistakes, and prints an ordered, shell-quoted command plan:
backup, dry runs for every URL encoding WordPress data commonly contains, the
real runs (only with --apply-steps), and cache/rewrite flushes.

Variants covered for each pair:
  plain          https://old.example
  json-escaped   https:\\/\\/old.example     (block attributes, JSON options)
  url-encoded    https%3A%2F%2Fold.example   (query strings, some builders)

`wp search-replace` handles PHP-serialized data itself, so no variant is needed
for serialized options.

Exit codes: 0 plan printed, 1 plan printed with warnings (--strict), 2 invalid input.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from urllib.parse import quote, urlsplit

VERSION = "0.1.0"


def validate(old: str, new: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not old or not new:
        errors.append("both --from and --to are required and must be non-empty")
        return errors, warnings
    if old == new:
        errors.append("--from and --to are identical")
    for label, val in (("--from", old), ("--to", new)):
        if any(c.isspace() for c in val):
            errors.append(f"{label} contains whitespace: {val!r}")
        if val.endswith("/") and len(val) > 1:
            warnings.append(
                f"{label} ends with '/'. Replace without the trailing slash, or both sides "
                "must have it, otherwise you create double slashes or miss matches"
            )
        if "://" in val:
            parts = urlsplit(val)
            if parts.scheme not in ("http", "https"):
                errors.append(f"{label} has an unexpected scheme: {parts.scheme}")
            if not parts.netloc:
                errors.append(f"{label} has no host")
    if old.endswith("/") != new.endswith("/"):
        warnings.append("only one side ends with '/'; make them consistent")
    if ("://" in old) != ("://" in new):
        warnings.append("one value has a scheme and the other does not; compare like with like")
    if old in new:
        warnings.append(
            f"the new value contains the old value ({old!r} in {new!r}); running the "
            "replacement twice will corrupt URLs (e.g. example.com -> example.com.au.au). "
            "Run it exactly once, or replace a more specific string such as '//old.host'"
        )
    if old.startswith("https://") and new.startswith("http://"):
        warnings.append("you are downgrading https to http; is that intended?")
    if "://" not in old and "." not in old:
        warnings.append(
            f"{old!r} is a short, generic string; it may match unrelated content. "
            "Prefer full URLs or host names"
        )
    return errors, warnings


def variants(old: str, new: str) -> list[tuple[str, str, str]]:
    out = [("plain", old, new)]
    if "/" in old or "/" in new:
        out.append(("json-escaped", old.replace("/", "\\/"), new.replace("/", "\\/")))
    if "://" in old:
        out.append(("url-encoded", quote(old, safe=""), quote(new, safe="")))
    return out


def build_plan(args: argparse.Namespace) -> list[dict]:
    base_flags = ["--precise", "--skip-columns=guid", "--report-changed-only"]
    if args.all_tables:
        base_flags.insert(0, "--all-tables")
    else:
        base_flags.insert(0, "--all-tables-with-prefix")
    if args.network:
        base_flags.append("--network")
    if args.url:
        base_flags.append(f"--url={args.url}")
    wp = ["wp"]
    if args.ssh:
        wp.append(f"--ssh={args.ssh}")
    if args.skip_plugins:
        wp += ["--skip-plugins", "--skip-themes"]

    def cmd(parts: list[str]) -> str:
        return " ".join(shlex.quote(p) for p in parts)

    steps: list[dict] = []
    steps.append(
        {
            "step": "backup",
            "command": cmd([*wp, "db", "export", args.backup_file]),
            "why": "Full SQL backup you can restore with `wp db import`.",
        }
    )
    steps.append(
        {
            "step": "baseline",
            "command": cmd([*wp, "option", "get", "home"])
            + " && "
            + cmd([*wp, "option", "get", "siteurl"]),
            "why": "Record the current home/siteurl values.",
        }
    )
    for name, o, n in variants(args.old, args.new):
        steps.append(
            {
                "step": f"dry-run:{name}",
                "command": cmd([*wp, "search-replace", o, n, *base_flags, "--dry-run"]),
                "why": f"Preview the {name} replacement; nothing is written.",
            }
        )
    if args.export:
        # --export writes one SQL file for one pair; run the other variants after import.
        steps.append(
            {
                "step": "export:plain",
                "command": cmd(
                    [*wp, "search-replace", args.old, args.new, *base_flags]
                    + [f"--export={args.export}"]
                ),
                "why": "Write a migrated SQL file instead of changing this database "
                "(import it on the target, then run the escaped variants there).",
            }
        )
    if args.apply_steps:
        for name, o, n in variants(args.old, args.new):
            steps.append(
                {
                    "step": f"apply:{name}",
                    "command": cmd([*wp, "search-replace", o, n, *base_flags]),
                    "why": "Writes to the database. Run only after reviewing the dry run.",
                }
            )
        steps.append(
            {
                "step": "flush",
                "command": cmd([*wp, "cache", "flush"]) + " && " + cmd([*wp, "rewrite", "flush"]),
                "why": "Clear the object cache and regenerate rewrite rules.",
            }
        )
        steps.append(
            {
                "step": "verify",
                "command": cmd([*wp, "option", "get", "home"])
                + " && "
                + cmd([*wp, "search-replace", args.old, args.new, *base_flags, "--dry-run"]),
                "why": "The second dry run should report 0 replacements.",
            }
        )
    return steps


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="search_replace_plan.py",
        description="Print a safe, ordered WP-CLI search-replace plan (backup, dry runs, "
        "JSON-escaped and URL-encoded variants). Never runs anything.",
        epilog="Example: python3 search_replace_plan.py --from https://staging.example.com "
        "--to https://example.com --apply-steps",
    )
    p.add_argument("--from", dest="old", required=True, help="value to replace")
    p.add_argument("--to", dest="new", required=True, help="replacement value")
    p.add_argument("--apply-steps", action="store_true", help="include the writing steps")
    p.add_argument("--network", action="store_true", help="multisite: all sites' tables")
    p.add_argument("--url", help="multisite: target one site (--url=...)")
    p.add_argument("--all-tables", action="store_true", help="every table, not just the prefix")
    p.add_argument("--ssh", help="run against a remote alias/host via WP-CLI --ssh")
    p.add_argument("--skip-plugins", action="store_true", help="add --skip-plugins --skip-themes")
    p.add_argument("--export", help="write migrated SQL to this file instead of the live DB")
    p.add_argument("--backup-file", default="backup-before-search-replace.sql")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--strict", action="store_true", help="exit 1 when there are warnings")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors, warnings = validate(args.old, args.new)
    if errors:
        if args.json:
            print(json.dumps({"errors": errors, "warnings": warnings}, indent=2))
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 2
    steps = build_plan(args)
    if args.json:
        print(json.dumps({"version": VERSION, "warnings": warnings, "steps": steps}, indent=2))
    else:
        print("#!/bin/sh")
        print(f"# search-replace plan: {args.old} -> {args.new}")
        print("# Review every dry run before running the apply steps.")
        print("set -e")
        for w in warnings:
            print(f"# WARNING: {w}")
        for s in steps:
            print(f"\n# {s['step']}: {s['why']}")
            print(s["command"])
        if not args.apply_steps:
            print("\n# Dry runs only. Re-run with --apply-steps to print the writing commands.")
    return 1 if (warnings and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
