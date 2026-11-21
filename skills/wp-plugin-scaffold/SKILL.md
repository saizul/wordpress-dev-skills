---
name: wp-plugin-scaffold
description: Create a modern WordPress plugin skeleton - namespaced PSR-4 classes with Composer autoload (plus a fallback autoloader), a Settings API page that follows nonce/capability/sanitize/escape rules, uninstall.php, PHPCS with WordPress-Extra and PHPCompatibilityWP, PHPUnit with Brain Monkey unit tests, GitHub Actions CI, readme.txt and .distignore. Includes a generator script. Use when starting a new WordPress plugin, restructuring a single-file plugin into classes, or adding coding standards, tests and CI to an existing plugin.
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Modern WordPress plugin scaffold

Script paths below are relative to this skill's directory.

## When to use

- Starting a plugin (client project, product, WordPress.org submission).
- Converting a "everything in one file" plugin to namespaced classes.
- Adding PHPCS, PHPUnit and CI to an existing plugin (generate into a temp folder and
  copy the tooling files).

Not for: block-only plugins (start with `npx @wordpress/create-block`, see
`wp-block-dev`), themes, or must-use plugins that are a few lines long.

## Workflow

1. **Collect inputs** (ask if missing): slug (folder + text domain), human name,
   PHP namespace (`Vendor\Plugin`), option/hook prefix, author, minimum WP/PHP versions.
   Check the slug is free on WordPress.org if the plugin will be published there:
   `https://wordpress.org/plugins/<slug>/` should 404.
2. **Preview, then generate**:
   ```bash
   python3 scripts/scaffold_plugin.py acme-reviews --name "Acme Reviews" \
     --namespace "Acme\\Reviews" --prefix acme_reviews --author "Acme Ltd" \
     --requires-wp 6.5 --requires-php 7.4 --dest wp-content/plugins --dry-run
   python3 scripts/scaffold_plugin.py acme-reviews ...same options... --dest wp-content/plugins
   ```
   Existing files are never overwritten without `--force`. `--json` prints the file list.
3. **Install tooling and verify** (needs Composer and network):
   ```bash
   cd wp-content/plugins/acme-reviews
   composer install
   composer lint     # phpcs: WordPress-Extra, WordPress-Docs, PHPCompatibilityWP
   composer test     # phpunit + Brain Monkey, no database needed
   ```
   The generated skeleton passes both out of the box. Fix anything you add with
   `composer lint:fix` (phpcbf) and then by hand.
4. **Activate**: `wp plugin activate acme-reviews`; open Settings > Acme Reviews.
5. **Build features** in `src/` (one class per responsibility, hooks registered in
   `Plugin::boot()`). Follow the rules below and review with `wp-security-review`.
6. **Release**: validate readme.txt with `wp-readme-txt`; create the zip with
   `wp dist-archive .` (WP-CLI package `wp-cli/dist-archive-command`, honours
   `.distignore`) or `git archive`.

## What gets generated

```
acme-reviews/
  acme-reviews.php          header, constants, autoloader, activation hooks
  src/Plugin.php            singleton that wires hooks; settings helper
  src/Admin/Settings.php    Settings API page (nonce + capability via options.php)
  uninstall.php             removes the plugin option
  composer.json             PSR-4 autoload, dev tools, lint/test scripts
  phpcs.xml.dist            WPCS 3 rules, text domain + prefix checks, PHP version
  phpunit.xml.dist          unit suite in tests/Unit
  tests/bootstrap.php, tests/Unit/PluginTest.php
  .github/workflows/ci.yml  PHP matrix: lint + tests
  readme.txt, .distignore, .editorconfig, .gitignore, languages/
```

## Rules the skeleton follows (keep following them)

- Every PHP file starts with `defined( 'ABSPATH' ) || exit;` (except uninstall.php,
  which checks `WP_UNINSTALL_PLUGIN`).
- Prefix everything global (options, hooks, transients, cron hooks, AJAX actions)
  with the plugin prefix; classes live in the namespace.
- Add options with autoload off unless they are needed on every request
  (`add_option( $name, $value, '', false )`).
- Register hooks on `plugins_loaded`/`init`; do no work at file load time.
- Sanitize on input (`sanitize_callback`), escape on output, check capabilities and
  nonces for every state change.
- Load translations with the text domain equal to the slug.
- Clean up in uninstall.php, not on deactivation (users deactivate to debug).

More patterns (REST controller, CLI command, cron, custom tables, assets):
[references/structure.md](references/structure.md).
