#!/usr/bin/env python3
"""Check a WooCommerce extension for HPOS (High-Performance Order Storage) problems.

With HPOS enabled, orders live in custom tables (wc_orders, wc_orders_meta, ...)
instead of wp_posts/wp_postmeta. Code that reads or writes orders through post
APIs silently breaks. This scanner flags those patterns and checks that the
plugin declares its compatibility with FeaturesUtil::declare_compatibility().

It is a heuristic line scanner: confirm each finding by reading the code.
Suppress a reviewed line with a trailing comment: // hpos-ignore

Exit codes: 0 clean (at --fail-on), 1 findings, 2 usage error.
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
SEVERITIES = ["info", "low", "medium", "high"]
DEFAULT_EXCLUDES = ["vendor", "node_modules", ".git", "build", "dist", "tests"]
ORDER_VAR = r"\$(?:order_id|order|post_id_order|wc_order_id|order->get_id\(\)|order->id)\b"

LINE_RULES = [
    (
        "HPOS001",
        "high",
        re.compile(r"\b(?:get|update|add|delete)_post_meta\s*\(\s*" + ORDER_VAR),
        "Order meta accessed through post meta functions",
        "Use $order = wc_get_order( $id ); $order->get_meta() / update_meta_data() / "
        "delete_meta_data(), then $order->save().",
    ),
    (
        "HPOS002",
        "high",
        re.compile(r"\bget_post\s*\(\s*" + ORDER_VAR),
        "Order loaded with get_post()",
        "Use wc_get_order( $order_id ).",
    ),
    (
        "HPOS003",
        "high",
        re.compile(
            r"['\"]post_type['\"]\s*=>\s*(?:array\s*\(|\[)?\s*['\"]shop_order(?:_refund)?['\"]"
        ),
        "Orders queried with WP_Query/get_posts (post_type shop_order)",
        "Use wc_get_orders( array( ... ) ) or WC_Order_Query.",
    ),
    (
        "HPOS004",
        "high",
        re.compile(r"\$wpdb\b.*shop_order|shop_order.*\$wpdb\b|\bwp_posts\b.*shop_order"),
        "Direct SQL against posts/postmeta for orders",
        "Use wc_get_orders(), or OrderUtil::get_table_for_orders() when SQL is unavoidable.",
    ),
    (
        "HPOS005",
        "medium",
        re.compile(r"\bwp_(?:update|delete|trash|insert)_post\s*\(\s*" + ORDER_VAR),
        "Order changed with wp_*_post()",
        "Use $order->set_*() + $order->save(), $order->delete() or wc_create_order().",
    ),
    (
        "HPOS006",
        "medium",
        re.compile(r"\bget_post_(?:type|status)\s*\(\s*" + ORDER_VAR),
        "Order type/status read through post functions",
        "Use OrderUtil::get_order_type( $id ) / $order->get_status().",
    ),
    (
        "HPOS007",
        "medium",
        re.compile(
            r"['\"](?:save_post_shop_order|wp_insert_post_shop_order|"
            r"woocommerce_process_shop_order_meta_legacy)['\"]"
        ),
        "Post lifecycle hook used for orders",
        "Use woocommerce_new_order, woocommerce_update_order or "
        "woocommerce_process_shop_order_meta.",
    ),
    (
        "HPOS008",
        "medium",
        re.compile(r"\badd_meta_box\s*\([^;]*['\"]shop_order['\"]"),
        "Meta box registered only for the legacy shop_order screen",
        "Use wc_get_page_screen_id( 'shop-order' ) as the screen so it works on both.",
    ),
    (
        "HPOS009",
        "low",
        re.compile(r"\bmetadata_exists\s*\(\s*['\"]post['\"]\s*,\s*" + ORDER_VAR),
        "metadata_exists('post', ...) used on an order",
        "Use $order->meta_exists( $key ).",
    ),
]

# HPOS011: SQL that reads order meta from postmeta, possibly spread over several lines.
POSTMETA_SQL = re.compile(r"\$wpdb->postmeta\b|\bwp_postmeta\b")
ORDER_META_HINT = re.compile(
    r"shop_order|\$order_id\b|['\"](?:_billing_|_shipping_|_order_|_customer_user|_payment_method|"
    r"_transaction_id|_paid_date|_date_paid|_date_completed|_cart_hash)"
)
SQL_RULE = (
    "HPOS011",
    "high",
    "SQL reads or joins postmeta for order meta",
    "With HPOS, order meta lives in wc_orders_meta: use wc_get_orders( array( 'meta_query' "
    "=> ... ) ), $order->get_meta(), or OrderUtil::get_table_for_order_meta() when SQL is "
    "unavoidable.",
)


def statements(code: str):
    """Yield (start offset, text) for each PHP statement (split on ';' outside strings).

    ``code`` must already have comments stripped. Semicolons inside string literals
    (common in SQL) do not end a statement.
    """
    start, state, i, n = 0, None, 0, len(code)
    while i < n:
        c = code[i]
        if state is None:
            if c in ("'", '"'):
                state = c
            elif c == ";":
                yield start, code[start : i + 1]
                start = i + 1
        elif c == "\\":
            i += 1
        elif c == state:
            state = None
        i += 1
    if start < n:
        yield start, code[start:]


LEGACY_LIST_HOOKS = re.compile(
    r"['\"](?:manage_edit-shop_order_columns|manage_shop_order_posts_custom_column|"
    r"bulk_actions-edit-shop_order|handle_bulk_actions-edit-shop_order)['\"]"
)
HPOS_LIST_HOOKS = re.compile(
    r"['\"](?:manage_woocommerce_page_wc-orders_columns|"
    r"manage_woocommerce_page_wc-orders_custom_column|"
    r"bulk_actions-woocommerce_page_wc-orders|"
    r"handle_bulk_actions-woocommerce_page_wc-orders)['\"]"
)
DECLARE = re.compile(
    r"declare_compatibility\s*\(\s*['\"](custom_order_tables|cart_checkout_blocks)['\"]"
    r"\s*,[^;]*?(?:,\s*(true|false)\s*)?\)",
    re.S,
)


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
    """Blank out PHP comments, keeping strings, offsets and newlines."""
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
            else:
                out.append(" ")
        else:
            if c == "*" and nxt == "/":
                state = None
                out.append("  ")
                i += 1
            else:
                out.append("\n" if c == "\n" else " ")
        i += 1
    return "".join(out)


def scan_file_text(src: str, path: str) -> tuple[list[Finding], dict]:
    code = strip_comments(src)
    raw_lines = src.splitlines()
    findings: list[Finding] = []
    for idx, line in enumerate(code.splitlines(), start=1):
        raw = raw_lines[idx - 1] if idx <= len(raw_lines) else ""
        if "hpos-ignore" in raw:
            continue
        for rid, sev, rx, msg, fix in LINE_RULES:
            if rx.search(line):
                findings.append(Finding(rid, sev, msg, path, idx, raw.strip()[:200], fix))
    flagged = {f.line for f in findings if f.rule == "HPOS004"}
    for offset, stmt in statements(code):
        match = POSTMETA_SQL.search(stmt)
        if not match or not ORDER_META_HINT.search(stmt):
            continue
        idx = code.count("\n", 0, offset + match.start()) + 1
        raw = raw_lines[idx - 1] if idx <= len(raw_lines) else ""
        if idx in flagged or "hpos-ignore" in raw:
            continue
        rid, sev, msg, fix = SQL_RULE
        findings.append(Finding(rid, sev, msg, path, idx, raw.strip()[:200], fix))
    facts = {"declarations": {}, "legacy_list_hooks": [], "hpos_list_hooks": False}
    for m in DECLARE.finditer(code):
        flag = m.group(2) or "true"
        facts["declarations"][m.group(1)] = flag == "true"
    for m in LEGACY_LIST_HOOKS.finditer(code):
        lineno = code.count("\n", 0, m.start()) + 1
        facts["legacy_list_hooks"].append((lineno, raw_lines[lineno - 1].strip()[:200]))
    facts["hpos_list_hooks"] = bool(HPOS_LIST_HOOKS.search(code))
    return findings, facts


def iter_php_files(root: str, excludes: list[str]):
    if os.path.isfile(root):
        yield root
        return
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not any(fnmatch.fnmatch(d, p) for p in excludes))
        for name in sorted(files):
            if name.endswith(".php"):
                yield os.path.join(base, name)


def scan(root: str, excludes: list[str]) -> dict:
    findings: list[Finding] = []
    declarations: dict[str, bool] = {}
    legacy: list[tuple[str, int, str]] = []
    has_hpos_hooks = False
    files = 0
    for path in iter_php_files(root, excludes):
        files += 1
        with open(path, encoding="utf-8", errors="replace") as fh:
            f, facts = scan_file_text(fh.read(), path)
        findings.extend(f)
        declarations.update(facts["declarations"])
        legacy.extend((path, ln, snip) for ln, snip in facts["legacy_list_hooks"])
        has_hpos_hooks = has_hpos_hooks or facts["hpos_list_hooks"]

    if legacy and not has_hpos_hooks:
        for path, ln, snip in legacy:
            findings.append(
                Finding(
                    "HPOS010",
                    "medium",
                    "Order list customised only for the legacy posts screen",
                    path,
                    ln,
                    snip,
                    "Also hook manage_woocommerce_page_wc-orders_columns / "
                    "manage_woocommerce_page_wc-orders_custom_column (and bulk_actions-"
                    "woocommerce_page_wc-orders).",
                )
            )
    if "custom_order_tables" not in declarations:
        findings.append(
            Finding(
                "HPOS100",
                "high",
                "No HPOS compatibility declaration found",
                root,
                0,
                "",
                "On before_woocommerce_init call \\Automattic\\WooCommerce\\Utilities\\"
                "FeaturesUtil::declare_compatibility( 'custom_order_tables', __FILE__, true ).",
            )
        )
    elif declarations["custom_order_tables"] is False:
        findings.append(
            Finding(
                "HPOS101",
                "info",
                "Plugin declares itself INCOMPATIBLE with HPOS",
                root,
                0,
                "",
                "Fix the findings above, then declare compatibility with true.",
            )
        )
    if "cart_checkout_blocks" not in declarations:
        findings.append(
            Finding(
                "HPOS102",
                "low",
                "No Cart/Checkout blocks compatibility declaration",
                root,
                0,
                "",
                "If the plugin touches cart or checkout, test with the blocks and declare "
                "'cart_checkout_blocks'.",
            )
        )
    findings.sort(key=lambda x: (x.file, x.line, x.rule))
    return {"files_scanned": files, "declarations": declarations, "findings": findings}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hpos_check.py",
        description="Flag WooCommerce code that breaks with HPOS (custom order tables) and "
        "check the compatibility declarations.",
        epilog="Example: python3 hpos_check.py wp-content/plugins/my-extension --json",
    )
    p.add_argument("path", help="plugin directory (or a single PHP file)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium")
    p.add_argument("--exclude", action="append", default=[], help="dir glob to skip")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not os.path.exists(args.path):
        print(f"error: path not found: {args.path}", file=sys.stderr)
        return 2
    result = scan(args.path, DEFAULT_EXCLUDES + args.exclude)
    findings = result["findings"]
    rank = SEVERITIES.index(args.fail_on)
    failing = [f for f in findings if SEVERITIES.index(f.severity) >= rank]
    if args.json:
        print(
            json.dumps(
                {
                    "version": VERSION,
                    "files_scanned": result["files_scanned"],
                    "declarations": result["declarations"],
                    "findings": [asdict(f) for f in findings],
                },
                indent=2,
            )
        )
    else:
        for f in findings:
            loc = f"{f.file}:{f.line}" if f.line else f.file
            print(f"{loc}: [{f.severity.upper()}] {f.rule} {f.message}")
            if f.snippet:
                print(f"    {f.snippet}")
            print(f"    fix: {f.fix}")
        decl = ", ".join(f"{k}={v}" for k, v in result["declarations"].items()) or "none"
        print(
            f"\nScanned {result['files_scanned']} PHP file(s); declarations: {decl}; "
            f"{len(findings)} finding(s)."
        )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
