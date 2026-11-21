#!/usr/bin/env python3
"""Flag risky security patterns in WordPress PHP code.

A fast, dependency-free first pass for code review. It looks for the classic
WordPress vulnerability shapes: unescaped output, unsanitized input, SQL built
without $wpdb->prepare(), AJAX/admin-post handlers without nonce or capability
checks, REST routes without a permission_callback, and dangerous PHP functions.

It is a heuristic line scanner, not a PHP parser. Treat every finding as
"look here", confirm it by reading the code, and run PHPCS with the
WordPress-Extra standard for full coverage.

Suppress a reviewed line with a trailing comment:
    // wpsec-ignore                (all rules on this line)
    // wpsec-ignore: WPS002,WPS012 (only these rules)

Exit codes: 0 no findings at or above --fail-on, 1 findings, 2 usage error.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import asdict, dataclass

VERSION = "0.1.0"
SEVERITIES = ["info", "low", "medium", "high", "critical"]
DEFAULT_EXCLUDES = ["vendor", "node_modules", ".git", "build", "dist"]

SUPERGLOBAL = r"\$_(?:GET|POST|REQUEST|COOKIE|SERVER|FILES)\b"
SANITIZERS = re.compile(
    r"\b(?:sanitize_\w+|absint|intval|floatval|boolval|wp_kses\w*|esc_\w+|"
    r"filter_input|filter_var|is_numeric|ctype_\w+|in_array|array_key_exists|"
    r"wp_verify_nonce|check_admin_referer|check_ajax_referer|isset|empty|"
    r"wp_validate_redirect|rest_sanitize_\w+|map_deep|count|array_map)\s*\(|\(\s*(?:int|float|bool)\s*\)"
)
ESCAPERS = re.compile(
    r"\b(?:esc_\w+|wp_kses\w*|absint|intval|floatval|number_format_i18n|"
    r"wp_json_encode|json_encode|sanitize_\w+|selected|checked|disabled)\s*\("
    r"|\(\s*(?:int|float)\s*\)"
)

RULES = {
    "WPS001": ("high", "Superglobal echoed without escaping (XSS)"),
    "WPS002": ("high", "SQL query built with variables and no $wpdb->prepare()"),
    "WPS003": ("critical", "Request data concatenated into SQL (SQL injection)"),
    "WPS004": ("critical", "Code execution function (eval/assert/create_function)"),
    "WPS005": ("high", "unserialize() on request data (object injection)"),
    "WPS006": ("high", "Shell command execution"),
    "WPS007": ("critical", "include/require path built from request data"),
    "WPS008": ("high", "extract() on request data"),
    "WPS009": ("high", "REST route without permission_callback"),
    "WPS010": ("info", "REST route is public (permission_callback __return_true)"),
    "WPS011": ("high", "AJAX/admin-post handler file has no nonce check"),
    "WPS012": ("medium", "Request data used without sanitization"),
    "WPS013": ("low", "Variable echoed without an escaping function"),
    "WPS014": ("medium", "Redirect to request data without wp_safe_redirect()"),
    "WPS015": ("high", "Filesystem function called with request data (path traversal)"),
    "WPS016": ("low", "Quoted placeholder in $wpdb->prepare() ('%s' should be %s)"),
    "WPS017": ("medium", "Privileged AJAX/admin-post handler file has no capability check"),
    "WPS018": ("medium", "Dynamic SQL clause (ORDER BY/LIMIT) from variable; whitelist it"),
}

FIXES = {
    "WPS001": "Escape late: esc_html(), esc_attr(), esc_url() or wp_kses_post() on output.",
    "WPS002": "Use $wpdb->prepare( 'SELECT ... WHERE id = %d', $id ).",
    "WPS003": "Never concatenate request data into SQL; use $wpdb->prepare() with placeholders.",
    "WPS004": "Remove dynamic code execution; use callbacks or a whitelist.",
    "WPS005": "Use json_decode() for untrusted data, or maybe_unserialize() only on trusted data.",
    "WPS006": "Avoid shelling out; if unavoidable use escapeshellarg() on every argument.",
    "WPS007": "Map request values to a fixed whitelist of files; never build include paths.",
    "WPS008": "Read the specific keys you need and sanitize each one.",
    "WPS009": "Add 'permission_callback' => fn() => current_user_can( 'edit_posts' ).",
    "WPS010": "Fine for truly public read-only endpoints; confirm no private data is returned.",
    "WPS011": "Call check_ajax_referer() / check_admin_referer() at the start of the handler.",
    "WPS012": "Wrap with wp_unslash() then sanitize_text_field()/absint()/sanitize_key() etc.",
    "WPS013": "Escape late even for 'trusted' values: echo esc_html( $value );",
    "WPS014": "Use wp_safe_redirect( wp_validate_redirect( $url, admin_url() ) ); exit;",
    "WPS015": "Validate with validate_file() / realpath() against an allowed base directory.",
    "WPS016": "prepare() quotes %s itself; remove the quotes around the placeholder.",
    "WPS017": "Check current_user_can( 'manage_options' ) (or a narrower cap) in the handler.",
    "WPS018": "Whitelist column names and directions: in_array( $orderby, $allowed, true ).",
}

DB_CALL = re.compile(r"\$wpdb\s*->\s*(query|get_results|get_row|get_var|get_col)\s*\(")
ECHO = re.compile(r"(?:\becho\b|\bprint\b|<\?=)")
IGNORE = re.compile(r"wpsec-ignore(?::\s*([A-Z0-9_,\s]+))?")
# A `phpcs:ignore` naming the matching WPCS sniff counts as a reviewed suppression.
PHPCS_SNIFFS = {
    "WPS001": "EscapeOutput",
    "WPS013": "EscapeOutput",
    "WPS002": "PreparedSQL",
    "WPS018": "PreparedSQL",
    "WPS012": "ValidatedSanitizedInput",
}
OPTIONS = {"respect_phpcs": True}


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    file: str
    line: int
    snippet: str
    fix: str


def strip_comments(src: str) -> str:
    """Blank out PHP comments while keeping strings, offsets and newlines."""
    out = []
    i, n = 0, len(src)
    state = None  # None, "'", '"', "line", "block"
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state is None:
            if c in ("'", '"'):
                state = c
                out.append(c)
            elif c == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 1
            elif c == "#" and nxt != "[":
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
            if c == "\\":
                out.append(nxt)
                i += 1
            elif c == state:
                state = None
        elif state == "line":
            if c == "\n":
                state = None
                out.append("\n")
            elif c == "?" and nxt == ">":
                state = None
                out.append(c)
            else:
                out.append(" ")
        elif state == "block":
            if c == "*" and nxt == "/":
                state = None
                out.append("  ")
                i += 1
            else:
                out.append("\n" if c == "\n" else " ")
        i += 1
    return "".join(out)


def balanced_call(text: str, start: int) -> str:
    """Return text from the '(' at or after start up to its matching ')'."""
    open_idx = text.find("(", start)
    if open_idx == -1:
        return ""
    depth = 0
    quote = None
    for j in range(open_idx, min(len(text), open_idx + 20000)):
        ch = text[j]
        if quote:
            if ch == "\\":
                continue
            if ch == quote and text[j - 1] != "\\":
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx : j + 1]
    return text[open_idx:]


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def ignored(raw_line: str, rule: str) -> bool:
    sniff = PHPCS_SNIFFS.get(rule)
    if OPTIONS["respect_phpcs"] and sniff and "phpcs:ignore" in raw_line and sniff in raw_line:
        return True
    m = IGNORE.search(raw_line)
    if not m:
        return False
    if not m.group(1):
        return True
    wanted = {r.strip() for r in m.group(1).split(",") if r.strip()}
    return rule in wanted


def scan_text(src: str, path: str = "<string>") -> list[Finding]:
    code = strip_comments(src)
    raw_lines = src.splitlines()
    lines = code.splitlines()
    findings: list[Finding] = []

    def add(rule: str, lineno: int) -> None:
        raw = raw_lines[lineno - 1] if 0 < lineno <= len(raw_lines) else ""
        if ignored(raw, rule):
            return
        sev, msg = RULES[rule]
        key = (rule, lineno)
        if any((f.rule, f.line) == key for f in findings):
            return
        findings.append(Finding(rule, sev, msg, path, lineno, raw.strip()[:200], FIXES[rule]))

    for idx, line in enumerate(lines, start=1):
        has_sg = re.search(SUPERGLOBAL, line) is not None
        if ECHO.search(line):
            if has_sg and not ESCAPERS.search(line):
                add("WPS001", idx)
            elif re.search(r"(?:\becho\b|\bprint\b|<\?=)\s*\$\w+", line) and not ESCAPERS.search(
                line
            ):
                add("WPS013", idx)
        if re.search(r"\b(?:eval|create_function)\s*\(|\bassert\s*\(\s*\$", line):
            add("WPS004", idx)
        if re.search(r"preg_replace\s*\(\s*['\"](.).*\1[a-zA-Z]*e[a-zA-Z]*['\"]", line):
            add("WPS004", idx)
        if re.search(r"\bunserialize\s*\([^;]*" + SUPERGLOBAL, line):
            add("WPS005", idx)
        if re.search(r"(?<![\w>:$])(?:exec|shell_exec|system|passthru|proc_open|popen)\s*\(", line):
            add("WPS006", idx)
        if re.search(r"\b(?:include|require)(?:_once)?\b[^;]*" + SUPERGLOBAL, line):
            add("WPS007", idx)
        if re.search(r"\bextract\s*\(\s*" + SUPERGLOBAL, line):
            add("WPS008", idx)
        if re.search(r"\bwp_redirect\s*\([^;]*" + SUPERGLOBAL, line):
            add("WPS014", idx)
        if re.search(
            r"\b(?:file_get_contents|fopen|readfile|unlink|file_put_contents|copy|rename|"
            r"opendir|scandir|file)\s*\([^;]*" + SUPERGLOBAL,
            line,
        ) and not re.search(r"\$_FILES\s*\[[^\]]+\]\s*\[\s*['\"]tmp_name['\"]\s*\]", line):
            add("WPS015", idx)
        if re.search(r"->\s*prepare\s*\([^;]*'%[sdf]'", line):
            add("WPS016", idx)
        if has_sg and not SANITIZERS.search(line) and not ECHO.search(line):
            if re.search(r"=\s*" + SUPERGLOBAL + r"\s*\[", line) or re.search(
                r"\(\s*" + SUPERGLOBAL + r"\s*\[", line
            ):
                add("WPS012", idx)

    for m in DB_CALL.finditer(code):
        call = balanced_call(code, m.end() - 1)
        lineno = line_of(code, m.start())
        inner = call[1:-1] if call.endswith(")") else call[1:]
        if re.match(r"\s*\$wpdb\s*->\s*prepare\s*\(", inner):
            continue
        if re.search(SUPERGLOBAL, inner):
            add("WPS003", lineno)
            continue
        single = re.fullmatch(r"\s*\$(\w+)\s*", inner)
        if single and re.search(
            r"\$" + single.group(1) + r"\s*=\s*\$wpdb\s*->\s*prepare\s*\(", code
        ):
            continue  # $sql = $wpdb->prepare( ... ); $wpdb->query( $sql );
        cleaned = re.sub(r"\$wpdb\s*->\s*\w+|\{\$wpdb->\w+\}", "", inner)
        if re.search(r"\$\w+", cleaned):
            if re.search(r"\b(?:ORDER\s+BY|LIMIT)\b[^;]*\$\w+", cleaned, re.I):
                add("WPS018", lineno)
            else:
                add("WPS002", lineno)

    for m in re.finditer(r"\bregister_rest_route\s*\(", code):
        call = balanced_call(code, m.end() - 1)
        lineno = line_of(code, m.start())
        if "permission_callback" not in call:
            add("WPS009", lineno)
        elif re.search(r"permission_callback['\"]\s*=>\s*['\"]__return_true['\"]", call):
            add("WPS010", lineno)

    handlers = list(re.finditer(r"add_action\s*\(\s*['\"](wp_ajax_|admin_post_)(nopriv_)?", code))
    if handlers:
        has_nonce = re.search(
            r"\b(?:check_ajax_referer|wp_verify_nonce|check_admin_referer)\s*\(", code
        )
        has_cap = re.search(r"\bcurrent_user_can\s*\(", code)
        for h in handlers:
            lineno = line_of(code, h.start())
            if not has_nonce:
                add("WPS011", lineno)
            if not h.group(2) and not has_cap:
                add("WPS017", lineno)

    # WPS012 is noise when a more specific rule already explains the same line.
    specific = {f.line for f in findings if f.rule not in ("WPS012", "WPS013")}
    findings = [f for f in findings if not (f.rule == "WPS012" and f.line in specific)]
    findings.sort(key=lambda f: (f.line, f.rule))
    return findings


def iter_php_files(paths: list[str], excludes: list[str]):
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for root, dirs, files in os.walk(p):
            dirs[:] = sorted(
                d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in excludes)
            )
            for name in sorted(files):
                full = os.path.join(root, name)
                if not name.endswith(".php"):
                    continue
                rel = os.path.relpath(full, p)
                if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
                    continue
                yield full


def to_sarif(findings: list[Finding]) -> dict:
    level = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "wp-security-scan",
                        "version": VERSION,
                        "rules": [
                            {
                                "id": rid,
                                "shortDescription": {"text": msg},
                                "help": {"text": FIXES[rid]},
                            }
                            for rid, (_, msg) in RULES.items()
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": f.rule,
                        "level": level.get(f.severity, "note"),
                        "message": {"text": f"{f.message}. {f.fix}"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": f.file.replace(os.sep, "/")},
                                    "region": {"startLine": f.line},
                                }
                            }
                        ],
                    }
                    for f in findings
                ],
            }
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wp_security_scan.py",
        description="Flag risky security patterns (XSS, SQLi, CSRF, missing capability "
        "checks, dangerous functions) in WordPress PHP files.",
        epilog="Example: python3 wp_security_scan.py wp-content/plugins/my-plugin --fail-on high",
    )
    p.add_argument("paths", nargs="+", help="PHP files or directories to scan")
    p.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    p.add_argument("--json", action="store_true", help="shortcut for --format json")
    p.add_argument(
        "--fail-on",
        choices=SEVERITIES,
        default="medium",
        help="exit 1 when a finding has at least this severity (default: medium)",
    )
    p.add_argument(
        "--min-severity", choices=SEVERITIES, default="low", help="hide findings below this"
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="glob of dirs/files to skip (repeatable); vendor, node_modules, .git, build, "
        "dist are always skipped",
    )
    p.add_argument(
        "--no-phpcs-ignore",
        action="store_true",
        help="also report lines suppressed with a matching phpcs:ignore comment",
    )
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fmt = "json" if args.json else args.format
    OPTIONS["respect_phpcs"] = not args.no_phpcs_ignore
    for p in args.paths:
        if not os.path.exists(p):
            print(f"error: path not found: {p}", file=sys.stderr)
            return 2
    excludes = DEFAULT_EXCLUDES + args.exclude
    min_rank = SEVERITIES.index(args.min_severity)
    findings: list[Finding] = []
    scanned = 0
    for path in iter_php_files(args.paths, excludes):
        scanned += 1
        with open(path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        findings.extend(f for f in scan_text(src, path) if SEVERITIES.index(f.severity) >= min_rank)

    fail_rank = SEVERITIES.index(args.fail_on)
    failing = [f for f in findings if SEVERITIES.index(f.severity) >= fail_rank]
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}

    if fmt == "json":
        print(
            json.dumps(
                {
                    "version": VERSION,
                    "files_scanned": scanned,
                    "counts": counts,
                    "findings": [asdict(f) for f in findings],
                },
                indent=2,
            )
        )
    elif fmt == "sarif":
        print(json.dumps(to_sarif(findings), indent=2))
    else:
        for f in findings:
            print(f"{f.file}:{f.line}: [{f.severity.upper()}] {f.rule} {f.message}")
            print(f"    {f.snippet}")
            print(f"    fix: {f.fix}")
        summary = ", ".join(f"{counts[s]} {s}" for s in reversed(SEVERITIES) if counts[s])
        print(f"\nScanned {scanned} PHP file(s): {summary or 'no findings'}.")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
