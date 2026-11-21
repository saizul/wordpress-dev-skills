## What does this pull request do?

<!-- One or two sentences. Link the issue: "Closes #123". -->

## Type

- [ ] New skill
- [ ] New or changed scanner/validator rule
- [ ] Skill content (workflow, recipes, references)
- [ ] Bug fix
- [ ] Documentation / repository tooling

## Checklist

- [ ] `python tools/validate_skills.py` passes
- [ ] `pytest` passes and new behaviour has tests
- [ ] `ruff check . && ruff format --check .` passes
- [ ] Commands and APIs are correct for current WordPress / WP-CLI / WooCommerce; minimum
      versions are stated for new features
- [ ] Scripts stay stdlib-only, read-only/dry-run by default, and never print secrets
- [ ] New skills are listed in README.md, AGENTS.md and `.claude-plugin/marketplace.json`
- [ ] CHANGELOG.md updated under "Unreleased"
