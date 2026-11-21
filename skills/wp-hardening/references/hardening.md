# Hardening details

## check_wp_config.py findings

| ID | Severity | Meaning |
| --- | --- | --- |
| WPH001 | high | Auth keys/salts missing, shorter than 32 chars, or the sample placeholder |
| WPH002 | medium | Two or more keys/salts identical |
| WPH010 | medium | `WP_DEBUG` true |
| WPH011 | high | Debug output shown to visitors |
| WPH012 | medium | `WP_DEBUG_LOG` true (web-reachable wp-content/debug.log) |
| WPH013 | medium | `SAVEQUERIES` on |
| WPH014 | low | `SCRIPT_DEBUG` on |
| WPH020 | medium | File editor enabled (no `DISALLOW_FILE_EDIT`/`DISALLOW_FILE_MODS`) |
| WPH021 | info | `DISALLOW_FILE_MODS` not set |
| WPH030 | low | `FORCE_SSL_ADMIN` not true |
| WPH040 | medium | `AUTOMATIC_UPDATER_DISABLED` true |
| WPH041 | medium | `WP_AUTO_UPDATE_CORE` false |
| WPH050 | medium | DB user is root |
| WPH051 | high | Empty DB password |
| WPH060 | info | Default `wp_` table prefix |
| WPH070 | info | `WP_ENVIRONMENT_TYPE` not set |
| WPH100 | high | wp-config.php world-writable |
| WPH101 | medium | wp-config.php world-readable |
| WPH110 | high | `.git` directory in the web root |
| WPH111 | high | Leaked file: config backup, SQL dump, phpinfo, debug.log, adminer, .env |
| WPH120 | high | World-writable files or directories |

Constants defined with expressions (for example `getenv( 'DB_PASSWORD' )`) are
reported as present without evaluating them.

## Permissions

```bash
cd /var/www/example.com/htdocs
find . -type d -exec chmod 755 {} +
find . -type f -exec chmod 644 {} +
chmod 640 wp-config.php            # owner rw, group (web server) r
chown -R deploy:www-data .         # adapt to your stack; uploads must be writable by PHP
```

Where PHP-FPM runs as the site owner (per-site pools), 600 on wp-config.php works.
Never use 777. If something "needs" 777, fix the ownership instead.

## Block PHP in uploads

Nginx:

```nginx
location ~* ^/wp-content/uploads/.*\.(?:php|phtml|phar)$ { deny all; }
location ~ /\.(?!well-known) { deny all; }
location ~* /(?:wp-config\.php|readme\.html|license\.txt|debug\.log)$ { deny all; }
```

Apache (`wp-content/uploads/.htaccess`):

```apache
<FilesMatch "\.(?:php|phtml|phar)$">
    Require all denied
</FilesMatch>
```

## XML-RPC

Used by Jetpack, the WordPress mobile app (older versions) and some publishing tools.
If none are used, block it at the server (cheaper than a plugin):

```nginx
location = /xmlrpc.php { deny all; }
```

or in a must-use plugin: `add_filter( 'xmlrpc_enabled', '__return_false' );` (this only
disables authenticated methods; pingback methods stay unless you also filter
`xmlrpc_methods`).

## REST API user enumeration

`/wp-json/wp/v2/users` lists authors with published posts. To hide it for anonymous
visitors (keeps the editor working):

```php
add_filter( 'rest_endpoints', function ( $endpoints ) {
	if ( ! is_user_logged_in() ) {
		unset( $endpoints['/wp/v2/users'], $endpoints['/wp/v2/users/(?P<id>[\d]+)'] );
	}
	return $endpoints;
} );
```

Also block `?author=N` redirects if usernames are sensitive.

## Security headers

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
# CSP: start in report-only mode; WordPress admin and page builders need 'unsafe-inline'.
add_header Content-Security-Policy-Report-Only "default-src 'self'; img-src 'self' data: https:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:" always;
fastcgi_hide_header X-Powered-By;
server_tokens off;
```

Only add `preload` to HSTS when every subdomain serves HTTPS.

## Login protection

- 2FA for every administrator and shop manager (Two Factor plugin or the security
  plugin you already run).
- Rate-limit `wp-login.php` and `xmlrpc.php` at the server (`limit_req` in Nginx) or
  with a login-limiting plugin; fail2ban on the access log for VPS setups.
- Remove unused administrator accounts: `wp user list --role=administrator`.
- Application passwords: review with `wp user application-password list <user>`.

## Backups

Off-server, automated, versioned, with a tested restore. Database plus `wp-content`.
Keep at least one copy the web server user cannot delete.
