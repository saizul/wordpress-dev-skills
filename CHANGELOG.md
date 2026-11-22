# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `woocommerce-dev`: `hpos_check.py` rule HPOS011 flags SQL that reads or joins
  `$wpdb->postmeta` for order meta (order meta keys such as `_billing_email`, `$order_id`
  or `shop_order`), also when the query spans several lines or contains `;` in the SQL.

## [0.1.0] - 2026-11-21

### Added

- `wp-plugin-scaffold` skill with `scaffold_plugin.py`: namespaced plugin, Composer
  PSR-4 + fallback autoloader, Settings API page, PHPCS (WordPress-Extra,
  PHPCompatibilityWP), PHPUnit + Brain Monkey, GitHub Actions, readme.txt.
- `wp-security-review` skill with `wp_security_scan.py`: 18 rules, text/JSON/SARIF
  output, `wpsec-ignore` and matching `phpcs:ignore` suppressions.
- `wp-cli-ops` skill with `search_replace_plan.py` and a recipe reference.
- `wp-performance-audit` skill with `analyze_options.py` for `wp option list` output
  (WordPress 6.6+ autoload values).
- `wp-block-dev` skill with `validate_block_json.py`.
- `woocommerce-dev` skill with `hpos_check.py`, HPOS replacements and a hook map.
- `wp-hardening` skill with `check_wp_config.py` (never prints secrets).
- `wp-readme-txt` skill with `readme_txt.py` (generate and validate).
- Claude Code plugin marketplace (`wp-dev@wordpress-dev-skills`), `AGENTS.md` for
  Codex and other agents, `tools/validate_skills.py`, CI and release workflows.

[Unreleased]: https://github.com/saizul/wordpress-dev-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saizul/wordpress-dev-skills/releases/tag/v0.1.0
