---
name: wp-security-review
description: Security review of WordPress plugin or theme PHP code - escaping, sanitization, nonces, capability checks, $wpdb->prepare(), REST permission callbacks, file and shell functions. Includes a scanner script that flags risky patterns with file:line and a fix. Use when reviewing or auditing a WordPress plugin/theme, before a release or WordPress.org submission, when a PR touches forms, AJAX, REST routes or SQL, or when the user asks "is this plugin secure?".
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# WordPress security review

Find the vulnerabilities that actually get WordPress plugins exploited: XSS from
unescaped output, SQL injection, CSRF (missing nonces), broken access control
(missing capability checks / REST `permission_callback`), object injection,
path traversal and remote code execution.

## When to use

- Reviewing a plugin/theme, a pull request, or code you just wrote that handles
  `$_GET`/`$_POST`/`$_REQUEST`, forms, AJAX, `admin-post.php`, REST routes or SQL.
- Before tagging a release or submitting to WordPress.org.

Not for: server/wp-config hardening (use `wp-hardening`), known-CVE checks of
installed plugins (use WPScan or Patchstack/Wordfence databases), or JavaScript-only code.

## Workflow

1. **Scope.** Identify the plugin root and its entry points. List them before reading code:
   ```bash
   grep -rnE "add_action\(\s*['\"](wp_ajax_|admin_post_|rest_api_init)|register_rest_route|add_shortcode|add_menu_page|add_submenu_page|add_options_page" --include=*.php .
   ```
2. **Run the scanner** (read-only, stdlib Python 3.9+):
   ```bash
   python3 scripts/wp_security_scan.py path/to/plugin
   python3 scripts/wp_security_scan.py path/to/plugin --format sarif > wpsec.sarif   # GitHub code scanning
   python3 scripts/wp_security_scan.py path/to/plugin --json --min-severity medium
   ```
   Exit code 1 means findings at or above `--fail-on` (default `medium`).
   `vendor/`, `node_modules/`, `build/`, `dist/` are skipped.
3. **Triage every finding by reading the code.** The scanner is a heuristic
   line scanner. For each finding decide: real issue / false positive / needs context.
   Follow the data: where does the variable come from, and is it escaped at output?
4. **Manual pass over each entry point** with the checklist below. The scanner
   cannot see logic bugs such as a capability check on the wrong action, an
   IDOR (user A editing user B's post), or a nonce checked but its result ignored.
5. **Run PHPCS** if the project has Composer:
   `vendor/bin/phpcs --standard=WordPress-Extra --sniffs=WordPress.Security.EscapeOutput,WordPress.Security.NonceVerification,WordPress.Security.ValidatedSanitizedInput,WordPress.DB.PreparedSQL .`
6. **Report** (format below). Offer patches for confirmed issues; do not "fix"
   false positives by adding ignore comments without explaining why.

## Entry-point checklist

For every AJAX action, admin-post handler, REST route, form handler and shortcode:

- [ ] **Nonce**: `check_ajax_referer()` / `check_admin_referer()` / `wp_verify_nonce()` before any state change. GET requests must not change state.
- [ ] **Capability**: `current_user_can( 'specific_cap' )` - not `is_admin()` (that only means "an admin page is loading"), not `is_user_logged_in()` for privileged actions.
- [ ] **Object-level access**: `current_user_can( 'edit_post', $post_id )` when acting on a specific object.
- [ ] **REST**: every `register_rest_route()` has a `permission_callback`; `__return_true` only for public read-only data.
- [ ] **Input**: `wp_unslash()` then sanitize by type (`absint`, `sanitize_text_field`, `sanitize_key`, `sanitize_email`, `esc_url_raw`, `wp_kses_post`); validate against a whitelist for enums/order-by.
- [ ] **SQL**: `$wpdb->prepare()` with `%d %s %f %i` placeholders (no quotes around `%s`); `esc_like()` for LIKE; whitelist ORDER BY columns.
- [ ] **Output**: escape late with the right context: `esc_html`, `esc_attr`, `esc_url`, `esc_js`, `wp_kses_post`; `wp_json_encode` for JSON in scripts.
- [ ] **Redirects**: `wp_safe_redirect()` + `exit`.
- [ ] **Files**: uploads via `wp_handle_upload()` with an allowed mime list; no include/require/readfile built from input.
- [ ] **Dangerous functions**: no `eval`, `unserialize` on user data, `extract`, shell execution.
- [ ] **Secrets**: no API keys in code or in autoloaded options returned to the front end.

Details and safe/unsafe code pairs: [references/patterns.md](references/patterns.md).
Rule list with IDs: [references/rules.md](references/rules.md).

## Suppressing reviewed lines

Add `// wpsec-ignore: WPS002` (or `// wpsec-ignore` for all rules) with a reason.
A `phpcs:ignore` that names the matching WPCS sniff (EscapeOutput, PreparedSQL,
ValidatedSanitizedInput) is honoured too; pass `--no-phpcs-ignore` to see those lines anyway.

## Output format

```
## Security review: <plugin> <version>
Summary: X critical, Y high, Z medium. Scanner: N findings, M confirmed.

### [CRITICAL] SQL injection in Reports::export() - includes/class-reports.php:88
Impact: any subscriber can read the users table via the `orderby` parameter.
Evidence: <3-6 lines of code>
Fix: <patch or exact replacement>

### False positives
- WPS013 templates/card.php:12 - value is already passed through esc_html() on line 10.
```

Order by severity; say who can trigger each issue (unauthenticated, subscriber,
editor, admin) because that decides real severity.
