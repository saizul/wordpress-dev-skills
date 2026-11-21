# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## What counts as a vulnerability

- A script that writes, deletes or executes something without being asked to
  (for example the scaffold overwriting files without `--force`)
- A script printing secrets such as wp-config.php passwords, keys or salts
- Command injection through file names, option names or arguments in printed
  WP-CLI commands (they are meant to be safely shell-quoted)
- Path traversal: a script reading or writing outside the path it was given
- Skill instructions that would lead an agent to weaken a site's security
  (for example disabling escaping or recommending 777 permissions)

A scanner rule that misses a vulnerable pattern (false negative) is a bug, not a
security vulnerability: please open a normal issue with a code sample.

## Reporting

Please **do not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/saizul/wordpress-dev-skills/security/advisories/new)
with the version, the impact and steps to reproduce. Do not include real credentials,
customer data or private site URLs.

You will get an answer within 5 working days. Fixes are released as soon as possible
and credited in the changelog unless you prefer otherwise.
