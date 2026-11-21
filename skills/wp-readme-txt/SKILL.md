---
name: wp-readme-txt
description: Write, generate and validate the readme.txt that WordPress.org uses for a plugin's directory page - header fields (Contributors, Tags, Requires at least, Tested up to, Stable tag, Requires PHP, License), the 150-character short description, sections, changelog and upgrade notices. Includes a script that generates a readme.txt from the plugin header and validates an existing one, including Stable tag vs plugin Version. Use when preparing a WordPress.org submission or release, bumping "Tested up to", or when the plugin page shows wrong data.
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# WordPress.org readme.txt

Script paths below are relative to this skill's directory.

## When to use

- Submitting a plugin to WordPress.org, tagging a release, bumping "Tested up to".
- The directory page shows an old version, missing sections or a cut-off description.

Not for: GitHub README.md files (no header rules apply), theme readmes (themes use
`style.css` headers and a different readme format).

## Workflow

1. **New readme**: generate from the main plugin file header (Plugin Name,
   Description, Version, Requires at least, Requires PHP, License):
   ```bash
   python3 scripts/readme_txt.py generate my-plugin.php \
     --contributors mywporgname --tags "seo, schema, faq" --tested-up-to 6.8 -o readme.txt
   ```
   It refuses to overwrite without `--force`. Then write the real Description, FAQ,
   Screenshots and Changelog content.
2. **Validate** (always before tagging):
   ```bash
   python3 scripts/readme_txt.py validate readme.txt --plugin-file my-plugin.php
   python3 scripts/readme_txt.py validate readme.txt --plugin-file my-plugin.php --wp-latest 6.8 --strict --json
   ```
   Errors exit 1. Checks: `=== Name ===` line, required headers, contributor usernames,
   at most 5 tags, numeric versions, Tested up to as a major version, Stable tag not
   `trunk` and equal to the plugin `Version`, Requires at least / Requires PHP matching
   the plugin header, short description present, at most 150 characters and no markup,
   a Description section, a changelog entry for the Stable tag, upgrade notices under
   300 characters, file under 10 KB, GPL-compatible license.
3. **Release checklist**:
   - [ ] `Version:` in the plugin header, `Stable tag:` and any version constant all match.
   - [ ] Changelog entry added (`= 1.2.0 =`).
   - [ ] `Tested up to:` is the current major WordPress version you actually tested.
   - [ ] SVN: copy trunk to `tags/<version>`; the directory reads readme.txt from the
         Stable tag's folder, so edit it there for readme-only changes.
   - [ ] Assets (banner, icon, screenshots) live in the SVN `/assets` folder, not the plugin zip.
4. **Report** the validator output and the final header block.

## Writing guidance

- Short description: one sentence on what it does for the user, no keyword stuffing,
  no markup, at most 150 characters.
- Tags: 1-5 terms people search for; no competitor names; tags only your plugin uses
  are not shown.
- Contributors: WordPress.org usernames (case-sensitive), not display names.
- Description: problem, features as a list, who it is for, privacy note if the plugin
  calls external services (required by the guidelines when data leaves the site).
- FAQ: real support questions. Screenshots: `1. Caption` maps to
  `assets/screenshot-1.png` in SVN.
- Keep the readme under 10 KB: move old changelog entries to `changelog.txt`.

Full field reference and a template: [references/readme-format.md](references/readme-format.md).
