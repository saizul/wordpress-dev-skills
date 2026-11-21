import json
import shlex

from conftest import load_script, run_script

SKILL, SCRIPT = "wp-cli-ops", "search_replace_plan.py"
plan = load_script(SKILL, SCRIPT)


def test_validate_errors():
    assert plan.validate("a", "a")[0]
    assert plan.validate("", "x")[0]
    assert plan.validate("https://a .com", "https://b.com")[0]
    assert plan.validate("ftp://a.com", "https://b.com")[0]


def test_validate_warnings():
    _, w = plan.validate("https://a.com/", "https://b.com")
    assert any("trailing slash" in x or "ends with '/'" in x for x in w)
    _, w = plan.validate("example.com", "example.com.au")
    assert any("twice" in x for x in w)
    _, w = plan.validate("https://a.com", "http://a.org")
    assert any("downgrading" in x for x in w)
    _, w = plan.validate("https://staging.example.com", "https://example.com")
    assert w == []


def test_variants():
    v = dict((n, (o, nn)) for n, o, nn in plan.variants("https://old.test", "https://new.test"))
    assert v["json-escaped"] == ("https:\\/\\/old.test", "https:\\/\\/new.test")
    assert v["url-encoded"] == ("https%3A%2F%2Fold.test", "https%3A%2F%2Fnew.test")
    assert [n for n, _, _ in plan.variants("old.test", "new.test")] == ["plain"]


def steps(*args):
    res = run_script(SKILL, SCRIPT, *args, "--json")
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)["steps"]


def test_dry_run_only_by_default():
    s = steps("--from", "https://old.test", "--to", "https://new.test")
    names = [x["step"] for x in s]
    assert names[0] == "backup"
    assert all(not n.startswith("apply") for n in names)
    for x in s:
        if x["step"].startswith("dry-run"):
            assert "--dry-run" in x["command"]
            assert "--skip-columns=guid" in x["command"]
            assert "--precise" in x["command"]


def test_apply_steps_and_flags():
    s = steps(
        "--from",
        "https://old.test",
        "--to",
        "https://new.test",
        "--apply-steps",
        "--network",
        "--ssh",
        "deploy@host/path",
        "--skip-plugins",
    )
    names = [x["step"] for x in s]
    assert "apply:plain" in names and names[-1] == "verify"
    apply_cmd = next(x["command"] for x in s if x["step"] == "apply:json-escaped")
    parts = shlex.split(apply_cmd)
    assert parts[:2] == ["wp", "--ssh=deploy@host/path"]
    assert "--network" in parts and "--dry-run" not in parts
    assert "https:\\/\\/old.test" in parts


def test_export_step():
    s = steps("--from", "https://old.test", "--to", "https://new.test", "--export", "out.sql")
    exp = [x for x in s if x["step"].startswith("export")]
    assert len(exp) == 1 and "--export=out.sql" in exp[0]["command"]


def test_shell_output_and_strict():
    res = run_script(SKILL, SCRIPT, "--from", "example.com", "--to", "example.com.au")
    assert res.returncode == 0
    assert res.stdout.startswith("#!/bin/sh")
    assert "# WARNING:" in res.stdout
    strict = run_script(
        SKILL, SCRIPT, "--from", "example.com", "--to", "example.com.au", "--strict"
    )
    assert strict.returncode == 1


def test_invalid_input_exit_two():
    assert run_script(SKILL, SCRIPT, "--from", "a", "--to", "a").returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
