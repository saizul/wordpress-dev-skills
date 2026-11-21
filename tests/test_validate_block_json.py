import json

from conftest import load_script, run_script

SKILL, SCRIPT = "wp-block-dev", "validate_block_json.py"
vb = load_script(SKILL, SCRIPT)

GOOD = {
    "$schema": "https://schemas.wp.org/trunk/block.json",
    "apiVersion": 3,
    "name": "my-plugin/latest-reviews",
    "version": "0.1.0",
    "title": "Latest Reviews",
    "category": "widgets",
    "textdomain": "my-plugin",
    "attributes": {
        "count": {"type": "integer", "default": 3},
        "layout": {"type": "string", "enum": ["list", "grid"], "default": "list"},
        "url": {"type": "string", "source": "attribute", "selector": "img", "attribute": "src"},
    },
    "editorScript": "file:./index.js",
    "style": ["file:./style-index.css", "wp-block-library"],
    "render": "file:./render.php",
}


def write_block(tmp_path, data, files=("index.js", "style-index.css", "render.php")):
    for f in files:
        (tmp_path / f).write_text("")
    p = tmp_path / "block.json"
    p.write_text(json.dumps(data))
    return str(p)


def levels(issues):
    return [i["level"] for i in issues]


def test_good_block_has_no_issues(tmp_path):
    assert vb.check_block(write_block(tmp_path, GOOD)) == []


def test_src_extension_fallback(tmp_path):
    p = write_block(tmp_path, GOOD, files=("index.tsx", "style-index.scss", "render.php"))
    assert vb.check_block(p) == []


def test_missing_assets_and_bad_name(tmp_path):
    data = dict(GOOD, name="MyPlugin/Block")
    p = write_block(tmp_path, data, files=())
    msgs = " ".join(i["message"] for i in vb.check_block(p))
    assert "namespace/block-name" in msgs
    assert "editorScript: file:./index.js not found" in msgs
    assert "render: file:./render.php not found" in msgs


def test_attribute_errors(tmp_path):
    data = dict(GOOD)
    data["attributes"] = {
        "a": {"default": 1},
        "b": {"type": "text"},
        "c": {"type": "string", "source": "attribute", "selector": "a"},
        "d": {"type": "string", "enum": ["x"], "default": "y"},
        "e": {"type": "string", "source": "meta", "meta": "k"},
    }
    issues = vb.check_block(write_block(tmp_path, data))
    msgs = [i["message"] for i in issues]
    assert any("'a' needs a type" in m for m in msgs)
    assert any("invalid type 'text'" in m for m in msgs)
    assert any("no 'attribute' key" in m for m in msgs)
    assert any("not in its enum" in m for m in msgs)
    assert any("deprecated source 'meta'" in m for m in msgs)


def test_warnings_for_old_api_and_unknown_keys(tmp_path):
    data = {"name": "a/b", "title": "B", "apiVersion": 2, "categroy": "text"}
    issues = vb.check_block(write_block(tmp_path, data, files=()))
    assert set(levels(issues)) == {"warning"}
    msgs = " ".join(i["message"] for i in issues)
    assert "apiVersion 2" in msgs and "'categroy'" in msgs and "textdomain" in msgs


def test_invalid_json(tmp_path):
    p = tmp_path / "block.json"
    p.write_text("{ nope")
    assert levels(vb.check_block(str(p))) == ["error"]


def test_render_must_be_php_file(tmp_path):
    (tmp_path / "render.html").write_text("")
    data = dict(GOOD, render="file:./render.html")
    msgs = [i["message"] for i in vb.check_block(write_block(tmp_path, data))]
    assert "render must point to a .php file" in msgs


def test_interactivity_warning(tmp_path):
    data = dict(GOOD, supports={"interactivity": True})
    msgs = " ".join(i["message"] for i in vb.check_block(write_block(tmp_path, data)))
    assert "viewScriptModule" in msgs


def test_cli_directory_scan_skips_node_modules(tmp_path):
    good = tmp_path / "src" / "reviews"
    good.mkdir(parents=True)
    write_block(good, GOOD)
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "block.json").write_text("{bad")
    res = run_script(SKILL, SCRIPT, str(tmp_path), "--json")
    assert res.returncode == 0, res.stdout
    assert len(json.loads(res.stdout)["files"]) == 1


def test_cli_exit_codes(tmp_path):
    write_block(tmp_path, {"name": "a/b", "title": "B"}, files=())
    assert run_script(SKILL, SCRIPT, str(tmp_path)).returncode == 0  # warnings only
    assert run_script(SKILL, SCRIPT, str(tmp_path), "--strict").returncode == 1
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_script(SKILL, SCRIPT, str(empty)).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
