---
name: wp-cli-ops
description: Safe WP-CLI recipes for WordPress operations - domain/URL migrations with search-replace (backup and dry run first, JSON-escaped and URL-encoded variants), database export/import, cron inspection, cache and transient flushing, plugin/core updates, maintenance mode and debugging a broken site. Includes a planner script that prints a reviewed, shell-quoted search-replace plan. Use when moving a site to a new domain or from staging to production, running WP-CLI on a live site, fixing WP-Cron, or when the user asks for a wp command.
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# WP-CLI operations, safely

Script paths below are relative to this skill's directory.

## When to use

- Moving a site to a new domain, from HTTP to HTTPS, or from staging to production.
- Running maintenance on a live site: updates, database work, cron, caches, users.
- A site is broken and wp-admin is unreachable.

Not for: provisioning servers or installing WP-CLI itself, and hosting control panels
that replace WP-CLI with their own tools.

## Ground rules (apply to every recipe)

1. **Know where you are.** Run `wp option get home` and `wp core version` first; on
   multisite `wp site list`. Never assume the environment.
2. **Back up before writing:** `wp db export backup-$(date +%Y%m%d-%H%M%S).sql`.
   Keep the dump outside the web root.
3. **Dry run first** whenever the command supports it (`search-replace --dry-run`,
   `plugin update --dry-run`, `media regenerate` on one ID first).
4. **Run as the web server user** (or the site owner) so new files get the right
   owner: `sudo -u www-data wp ...`. Avoid `--allow-root`.
5. **Do not paste secrets** into commands that end up in shell history; WP-CLI reads
   DB credentials from wp-config.php.
6. **Broken site?** Add `--skip-plugins --skip-themes` to get WP-CLI to load at all.

## Workflow: domain / URL migration

1. Generate the plan (the script never runs anything):
   ```bash
   python3 scripts/search_replace_plan.py --from https://staging.example.com --to https://example.com
   python3 scripts/search_replace_plan.py --from https://old.example --to https://new.example --apply-steps > migrate.sh
   python3 scripts/search_replace_plan.py --from http://example.com --to https://example.com --network --apply-steps
   ```
   Options: `--network` / `--url=` for multisite, `--all-tables` for non-prefixed
   tables, `--ssh=user@host/path` for a remote alias, `--export=file.sql` to write a
   migrated dump instead of changing the live DB, `--json` for machine output,
   `--strict` to exit 1 on warnings.
2. Read the warnings. The important ones: trailing slash mismatch, and the new value
   containing the old one (`example.com` -> `example.com.au`) which corrupts URLs if
   the replacement runs twice.
3. Run the backup and the dry runs; check the "replacements" counts per table look sane.
4. Run the apply steps, then the verification dry run (should report 0).
5. Flush caches (object cache, page cache plugin, CDN) and test login, a post, media
   URLs and a form.

What the plan covers and why: `--precise` (PHP-level replace, handles serialized data
inside non-serialized columns), `--skip-columns=guid` (GUIDs must not change),
`--all-tables-with-prefix` (custom plugin tables), JSON-escaped `https:\/\/` for block
attributes and page builders, URL-encoded `https%3A%2F%2F` for query strings.

## Other recipes

See [references/recipes.md](references/recipes.md) for copy-ready commands:
database (export/import/optimize, find big tables), cron (list, run due events,
switch to system cron), cache and transients, updates with rollback, users
(reset a locked-out admin), maintenance mode, debugging (`wp eval`, `wp shell`,
`--debug`), media regeneration, multisite loops.

## Decision points

- Is the change reversible? If not (deletes, search-replace, `db reset`), back up and
  confirm with the user before running.
- Live site with traffic? Use `wp maintenance-mode activate` for multi-step DB work,
  and do it off-peak.
- `wp search-replace` vs SQL `REPLACE()`: always WP-CLI. SQL breaks serialized string
  lengths.
- Plugin update failing on production? Update on staging, commit/deploy, or use
  `wp plugin update <slug> --version=<x>` to pin; roll back with
  `wp plugin install <slug> --version=<previous> --force`.

## Output

Give the user the exact commands in order, mark which ones write data, and state the
backup file name. After running, report the counts WP-CLI printed.
