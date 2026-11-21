---
name: wp-hardening
description: Harden a WordPress installation - wp-config.php constants (salts, debug output, file editing, auto-updates, SSL admin), file and directory permissions, leftover files that leak data (debug.log, SQL dumps, .git, phpinfo), XML-RPC, REST user enumeration, login protection and HTTP security headers. Includes a read-only checker that audits wp-config.php without ever printing secrets. Use when securing a new or existing WordPress site, after a hack clean-up, before go-live, or when the user asks how to harden WordPress or wp-config.
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# WordPress hardening

Script paths below are relative to this skill's directory.

## When to use

- New site going live, server migration, post-incident clean-up, periodic audit.
- User asks about wp-config security constants, file permissions, XML-RPC or headers.

Not for: reviewing plugin source code (use `wp-security-review`), malware removal
(use a dedicated scanner and restore from clean backups), WAF configuration details.

## Workflow

1. **Audit wp-config.php and the web root** (read-only; secrets are never printed):
   ```bash
   python3 scripts/check_wp_config.py /var/www/example.com/htdocs/wp-config.php
   python3 scripts/check_wp_config.py --wp-root /var/www/example.com/htdocs          # + permissions and leftover files
   python3 scripts/check_wp_config.py --wp-root . --json --fail-on high             # CI / scripting
   ```
   It finds wp-config.php in the root or one level above (both are supported by core).
2. **Check the live site** from outside (read-only):
   ```bash
   curl -sI https://example.com/ | grep -iE "strict-transport|x-content-type|x-frame|referrer-policy|permissions-policy|content-security|server|x-powered-by"
   curl -s -o /dev/null -w "%{http_code}\n" https://example.com/xmlrpc.php           # 405 = reachable (POST-only), 403 = blocked
   curl -s https://example.com/wp-json/wp/v2/users | head -c 300                       # user enumeration?
   curl -s -o /dev/null -w "%{http_code}\n" https://example.com/wp-content/debug.log  # must not be 200
   curl -s -o /dev/null -w "%{http_code}\n" https://example.com/.git/HEAD             # must not be 200
   ```
3. **Integrity**: `wp core verify-checksums` and `wp plugin verify-checksums --all`
   (wordpress.org plugins only). Unexpected files in `wp-content/uploads/*.php` are a red flag.
4. **Apply fixes** in this order (each is explained in
   [references/hardening.md](references/hardening.md)):
   1. Updates: core, plugins, themes, PHP version; remove unused plugins/themes.
   2. wp-config constants (snippet below); fresh salts with `wp config shuffle-salts`.
   3. Permissions: directories 755, files 644, wp-config.php 640 or 600; nothing world-writable.
   4. Delete leaked files; move logs outside the web root.
   5. Block PHP execution in uploads; deny xmlrpc.php if unused; restrict REST user listing.
   6. Security headers at the web server or CDN.
   7. Login: strong passwords, 2FA for administrators, rate limiting (server or plugin).
   8. Backups off-server, tested restore.
5. **Re-run the checker** and the curl checks; report what changed.

Confirm with the user before changes that can break things: `DISALLOW_FILE_MODS`
(blocks dashboard updates), blocking XML-RPC (Jetpack and some mobile apps use it),
CSP headers (can break scripts), and permission changes on shared hosting.

## Recommended wp-config.php block

```php
define( 'WP_ENVIRONMENT_TYPE', 'production' );
define( 'DISALLOW_FILE_EDIT', true );
// define( 'DISALLOW_FILE_MODS', true );     // git/CI-deployed sites only
define( 'FORCE_SSL_ADMIN', true );
define( 'WP_DEBUG', false );
define( 'WP_DEBUG_DISPLAY', false );
define( 'WP_DEBUG_LOG', false );             // or a path outside the web root
define( 'WP_AUTO_UPDATE_CORE', 'minor' );
define( 'WP_POST_REVISIONS', 20 );
// Salts: run `wp config shuffle-salts` (everyone is logged out).
```

## Output format

```
## Hardening report: example.com
Checker: 2 high, 3 medium (before) -> 0 high, 1 medium (after)
| Item | Status | Action taken / recommended |
| Debug output | fixed | WP_DEBUG_DISPLAY false |
| xmlrpc.php | open (Jetpack in use) | kept; rate-limited at server |
...
Manual follow-ups: enable 2FA for 3 admins, set up off-site backups.
```
