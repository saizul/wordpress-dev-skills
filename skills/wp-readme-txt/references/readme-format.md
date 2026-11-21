# readme.txt format

Source: WordPress Plugin Handbook, "How Your Plugin Readme.txt Works".

## Header fields

| Field | Required | Rule |
| --- | --- | --- |
| `=== Plugin Name ===` | yes | First line; should match the `Plugin Name:` header |
| `Contributors:` | yes | Comma-separated WordPress.org usernames (case-sensitive) |
| `Donate link:` | no | URL shown in the sidebar |
| `Tags:` | recommended | 1 to 5 comma-separated terms |
| `Requires at least:` | recommended | Minimum WordPress version, numbers only |
| `Tested up to:` | yes | Major WordPress version, numbers only (6.8, not "WP 6.8") |
| `Requires PHP:` | recommended | Minimum PHP version, numbers only |
| `Stable tag:` | yes | The plugin version in `tags/`; numbers and periods; `trunk` discouraged |
| `License:` | yes | GPLv2 or later, or a GPL-compatible license |
| `License URI:` | recommended | URL of the license text |

The plugin header (main PHP file) is authoritative for `Requires at least` and
`Requires PHP` when both are set; keep them identical to avoid confusion.

## Body

```
=== My Plugin ===
Contributors: myusername
Tags: forms, contact
Requires at least: 6.5
Tested up to: 6.8
Requires PHP: 7.4
Stable tag: 1.2.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

One sentence, at most 150 characters, plain text: what the plugin does.

== Description ==

Longer description. Markdown-style formatting is supported:
**bold**, *italic*, [links](https://example.com), lists with `*` or `1.`.

= Subheading =

More text.

== Installation ==

1. Upload or install from Plugins > Add New.
2. Activate.

== Frequently Asked Questions ==

= A question? =

An answer.

== Screenshots ==

1. Caption for assets/screenshot-1.png

== Changelog ==

= 1.2.0 =
* Added: ...
* Fixed: ...

== Upgrade Notice ==

= 1.2.0 =
Short reason to upgrade (at most 300 characters).
```

## Common rejections and surprises

- Stable tag points to a version with no `tags/<version>` folder: the directory shows
  the old version or trunk.
- Readme edited in trunk only: if Stable tag is a version, the page reads the readme
  from that tag folder.
- "Tested up to" more than a few major versions behind: users see a "not tested with
  the latest releases" notice.
- Calling external services without documenting them in the readme (what, when, links
  to terms and privacy policy) violates the plugin guidelines.
