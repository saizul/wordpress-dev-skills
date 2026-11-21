# Performance checklist and queries

## Autoload facts

- All autoloaded options are fetched in one query and cached as a single
  `alloptions` entry. With a persistent object cache, a multi-megabyte `alloptions`
  is read and unserialized on every request, and some caches have a 1 MB item limit
  (Memcached default), which makes the entry fail to cache at all.
- WordPress 6.6+ stores `on`, `off`, `auto`, `auto-on`, `auto-off` (older sites `yes`/`no`).
  `auto` lets core decide; core no longer autoloads newly added large options
  (over 150 KB by default, filter `wp_max_autoloaded_option_size`).
- `wp option set-autoload <name> off` / `wp option get-autoload <name>` change or show
  one option.

SQL equivalent (read-only) when WP-CLI is unavailable:

```sql
SELECT option_name, LENGTH(option_value) AS bytes
FROM wp_options
WHERE autoload IN ('yes', 'on', 'auto-on', 'auto')
ORDER BY bytes DESC
LIMIT 20;
```

## Common bloat sources

| Pattern | Usual cause | Fix |
| --- | --- | --- |
| `_transient_*` autoloaded | `set_transient()` without expiration | Delete expired; fix the plugin to pass an expiration |
| `rewrite_rules` > 500 KB | Many CPTs/taxonomies, or rules regenerated on every request | `wp rewrite flush`; find code calling `flush_rewrite_rules()` on `init` |
| `cron` > 500 KB | Duplicate scheduled events | `wp cron event list`, delete duplicates, fix scheduling code |
| Options of removed plugins | Plugins without uninstall cleanup | Back up, then `wp option delete` |
| Page-builder/SEO settings | Large arrays saved as one option | `set-autoload off` if not needed on the front end |

## Slow query log (MySQL/MariaDB)

```sql
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.5;
SHOW VARIABLES LIKE 'slow_query_log_file';
```

Summarize with `mysqldumpslow -s t -t 20 /var/log/mysql/mysql-slow.log` or
`pt-query-digest`. Turn it off afterwards.

## Index checks

```sql
SHOW INDEX FROM wp_postmeta;     -- expect meta_key index; large sites benefit from (meta_key, post_id)
SHOW TABLE STATUS WHERE Data_free > 100*1024*1024;  -- fragmented tables
```

Plugin "Index WP MySQL For Speed" adds better indexes to core tables; test on staging.

## Big tables to look at

`wp_actionscheduler_actions` / `_logs` (WooCommerce), `wp_wc_sessions`,
`wp_options` itself, `wp_postmeta`, security/log plugin tables, `wp_comments` spam.
Prune with the owning plugin's tools when possible.

## PHP and server

- PHP 8.1+ with OPcache enabled (`opcache.memory_consumption` >= 128,
  `opcache.max_accelerated_files` >= 10000).
- `WP_MEMORY_LIMIT` 256M only if needed; memory is not speed.
- PHP-FPM `pm.max_children` sized to RAM; queueing workers look like slow TTFB.
- Full-page cache (plugin, Nginx FastCGI cache, or CDN) for anonymous traffic; exclude
  cart/checkout/my-account and logged-in users.

## Front-end quick wins

- Images: WebP/AVIF, correct `sizes`, lazy-load below the fold, no lazy-load on the LCP image.
- Fonts: self-host, `font-display: swap`, preload one or two files at most.
- JS: defer non-critical, remove jQuery-dependent plugins from pages that do not need them.
- Use `wp_enqueue_script( ..., array( 'strategy' => 'defer' ) )` (WP 6.3+).
