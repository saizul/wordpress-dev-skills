#!/usr/bin/env python3
"""Validate WordPress block.json files.

Checks the metadata that most often breaks block registration or builds:
name format, required fields, apiVersion, attribute definitions, and that
every `file:` asset (editorScript, viewScriptModule, style, render, ...) exists
next to the block.json. Pass one or more block.json files or directories
(searched recursively; node_modules and vendor are skipped).

Exit codes: 0 valid, 1 errors (or warnings with --strict), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

VERSION = "0.1.0"
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*/[a-z][a-z0-9-]*$")
CORE_CATEGORIES = {"text", "media", "design", "widgets", "theme", "embed"}
ATTR_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}
ATTR_SOURCES = {"attribute", "text", "html", "rich-text", "query", "raw", "meta"}
ASSET_FIELDS = [
    "editorScript",
    "script",
    "viewScript",
    "viewScriptModule",
    "editorStyle",
    "style",
    "viewStyle",
]
KNOWN_KEYS = {
    "$schema",
    "apiVersion",
    "name",
    "title",
    "category",
    "parent",
    "ancestor",
    "allowedBlocks",
    "icon",
    "description",
    "keywords",
    "version",
    "textdomain",
    "attributes",
    "providesContext",
    "usesContext",
    "selectors",
    "supports",
    "styles",
    "example",
    "variations",
    "blockHooks",
    "render",
    "editorScript",
    "script",
    "viewScript",
    "viewScriptModule",
    "editorStyle",
    "style",
    "viewStyle",
}
SKIP_DIRS = {"node_modules", "vendor", ".git"}


def check_block(path: str) -> list[dict]:
    issues: list[dict] = []

    def err(msg: str) -> None:
        issues.append({"level": "error", "file": path, "message": msg})

    def warn(msg: str) -> None:
        issues.append({"level": "warning", "file": path, "message": msg})

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        err(f"invalid JSON: {exc}")
        return issues
    if not isinstance(data, dict):
        err("block.json must contain a JSON object")
        return issues
    base = os.path.dirname(os.path.abspath(path))

    if "$schema" not in data:
        warn('add "$schema": "https://schemas.wp.org/trunk/block.json" for editor validation')
    api = data.get("apiVersion")
    if api is None:
        warn("apiVersion missing (defaults to 1); use 3 for WordPress 6.3+")
    elif not isinstance(api, int) or api < 1:
        err(f"apiVersion must be a positive integer, got {api!r}")
    elif api < 3:
        warn(f"apiVersion {api}: use 3 so the block works in the iframed editor")

    name = data.get("name")
    if not name:
        err("name is required (namespace/block-name)")
    elif not isinstance(name, str) or not NAME_RE.match(name):
        err(f"name {name!r} must be 'namespace/block-name' using lowercase a-z, 0-9 and '-'")
    if not data.get("title"):
        err("title is required")
    cat = data.get("category")
    if cat is None:
        warn("category missing; the block shows under 'Uncategorized'")
    elif cat not in CORE_CATEGORIES:
        warn(
            f"category {cat!r} is not a core category ({', '.join(sorted(CORE_CATEGORIES))}); "
            "register it with the block_categories_all filter"
        )
    if "textdomain" not in data:
        warn("textdomain missing; title/description/keywords will not be translatable")
    if "version" not in data:
        warn("version missing; recommended for cache busting of assets without an .asset.php")

    for key in data:
        if key not in KNOWN_KEYS and not key.startswith("__experimental"):
            warn(f"unknown top-level key {key!r} (typo?)")

    for parent_key in ("parent", "ancestor", "allowedBlocks"):
        val = data.get(parent_key)
        if val is not None and (
            not isinstance(val, list) or not all(isinstance(v, str) for v in val)
        ):
            err(f"{parent_key} must be an array of block names")

    attrs = data.get("attributes", {})
    if not isinstance(attrs, dict):
        err("attributes must be an object")
        attrs = {}
    for aname, spec in attrs.items():
        if not isinstance(spec, dict):
            err(f"attribute {aname!r} must be an object")
            continue
        types = spec.get("type")
        if types is None and "enum" not in spec:
            err(f"attribute {aname!r} needs a type (or enum)")
        if types is not None:
            tlist = types if isinstance(types, list) else [types]
            bad = [t for t in tlist if t not in ATTR_TYPES]
            if bad:
                err(f"attribute {aname!r} has invalid type {bad[0]!r}")
        src = spec.get("source")
        if src is not None:
            if src not in ATTR_SOURCES:
                err(f"attribute {aname!r} has invalid source {src!r}")
            elif src == "attribute" and "attribute" not in spec:
                err(f"attribute {aname!r} uses source 'attribute' but has no 'attribute' key")
            elif src == "meta":
                warn(f"attribute {aname!r} uses deprecated source 'meta'; use block bindings")
            elif src == "html" and types not in (None, "string"):
                warn(f"attribute {aname!r}: source 'html' should be type 'string'")
        if "enum" in spec and "default" in spec and spec["default"] not in spec["enum"]:
            err(f"attribute {aname!r} default {spec['default']!r} is not in its enum")

    def check_file_ref(field: str, ref: str) -> None:
        if not ref.startswith("file:"):
            return
        rel = ref[5:]
        target = os.path.normpath(os.path.join(base, rel))
        if not os.path.exists(target):
            # @wordpress/scripts maps index.js -> index.js in build; src often uses .js/.tsx.
            stem, ext = os.path.splitext(target)
            alts = [stem + e for e in (".js", ".jsx", ".ts", ".tsx", ".scss", ".css")]
            if ext in (".js", ".css") and any(os.path.exists(a) for a in alts):
                return
            err(f"{field}: {ref} not found (looked for {os.path.relpath(target, base)})")

    for field in ASSET_FIELDS:
        val = data.get(field)
        if val is None:
            continue
        refs = val if isinstance(val, list) else [val]
        for ref in refs:
            if not isinstance(ref, str):
                err(f"{field} entries must be strings")
                continue
            check_file_ref(field, ref)

    if "viewScript" in data and "viewScriptModule" in data:
        warn(
            "both viewScript and viewScriptModule set; the Interactivity API uses viewScriptModule"
        )
    supports = data.get("supports", {})
    if (
        isinstance(supports, dict)
        and supports.get("interactivity")
        and "viewScriptModule" not in data
    ):
        warn("supports.interactivity is set but there is no viewScriptModule")

    render = data.get("render")
    if render is not None:
        if not isinstance(render, str) or not render.startswith("file:"):
            err("render must be 'file:./render.php'")
        else:
            check_file_ref("render", render)
            if not render.endswith(".php"):
                err("render must point to a .php file")
    return issues


def find_block_files(paths: list[str]) -> list[str]:
    found: list[str] = []
    for p in paths:
        if os.path.isfile(p):
            found.append(p)
            continue
        for root, dirs, files in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            if "block.json" in files:
                found.append(os.path.join(root, "block.json"))
    return found


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate_block_json.py",
        description="Validate block.json files: name, required fields, apiVersion, "
        "attributes and file: asset references.",
        epilog="Example: python3 validate_block_json.py src/ --strict",
    )
    p.add_argument("paths", nargs="+", help="block.json files or directories")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    missing = [p for p in args.paths if not os.path.exists(p)]
    if missing:
        print(f"error: path not found: {missing[0]}", file=sys.stderr)
        return 2
    files = find_block_files(args.paths)
    if not files:
        print("error: no block.json found", file=sys.stderr)
        return 2
    issues = [i for f in files for i in check_block(f)]
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    if args.json:
        print(json.dumps({"version": VERSION, "files": files, "issues": issues}, indent=2))
    else:
        for i in issues:
            print(f"{i['file']}: {i['level']}: {i['message']}")
        print(
            f"\n{len(files)} block.json file(s): {len(errors)} error(s), {len(warnings)} warning(s)."
        )
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
