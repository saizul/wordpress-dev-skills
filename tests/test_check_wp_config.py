import json
import os
import stat

import pytest

from conftest import load_script, run_script

SKILL, SCRIPT = "wp-hardening", "check_wp_config.py"
cfg = load_script(SKILL, SCRIPT)

SALT_KEYS = cfg.SALT_KEYS


def fake_salt(i: int) -> str:
    # Obviously fake, but long and unique, including characters salts really contain.
    return f"test-only-{i}-" + "x/*#);" + "abcdefghij" * 4


def hardened_config() -> str:
    lines = ["<?php"]
    lines += [f"define( '{k}', '{fake_salt(i)}' );" for i, k in enumerate(SALT_KEYS)]
    lines += [
        "define( 'DB_USER', 'site_user' );",
        "define( 'DB_PASSWORD', getenv( 'DB_PASS' ) );",
        "define( 'WP_DEBUG', false );",
        "define( 'DISALLOW_FILE_EDIT', true );",
        "define( 'DISALLOW_FILE_MODS', true );",
        "define( 'FORCE_SSL_ADMIN', true );",
        "define( 'WP_ENVIRONMENT_TYPE', 'production' );",
        "$table_prefix = 'x7_';",
        "// define( 'WP_DEBUG', true );",
        "/* define( 'SAVEQUERIES', true ); */",
    ]
    return "\n".join(lines) + "\n"


def ids(findings):
    return {f["id"] for f in findings}


def test_hardened_config_is_clean():
    consts, prefix = cfg.parse_config(hardened_config())
    assert prefix == "x7_"
    assert consts["WP_DEBUG"] is False
    assert consts["DB_PASSWORD"] == {"expr": "getenv( 'DB_PASS' )"}
    assert cfg.audit_config(consts, prefix) == []


def test_salts_with_special_characters_parse_fully():
    consts, _ = cfg.parse_config(hardened_config())
    assert consts["NONCE_SALT"] == fake_salt(7)
    assert "SAVEQUERIES" not in consts  # inside a block comment


def test_default_insecure_config():
    src = "\n".join(
        ["<?php"]
        + [f"define( '{k}', 'put your unique phrase here' );" for k in SALT_KEYS]
        + [
            "define( 'DB_USER', 'root' );",
            "define( 'DB_PASSWORD', '' );",
            "define( 'WP_DEBUG', true );",
            "define( 'WP_DEBUG_LOG', true );",
            "define( 'SAVEQUERIES', true );",
            "define( 'SCRIPT_DEBUG', true );",
            "define( 'AUTOMATIC_UPDATER_DISABLED', true );",
            "define( 'WP_AUTO_UPDATE_CORE', false );",
            "$table_prefix = 'wp_';",
        ]
    )
    found = ids(cfg.audit_config(*cfg.parse_config(src)))
    assert {
        "WPH001",
        "WPH002",
        "WPH010",
        "WPH011",
        "WPH012",
        "WPH013",
        "WPH014",
        "WPH020",
        "WPH021",
        "WPH030",
        "WPH040",
        "WPH041",
        "WPH050",
        "WPH051",
        "WPH060",
        "WPH070",
    } <= found


def test_debug_display_false_is_not_high():
    src = "<?php define( 'WP_DEBUG', true ); define( 'WP_DEBUG_DISPLAY', false );"
    found = ids(cfg.audit_config(*cfg.parse_config(src)))
    assert "WPH010" in found and "WPH011" not in found


def test_secrets_never_printed(tmp_path):
    p = tmp_path / "wp-config.php"
    p.write_text(hardened_config() + "define( 'DB_PASSWORD2', 'hunter2-test' );\n")
    res = run_script(SKILL, SCRIPT, str(p), "--json")
    out = res.stdout
    assert "hunter2-test" not in out
    assert fake_salt(0) not in out
    assert "DB_PASSWORD2" in json.loads(out)["constants_found"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_wp_root_permissions_and_leaks(tmp_path):
    root = tmp_path / "htdocs"
    (root / "wp-content").mkdir(parents=True)
    (root / ".git").mkdir()
    conf = root / "wp-config.php"
    conf.write_text(hardened_config())
    conf.chmod(0o666)
    (root / "wp-content" / "debug.log").write_text("x")
    (root / "backup.sql").write_text("x")
    (root / "phpinfo.php").write_text("<?php phpinfo();")
    (root / "wp-config.php.bak").write_text("x")
    open_dir = root / "wp-content" / "cache"
    open_dir.mkdir()
    open_dir.chmod(0o777)
    findings = cfg.audit_files(str(conf), str(root))
    found = ids(findings)
    assert {"WPH100", "WPH110", "WPH111", "WPH120"} <= found
    leaked = {os.path.basename(f["path"]) for f in findings if f["id"] == "WPH111"}
    assert leaked == {"debug.log", "backup.sql", "phpinfo.php", "wp-config.php.bak"}
    conf.chmod(0o644)
    assert "WPH101" in ids(cfg.audit_files(str(conf), None))
    conf.chmod(0o640)
    assert cfg.audit_files(str(conf), None) == []
    open_dir.chmod(stat.S_IRWXU)


def test_find_config_one_level_up(tmp_path):
    (tmp_path / "htdocs").mkdir()
    (tmp_path / "wp-config.php").write_text("<?php")
    assert cfg.find_config(str(tmp_path / "htdocs")) == str(tmp_path / "wp-config.php")


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.php"
    good.write_text(hardened_config())
    good.chmod(0o640)
    assert run_script(SKILL, SCRIPT, str(good)).returncode == 0
    bad = tmp_path / "bad.php"
    bad.write_text("<?php define( 'WP_DEBUG', true );")
    assert run_script(SKILL, SCRIPT, str(bad)).returncode == 1
    assert run_script(SKILL, SCRIPT, str(bad), "--fail-on", "high").returncode == 1
    assert run_script(SKILL, SCRIPT, str(tmp_path / "none.php")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
