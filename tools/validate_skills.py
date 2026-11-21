#!/usr/bin/env python3
"""Validate every skill in this repository and the plugin marketplace files.

Checks, per skills/<name>/SKILL.md:
  - YAML frontmatter with only known keys (name, description, license,
    compatibility, metadata, allowed-tools)
  - name: 1-64 chars, lowercase a-z/0-9 and single hyphens, equal to the folder name
  - description: 1-1024 chars and says when to use the skill ("Use when ...")
  - compatibility: at most 500 chars
  - body has "## When to use" and "## Workflow" sections and stays under the line limit
  - every relative link and every scripts/ or references/ path mentioned exists
  - every script in scripts/ is referenced by a test file in tests/
Repository level:
  - .claude-plugin/marketplace.json: name, owner.name, plugins[] with name + source,
    relative sources inside the repo, metadata.skills listing exactly the skill folders
  - .claude-plugin/plugin.json: name equal to the marketplace entry, version present in
    CHANGELOG.md
  - README.md mentions every skill

Stdlib only. Exit codes: 0 valid, 1 problems found, 2 repository not found.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
REQUIRED_SECTIONS = ["## When to use", "## Workflow"]
MAX_BODY_LINES = 400
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
PATH_RE = re.compile(r"(?<![\w/.-])((?:scripts|references)/[\w./-]+\.\w+)")
RESERVED_PLUGIN = re.compile(r"^(?:claude|anthropic|anthropics|cc-plugin)(?:-|$)")


def parse_frontmatter(text: str) -> tuple[dict, str, list[str]]:
    """Parse the small YAML subset used in SKILL.md frontmatter."""
    errors: list[str] = []
    if not text.startswith("---\n"):
        return {}, text, ["SKILL.md must start with '---' frontmatter"]
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text, ["frontmatter is not closed with '---'"]
    block = text[4:end]
    body = text[end + 5 :]
    data: dict = {}
    current_map: str | None = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")):
            if current_map is None:
                errors.append(f"unexpected indented line in frontmatter: {raw.strip()!r}")
                continue
            m = re.match(r"^\s+([\w.-]+):\s*(.*)$", raw)
            if not m:
                errors.append(f"cannot parse frontmatter line: {raw.strip()!r}")
                continue
            data[current_map][m.group(1)] = _scalar(m.group(2))
            continue
        m = re.match(r"^([\w-]+):\s*(.*)$", raw)
        if not m:
            errors.append(f"cannot parse frontmatter line: {raw!r}")
            continue
        key, val = m.group(1), m.group(2)
        if key in data:
            errors.append(f"duplicate frontmatter key {key!r}")
        if val == "":
            data[key] = {}
            current_map = key
        else:
            data[key] = _scalar(val)
            current_map = None
    return data, body, errors


def _scalar(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    return val


def check_skill(skill_dir: str, tests_text: str) -> list[str]:
    problems: list[str] = []
    folder = os.path.basename(skill_dir.rstrip("/"))
    path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(path):
        return [f"{folder}: SKILL.md missing"]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    fm, body, errs = parse_frontmatter(text)
    problems += [f"{folder}: {e}" for e in errs]

    for key in fm:
        if key not in ALLOWED_KEYS:
            problems.append(f"{folder}: unknown frontmatter key {key!r}")
    name = fm.get("name")
    if not isinstance(name, str) or not name:
        problems.append(f"{folder}: frontmatter 'name' is required")
    else:
        if len(name) > 64:
            problems.append(f"{folder}: name longer than 64 characters")
        if not NAME_RE.match(name):
            problems.append(
                f"{folder}: name {name!r} must be lowercase letters, digits, single hyphens"
            )
        if name != folder:
            problems.append(f"{folder}: name {name!r} does not match folder name")
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        problems.append(f"{folder}: frontmatter 'description' is required")
    else:
        if len(desc) > 1024:
            problems.append(f"{folder}: description is {len(desc)} chars (max 1024)")
        if not re.search(r"\buse (?:it )?when\b", desc, re.I):
            problems.append(f"{folder}: description should say when to use it ('Use when ...')")
    comp = fm.get("compatibility")
    if isinstance(comp, str) and len(comp) > 500:
        problems.append(f"{folder}: compatibility longer than 500 characters")
    if "metadata" in fm and not isinstance(fm["metadata"], dict):
        problems.append(f"{folder}: metadata must be a mapping")

    for section in REQUIRED_SECTIONS:
        if not re.search(r"^" + re.escape(section) + r"\b", body, re.M):
            problems.append(f"{folder}: missing section '{section}'")
    lines = body.count("\n") + 1
    if lines > MAX_BODY_LINES:
        problems.append(
            f"{folder}: SKILL.md body is {lines} lines (max {MAX_BODY_LINES}); move detail to references/"
        )

    refs = set()
    prose = re.sub(r"```.*?```", "", body, flags=re.S)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    for target in LINK_RE.findall(prose):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        refs.add(target.split("#", 1)[0])
    refs.update(PATH_RE.findall(body))
    for ref in sorted(refs):
        if not ref:
            continue
        full = os.path.normpath(os.path.join(skill_dir, ref))
        if not full.startswith(os.path.normpath(skill_dir)):
            problems.append(f"{folder}: reference {ref!r} points outside the skill folder")
        elif not os.path.exists(full):
            problems.append(f"{folder}: referenced file {ref!r} does not exist")

    scripts_dir = os.path.join(skill_dir, "scripts")
    if os.path.isdir(scripts_dir):
        for script in sorted(os.listdir(scripts_dir)):
            if script.startswith(".") or script == "__pycache__":
                continue
            if script not in tests_text:
                problems.append(f"{folder}: scripts/{script} has no test in tests/")
    return problems


def check_repo(root: str) -> list[str]:
    problems: list[str] = []
    skills_root = os.path.join(root, "skills")
    if not os.path.isdir(skills_root):
        return [f"no skills/ directory in {root}"]
    skills = sorted(
        d
        for d in os.listdir(skills_root)
        if os.path.isdir(os.path.join(skills_root, d)) and not d.startswith(".")
    )
    if not skills:
        problems.append("skills/ is empty")

    tests_text = ""
    tests_dir = os.path.join(root, "tests")
    if os.path.isdir(tests_dir):
        for base, _dirs, files in os.walk(tests_dir):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(base, f), encoding="utf-8") as fh:
                        tests_text += fh.read()
    for s in skills:
        problems += check_skill(os.path.join(skills_root, s), tests_text)

    mp_path = os.path.join(root, ".claude-plugin", "marketplace.json")
    try:
        with open(mp_path, encoding="utf-8") as fh:
            mp = json.load(fh)
    except FileNotFoundError:
        return problems + [".claude-plugin/marketplace.json missing"]
    except json.JSONDecodeError as exc:
        return problems + [f"marketplace.json is not valid JSON: {exc}"]

    if not isinstance(mp.get("name"), str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*", mp.get("name", "")
    ):
        problems.append("marketplace.json: name must be letters, digits, '.', '_' or '-'")
    if not isinstance(mp.get("owner"), dict) or not mp["owner"].get("name"):
        problems.append("marketplace.json: owner.name is required")
    plugins = mp.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        problems.append("marketplace.json: plugins must be a non-empty array")
        plugins = []
    listed: set[str] = set()
    names = [p.get("name") for p in plugins if isinstance(p, dict)]
    if len(names) != len(set(names)):
        problems.append("marketplace.json: duplicate plugin names")
    for i, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            problems.append(f"marketplace.json: plugins[{i}] must be an object")
            continue
        pname, source = entry.get("name"), entry.get("source")
        if not pname or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(pname)):
            problems.append(f"marketplace.json: plugins[{i}].name invalid")
        elif RESERVED_PLUGIN.match(str(pname).lower()):
            problems.append(f"marketplace.json: plugin name {pname!r} is reserved")
        if not source:
            problems.append(f"marketplace.json: plugins[{i}].source is required")
            continue
        meta_skills = entry.get("metadata", {}).get("skills", [])
        listed.update(meta_skills)
        if isinstance(source, str):
            if not (source == "." or source.startswith("./")) or ".." in source:
                problems.append(
                    f"marketplace.json: plugins[{i}].source must start with './' and not contain '..'"
                )
                continue
            pdir = os.path.normpath(os.path.join(root, source))
            if not os.path.isdir(pdir):
                problems.append(f"marketplace.json: plugins[{i}].source {source!r} does not exist")
                continue
            pj_path = os.path.join(pdir, ".claude-plugin", "plugin.json")
            if os.path.isfile(pj_path):
                try:
                    with open(pj_path, encoding="utf-8") as fh:
                        pj = json.load(fh)
                except json.JSONDecodeError as exc:
                    problems.append(f"plugin.json is not valid JSON: {exc}")
                    continue
                if pj.get("name") != pname:
                    problems.append(
                        f"plugin.json name {pj.get('name')!r} != marketplace entry {pname!r}"
                    )
                version = pj.get("version")
                changelog = os.path.join(root, "CHANGELOG.md")
                if version and os.path.isfile(changelog):
                    with open(changelog, encoding="utf-8") as fh:
                        if f"[{version}]" not in fh.read():
                            problems.append(
                                f"CHANGELOG.md has no [{version}] entry for plugin.json version"
                            )
    missing = sorted(set(skills) - listed)
    extra = sorted(listed - set(skills))
    if missing:
        problems.append(f"marketplace.json metadata.skills is missing: {', '.join(missing)}")
    if extra:
        problems.append(
            f"marketplace.json metadata.skills lists unknown skills: {', '.join(extra)}"
        )

    readme = os.path.join(root, "README.md")
    if os.path.isfile(readme):
        with open(readme, encoding="utf-8") as fh:
            rtext = fh.read()
        for s in skills:
            if s not in rtext:
                problems.append(f"README.md does not mention skill {s}")
    else:
        problems.append("README.md missing")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="validate_skills.py",
        description="Validate SKILL.md files, marketplace.json and plugin.json in this repository.",
    )
    p.add_argument("root", nargs="?", default=os.path.join(os.path.dirname(__file__), ".."))
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    problems = check_repo(root)
    if args.json:
        print(json.dumps({"root": root, "ok": not problems, "problems": problems}, indent=2))
    elif problems:
        for prob in problems:
            print(f"FAIL {prob}")
        print(f"\n{len(problems)} problem(s).")
    else:
        count = len([d for d in os.listdir(os.path.join(root, "skills")) if not d.startswith(".")])
        print(f"OK: {count} skills, marketplace and plugin manifests valid.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
