---
name: wp-block-dev
description: Build Gutenberg blocks the modern way - block.json metadata (apiVersion 3), static vs dynamic (render.php) blocks, @wordpress/scripts and @wordpress/create-block builds, registering one or many blocks from PHP, attributes, supports, the Interactivity API and block deprecations. Includes a block.json validator that checks names, attributes and that every file: asset exists. Use when creating or debugging a WordPress block, when a block shows "This block contains unexpected or invalid content", or when registering blocks from a plugin or theme.
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# WordPress block development

Script paths below are relative to this skill's directory.

## When to use

- Creating a block or block plugin, adding blocks to an existing plugin/theme.
- A block fails to register, its assets do not load, or the editor shows
  "unexpected or invalid content".
- Choosing static vs dynamic rendering, or adding front-end interactivity.

Not for: classic shortcodes/widgets, full site editing theme.json styling (only
touched where blocks need it), React apps unrelated to the editor.

## Workflow: new block

1. **Scaffold** (needs Node 20+; network for npm):
   ```bash
   npx @wordpress/create-block@latest my-block --namespace my-plugin --variant dynamic
   # inside an existing plugin: put sources in src/<block>/ and build to build/<block>/
   ```
2. **Decide static vs dynamic** (see table below). Default to dynamic (`render.php`)
   when output depends on data that changes (posts, prices, user) or when you want to
   change markup later without block validation errors.
3. **Write `block.json`** first: `apiVersion: 3`, `name` `namespace/block`, `title`,
   `category`, `textdomain`, `attributes`, `supports`, asset fields with `file:` paths.
   Template: [references/block-json.md](references/block-json.md).
4. **Register from PHP** using the built metadata:
   ```php
   add_action( 'init', function () {
       // WP 6.8+: one call for every block in build/ (needs blocks-manifest.php from
       // `wp-scripts build --blocks-manifest`)
       if ( function_exists( 'wp_register_block_types_from_metadata_collection' ) ) {
           wp_register_block_types_from_metadata_collection( __DIR__ . '/build', __DIR__ . '/build/blocks-manifest.php' );
           return;
       }
       foreach ( glob( __DIR__ . '/build/*/block.json' ) as $file ) {
           register_block_type( dirname( $file ) );
       }
   } );
   ```
5. **Build**: `npm run start` (watch) / `npm run build`. `wp-scripts` copies block.json
   and render.php to build/ and writes `index.asset.php` with dependencies and a version hash.
6. **Validate**:
   ```bash
   python3 scripts/validate_block_json.py src/ build/          # errors exit 1
   python3 scripts/validate_block_json.py build/ --strict --json
   ```
7. **Test** in the editor and front end: insert, save, reload the editor (no validation
   warning), check the front end with the block's `supports` options changed, check
   the browser console. Add `npm run lint:js`, `lint:css` and `test:unit` from wp-scripts.

## Static vs dynamic

| | Static (`save()` returns markup) | Dynamic (`render` / `render_callback`) |
| --- | --- | --- |
| Output stored in post content | yes | only the comment delimiter + attributes |
| Changing markup later | needs a `deprecated` entry or posts show invalid content | just edit render.php |
| Server data (latest posts, prices) | no | yes |
| Works without PHP (e.g. in RSS/exports of raw content) | yes | rendered on request |

In `render.php` you get `$attributes`, `$content` and `$block`; wrap output with
`get_block_wrapper_attributes()` and escape everything:

```php
<div <?php echo get_block_wrapper_attributes(); ?>>
	<?php echo esc_html( $attributes['heading'] ?? '' ); ?>
</div>
```

## Fixing "unexpected or invalid content"

Cause: the saved HTML no longer matches what `save()` produces now. Fix by adding the
previous `save` and `attributes` to `deprecated` (newest first), or convert the block
to dynamic and make `save` return `null` (plus a deprecation for the old markup).
Never edit post content in bulk to "fix" it. Examples:
[references/block-json.md](references/block-json.md#deprecations).

## Interactivity API (front-end behaviour)

Use `"supports": { "interactivity": true }`, `"viewScriptModule": "file:./view.js"`,
`data-wp-interactive="namespace"` and directives (`data-wp-on--click`,
`data-wp-bind--hidden`, `data-wp-text`) in render.php, and `store()` from
`@wordpress/interactivity` in view.js. Build with `wp-scripts build --experimental-modules`
(needed for script modules in current @wordpress/scripts versions).

## Output

Deliver block.json, edit.js, save.js (or render.php), the PHP registration and any
CSS, then the validator output. Mention the minimum WordPress version the features need.
