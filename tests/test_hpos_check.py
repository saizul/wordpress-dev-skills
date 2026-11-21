import json

from conftest import load_script, run_script

SKILL, SCRIPT = "woocommerce-dev", "hpos_check.py"
hpos = load_script(SKILL, SCRIPT)


def test_legacy_fixture(fixtures):
    res = hpos.scan(str(fixtures / "hpos" / "legacy"), hpos.DEFAULT_EXCLUDES)
    found = {f.rule for f in res["findings"]}
    assert {
        "HPOS001",
        "HPOS002",
        "HPOS003",
        "HPOS004",
        "HPOS006",
        "HPOS007",
        "HPOS008",
        "HPOS010",
        "HPOS100",
        "HPOS102",
    } <= found
    lines = [f.line for f in res["findings"] if f.rule == "HPOS001"]
    assert lines == [9, 10]  # comment and hpos-ignore lines are skipped


def test_modern_fixture_is_clean(fixtures):
    res = hpos.scan(str(fixtures / "hpos" / "modern"), hpos.DEFAULT_EXCLUDES)
    assert res["findings"] == []
    assert res["declarations"] == {"custom_order_tables": True, "cart_checkout_blocks": True}


def test_incompatible_declaration_reported(tmp_path):
    (tmp_path / "p.php").write_text(
        "<?php FeaturesUtil::declare_compatibility( 'custom_order_tables', __FILE__, false );"
    )
    res = hpos.scan(str(tmp_path), [])
    assert "HPOS101" in {f.rule for f in res["findings"]}
    assert res["declarations"]["custom_order_tables"] is False


def test_order_object_calls_not_flagged():
    findings, _ = hpos.scan_file_text(
        "<?php $order = wc_get_order( $order_id ); $order->get_meta( '_x' );", "x.php"
    )
    assert findings == []


def test_post_meta_on_products_not_flagged():
    findings, _ = hpos.scan_file_text(
        "<?php get_post_meta( $product_id, '_price', true );", "x.php"
    )
    assert findings == []


def test_cli(fixtures):
    res = run_script(SKILL, SCRIPT, str(fixtures / "hpos" / "legacy"), "--json")
    assert res.returncode == 1
    assert json.loads(res.stdout)["files_scanned"] == 1
    ok = run_script(SKILL, SCRIPT, str(fixtures / "hpos" / "modern"))
    assert ok.returncode == 0
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
    assert run_script(SKILL, SCRIPT, "/nonexistent/path").returncode == 2
