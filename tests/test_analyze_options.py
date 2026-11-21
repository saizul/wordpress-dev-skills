import json

from conftest import load_script, run_script

SKILL, SCRIPT = "wp-performance-audit", "analyze_options.py"
ao = load_script(SKILL, SCRIPT)

ROWS = [
    {"option_name": "siteurl", "size_bytes": "30", "autoload": "on"},
    {"option_name": "rewrite_rules", "size_bytes": "150000", "autoload": "yes"},
    {"option_name": "bigbuilder_cache", "size_bytes": "700000", "autoload": "auto"},
    {"option_name": "bigbuilder_settings", "size_bytes": "5000", "autoload": "auto-on"},
    {"option_name": "_transient_feed_abc", "size_bytes": "2000", "autoload": "yes"},
    {"option_name": "not_loaded", "size_bytes": "900000", "autoload": "off"},
    {"option_name": "legacy_no", "size_bytes": "900000", "autoload": "no"},
    {"option_name": "auto_off", "size_bytes": "900000", "autoload": "auto-off"},
]


def test_parse_json_and_csv():
    rows = ao.parse_rows(json.dumps(ROWS))
    assert len(rows) == 8 and rows[1]["size"] == 150000
    csv_text = "option_name,size_bytes,autoload\nsiteurl,30,on\nfoo,10,off\n"
    assert ao.parse_rows(csv_text)[1] == {"name": "foo", "size": 10, "autoload": "off"}


def test_size_computed_from_value_when_missing():
    rows = ao.parse_rows(
        json.dumps([{"option_name": "x", "option_value": "héllo", "autoload": "yes"}])
    )
    assert rows[0]["size"] == 6  # bytes, not characters


def test_parse_errors():
    for bad in ("", "[1, 2]", json.dumps([{"option_name": "x"}])):
        try:
            ao.parse_rows(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_analyze_counts_only_autoloaded_values():
    rep = ao.analyze(ao.parse_rows(json.dumps(ROWS)), 800_000, 100_000, 10)
    assert rep["autoload_count"] == 5
    assert rep["autoload_bytes"] == 30 + 150000 + 700000 + 5000 + 2000
    assert rep["top"][0]["option"] == "bigbuilder_cache"
    types = {i["type"] for i in rep["issues"]}
    assert types == {"autoload_total", "large_option", "autoloaded_transients"}
    assert rep["by_prefix"][0]["prefix"] == "bigbuilder"


def test_core_options_not_suggested_for_autoload_off():
    rep = ao.analyze(ao.parse_rows(json.dumps(ROWS)), 800_000, 100_000, 10)
    cmds = "\n".join(rep["suggested_commands"])
    assert "set-autoload bigbuilder_cache off" in cmds
    assert "rewrite_rules off" not in cmds
    assert rep["core_options_skipped"] == ["rewrite_rules"]
    assert cmds.splitlines()[0].startswith("wp db export")


def test_shell_quoting_of_odd_names():
    rows = [{"name": "weird name;rm", "size": 200000, "autoload": "yes"}]
    rep = ao.analyze(rows, 800_000, 100_000, 5)
    assert "'weird name;rm'" in "\n".join(rep["suggested_commands"])


def test_healthy_site_exit_zero(tmp_path):
    f = tmp_path / "o.json"
    f.write_text(json.dumps([{"option_name": "siteurl", "size_bytes": 30, "autoload": "on"}]))
    res = run_script(SKILL, SCRIPT, str(f))
    assert res.returncode == 0
    assert "healthy" in res.stdout


def test_cli_stdin_json_and_exit_one():
    res = run_script(SKILL, SCRIPT, "-", "--json", stdin=json.dumps(ROWS))
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["autoload_human"].endswith("KB")
    assert "option_value" not in res.stdout


def test_cli_help_and_bad_input(tmp_path):
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert run_script(SKILL, SCRIPT, str(bad)).returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.json")).returncode == 2
