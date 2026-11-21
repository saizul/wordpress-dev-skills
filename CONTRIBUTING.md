# Contributing to WordPress Dev Skills

Thanks for helping! New skills, new scanner rules, better recipes, bug reports and
corrections of outdated WordPress advice are all welcome.

- [Ways to contribute](#ways-to-contribute)
- [Good first issues](#good-first-issues)
- [Development setup](#development-setup)
- [Write a skill](#write-a-skill)
- [Write a script](#write-a-script)
- [Pull request process](#pull-request-process)

## Ways to contribute

| Size | Idea |
| --- | --- |
| 10 minutes | Fix a typo, a wrong hook argument count or an outdated version number |
| 30 minutes | Add a false-positive/negative test case for a scanner rule |
| 1-2 hours | Add a scanner rule, a WP-CLI recipe or one of the good first issues |
| Larger | A new skill (open a "New skill proposal" issue first) |

Comment on an issue before you start so nobody else picks the same one.

## Good first issues

Each of these is self-contained.

1. **WPS019: `wp_ajax_nopriv_` handler that writes data.** Flag `nopriv` handlers that
   call `update_option`, `wp_insert_post` or `$wpdb->insert` without rate limiting
   hints. (`skills/wp-security-review/scripts/wp_security_scan.py`, tests, `references/rules.md`)
2. **Heredoc awareness in the security scanner.** Treat `<<<EOT ... EOT;` as a string
   so SQL inside heredocs is checked. (scanner, tests)
3. **HPOS: `$wpdb->postmeta` joins on order IDs.** New rule in `hpos_check.py` with
   fixture lines and a replacement in `references/hpos.md`.
4. **`analyze_options.py --sql` input.** Accept tab-separated output of
   `wp db query "SELECT option_name, LENGTH(option_value), autoload FROM wp_options" --skip-column-names`.
5. **block.json: validate `supports` keys** against the documented list and warn on
   unknown ones (typos like `colour`). (`validate_block_json.py`, tests)
6. **readme.txt: check `== Screenshots ==` numbering** (1., 2., 3. without gaps) and
   warn when a `Donate link:` is not a URL. (`readme_txt.py`, tests)
7. **wp-config: detect `WP_DEBUG` set from `getenv()`** and report it as "depends on
   environment" instead of unknown. (`check_wp_config.py`, tests)
8. **search-replace plan: www mismatch hint.** Warn when `--from` and `--to` differ only
   by `www.` and the site may store both forms. (`search_replace_plan.py`, tests)
9. **New reference: `wp-cli-ops/references/multisite.md`** with network-wide recipes,
   linked from the skill.
10. **Windows paths in the scaffold output** (`--dest` with backslashes) and a test.

## Development setup

```bash
git clone https://github.com/saizul/wordpress-dev-skills
cd wordpress-dev-skills
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install ruff pytest
python tools/validate_skills.py
pytest
ruff check . && ruff format --check .
```

Try a skill locally in Claude Code without installing the marketplace:
`claude --plugin-dir .` from the repository root, or copy one folder to
`.claude/skills/` in a test project.

## Write a skill

1. Open a "New skill proposal" issue describing the task, the trigger phrases and
   what the helper script (if any) would check.
2. Copy the template: `cp -r templates/skill skills/wp-your-skill` and rename `name:`
   to match the folder (lowercase, digits, single hyphens, max 64 characters).
3. Write the `description` (max 1024 characters): **what** it does (concrete tools,
   files, APIs) and **when** to use it ("Use when ..."). This is what agents match on.
4. Body: imperative steps, exact commands, decision points, a checklist, the output
   format, and "Not for" boundaries. Keep `SKILL.md` under 400 lines and move long
   material into `references/*.md`, linked from the body.
5. Add the skill to the table in `README.md`, to `metadata.skills` in
   `.claude-plugin/marketplace.json`, to the table in `AGENTS.md`, and to `CHANGELOG.md`.
6. Run the validator; it checks frontmatter, sections, links, tests and the marketplace.

Quality bar: every command must be correct for current WordPress, WP-CLI and
WooCommerce versions. Cite the minimum version when a feature is new
(e.g. "WP 6.5+"). Prefer read-only and dry-run steps first; mark commands that write.

## Write a script

- Python 3.9+ standard library only (or POSIX sh), in `skills/<skill>/scripts/`.
- `argparse` with a helpful `--help` and an example in the epilog.
- `--json` for structured output; exit 0 when clean, 1 for findings, 2 for usage errors.
- No network calls unless the skill's purpose needs it, and then opt-in by flag.
- Never print secrets; never write outside the target the user named; no overwrites
  without `--force`.
- Tests in `tests/test_<script_name>.py` using the helpers in `tests/conftest.py`
  (`load_script`, `run_script`). Cover the happy path, each rule, edge cases and exit codes.
- Each skill folder must stay self-contained (it is zipped and copied on its own), so
  do not import code from another skill.

## Pull request process

1. Branch from `main`, keep the PR focused, update docs and the changelog.
2. CI runs the validator, ruff and pytest on Python 3.11-3.13; all must pass.
3. A maintainer reviews within a few days. Squash-merge is used; releases are tagged
   `vX.Y.Z` and the release workflow attaches skill zips.

By contributing you agree that your work is released under the MIT License.
