#!/usr/bin/env python3
"""Generate and validate WordPress.org plugin readme.txt files.

  validate  check a readme.txt against the WordPress.org plugin directory rules
            (header fields, tags, short description length, Stable tag, sections)
            and, with --plugin-file, against the main plugin file header
  generate  write a readme.txt skeleton from the main plugin file header

Rules follow "How Your Plugin Readme.txt Works" in the WordPress Plugin
Handbook: 1-5 tags, short description of at most 150 characters, Tested up to
as a major version number, Stable tag as the plugin version (not trunk),
readme under 10 KB.

Exit codes: 0 valid, 1 errors (or warnings with --strict), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

VERSION = "0.1.0"
MAX_TAGS = 5
MAX_SHORT = 150
MAX_BYTES = 10 * 1024
PLUGIN_HEADERS = {
    "name": "Plugin Name",
    "uri": "Plugin URI",
    "description": "Description",
    "version": "Version",
    "requires_wp": "Requires at least",
    "requires_php": "Requires PHP",
    "author": "Author",
    "license": "License",
    "license_uri": "License URI",
    "text_domain": "Text Domain",
}
REQUIRED = ["Contributors", "Tested up to", "Stable tag", "License"]
RECOMMENDED = ["Tags", "Requires at least", "Requires PHP", "License URI"]
GPL_COMPATIBLE = re.compile(
    r"GPL|MIT|BSD|Apache|MPL|ISC|Expat|Artistic|LGPL|CC0|Public Domain", re.I
)
VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")


def plugin_headers(path: str) -> dict:
    """Read plugin headers the way WordPress get_file_data() does (first 8 KB)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.read(8192)
    out = {}
    for key, label in PLUGIN_HEADERS.items():
        m = re.search(r"^[ \t/*#@]*" + re.escape(label) + r":(.*)$", head, re.M | re.I)
        if m:
            val = re.sub(r"\s*(?:\*/|\?>).*", "", m.group(1)).strip()
            if val:
                out[key] = val
    return out


def parse_readme(text: str) -> dict:
    lines = text.splitlines()
    result: dict = {"name": None, "headers": {}, "short": "", "sections": {}}
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines):
        m = re.match(r"^===\s*(.+?)\s*===\s*$", lines[i].strip())
        if m:
            result["name"] = m.group(1)
            i += 1
    while i < len(lines) and lines[i].strip():
        m = re.match(r"^\s*([A-Za-z][A-Za-z ]*?)\s*:\s*(.*)$", lines[i])
        if m:
            result["headers"][m.group(1).strip()] = m.group(2).strip()
        i += 1
    short: list[str] = []
    while i < len(lines) and not lines[i].startswith("=="):
        if lines[i].strip() or short:
            if not lines[i].strip():
                break
            short.append(lines[i].strip())
        i += 1
    result["short"] = " ".join(short)
    current = None
    for line in lines[i:]:
        m = re.match(r"^==\s*(.+?)\s*==\s*$", line.strip())
        if m and not line.strip().startswith("==="):
            current = m.group(1)
            result["sections"][current] = []
        elif current:
            result["sections"][current].append(line)
    result["sections"] = {k: "\n".join(v).strip() for k, v in result["sections"].items()}
    return result


def validate(text: str, plugin: dict | None = None, wp_latest: str | None = None) -> list[dict]:
    issues: list[dict] = []

    def err(field: str, msg: str) -> None:
        issues.append({"level": "error", "field": field, "message": msg})

    def warn(field: str, msg: str) -> None:
        issues.append({"level": "warning", "field": field, "message": msg})

    r = parse_readme(text)
    h = {k.lower(): v for k, v in r["headers"].items()}
    if not r["name"]:
        err("name", "first line must be '=== Plugin Name ==='")
    for f in REQUIRED:
        if not h.get(f.lower()):
            err(f, f"'{f}:' header is required")
    for f in RECOMMENDED:
        if not h.get(f.lower()):
            warn(f, f"'{f}:' header is recommended")

    contrib = h.get("contributors", "")
    for c in (x.strip() for x in contrib.split(",") if x.strip()):
        if " " in c or not re.fullmatch(r"[A-Za-z0-9_.-]+", c):
            err("Contributors", f"{c!r} is not a WordPress.org username (no spaces)")
    tags = [t.strip() for t in h.get("tags", "").split(",") if t.strip()]
    if len(tags) > MAX_TAGS:
        warn(
            "Tags",
            f"{len(tags)} tags; only the first {MAX_TAGS} are used: {', '.join(tags[:MAX_TAGS])}",
        )
    if len({t.lower() for t in tags}) != len(tags):
        warn("Tags", "duplicate tags")

    tested = h.get("tested up to")
    if tested:
        if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", tested):
            err("Tested up to", f"{tested!r} must be a WordPress version number such as 6.8")
        elif tested.count(".") == 2:
            warn("Tested up to", "use the major version only (6.8, not 6.8.1)")
        if wp_latest and re.fullmatch(r"\d+\.\d+(?:\.\d+)?", tested):
            if _ver(tested)[:2] < _ver(wp_latest)[:2]:
                warn(
                    "Tested up to",
                    f"{tested} is older than WordPress {wp_latest}; the directory shows "
                    "'not tested with the latest 3 major releases' warnings over time",
                )
    for f in ("requires at least", "requires php"):
        v = h.get(f)
        if v and not VERSION_RE.match(v):
            err(f.title(), f"{v!r} must be numbers and dots only")

    stable = h.get("stable tag")
    if stable:
        if stable.lower() == "trunk":
            warn("Stable tag", "'trunk' is discouraged; use the released version and an SVN tag")
        elif not VERSION_RE.match(stable):
            err("Stable tag", f"{stable!r} must be numbers and dots (e.g. 1.4.2)")
    lic = h.get("license")
    if lic and not GPL_COMPATIBLE.search(lic):
        warn("License", f"{lic!r} does not look GPL-compatible (required on WordPress.org)")

    if not r["short"]:
        err("short description", "add a one-line short description after the header block")
    else:
        if len(r["short"]) > MAX_SHORT:
            err(
                "short description",
                f"{len(r['short'])} characters; maximum is {MAX_SHORT} (the rest is cut off)",
            )
        if re.search(r"<[a-z][^>]*>|\[[^\]]+\]\(|\*\*", r["short"], re.I):
            warn("short description", "no markup allowed in the short description")

    sections = {k.lower(): v for k, v in r["sections"].items()}
    if "description" not in sections:
        err("Description", "'== Description ==' section is required")
    elif not sections["description"]:
        err("Description", "Description section is empty")
    if "changelog" not in sections:
        warn("Changelog", "'== Changelog ==' section is recommended")
    elif stable and stable.lower() != "trunk":
        if not re.search(r"^=\s*v?" + re.escape(stable) + r"\b", sections["changelog"], re.M):
            warn("Changelog", f"no '= {stable} =' entry for the Stable tag")
    if "upgrade notice" in sections:
        for m in re.finditer(
            r"^=\s*(.+?)\s*=\s*\n(.*?)(?=^=|\Z)", sections["upgrade notice"], re.M | re.S
        ):
            if len(m.group(2).strip()) > 300:
                warn("Upgrade Notice", f"notice for {m.group(1)} is over 300 characters")
    if len(text.encode("utf-8")) > MAX_BYTES:
        warn("size", "readme.txt is over 10 KB; move old changelog entries to changelog.txt")

    if plugin:
        if plugin.get("version") and stable and stable.lower() != "trunk":
            if plugin["version"] != stable:
                err("Stable tag", f"Stable tag {stable} != plugin Version {plugin['version']}")
        for key, field in (("requires_wp", "requires at least"), ("requires_php", "requires php")):
            if plugin.get(key) and h.get(field) and plugin[key] != h[field]:
                warn(field.title(), f"readme says {h[field]}, plugin header says {plugin[key]}")
        if plugin.get("name") and r["name"] and plugin["name"] != r["name"]:
            warn("name", f"readme name {r['name']!r} != Plugin Name {plugin['name']!r}")
    return issues


def _ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def generate(plugin: dict, contributors: str, tags: str, tested: str) -> str:
    name = plugin.get("name", "My Plugin")
    short = plugin.get("description", "Short description of the plugin.")
    if len(short) > MAX_SHORT:
        short = short[: MAX_SHORT - 1].rstrip() + "."
    version = plugin.get("version", "0.1.0")
    lines = [
        f"=== {name} ===",
        f"Contributors: {contributors}",
        f"Tags: {tags}",
        f"Requires at least: {plugin.get('requires_wp', '6.5')}",
        f"Tested up to: {tested}",
        f"Requires PHP: {plugin.get('requires_php', '7.4')}",
        f"Stable tag: {version}",
        f"License: {plugin.get('license', 'GPLv2 or later')}",
        f"License URI: {plugin.get('license_uri', 'https://www.gnu.org/licenses/gpl-2.0.html')}",
        "",
        short,
        "",
        "== Description ==",
        "",
        f"{name} ... (what it does, who it is for, and the main features).",
        "",
        "= Features =",
        "",
        "* Feature one",
        "* Feature two",
        "",
        "== Installation ==",
        "",
        "1. Install the plugin from Plugins > Add New, or upload the folder to `/wp-content/plugins/`.",
        "2. Activate the plugin through the Plugins screen.",
        "3. Go to Settings and configure it.",
        "",
        "== Frequently Asked Questions ==",
        "",
        "= Does it work with multisite? =",
        "",
        "Answer.",
        "",
        "== Screenshots ==",
        "",
        "1. Settings screen (assets/screenshot-1.png).",
        "",
        "== Changelog ==",
        "",
        f"= {version} =",
        "* Initial release.",
        "",
        "== Upgrade Notice ==",
        "",
        f"= {version} =",
        "Initial release.",
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="readme_txt.py",
        description="Validate or generate a WordPress.org plugin readme.txt.",
        epilog="Examples:\n  readme_txt.py validate readme.txt --plugin-file my-plugin.php\n"
        "  readme_txt.py generate my-plugin.php --contributors myname --tags 'seo, schema' "
        "--tested-up-to 6.8 -o readme.txt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check a readme.txt")
    v.add_argument("readme", help="path to readme.txt")
    v.add_argument("--plugin-file", help="main plugin PHP file to cross-check headers")
    v.add_argument(
        "--wp-latest", help="latest WordPress major version, e.g. 6.8, to compare Tested up to"
    )
    v.add_argument("--json", action="store_true", help="print JSON")
    v.add_argument("--strict", action="store_true", help="treat warnings as failures")
    g = sub.add_parser("generate", help="create readme.txt from the plugin header")
    g.add_argument("plugin_file", help="main plugin PHP file")
    g.add_argument("--contributors", required=True, help="comma-separated WordPress.org usernames")
    g.add_argument("--tags", default="", help="comma-separated tags (max 5)")
    g.add_argument("--tested-up-to", required=True, help="WordPress major version, e.g. 6.8")
    g.add_argument("-o", "--output", help="write to this file (default: stdout)")
    g.add_argument("--force", action="store_true", help="overwrite an existing output file")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "generate":
        if not os.path.isfile(args.plugin_file):
            print(f"error: not found: {args.plugin_file}", file=sys.stderr)
            return 2
        plugin = plugin_headers(args.plugin_file)
        if "name" not in plugin:
            print("error: no 'Plugin Name:' header in that file", file=sys.stderr)
            return 2
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        if len(tags) > MAX_TAGS:
            print(f"error: at most {MAX_TAGS} tags", file=sys.stderr)
            return 2
        text = generate(plugin, args.contributors, ", ".join(tags), args.tested_up_to)
        if args.output:
            if os.path.exists(args.output) and not args.force:
                print(f"error: {args.output} exists (use --force)", file=sys.stderr)
                return 2
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"wrote {args.output}")
        else:
            sys.stdout.write(text)
        return 0

    if not os.path.isfile(args.readme):
        print(f"error: not found: {args.readme}", file=sys.stderr)
        return 2
    plugin = None
    if args.plugin_file:
        if not os.path.isfile(args.plugin_file):
            print(f"error: not found: {args.plugin_file}", file=sys.stderr)
            return 2
        plugin = plugin_headers(args.plugin_file)
    with open(args.readme, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    issues = validate(text, plugin, args.wp_latest)
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    if args.json:
        print(json.dumps({"version": VERSION, "file": args.readme, "issues": issues}, indent=2))
    else:
        for i in issues:
            print(f"{i['level']}: [{i['field']}] {i['message']}")
        print(f"\n{args.readme}: {len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
