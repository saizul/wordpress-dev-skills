---
name: wp-performance-audit
description: Diagnose slow WordPress sites from the server side - autoloaded options bloat, slow and repeated database queries, missing persistent object cache, WP-Cron overload, heavy plugins and front-end assets. Includes a script that analyzes `wp option list` output and prints the biggest autoloaded options with safe follow-up commands. Use when a WordPress site has slow TTFB, a slow admin, high database CPU, a Site Health "autoloaded options" warning, or before/after a hosting migration.
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# WordPress performance audit

Script paths below are relative to this skill's directory. Every step is read-only
unless marked (writes).

## When to use

- TTFB over ~600 ms on uncached pages, slow wp-admin, high MySQL CPU.
- Site Health warns about autoloaded options or a missing object cache.
- After installing a big plugin, or before choosing hosting/caching.

Not for: Core Web Vitals of front-end rendering alone (use Lighthouse/PageSpeed and
fix images, fonts, JS), or load testing.

## Workflow

1. **Baseline** an uncached request (bypass page cache with a query string):
   ```bash
   curl -s -o /dev/null -w "TTFB %{time_starttransfer}s total %{time_total}s\n" "https://example.com/?nocache=$(date +%s)"
   wp core version && wp plugin list --status=active --format=count
   wp eval 'echo wp_using_ext_object_cache() ? "object cache: persistent\n" : "object cache: none\n";'
   ```
2. **Autoloaded options** (the most common server-side problem):
   ```bash
   wp option list --fields=option_name,size_bytes,autoload --format=json > options.json
   python3 scripts/analyze_options.py options.json            # text report
   python3 scripts/analyze_options.py options.json --json     # machine-readable
   ```
   The report shows total autoload size against an 800 KB threshold (the value Site
   Health uses), the largest options, totals per prefix (which usually identifies the
   plugin), autoloaded transients, and `wp option get-autoload` / `set-autoload ... off`
   commands for large non-core options. Exit code 1 means the total or an option is over
   the limits (`--threshold`, `--large`).
   Before turning autoload off, confirm the owner plugin does not read the option on
   every request (otherwise you trade one big query for many). Options left by
   uninstalled plugins can be deleted (writes): `wp option delete <name>` after a backup.
3. **Object cache.** No persistent cache on a dynamic site (WooCommerce, membership,
   busy admin) is the next biggest win: Redis or Memcached plus a drop-in
   (`wp-content/object-cache.php`). Check `wp cache type`.
4. **Database queries.** Install Query Monitor on staging (or production for an admin
   session) and look at: slow queries, duplicate queries, queries by component.
   Without a UI:
   ```bash
   wp db size --tables --human-readable                       # bloated tables (sessions, logs, actionscheduler)
   wp db query "SELECT COUNT(*) FROM $(wp db prefix)postmeta"
   ```
   See [references/checklist.md](references/checklist.md) for slow query log setup and
   index checks.
5. **Cron.** `wp cron event list --format=count`, `wp cron test`. Thousands of events or
   overdue events on every request: move to system cron (see `wp-cli-ops`).
6. **Plugins.** `wp profile stage --all` / `wp profile hook --all --spotlight` (package
   `wp-cli/profile-command`) shows which hooks/plugins cost time. Deactivate on staging
   to confirm, never guess on production.
7. **Assets.** Count scripts/styles per page (Query Monitor "Scripts"), look for plugins
   loading everything on every page; dequeue conditionally with `wp_dequeue_script()`.
8. **Report** using the format below and re-measure after each change.

## Output format

```
## Performance audit: example.com (WP 6.x, PHP 8.x, 38 plugins)
Baseline TTFB (uncached): 1.8 s
| Area | Finding | Impact | Fix | Risk |
| Autoload | 3.4 MB autoloaded; 2.1 MB in "rank_math" options | high | set-autoload off for X, Y | low |
| Object cache | none | high | Redis + drop-in | low |
...
Next steps in order, then re-measure.
```

Only recommend changes you can justify with a number from the audit.
