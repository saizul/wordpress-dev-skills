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


MULTILINE_JOIN = """<?php
global $wpdb;
$rows = $wpdb->get_results(
    "SELECT p.ID, pm.meta_value
     FROM {$wpdb->posts} p
     INNER JOIN {$wpdb->postmeta} pm ON pm.post_id = p.ID
     WHERE pm.meta_key = '_billing_email'; -- semicolon inside the SQL string
     AND p.post_status = 'wc-processing'"
);
"""


def test_multiline_postmeta_join_for_order_meta():
    findings, _ = hpos.scan_file_text(MULTILINE_JOIN, "x.php")
    assert [(f.rule, f.line) for f in findings] == [("HPOS011", 6)]
    assert "wc_orders_meta" in findings[0].fix


def test_postmeta_sql_with_order_id():
    src = '<?php\n$wpdb->get_var( $wpdb->prepare(\n  "SELECT meta_value FROM $wpdb->postmeta\n'
    src += "   WHERE post_id = %d AND meta_key = %s\", $order_id, '_my_key' ) );\n"
    findings, _ = hpos.scan_file_text(src, "x.php")
    assert [(f.rule, f.line) for f in findings] == [("HPOS011", 3)]


def test_postmeta_sql_for_products_and_ignores_not_flagged():
    product = (
        "<?php $wpdb->get_col( \"SELECT post_id FROM {$wpdb->postmeta} WHERE meta_key = '_sku'\" );"
    )
    assert hpos.scan_file_text(product, "x.php")[0] == []
    ignored = (
        "<?php $wpdb->query( \"DELETE FROM {$wpdb->postmeta} WHERE meta_key = '_order_key'\" );"
        " // hpos-ignore"
    )
    assert hpos.scan_file_text(ignored, "x.php")[0] == []
    commented = "<?php\n// $wpdb->postmeta has _billing_email\n$x = 1;\n"
    assert hpos.scan_file_text(commented, "x.php")[0] == []


def test_postmeta_sql_not_double_reported_with_hpos004():
    src = "<?php $wpdb->get_results( \"SELECT * FROM {$wpdb->postmeta} pm JOIN x WHERE type='shop_order'\" );"
    rules = [f.rule for f in hpos.scan_file_text(src, "x.php")[0]]
    assert rules == ["HPOS004"]
