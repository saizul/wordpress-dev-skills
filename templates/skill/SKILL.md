---
name: wp-your-skill
description: One or two sentences on WHAT the skill does, naming the concrete tools, files and APIs it covers. Use when ... (list the situations and phrases that should trigger it).
license: MIT
metadata:
  author: Your Name
  version: "0.1.0"
---

# Title

Script paths below are relative to this skill's directory.

## When to use

- Situation 1 (what the user is doing or asking).
- Situation 2.

Not for: neighbouring tasks and which skill or tool handles them instead.

## Workflow

1. **Gather facts** (read-only commands first):
   ```bash
   wp core version
   ```
2. **Run the helper** if the skill has one:
   ```bash
   python3 scripts/your_script.py path --json
   ```
3. **Decide**: explain the decision points and what to do in each case.
4. **Change** only after the user confirms anything irreversible; back up first.
5. **Verify** with a command that proves the result.

## Checklist

- [ ] Item the agent must check every time.

## Output format

Describe exactly what the agent should hand back (table, patch, commands in order).

Long reference material goes in [references/](references/) and is linked from here.
