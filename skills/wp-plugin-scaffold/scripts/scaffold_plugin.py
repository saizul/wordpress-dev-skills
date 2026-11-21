#!/usr/bin/env python3
"""Generate a modern WordPress plugin skeleton.

Creates a plugin with: a namespaced PSR-4 `src/` (Composer autoload plus a
fallback autoloader so the plugin runs without `vendor/`), a Settings API page
that shows nonce/capability/sanitize/escape patterns, uninstall.php,
PHPCS (WordPress-Extra + PHPCompatibilityWP), PHPUnit with Brain Monkey unit
tests (no database needed), a GitHub Actions workflow, readme.txt,
.distignore, .editorconfig and .gitignore.

Nothing is overwritten unless --force is given. Use --dry-run to list files.

Exit codes: 0 created (or dry run), 1 target exists, 2 invalid arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

VERSION = "0.1.0"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NS_RE = re.compile(r"^[A-Z][A-Za-z0-9]*(?:\\[A-Z][A-Za-z0-9]*)*$")

MAIN = """<?php
/**
 * Plugin Name:       {{NAME}}
 * Plugin URI:        {{PLUGIN_URI}}
 * Description:       {{DESCRIPTION}}
 * Version:           0.1.0
 * Requires at least: {{REQUIRES_WP}}
 * Requires PHP:      {{REQUIRES_PHP}}
 * Author:            {{AUTHOR}}
 * Author URI:        {{AUTHOR_URI}}
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       {{SLUG}}
 * Domain Path:       /languages
 *
 * @package {{NS}}
 */

namespace {{NS}};

defined( 'ABSPATH' ) || exit;

const VERSION     = '0.1.0';
const PLUGIN_FILE = __FILE__;

if ( is_readable( __DIR__ . '/vendor/autoload.php' ) ) {
	require __DIR__ . '/vendor/autoload.php';
} else {
	// Fallback PSR-4 autoloader so the plugin also runs when deployed without vendor/.
	spl_autoload_register(
		static function ( $class_name ) {
			$prefix = __NAMESPACE__ . '\\\\';
			if ( 0 !== strpos( $class_name, $prefix ) ) {
				return;
			}
			$file = __DIR__ . '/src/' . str_replace( '\\\\', '/', substr( $class_name, strlen( $prefix ) ) ) . '.php';
			if ( is_readable( $file ) ) {
				require $file;
			}
		}
	);
}

register_activation_hook( __FILE__, array( Plugin::class, 'activate' ) );
register_deactivation_hook( __FILE__, array( Plugin::class, 'deactivate' ) );

add_action( 'plugins_loaded', array( Plugin::instance(), 'boot' ) );
"""

PLUGIN_CLASS = """<?php
/**
 * Main plugin class.
 *
 * @package {{NS}}
 */

namespace {{NS}};

use {{NS}}\\Admin\\Settings;

defined( 'ABSPATH' ) || exit;

/**
 * Wires hooks. Keep logic in small classes; this class only connects them.
 */
final class Plugin {

	/**
	 * Option name that stores all plugin settings.
	 */
	const OPTION = '{{PREFIX}}_settings';

	/**
	 * Singleton instance.
	 *
	 * @var Plugin|null
	 */
	private static $instance = null;

	/**
	 * Get the shared instance.
	 *
	 * @return Plugin
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Register hooks. Runs on plugins_loaded.
	 *
	 * @return void
	 */
	public function boot() {
		add_action( 'init', array( $this, 'load_textdomain' ) );
		if ( is_admin() ) {
			( new Settings() )->register();
		}
	}

	/**
	 * Load translations.
	 *
	 * @return void
	 */
	public function load_textdomain() {
		load_plugin_textdomain( '{{SLUG}}', false, dirname( plugin_basename( PLUGIN_FILE ) ) . '/languages' );
	}

	/**
	 * Activation: add options with autoload off unless they are needed on every request.
	 *
	 * @return void
	 */
	public static function activate() {
		add_option( self::OPTION, array( 'enabled' => true ), '', false );
	}

	/**
	 * Deactivation: clear scheduled events. Data is removed in uninstall.php.
	 *
	 * @return void
	 */
	public static function deactivate() {
		wp_clear_scheduled_hook( '{{PREFIX}}_daily' );
	}

	/**
	 * Read one setting.
	 *
	 * @param string $key      Setting key.
	 * @param mixed  $fallback Value returned when the setting is missing.
	 * @return mixed
	 */
	public static function get_setting( $key, $fallback = null ) {
		$settings = get_option( self::OPTION, array() );
		return is_array( $settings ) && array_key_exists( $key, $settings ) ? $settings[ $key ] : $fallback;
	}
}
"""

SETTINGS_CLASS = """<?php
/**
 * Settings page built on the Settings API.
 *
 * @package {{NS}}
 */

namespace {{NS}}\\Admin;

use {{NS}}\\Plugin;

defined( 'ABSPATH' ) || exit;

/**
 * Settings screen under Settings > {{NAME}}.
 *
 * The Settings API handles the nonce (settings_fields) and the manage_options
 * check for options.php; sanitize() is the single place input is cleaned.
 */
class Settings {

	const PAGE = '{{SLUG}}';

	/**
	 * Hook into admin.
	 *
	 * @return void
	 */
	public function register() {
		add_action( 'admin_menu', array( $this, 'add_page' ) );
		add_action( 'admin_init', array( $this, 'register_settings' ) );
	}

	/**
	 * Add the options page.
	 *
	 * @return void
	 */
	public function add_page() {
		add_options_page(
			__( '{{NAME}}', '{{SLUG}}' ),
			__( '{{NAME}}', '{{SLUG}}' ),
			'manage_options',
			self::PAGE,
			array( $this, 'render' )
		);
	}

	/**
	 * Register the setting, section and fields.
	 *
	 * @return void
	 */
	public function register_settings() {
		register_setting(
			self::PAGE,
			Plugin::OPTION,
			array(
				'type'              => 'array',
				'sanitize_callback' => array( $this, 'sanitize' ),
				'default'           => array( 'enabled' => true ),
			)
		);
		add_settings_section( 'general', __( 'General', '{{SLUG}}' ), '__return_false', self::PAGE );
		add_settings_field(
			'enabled',
			__( 'Enable', '{{SLUG}}' ),
			array( $this, 'field_enabled' ),
			self::PAGE,
			'general'
		);
	}

	/**
	 * Sanitize everything that comes from the form.
	 *
	 * @param mixed $input Raw input.
	 * @return array
	 */
	public function sanitize( $input ) {
		$input = is_array( $input ) ? $input : array();
		return array(
			'enabled' => ! empty( $input['enabled'] ),
		);
	}

	/**
	 * Checkbox field. Escape late.
	 *
	 * @return void
	 */
	public function field_enabled() {
		printf(
			'<input type="checkbox" name="%1$s[enabled]" value="1" %2$s />',
			esc_attr( Plugin::OPTION ),
			checked( (bool) Plugin::get_setting( 'enabled', true ), true, false )
		);
	}

	/**
	 * Render the page.
	 *
	 * @return void
	 */
	public function render() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		echo '<div class="wrap"><h1>' . esc_html( get_admin_page_title() ) . '</h1><form method="post" action="options.php">';
		settings_fields( self::PAGE );
		do_settings_sections( self::PAGE );
		submit_button();
		echo '</form></div>';
	}
}
"""

UNINSTALL = """<?php
/**
 * Runs when the plugin is deleted from the Plugins screen.
 *
 * @package {{NS}}
 */

defined( 'WP_UNINSTALL_PLUGIN' ) || exit;

delete_option( '{{PREFIX}}_settings' );
// For multisite, loop over get_sites() and delete per-site options if you store any.
"""

COMPOSER = {
    "name": "{{COMPOSER_NAME}}",
    "description": "{{DESCRIPTION}}",
    "type": "wordpress-plugin",
    "license": "GPL-2.0-or-later",
    "require": {"php": ">={{REQUIRES_PHP}}"},
    "require-dev": {
        "brain/monkey": "^2.6",
        "dealerdirect/phpcodesniffer-composer-installer": "^1.0",
        "phpcompatibility/phpcompatibility-wp": "^2.1",
        "phpunit/phpunit": "^9.6",
        "wp-coding-standards/wpcs": "^3.1",
    },
    "autoload": {},
    "autoload-dev": {},
    "config": {
        "allow-plugins": {"dealerdirect/phpcodesniffer-composer-installer": True},
        "sort-packages": True,
    },
    "scripts": {
        "lint": "phpcs",
        "lint:fix": "phpcbf",
        "test": "phpunit",
    },
}

PHPCS = """<?xml version="1.0"?>
<ruleset name="{{NAME}}">
	<description>Coding standards for {{NAME}}.</description>

	<file>.</file>
	<exclude-pattern>/vendor/*</exclude-pattern>
	<exclude-pattern>/node_modules/*</exclude-pattern>
	<exclude-pattern>/build/*</exclude-pattern>

	<arg name="extensions" value="php"/>
	<arg name="colors"/>
	<arg value="sp"/>

	<config name="testVersion" value="{{REQUIRES_PHP}}-"/>
	<config name="minimum_wp_version" value="{{REQUIRES_WP}}"/>

	<rule ref="WordPress-Extra"/>
	<rule ref="WordPress-Docs">
		<exclude-pattern>/tests/*</exclude-pattern>
	</rule>
	<rule ref="PHPCompatibilityWP"/>

	<rule ref="WordPress.WP.I18n">
		<properties>
			<property name="text_domain" type="array">
				<element value="{{SLUG}}"/>
			</property>
		</properties>
	</rule>
	<rule ref="WordPress.NamingConventions.PrefixAllGlobals">
		<properties>
			<property name="prefixes" type="array">
				<element value="{{PREFIX}}"/>
				<element value="{{NS_XML}}"/>
			</property>
		</properties>
	</rule>
	<!-- PSR-4 file names (src/Plugin.php) instead of class-plugin.php. -->
	<rule ref="WordPress.Files.FileName">
		<exclude-pattern>/src/*</exclude-pattern>
		<exclude-pattern>/tests/*</exclude-pattern>
	</rule>
	<rule ref="WordPress.Files.FileName.InvalidClassFileName">
		<exclude-pattern>*</exclude-pattern>
	</rule>
</ruleset>
"""

PHPUNIT = """<?xml version="1.0"?>
<phpunit
	bootstrap="tests/bootstrap.php"
	colors="true"
	convertDeprecationsToExceptions="true"
>
	<testsuites>
		<testsuite name="unit">
			<directory suffix="Test.php">tests/Unit</directory>
		</testsuite>
	</testsuites>
	<coverage>
		<include>
			<directory suffix=".php">src</directory>
		</include>
	</coverage>
</phpunit>
"""

BOOTSTRAP = """<?php
/**
 * PHPUnit bootstrap for Brain Monkey unit tests (no WordPress, no database).
 *
 * @package {{NS}}
 */

define( 'ABSPATH', __DIR__ . '/' ); // phpcs:ignore WordPress.NamingConventions.PrefixAllGlobals.NonPrefixedConstantFound

require dirname( __DIR__ ) . '/vendor/autoload.php';
"""

TEST = """<?php
/**
 * Unit tests for the Plugin and Settings classes.
 *
 * @package {{NS}}
 */

namespace {{NS}}\\Tests\\Unit;

use Brain\\Monkey;
use Brain\\Monkey\\Functions;
use {{NS}}\\Admin\\Settings;
use {{NS}}\\Plugin;
use PHPUnit\\Framework\\TestCase;

class PluginTest extends TestCase {

	protected function setUp(): void {
		parent::setUp();
		Monkey\\setUp();
	}

	protected function tearDown(): void {
		Monkey\\tearDown();
		parent::tearDown();
	}

	public function test_get_setting_returns_stored_value() {
		Functions\\expect( 'get_option' )->once()->with( Plugin::OPTION, array() )->andReturn( array( 'enabled' => false ) );
		$this->assertFalse( Plugin::get_setting( 'enabled', true ) );
	}

	public function test_get_setting_falls_back_to_default() {
		Functions\\when( 'get_option' )->justReturn( 'not-an-array' );
		$this->assertSame( 'x', Plugin::get_setting( 'missing', 'x' ) );
	}

	public function test_sanitize_casts_to_bool_and_drops_unknown_keys() {
		$clean = ( new Settings() )->sanitize(
			array(
				'enabled' => '1',
				'evil'    => '<script>',
			)
		);
		$this->assertSame( array( 'enabled' => true ), $clean );
	}

	public function test_sanitize_handles_non_array_input() {
		$this->assertSame( array( 'enabled' => false ), ( new Settings() )->sanitize( 'junk' ) );
	}
}
"""

CI = """name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    name: PHP ${{ matrix.php }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        php: ["{{REQUIRES_PHP}}", "8.1", "8.3"]
    steps:
      - uses: actions/checkout@v7
      - uses: shivammathur/setup-php@v2
        with:
          php-version: ${{ matrix.php }}
          coverage: none
          tools: composer
      - run: composer install --no-interaction --no-progress
      - name: PHPCS
        run: composer lint
      - name: PHPUnit
        run: composer test
"""

README = """=== {{NAME}} ===
Contributors: {{CONTRIBUTORS}}
Tags: {{TAGS}}
Requires at least: {{REQUIRES_WP}}
Tested up to: {{TESTED}}
Requires PHP: {{REQUIRES_PHP}}
Stable tag: 0.1.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

{{SHORT}}

== Description ==

{{DESCRIPTION}}

== Installation ==

1. Upload the plugin folder to `/wp-content/plugins/` or install it from Plugins > Add New.
2. Activate it through the Plugins screen.
3. Configure it under Settings > {{NAME}}.

== Changelog ==

= 0.1.0 =
* Initial release.
"""

GITIGNORE = """/vendor/
/node_modules/
/build/
.phpunit.result.cache
.phpcs-cache
*.zip
.DS_Store
"""

DISTIGNORE = """/.git
/.github
/node_modules
/tests
/vendor
.distignore
.editorconfig
.gitignore
.phpunit.result.cache
composer.json
composer.lock
phpcs.xml.dist
phpunit.xml.dist
"""

EDITORCONFIG = """root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = tab

[*.{json,yml,yaml}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false
"""


def slug_to_namespace(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("-") if part) or "MyPlugin"


def build_context(args: argparse.Namespace) -> dict:
    ns = args.namespace or slug_to_namespace(args.slug)
    prefix = args.prefix or args.slug.replace("-", "_")
    vendor = args.composer_vendor or ns.split("\\")[0].lower()
    desc = args.description or f"{args.name} plugin."
    return {
        "SLUG": args.slug,
        "NAME": args.name,
        "NS": ns,
        "NS_XML": ns,
        "PREFIX": prefix,
        "DESCRIPTION": desc,
        "SHORT": desc[:150],
        "AUTHOR": args.author,
        "AUTHOR_URI": args.author_uri,
        "PLUGIN_URI": args.plugin_uri,
        "REQUIRES_WP": args.requires_wp,
        "REQUIRES_PHP": args.requires_php,
        "TESTED": args.tested_up_to,
        "CONTRIBUTORS": args.contributors or "your-wordpress-org-username",
        "TAGS": args.tags or "",
        "COMPOSER_NAME": f"{vendor}/{args.slug}",
    }


def render(template: str, ctx: dict) -> str:
    out = template
    for key, val in ctx.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def composer_json(ctx: dict) -> str:
    data = json.loads(json.dumps(COMPOSER))
    data["name"] = ctx["COMPOSER_NAME"]
    data["description"] = ctx["DESCRIPTION"]
    data["require"] = {"php": ">=" + ctx["REQUIRES_PHP"]}
    data["autoload"] = {"psr-4": {ctx["NS"] + "\\": "src/"}}
    data["autoload-dev"] = {"psr-4": {ctx["NS"] + "\\Tests\\": "tests/"}}
    return json.dumps(data, indent=4) + "\n"


def files_for(ctx: dict) -> dict[str, str]:
    templates = {
        f"{ctx['SLUG']}.php": MAIN,
        "src/Plugin.php": PLUGIN_CLASS,
        "src/Admin/Settings.php": SETTINGS_CLASS,
        "uninstall.php": UNINSTALL,
        "phpcs.xml.dist": PHPCS,
        "phpunit.xml.dist": PHPUNIT,
        "tests/bootstrap.php": BOOTSTRAP,
        "tests/Unit/PluginTest.php": TEST,
        ".github/workflows/ci.yml": CI,
        "readme.txt": README,
        ".gitignore": GITIGNORE,
        ".distignore": DISTIGNORE,
        ".editorconfig": EDITORCONFIG,
        "languages/.gitkeep": "",
    }
    files = {path: render(tpl, ctx) for path, tpl in templates.items()}
    files["composer.json"] = composer_json(ctx)
    return files


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scaffold_plugin.py",
        description="Generate a modern WordPress plugin skeleton (namespaces, Composer "
        "autoload, PHPCS, PHPUnit + Brain Monkey, GitHub Actions, readme.txt).",
        epilog="Example: python3 scaffold_plugin.py acme-reviews --name 'Acme Reviews' "
        "--namespace 'Acme\\\\Reviews' --author 'Acme' --dest wp-content/plugins",
    )
    p.add_argument("slug", help="plugin slug / folder / text domain, e.g. acme-reviews")
    p.add_argument("--name", help="human name (default: from slug)")
    p.add_argument("--namespace", help="PHP namespace, e.g. Acme\\Reviews (default: from slug)")
    p.add_argument(
        "--prefix", help="global prefix for options/hooks (default: slug_with_underscores)"
    )
    p.add_argument("--description", help="one-line description (<=150 chars recommended)")
    p.add_argument("--author", default="Your Name")
    p.add_argument("--author-uri", default="https://example.com")
    p.add_argument("--plugin-uri", default="https://example.com")
    p.add_argument("--composer-vendor", help="Composer vendor (default: first namespace part)")
    p.add_argument("--requires-wp", default="6.5")
    p.add_argument("--requires-php", default="7.4")
    p.add_argument("--tested-up-to", default="6.8")
    p.add_argument("--contributors", help="WordPress.org usernames for readme.txt")
    p.add_argument("--tags", help="readme.txt tags, comma-separated (max 5)")
    p.add_argument("--dest", default=".", help="parent directory (default: current)")
    p.add_argument("--dry-run", action="store_true", help="list files, write nothing")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    p.add_argument("--json", action="store_true", help="print JSON summary")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not SLUG_RE.match(args.slug):
        print("error: slug must be lowercase letters, digits and single hyphens", file=sys.stderr)
        return 2
    if args.namespace and not NS_RE.match(args.namespace):
        print(
            "error: namespace must look like Vendor\\Plugin (StudlyCaps segments)", file=sys.stderr
        )
        return 2
    if args.prefix and not re.fullmatch(r"[a-z][a-z0-9_]*", args.prefix):
        print("error: prefix must be lowercase letters, digits and underscores", file=sys.stderr)
        return 2
    if args.tags and len([t for t in args.tags.split(",") if t.strip()]) > 5:
        print("error: WordPress.org uses at most 5 tags", file=sys.stderr)
        return 2
    args.name = args.name or " ".join(w.capitalize() for w in args.slug.split("-"))
    if re.search(r"[*<>'\"&\\\n]", args.name):
        print("error: name must not contain * < > ' \" & \\ or newlines", file=sys.stderr)
        return 2
    if args.description and ("*/" in args.description or "\n" in args.description):
        print("error: description must be one line without */", file=sys.stderr)
        return 2
    ctx = build_context(args)
    target = os.path.join(args.dest, args.slug)
    files = files_for(ctx)
    existing = [p for p in files if os.path.exists(os.path.join(target, p))]
    if existing and not args.force and not args.dry_run:
        print(
            f"error: {len(existing)} file(s) already exist in {target} (e.g. {existing[0]}); "
            "use --force to overwrite",
            file=sys.stderr,
        )
        return 1
    if not args.dry_run:
        for rel, text in files.items():
            full = os.path.join(target, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
    summary = {
        "version": VERSION,
        "target": target,
        "dry_run": args.dry_run,
        "namespace": ctx["NS"],
        "prefix": ctx["PREFIX"],
        "files": sorted(files),
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        verb = "Would create" if args.dry_run else "Created"
        print(
            f"{verb} {len(files)} files in {target} (namespace {ctx['NS']}, prefix {ctx['PREFIX']}):"
        )
        for f in sorted(files):
            print(f"  {f}")
        if not args.dry_run:
            print(f"\nNext: cd {target} && composer install && composer lint && composer test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
