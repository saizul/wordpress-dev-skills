# WordPress Dev Skills

[![CI](https://github.com/saizul/wordpress-dev-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/wordpress-dev-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/saizul/wordpress-dev-skills?sort=semver)](https://github.com/saizul/wordpress-dev-skills/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/saizul/wordpress-dev-skills?style=social)](https://github.com/saizul/wordpress-dev-skills/stargazers)

**Agent Skills that make Claude Code, Codex and other coding agents work like a senior
WordPress developer: secure by default, WP-CLI safe, HPOS-ready.**

Eight focused skills, each with a step-by-step workflow, checklists and a tested,
dependency-free helper script (Python 3 stdlib). Scripts are read-only or dry-run by
default and never print secrets.

## Skills

| Skill | What it does | Try asking |
| --- | --- | --- |
| [wp-plugin-scaffold](skills/wp-plugin-scaffold/SKILL.md) | Generates a modern plugin: namespaces, Composer PSR-4 + fallback autoloader, Settings API page, PHPCS (WordPress-Extra), PHPUnit + Brain Monkey, GitHub Actions, readme.txt | "Scaffold a plugin called Acme Reviews with namespace Acme\Reviews" |
| [wp-security-review](skills/wp-security-review/SKILL.md) | Audits escaping, sanitizing, nonces, capabilities, `$wpdb->prepare()`, REST `permission_callback`; scanner with 18 rules, JSON and SARIF output | "Security-review wp-content/plugins/my-plugin before I submit it" |
| [wp-cli-ops](skills/wp-cli-ops/SKILL.md) | Safe WP-CLI recipes; plans domain migrations with backup, dry runs and JSON-escaped/URL-encoded variants | "Move this site from staging.example.com to example.com" |
| [wp-performance-audit](skills/wp-performance-audit/SKILL.md) | Server-side performance audit; analyzes `wp option list` output for autoload bloat | "Why is TTFB 2 seconds? Here is wp option list output" |
| [wp-block-dev](skills/wp-block-dev/SKILL.md) | block.json (apiVersion 3), dynamic blocks, @wordpress/scripts, deprecations, Interactivity API; block.json validator | "Create a dynamic block that lists the latest 3 reviews" |
| [woocommerce-dev](skills/woocommerce-dev/SKILL.md) | CRUD-first WooCommerce code, hook map, HPOS and Cart/Checkout blocks compatibility; HPOS scanner | "Make my extension HPOS compatible" |
| [wp-hardening](skills/wp-hardening/SKILL.md) | wp-config constants, permissions, leaked files, XML-RPC, REST user enumeration, security headers; wp-config checker | "Harden this WordPress install at /var/www/site" |
| [wp-readme-txt](skills/wp-readme-txt/SKILL.md) | Generates and validates WordPress.org readme.txt (tags, 150-char short description, Stable tag vs Version) | "Prepare readme.txt for the 1.2.0 release" |

## Install

### Claude Code: plugin marketplace (recommended)

```text
/plugin marketplace add saizul/wordpress-dev-skills
/plugin install wp-dev@wordpress-dev-skills
```

Or from your shell: `claude plugin marketplace add saizul/wordpress-dev-skills` then
`claude plugin install wp-dev@wordpress-dev-skills`. Skills are namespaced by the plugin,
for example `/wp-dev:wp-security-review`. Update later with `/plugin marketplace update`.

### Claude Code: copy skills manually

```bash
git clone https://github.com/saizul/wordpress-dev-skills
# for you, in every project:
mkdir -p ~/.claude/skills && cp -r wordpress-dev-skills/skills/* ~/.claude/skills/
# or for one project (commit it so your team gets them):
mkdir -p .claude/skills && cp -r wordpress-dev-skills/skills/wp-security-review .claude/skills/
```

Each release also attaches one zip per skill and an all-skills zip.

### OpenAI Codex

Codex reads skills from `.agents/skills` in your repository (and parent directories up
to the repo root) and from `$HOME/.agents/skills` for your user
([Codex skills docs](https://developers.openai.com/codex/skills)):

```bash
git clone https://github.com/saizul/wordpress-dev-skills
mkdir -p ~/.agents/skills && cp -r wordpress-dev-skills/skills/* ~/.agents/skills/
# or per repository:
mkdir -p .agents/skills && cp -r wordpress-dev-skills/skills/wp-cli-ops .agents/skills/
```

Restart Codex if a new skill does not show up. See [AGENTS.md](AGENTS.md) for how agents
should use the skills.

### Other agents

The skills follow the open [Agent Skills format](https://agentskills.io/specification):
a folder with `SKILL.md` (YAML frontmatter + instructions) and optional `scripts/` and
`references/`. Any client that supports the format can load them; the scripts also run
on their own:

```bash
python3 skills/wp-security-review/scripts/wp_security_scan.py path/to/plugin --format sarif
```

## Usage examples

```text
> Review the AJAX handlers in includes/ for security problems and fix what you find.
  (wp-security-review: runs the scanner, triages findings, checks each entry point)

> We are moving shop.example.com to example.com tonight. Give me the exact commands.
  (wp-cli-ops: backup, dry runs for plain/JSON-escaped/URL-encoded URLs, apply, verify)

> wp option list --fields=option_name,size_bytes,autoload --format=json > options.json
> Analyze options.json and tell me what to turn off.
  (wp-performance-audit: totals, top options, owner prefixes, safe set-autoload commands)
```

Script cheat sheet (all support `--help`, `--json`, and non-zero exit codes for CI):

| Script | Purpose | Exit 1 when |
| --- | --- | --- |
| `wp-plugin-scaffold/scripts/scaffold_plugin.py` | create a plugin | target files exist (no `--force`) |
| `wp-security-review/scripts/wp_security_scan.py` | security scanner (text/JSON/SARIF) | findings >= `--fail-on` |
| `wp-cli-ops/scripts/search_replace_plan.py` | migration plan | warnings with `--strict` |
| `wp-performance-audit/scripts/analyze_options.py` | autoload analysis | over threshold / large options |
| `wp-block-dev/scripts/validate_block_json.py` | block.json validator | errors (or warnings with `--strict`) |
| `woocommerce-dev/scripts/hpos_check.py` | HPOS scanner | findings >= `--fail-on` |
| `wp-hardening/scripts/check_wp_config.py` | wp-config and web root audit | findings >= `--fail-on` |
| `wp-readme-txt/scripts/readme_txt.py` | readme.txt generate/validate | errors (or warnings with `--strict`) |

Use them in your plugin's CI, for example:

```yaml
- name: Security scan (fails the job on high/critical findings)
  run: python3 wordpress-dev-skills/skills/wp-security-review/scripts/wp_security_scan.py . --fail-on high
- name: SARIF for GitHub code scanning
  if: always()
  run: python3 wordpress-dev-skills/skills/wp-security-review/scripts/wp_security_scan.py . --format sarif > wpsec.sarif || true
- uses: github/codeql-action/upload-sarif@v3
  if: always()
  with: { sarif_file: wpsec.sarif }
```

## How skills work

At startup the agent only sees each skill's `name` and `description` (a few dozen
tokens). When your request matches a description, it loads that `SKILL.md`, follows the
workflow, and opens `references/*.md` or runs `scripts/*` only when a step needs them.
That keeps context small while giving the agent precise, tested procedures instead of
guesses.

```
skills/wp-security-review/
  SKILL.md              when to use, workflow, checklist, output format
  scripts/wp_security_scan.py
  references/patterns.md, references/rules.md
```

## FAQ

**Do the scripts need anything installed?** Python 3.9+ only. Generated plugins need
Composer to install PHPCS/PHPUnit; block development needs Node for `@wordpress/scripts`.

**Will they change my site?** No script writes to a database or a live site. The
scaffold writes new files (never overwrites without `--force`); the readme generator
writes only with `-o`. WP-CLI commands are printed for you to review, with writing
steps marked.

**Is the security scanner a replacement for PHPCS or a pentest?** No. It is a fast,
explainable first pass that points at lines to read. The skill tells the agent to
triage every finding and to run PHPCS with the WordPress security sniffs.

**Do secrets ever leave my machine?** The scripts make no network calls, and the
wp-config checker reports only whether secrets are set, never their values.

**Can I use only one skill?** Yes. Copy a single folder; each is self-contained.

## Roadmap

Ideas for new skills and features. Issues tagged
[good first issue](https://github.com/saizul/wordpress-dev-skills/labels/good%20first%20issue)
are a great place to start:

- [ ] `wp-theme-json`: build and validate theme.json for block themes
- [ ] `wp-rest-api`: design custom endpoints, schemas and authentication (application passwords, JWT)
- [ ] `wp-multisite-ops`: network-wide WP-CLI recipes and domain mapping
- [ ] `wp-i18n`: make-pot/make-json workflow, text domain checker script
- [ ] `wp-env-testing`: `@wordpress/env` + integration tests + Playwright e2e
- [ ] `wp-cron-debug`: script to analyze `wp cron event list` output for duplicates
- [ ] `woocommerce-payments-dev`: payment gateway skeleton with Store API/blocks support
- [ ] Security scanner: heredoc support and taint tracking across lines in one function
- [ ] HPOS scanner: detect `$wpdb->postmeta` joins for order meta

## Contributing

New skills, rules and fixes are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), copy
[templates/skill/SKILL.md](templates/skill/SKILL.md), then run:

```bash
python -m pip install ruff pytest
python tools/validate_skills.py && pytest && ruff check . && ruff format --check .
```

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report vulnerabilities
privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © Saizul Amin. WordPress is a registered trademark of the WordPress
Foundation; this project is not affiliated with or endorsed by it, Automattic or
WooCommerce.
