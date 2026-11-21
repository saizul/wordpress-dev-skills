# block.json reference and examples

## Dynamic block template

```json
{
	"$schema": "https://schemas.wp.org/trunk/block.json",
	"apiVersion": 3,
	"name": "my-plugin/latest-reviews",
	"version": "0.1.0",
	"title": "Latest Reviews",
	"category": "widgets",
	"icon": "star-filled",
	"description": "Shows the latest reviews.",
	"keywords": [ "reviews", "rating" ],
	"textdomain": "my-plugin",
	"attributes": {
		"count": { "type": "integer", "default": 3 },
		"showRating": { "type": "boolean", "default": true },
		"layout": { "type": "string", "enum": [ "list", "grid" ], "default": "list" }
	},
	"supports": {
		"html": false,
		"align": [ "wide", "full" ],
		"color": { "background": true, "text": true },
		"spacing": { "margin": true, "padding": true },
		"typography": { "fontSize": true }
	},
	"example": { "attributes": { "count": 2 } },
	"editorScript": "file:./index.js",
	"editorStyle": "file:./index.css",
	"style": "file:./style-index.css",
	"render": "file:./render.php"
}
```

`wp-scripts` builds `src/<block>/index.js` to `build/<block>/index.js`, `editor.scss`
imported in edit.js to `index.css`, and `style.scss` imported in index.js to
`style-index.css`. The validator accepts a `file:./index.js` reference in `src/` when
`index.js`, `.jsx`, `.ts` or `.tsx` exists, and `.css` when a `.scss` source exists.

## Field cheatsheet

| Field | Notes |
| --- | --- |
| `name` | `namespace/block-name`, lowercase, digits, hyphens; never change after release |
| `apiVersion` | 3 (WP 6.3+): required for the iframed editor in newer releases |
| `category` | core: text, media, design, widgets, theme, embed; custom via `block_categories_all` |
| `parent` / `ancestor` | restrict where it can be inserted |
| `allowedBlocks` | restrict inner blocks (WP 6.5+) |
| `usesContext` / `providesContext` | pass data such as `postId` to inner blocks |
| `editorScript` / `script` / `viewScript` | editor only / both / front end only (classic script) |
| `viewScriptModule` | front-end ES module (Interactivity API), WP 6.5+ |
| `editorStyle` / `style` / `viewStyle` | editor / both / front end only |
| `render` | `file:./render.php` for dynamic blocks |
| `blockHooks` | auto-insert relative to another block, e.g. `{ "core/post-content": "after" }` |
| `selectors` | custom CSS selectors for global styles |

## Attribute types and sources

Types: `string`, `number`, `integer`, `boolean`, `object`, `array`, `null`.
Sources (parse values from saved HTML, static blocks only):

```json
"url":     { "type": "string", "source": "attribute", "selector": "img", "attribute": "src" },
"caption": { "type": "string", "source": "html", "selector": "figcaption" },
"items":   { "type": "array", "source": "query", "selector": "li", "query": { "text": { "type": "string", "source": "text" } } }
```

Attributes without `source` are stored in the block comment delimiter as JSON.
`source: "meta"` is deprecated: use block bindings (`core/post-meta`) instead.

## Edit component skeleton

```js
import { __ } from '@wordpress/i18n';
import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import { PanelBody, RangeControl } from '@wordpress/components';
import ServerSideRender from '@wordpress/server-side-render';

export default function Edit( { attributes, setAttributes } ) {
	return (
		<>
			<InspectorControls>
				<PanelBody title={ __( 'Settings', 'my-plugin' ) }>
					<RangeControl
						label={ __( 'Number of reviews', 'my-plugin' ) }
						value={ attributes.count }
						onChange={ ( count ) => setAttributes( { count } ) }
						min={ 1 }
						max={ 10 }
					/>
				</PanelBody>
			</InspectorControls>
			<div { ...useBlockProps() }>
				<ServerSideRender block="my-plugin/latest-reviews" attributes={ attributes } />
			</div>
		</>
	);
}
```

`ServerSideRender` is convenient but slow (one REST request per change); for
frequently edited blocks render a JS preview instead.

## Deprecations

```js
const v1 = {
	attributes: { text: { type: 'string', source: 'html', selector: 'p' } },
	save( { attributes } ) {
		return <p className="old-class">{ attributes.text }</p>;
	},
	// optional: migrate( attributes ) { return { ...attributes, newAttr: 'x' }; },
};

registerBlockType( metadata.name, {
	edit: Edit,
	save,
	deprecated: [ v1 ], // newest first
} );
```

Converting a static block to dynamic: new `save` returns `null`, add the old save as a
deprecation so existing posts migrate silently when opened.

## package.json scripts

```json
{
	"scripts": {
		"build": "wp-scripts build --blocks-manifest",
		"start": "wp-scripts start --blocks-manifest",
		"lint:js": "wp-scripts lint-js",
		"lint:css": "wp-scripts lint-style",
		"test:unit": "wp-scripts test-unit-js",
		"plugin-zip": "wp-scripts plugin-zip"
	},
	"devDependencies": { "@wordpress/scripts": "^30.0.0" }
}
```

`--blocks-manifest` writes `build/blocks-manifest.php` for
`wp_register_block_types_from_metadata_collection()` (WP 6.8+; use @wordpress/scripts
30.14+, which fixed manifest generation bugs). On WP 6.7 use
`wp_register_block_metadata_collection()` plus `register_block_type()` per block. Add
`--experimental-modules` when a block uses `viewScriptModule`.
