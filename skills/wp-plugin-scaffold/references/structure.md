# Plugin structure patterns

Add these to the generated skeleton as needed. Register each class from
`Plugin::boot()`.

## REST controller

```php
namespace Acme\Reviews\Rest;

use WP_REST_Request;
use WP_REST_Server;

class ReviewsController {
	const NS = 'acme-reviews/v1';

	public function register() {
		add_action( 'rest_api_init', array( $this, 'routes' ) );
	}

	public function routes() {
		register_rest_route( self::NS, '/reviews', array(
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'index' ),
				'permission_callback' => '__return_true', // public, read-only
				'args'                => array(
					'per_page' => array( 'type' => 'integer', 'default' => 10, 'minimum' => 1, 'maximum' => 50 ),
				),
			),
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( $this, 'create' ),
				'permission_callback' => fn() => current_user_can( 'edit_posts' ),
				'args'                => array(
					'title' => array( 'type' => 'string', 'required' => true, 'sanitize_callback' => 'sanitize_text_field' ),
				),
			),
		) );
	}

	public function index( WP_REST_Request $request ) {
		return rest_ensure_response( array() );
	}

	public function create( WP_REST_Request $request ) {
		return new \WP_REST_Response( array( 'title' => $request['title'] ), 201 );
	}
}
```

## WP-CLI command

```php
if ( defined( 'WP_CLI' ) && WP_CLI ) {
	\WP_CLI::add_command( 'acme-reviews', \Acme\Reviews\Cli\Command::class );
}
```

Public methods become subcommands; document arguments with the docblock
`## OPTIONS` syntax so `wp help acme-reviews` works.

## Cron

```php
// Activation
if ( ! wp_next_scheduled( 'acme_reviews_daily' ) ) {
	wp_schedule_event( time() + HOUR_IN_SECONDS, 'daily', 'acme_reviews_daily' );
}
// Boot
add_action( 'acme_reviews_daily', array( $this, 'daily' ) );
// Deactivation (already in the skeleton)
wp_clear_scheduled_hook( 'acme_reviews_daily' );
```

Never schedule from `init` without the `wp_next_scheduled()` guard.

## Custom table

```php
public static function install_schema() {
	global $wpdb;
	require_once ABSPATH . 'wp-admin/includes/upgrade.php';
	$table   = $wpdb->prefix . 'acme_reviews';
	$charset = $wpdb->get_charset_collate();
	dbDelta( "CREATE TABLE {$table} (
		id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
		post_id bigint(20) unsigned NOT NULL,
		rating tinyint(3) unsigned NOT NULL,
		created_at datetime NOT NULL,
		PRIMARY KEY  (id),
		KEY post_id (post_id)
	) {$charset};" );
	update_option( 'acme_reviews_db_version', '1', false );
}
```

`dbDelta` is picky: two spaces after `PRIMARY KEY`, one field per line, lowercase
types. Run it on activation and when the stored db version is older than the code's.

## Assets

```php
add_action( 'admin_enqueue_scripts', function ( $hook ) {
	if ( 'settings_page_acme-reviews' !== $hook ) {
		return; // only on our screen
	}
	$asset = include plugin_dir_path( PLUGIN_FILE ) . 'build/admin.asset.php';
	wp_enqueue_script( 'acme-reviews-admin', plugins_url( 'build/admin.js', PLUGIN_FILE ), $asset['dependencies'], $asset['version'], array( 'in_footer' => true ) );
	wp_set_script_translations( 'acme-reviews-admin', 'acme-reviews' );
} );
```

## Integration tests (optional, with WordPress loaded)

Brain Monkey unit tests (in the skeleton) are fast and need no database. For tests
against a real WordPress, add `wp-phpunit/wp-phpunit` and `yoast/phpunit-polyfills`,
or use `@wordpress/env` (`npx wp-env start` then
`npx wp-env run tests-cli --env-cwd=wp-content/plugins/acme-reviews vendor/bin/phpunit`).

## Plugin header extras

```
 * Requires Plugins:  woocommerce          (WP 6.5+, dependency slugs)
 * Update URI:        false                (never update from WordPress.org)
 * Network:           true                 (network-activate only)
```
