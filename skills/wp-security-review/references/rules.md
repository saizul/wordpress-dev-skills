# wp_security_scan.py rules

| ID | Severity | Detects | Typical fix |
| --- | --- | --- | --- |
| WPS001 | high | `echo`/`print`/`<?=` of a superglobal with no escaping function on the line | `esc_html()`, `esc_attr()`, `esc_url()` |
| WPS002 | high | `$wpdb->query/get_results/get_row/get_var/get_col` with variables and no `prepare()` | `$wpdb->prepare()` |
| WPS003 | critical | Superglobal inside a `$wpdb` query call | `$wpdb->prepare()` with placeholders |
| WPS004 | critical | `eval`, `create_function`, `assert($var)`, `preg_replace` `/e` | Remove; use callbacks |
| WPS005 | high | `unserialize()` of request data | `json_decode()` |
| WPS006 | high | `exec`, `shell_exec`, `system`, `passthru`, `proc_open`, `popen` | Avoid, or `escapeshellarg()` |
| WPS007 | critical | `include`/`require` with request data | Whitelist of files |
| WPS008 | high | `extract()` on request data | Read keys explicitly |
| WPS009 | high | `register_rest_route()` without `permission_callback` | Add a capability check |
| WPS010 | info | `permission_callback => '__return_true'` | Confirm the endpoint is public |
| WPS011 | high | File registers `wp_ajax_*`/`admin_post_*` but never verifies a nonce | `check_ajax_referer()` |
| WPS012 | medium | Superglobal read/assigned without a sanitizer on the line | `sanitize_*()`, `absint()` |
| WPS013 | low | `echo $var` with no escaping function | Escape late |
| WPS014 | medium | `wp_redirect()` with request data | `wp_safe_redirect()` |
| WPS015 | high | `file_get_contents/fopen/readfile/unlink/...` with request data (`$_FILES[..]['tmp_name']` excluded) | `validate_file()`, `realpath()` base check |
| WPS016 | low | `'%s'` quoted placeholder inside `prepare()` | Remove the quotes |
| WPS017 | medium | File registers privileged `wp_ajax_*`/`admin_post_*` (not `nopriv`) but never calls `current_user_can()` | Add a capability check |
| WPS018 | medium | Variable in `ORDER BY`/`LIMIT` of an unprepared query | Whitelist / `absint()` |

## Known limits

- Line based: data flow across lines (`$x = $_GET['a']; ... echo $x;`) is only caught as
  WPS012 + WPS013, not as WPS001. Read the code.
- WPS011/WPS017 are file level: a nonce check in one handler hides a missing one in
  another handler of the same file. Check each callback.
- Heredoc/nowdoc strings are not parsed specially.
- `$wpdb->query( $sql )` is accepted when the same file assigns `$sql = $wpdb->prepare(...)`.
