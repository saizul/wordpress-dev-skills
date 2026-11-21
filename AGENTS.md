# AGENTS.md

Instructions for coding agents (OpenAI Codex, Claude Code, Cursor, Gemini CLI and other
Agent Skills clients) working with or inside this repository.

## Using the skills

- Skills live in `skills/<name>/SKILL.md`. Read the frontmatter `description` to decide
  whether a skill applies; when it does, read the whole `SKILL.md` and follow its
  workflow in order.
- Paths inside a skill (`scripts/...`, `references/...`) are relative to that skill's
  folder. Run scripts with `python3 <skill-dir>/scripts/<script>.py --help` first.
- Open `references/*.md` only when a workflow step points to it.
- Scripts are read-only or dry-run by default. Commands that write to a database or a
  live site are printed for review; ask the user before running them.
- Never print or paste secrets (wp-config values, API keys, passwords) into output,
  commits or issues.

| Task | Skill |
| --- | --- |
| New plugin, add PHPCS/PHPUnit/CI | `wp-plugin-scaffold` |
| Review plugin/theme code for vulnerabilities | `wp-security-review` |
| WP-CLI commands, migrations, search-replace, cron, cache | `wp-cli-ops` |
| Slow site, autoload bloat, object cache | `wp-performance-audit` |
| Gutenberg blocks, block.json | `wp-block-dev` |
| WooCommerce code, HPOS, hooks | `woocommerce-dev` |
| wp-config, permissions, headers, XML-RPC | `wp-hardening` |
| WordPress.org readme.txt | `wp-readme-txt` |

## Installing for Codex

Copy skill folders into `.agents/skills/` in the target repository or into
`$HOME/.agents/skills/`. Codex scans `.agents/skills` from the current directory up to
the repository root.

## Working on this repository

- Python 3.9+ stdlib only in `skills/*/scripts/` and `tools/`; no network calls.
- Every script needs `--help`, a `--json` option where output is structured, meaningful
  exit codes, and tests in `tests/test_<script>.py`.
- Keep each `SKILL.md` under 400 lines with `## When to use` and `## Workflow` sections.
- Before finishing a change run:

```bash
python tools/validate_skills.py
pytest
ruff check .
ruff format --check .
```

- Add a line to `CHANGELOG.md` under "Unreleased" for user-visible changes, and list new
  skills in `README.md` and in `.claude-plugin/marketplace.json` (`metadata.skills`).
