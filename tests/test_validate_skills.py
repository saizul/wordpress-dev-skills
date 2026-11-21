import json
import shutil
import subprocess
import sys

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import validate_skills as vs  # noqa: E402

SKILL_MD = """---
name: demo-skill
description: Does a demo thing. Use when testing the validator.
license: MIT
metadata:
  author: Test
  version: "0.1.0"
---

# Demo

## When to use

Testing.

## Workflow

Run `python3 scripts/demo.py`. See [the reference](references/notes.md).
"""


def make_repo(tmp_path, skill_md=SKILL_MD, skills_meta=("demo-skill",), test_mentions=True):
    root = tmp_path / "repo"
    skill = root / "skills" / "demo-skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "references").mkdir()
    (skill / "SKILL.md").write_text(skill_md)
    (skill / "scripts" / "demo.py").write_text("print('hi')\n")
    (skill / "references" / "notes.md").write_text("notes\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_demo.py").write_text("# demo.py\n" if test_mentions else "# nothing\n")
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": "0.1.0"})
    )
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "demo-market",
                "owner": {"name": "Test"},
                "plugins": [
                    {"name": "demo", "source": "./", "metadata": {"skills": list(skills_meta)}}
                ],
            }
        )
    )
    (root / "README.md").write_text("demo-skill\n")
    (root / "CHANGELOG.md").write_text("## [0.1.0]\n")
    return root


def test_this_repository_is_valid():
    assert vs.check_repo(str(ROOT)) == []


def test_minimal_repo_valid(tmp_path):
    assert vs.check_repo(str(make_repo(tmp_path))) == []


def test_frontmatter_parser():
    fm, body, errs = vs.parse_frontmatter(SKILL_MD)
    assert errs == []
    assert fm["name"] == "demo-skill"
    assert fm["metadata"] == {"author": "Test", "version": "0.1.0"}
    assert body.lstrip().startswith("# Demo")
    assert vs.parse_frontmatter("no frontmatter")[2]
    assert vs.parse_frontmatter("---\nname: x\n")[2]


def test_name_rules(tmp_path):
    for bad in ("Demo-Skill", "demo--skill", "-demo", "other-name", "a" * 65):
        root = make_repo(
            tmp_path / bad[:10].replace("-", "_"),
            SKILL_MD.replace("name: demo-skill", f"name: {bad}"),
        )
        assert any("name" in p for p in vs.check_repo(str(root))), bad


def test_description_rules(tmp_path):
    long = make_repo(tmp_path / "a", SKILL_MD.replace("Does a demo thing.", "x" * 1100))
    assert any("max 1024" in p for p in vs.check_repo(str(long)))
    no_when = make_repo(tmp_path / "b", SKILL_MD.replace(" Use when testing the validator.", ""))
    assert any("when to use" in p for p in vs.check_repo(str(no_when)))


def test_unknown_key_and_missing_sections(tmp_path):
    text = SKILL_MD.replace("license: MIT", "license: MIT\ntags: x").replace(
        "## Workflow", "## Steps"
    )
    probs = vs.check_repo(str(make_repo(tmp_path, text)))
    assert any("unknown frontmatter key 'tags'" in p for p in probs)
    assert any("missing section '## Workflow'" in p for p in probs)


def test_missing_references_and_tests(tmp_path):
    text = (
        SKILL_MD.replace("references/notes.md", "references/gone.md")
        + "\nAlso scripts/missing.py\n"
    )
    probs = vs.check_repo(str(make_repo(tmp_path, text, test_mentions=False)))
    assert any("'references/gone.md' does not exist" in p for p in probs)
    assert any("'scripts/missing.py' does not exist" in p for p in probs)
    assert any("scripts/demo.py has no test" in p for p in probs)


def test_links_inside_code_are_ignored(tmp_path):
    text = SKILL_MD + '\n```bash\ngrep -E "](not-a-file)" .\n```\n'
    assert vs.check_repo(str(make_repo(tmp_path, text))) == []


def test_body_line_limit(tmp_path):
    text = SKILL_MD + "line\n" * 450
    assert any("max 400" in p for p in vs.check_repo(str(make_repo(tmp_path, text))))


def test_marketplace_checks(tmp_path):
    root = make_repo(tmp_path, skills_meta=("demo-skill", "ghost"))
    assert any("unknown skills: ghost" in p for p in vs.check_repo(str(root)))
    root2 = make_repo(tmp_path / "two", skills_meta=())
    assert any("missing: demo-skill" in p for p in vs.check_repo(str(root2)))
    mp = root2 / ".claude-plugin" / "marketplace.json"
    data = json.loads(mp.read_text())
    data["plugins"][0]["source"] = "../elsewhere"
    data["owner"] = {}
    mp.write_text(json.dumps(data))
    probs = vs.check_repo(str(root2))
    assert any("owner.name" in p for p in probs)
    assert any("must start with './'" in p for p in probs)
    mp.write_text("{broken")
    assert any("not valid JSON" in p for p in vs.check_repo(str(root2)))


def test_plugin_json_name_and_changelog(tmp_path):
    root = make_repo(tmp_path)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "other", "version": "9.9.9"})
    )
    probs = vs.check_repo(str(root))
    assert any("!= marketplace entry" in p for p in probs)
    assert any("[9.9.9]" in p for p in probs)


def test_reserved_plugin_name(tmp_path):
    root = make_repo(tmp_path)
    mp = root / ".claude-plugin" / "marketplace.json"
    data = json.loads(mp.read_text())
    data["plugins"][0]["name"] = "claude-tools"
    mp.write_text(json.dumps(data))
    assert any("reserved" in p for p in vs.check_repo(str(root)))


def test_readme_mentions(tmp_path):
    root = make_repo(tmp_path)
    (root / "README.md").write_text("nothing\n")
    assert any("README.md does not mention" in p for p in vs.check_repo(str(root)))


def test_cli(tmp_path):
    root = make_repo(tmp_path)
    script = ROOT / "tools" / "validate_skills.py"
    ok = subprocess.run(
        [sys.executable, str(script), str(root), "--json"], capture_output=True, text=True
    )
    assert ok.returncode == 0 and json.loads(ok.stdout)["ok"] is True
    shutil.rmtree(root / "skills" / "demo-skill" / "references")
    bad = subprocess.run([sys.executable, str(script), str(root)], capture_output=True, text=True)
    assert bad.returncode == 1 and "FAIL" in bad.stdout
    missing = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "nope")], capture_output=True, text=True
    )
    assert missing.returncode == 2
