import json

from conftest import load_script, run_script

SKILL, SCRIPT = "wp-security-review", "wp_security_scan.py"
scan = load_script(SKILL, SCRIPT)


def rules(src: str) -> set[str]:
    return {f.rule for f in scan.scan_text(src)}


def test_vulnerable_fixture_finds_expected_rules(fixtures):
    src = (fixtures / "security" / "vulnerable.php").read_text()
    found = rules(src)
    expected = {
        "WPS001",
        "WPS002",
        "WPS003",
        "WPS004",
        "WPS005",
        "WPS006",
        "WPS007",
        "WPS008",
        "WPS009",
        "WPS010",
        "WPS011",
        "WPS012",
        "WPS013",
        "WPS014",
        "WPS015",
        "WPS016",
        "WPS017",
        "WPS018",
    }
    assert expected <= found


def test_safe_fixture_is_clean(fixtures):
    src = (fixtures / "security" / "safe.php").read_text()
    assert scan.scan_text(src) == []


def test_comments_are_ignored():
    src = "<?php\n// echo $_GET['x'];\n/* eval( $x ); */\n# system( $y );\n"
    assert scan.scan_text(src) == []


def test_urls_in_strings_do_not_start_comments():
    src = "<?php\n$u = 'https://example.com'; echo $_GET['x'];\n"
    assert "WPS001" in rules(src)


def test_escaped_output_not_flagged():
    assert rules("<?php echo esc_html( $_GET['q'] );") == set()
    assert rules("<?php echo esc_attr( $name );") == set()


def test_prepared_queries_not_flagged():
    src = "<?php $wpdb->get_row( $wpdb->prepare( 'SELECT * FROM t WHERE id = %d', $id ) );"
    assert rules(src) == set()


def test_prepared_variable_passed_to_query_not_flagged():
    src = "<?php\n$sql = $wpdb->prepare( 'DELETE FROM t WHERE id = %d', $id );\n$wpdb->query( $sql );\n"
    assert rules(src) == set()


def test_table_name_properties_are_not_variables():
    assert rules('<?php $wpdb->get_results( "SELECT ID FROM {$wpdb->posts} LIMIT 5" );') == set()


def test_multiline_query_detected():
    src = "<?php\n$wpdb->get_results(\n  \"SELECT * FROM t WHERE a = '\" . $_GET['a'] . \"'\"\n);\n"
    found = scan.scan_text(src)
    assert [f.rule for f in found if f.rule == "WPS003"] == ["WPS003"]
    assert found[0].line == 2


def test_rest_route_without_permission_callback():
    src = "<?php register_rest_route( 'a/v1', '/b', array( 'methods' => 'GET', 'callback' => 'cb' ) );"
    assert "WPS009" in rules(src)


def test_rest_route_with_permission_callback():
    src = (
        "<?php register_rest_route( 'a/v1', '/b', array( 'callback' => 'cb', "
        "'permission_callback' => function () { return current_user_can( 'edit_posts' ); } ) );"
    )
    assert rules(src) == set()


def test_nopriv_handler_does_not_need_capability():
    src = (
        "<?php add_action( 'wp_ajax_nopriv_x', 'cb' ); function cb() { check_ajax_referer( 'x' ); }"
    )
    assert rules(src) == set()


def test_inline_ignore_all_and_specific():
    assert rules("<?php echo $_GET['x']; // wpsec-ignore") == set()
    assert rules("<?php echo $_GET['x']; // wpsec-ignore: WPS001") == set()
    assert "WPS001" in rules("<?php echo $_GET['x']; // wpsec-ignore: WPS002")


def test_phpcs_ignore_with_matching_sniff_is_respected():
    line = "<?php echo $name; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped"
    assert rules(line) == set()
    scan.OPTIONS["respect_phpcs"] = False
    try:
        assert "WPS013" in rules(line)
    finally:
        scan.OPTIONS["respect_phpcs"] = True


def test_uploaded_tmp_name_is_not_path_traversal():
    src = "<?php $j = file_get_contents( $_FILES['f']['tmp_name'] );"
    assert "WPS015" not in rules(src)


def test_cli_json_and_exit_codes(fixtures):
    res = run_script(SKILL, SCRIPT, str(fixtures / "security"), "--json")
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["files_scanned"] == 2
    assert data["counts"]["critical"] >= 3
    clean = run_script(SKILL, SCRIPT, str(fixtures / "security" / "safe.php"))
    assert clean.returncode == 0
    high_only = run_script(SKILL, SCRIPT, str(fixtures / "security"), "--fail-on", "critical")
    assert high_only.returncode == 1


def test_cli_sarif(fixtures):
    res = run_script(SKILL, SCRIPT, str(fixtures / "security"), "--format", "sarif")
    sarif = json.loads(res.stdout)
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"]


def test_cli_excludes_vendor(tmp_path):
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.php").write_text("<?php eval( $x );")
    (tmp_path / "ok.php").write_text("<?php echo esc_html( 'hi' );")
    res = run_script(SKILL, SCRIPT, str(tmp_path), "--json")
    assert res.returncode == 0
    assert json.loads(res.stdout)["files_scanned"] == 1


def test_cli_help_and_missing_path(tmp_path):
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
    assert run_script(SKILL, SCRIPT, str(tmp_path / "nope")).returncode == 2
