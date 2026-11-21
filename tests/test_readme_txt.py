import json

from conftest import load_script, run_script

SKILL, SCRIPT = "wp-readme-txt", "readme_txt.py"
rt = load_script(SKILL, SCRIPT)

PLUGIN = """<?php
/**
 * Plugin Name:       Acme Reviews
 * Description:       Collect and show product reviews with schema markup.
 * Version:           1.2.0
 * Requires at least: 6.5
 * Requires PHP:      7.4
 * License:           GPL-2.0-or-later
 */
"""

GOOD = """=== Acme Reviews ===
Contributors: acme, jane-doe
Tags: reviews, schema, ratings
Requires at least: 6.5
Tested up to: 6.8
Requires PHP: 7.4
Stable tag: 1.2.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Collect and show product reviews with schema markup.

== Description ==

Long description.

== Changelog ==

= 1.2.0 =
* Added things.

== Upgrade Notice ==

= 1.2.0 =
Short notice.
"""


def messages(issues, level=None):
    return [i["message"] for i in issues if level is None or i["level"] == level]


def test_good_readme_valid():
    plugin = None
    assert rt.validate(GOOD, plugin) == []


def test_plugin_headers(tmp_path):
    p = tmp_path / "acme.php"
    p.write_text(PLUGIN)
    h = rt.plugin_headers(str(p))
    assert h["name"] == "Acme Reviews" and h["version"] == "1.2.0" and h["requires_php"] == "7.4"
    assert rt.validate(GOOD, h) == []


def test_version_mismatch_is_error(tmp_path):
    p = tmp_path / "acme.php"
    p.write_text(PLUGIN.replace("1.2.0", "1.3.0"))
    issues = rt.validate(GOOD, rt.plugin_headers(str(p)))
    assert any("Stable tag 1.2.0 != plugin Version 1.3.0" in m for m in messages(issues, "error"))


def test_common_mistakes():
    bad = (
        GOOD.replace("Contributors: acme, jane-doe", "Contributors: Jane Doe")
        .replace("Tags: reviews, schema, ratings", "Tags: a, b, c, d, e, f")
        .replace("Tested up to: 6.8", "Tested up to: WP 6.8")
        .replace("Stable tag: 1.2.0", "Stable tag: trunk")
        .replace(
            "Collect and show product reviews with schema markup.\n\n== Desc",
            "x" * 151 + "\n\n== Desc",
        )
    )
    issues = rt.validate(bad)
    errs = " | ".join(messages(issues, "error"))
    warns = " | ".join(messages(issues, "warning"))
    assert "not a WordPress.org username" in errs
    assert "must be a WordPress version number" in errs
    assert "151 characters" in errs
    assert "only the first 5 are used" in warns
    assert "'trunk' is discouraged" in warns


def test_missing_parts():
    issues = rt.validate("Contributors: a\n\nshort\n")
    errs = " ".join(messages(issues, "error"))
    assert "=== Plugin Name ===" in errs
    assert "'Tested up to:' header is required" in errs
    assert "Description" in errs


def test_tested_up_to_against_latest_and_minor():
    issues = rt.validate(GOOD.replace("Tested up to: 6.8", "Tested up to: 6.4.2"), wp_latest="6.8")
    warns = " ".join(messages(issues, "warning"))
    assert "major version only" in warns and "older than WordPress 6.8" in warns


def test_changelog_entry_and_size_and_license():
    text = GOOD.replace("= 1.2.0 =\n* Added", "= 1.1.0 =\n* Added").replace(
        "GPLv2 or later", "Proprietary"
    )
    text += "\n" + ("x" * 11000)
    warns = " ".join(messages(rt.validate(text), "warning"))
    assert "no '= 1.2.0 =' entry" in warns
    assert "over 10 KB" in warns
    assert "GPL-compatible" in warns


def test_markup_in_short_description():
    text = GOOD.replace("Collect and show", "**Collect** and show")
    assert any("no markup" in m for m in messages(rt.validate(text), "warning"))


def test_generate_round_trip(tmp_path):
    p = tmp_path / "acme.php"
    p.write_text(PLUGIN)
    text = rt.generate(rt.plugin_headers(str(p)), "acme", "reviews, schema", "6.8")
    assert text.startswith("=== Acme Reviews ===")
    assert messages(rt.validate(text, rt.plugin_headers(str(p))), "error") == []


def test_cli_generate_and_validate(tmp_path):
    p = tmp_path / "acme.php"
    p.write_text(PLUGIN)
    out = tmp_path / "readme.txt"
    res = run_script(
        SKILL,
        SCRIPT,
        "generate",
        str(p),
        "--contributors",
        "acme",
        "--tags",
        "reviews",
        "--tested-up-to",
        "6.8",
        "-o",
        str(out),
    )
    assert res.returncode == 0, res.stderr
    again = run_script(
        SKILL,
        SCRIPT,
        "generate",
        str(p),
        "--contributors",
        "acme",
        "--tested-up-to",
        "6.8",
        "-o",
        str(out),
    )
    assert again.returncode == 2  # refuses to overwrite
    val = run_script(SKILL, SCRIPT, "validate", str(out), "--plugin-file", str(p), "--json")
    assert val.returncode == 0
    assert json.loads(val.stdout)["issues"] == []
    too_many = run_script(
        SKILL,
        SCRIPT,
        "generate",
        str(p),
        "--contributors",
        "a",
        "--tags",
        "a,b,c,d,e,f",
        "--tested-up-to",
        "6.8",
    )
    assert too_many.returncode == 2


def test_cli_validate_failures(tmp_path):
    bad = tmp_path / "readme.txt"
    bad.write_text("nothing here")
    assert run_script(SKILL, SCRIPT, "validate", str(bad)).returncode == 1
    good = tmp_path / "good.txt"
    good.write_text(GOOD.replace("License URI: https://www.gnu.org/licenses/gpl-2.0.html\n", ""))
    assert run_script(SKILL, SCRIPT, "validate", str(good)).returncode == 0
    assert run_script(SKILL, SCRIPT, "validate", str(good), "--strict").returncode == 1
    assert run_script(SKILL, SCRIPT, "validate", str(tmp_path / "nope.txt")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
