import json
import re
import shutil
import subprocess

import pytest

from conftest import load_script, run_script

SKILL, SCRIPT = "wp-plugin-scaffold", "scaffold_plugin.py"
sc = load_script(SKILL, SCRIPT)
rt = load_script("wp-readme-txt", "readme_txt.py")
sec = load_script("wp-security-review", "wp_security_scan.py")


def generate(tmp_path, *extra):
    res = run_script(
        SKILL,
        SCRIPT,
        "acme-reviews",
        "--namespace",
        "Acme\\Reviews",
        "--author",
        "Acme",
        "--dest",
        str(tmp_path),
        "--json",
        *extra,
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout), tmp_path / "acme-reviews"


def test_slug_to_namespace():
    assert sc.slug_to_namespace("acme-reviews") == "AcmeReviews"
    assert sc.slug_to_namespace("seo2-tools") == "Seo2Tools"


def test_generates_expected_files(tmp_path):
    summary, root = generate(tmp_path)
    assert summary["namespace"] == "Acme\\Reviews" and summary["prefix"] == "acme_reviews"
    for rel in (
        "acme-reviews.php",
        "src/Plugin.php",
        "src/Admin/Settings.php",
        "uninstall.php",
        "composer.json",
        "phpcs.xml.dist",
        "phpunit.xml.dist",
        "tests/Unit/PluginTest.php",
        ".github/workflows/ci.yml",
        "readme.txt",
        ".distignore",
        "languages/.gitkeep",
    ):
        assert (root / rel).exists(), rel
    leftovers = [
        p for p in root.rglob("*") if p.is_file() and re.search(r"\{\{[A-Z_]+\}\}", p.read_text())
    ]
    assert leftovers == []


def test_composer_json_autoload(tmp_path):
    _, root = generate(tmp_path)
    data = json.loads((root / "composer.json").read_text())
    assert data["name"] == "acme/acme-reviews"
    assert data["autoload"]["psr-4"] == {"Acme\\Reviews\\": "src/"}
    assert data["autoload-dev"]["psr-4"] == {"Acme\\Reviews\\Tests\\": "tests/"}
    assert data["require"]["php"] == ">=7.4"


def test_main_file_header_and_namespace(tmp_path):
    _, root = generate(tmp_path, "--requires-php", "8.1")
    main = (root / "acme-reviews.php").read_text()
    assert "namespace Acme\\Reviews;" in main
    assert "Requires PHP:      8.1" in main
    assert "Text Domain:       acme-reviews" in main
    assert "$prefix = __NAMESPACE__ . '\\\\';" in main
    assert "${{ matrix.php }}" in (root / ".github/workflows/ci.yml").read_text()


def test_generated_readme_is_valid(tmp_path):
    _, root = generate(tmp_path, "--contributors", "acme", "--tags", "reviews, ratings")
    plugin = rt.plugin_headers(str(root / "acme-reviews.php"))
    issues = rt.validate((root / "readme.txt").read_text(), plugin)
    assert [i for i in issues if i["level"] == "error"] == []


def test_generated_code_passes_security_scan(tmp_path):
    _, root = generate(tmp_path)
    for php in root.rglob("*.php"):
        assert sec.scan_text(php.read_text(), str(php)) == [], php


def test_refuses_to_overwrite_and_dry_run(tmp_path):
    generate(tmp_path)
    res = run_script(SKILL, SCRIPT, "acme-reviews", "--dest", str(tmp_path))
    assert res.returncode == 1
    assert (
        run_script(SKILL, SCRIPT, "acme-reviews", "--dest", str(tmp_path), "--force").returncode
        == 0
    )
    dry = run_script(SKILL, SCRIPT, "other-plugin", "--dest", str(tmp_path), "--dry-run")
    assert dry.returncode == 0 and "Would create" in dry.stdout
    assert not (tmp_path / "other-plugin").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["Bad_Slug"],
        ["ok-slug", "--namespace", "lower\\case"],
        ["ok-slug", "--prefix", "Bad-Prefix"],
        ["ok-slug", "--name", "It's mine"],
        ["ok-slug", "--description", "ends */ comment"],
        ["ok-slug", "--tags", "a,b,c,d,e,f"],
    ],
)
def test_invalid_arguments(tmp_path, args):
    assert run_script(SKILL, SCRIPT, *args, "--dest", str(tmp_path)).returncode == 2


@pytest.mark.skipif(shutil.which("php") is None, reason="php not installed")
def test_generated_php_has_valid_syntax(tmp_path):
    _, root = generate(tmp_path)
    for php in root.rglob("*.php"):
        res = subprocess.run(["php", "-l", str(php)], capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr


def test_help():
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
