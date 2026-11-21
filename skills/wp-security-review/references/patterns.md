# Safe and unsafe WordPress patterns

## Output escaping (escape late, at the point of output)

```php
// Unsafe
echo '<a href="' . $url . '">' . $title . '</a>';
// Safe
echo '<a href="' . esc_url( $url ) . '">' . esc_html( $title ) . '</a>';
printf( '<input value="%s">', esc_attr( $value ) );
echo wp_kses_post( $html_from_editor );
// Translations are not escaped
esc_html_e( 'Saved.', 'my-plugin' );
echo esc_html( sprintf( __( '%d items', 'my-plugin' ), $count ) );
// Data for JavaScript
wp_add_inline_script( 'my-handle', 'const myData = ' . wp_json_encode( $data ) . ';', 'before' );
```

## Input: unslash, then sanitize by type

```php
$id    = isset( $_POST['id'] ) ? absint( $_POST['id'] ) : 0;
$name  = isset( $_POST['name'] ) ? sanitize_text_field( wp_unslash( $_POST['name'] ) ) : '';
$key   = isset( $_GET['tab'] ) ? sanitize_key( $_GET['tab'] ) : 'general';
$email = sanitize_email( wp_unslash( $_POST['email'] ?? '' ) );
$url   = esc_url_raw( wp_unslash( $_POST['url'] ?? '' ) );
$ids   = array_map( 'absint', (array) wp_unslash( $_POST['ids'] ?? array() ) );
// Enums: whitelist
$order = in_array( $_GET['order'] ?? '', array( 'asc', 'desc' ), true ) ? $_GET['order'] : 'desc';
```

## Nonces + capabilities

```php
// Form
wp_nonce_field( 'myplugin_save', 'myplugin_nonce' );

// admin-post handler
add_action( 'admin_post_myplugin_save', function () {
	if ( ! current_user_can( 'manage_options' ) ) {
		wp_die( esc_html__( 'Not allowed.', 'my-plugin' ), 403 );
	}
	check_admin_referer( 'myplugin_save', 'myplugin_nonce' );
	// ... sanitize + save ...
	wp_safe_redirect( add_query_arg( 'updated', '1', wp_get_referer() ) );
	exit;
} );

// AJAX
add_action( 'wp_ajax_myplugin_toggle', function () {
	check_ajax_referer( 'myplugin_toggle' );               // dies on failure
	$post_id = absint( $_POST['post_id'] ?? 0 );
	if ( ! current_user_can( 'edit_post', $post_id ) ) {   // object-level check
		wp_send_json_error( null, 403 );
	}
	wp_send_json_success();
} );
```

A nonce proves intent, not permission: always pair it with a capability check.
`wp_ajax_nopriv_*` handlers are public: treat every input as hostile, rate-limit
expensive work.

## REST API

```php
register_rest_route( 'myplugin/v1', '/items/(?P<id>\d+)', array(
	'methods'             => WP_REST_Server::EDITABLE,
	'callback'            => 'myplugin_update_item',
	'permission_callback' => fn( $req ) => current_user_can( 'edit_post', (int) $req['id'] ),
	'args'                => array(
		'id'    => array( 'type' => 'integer', 'required' => true ),
		'title' => array( 'type' => 'string', 'sanitize_callback' => 'sanitize_text_field' ),
	),
) );
```

REST nonces (`X-WP-Nonce: wp_create_nonce( 'wp_rest' )`) are checked by core for
cookie auth; `permission_callback` is still required.

## SQL

```php
// Unsafe
$wpdb->get_results( "SELECT * FROM {$wpdb->posts} WHERE post_title = '$title'" );
// Safe
$wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$wpdb->posts} WHERE post_title = %s", $title ) );
// LIKE
$like = '%' . $wpdb->esc_like( $term ) . '%';
$wpdb->prepare( "SELECT ID FROM {$wpdb->posts} WHERE post_title LIKE %s", $like );
// IN ()
$in = implode( ',', array_fill( 0, count( $ids ), '%d' ) );
$wpdb->prepare( "SELECT * FROM {$wpdb->posts} WHERE ID IN ($in)", $ids );
// Identifiers (WP 6.2+)
$wpdb->prepare( 'SELECT * FROM %i WHERE id = %d', $table, $id );
// ORDER BY cannot be a placeholder: whitelist
$orderby = in_array( $orderby, array( 'post_date', 'post_title' ), true ) ? $orderby : 'post_date';
```

Prefer `$wpdb->insert/update/delete` with format arrays, or WP_Query/get_posts.

## Files and uploads

```php
$file = wp_handle_upload( $_FILES['import'], array(
	'test_form' => false,
	'mimes'     => array( 'json' => 'application/json' ),
) );
// Never: include $_GET['view'] . '.php';
$views = array( 'list' => 'views/list.php', 'edit' => 'views/edit.php' );
$view  = $views[ sanitize_key( $_GET['view'] ?? 'list' ) ] ?? $views['list'];
include __DIR__ . '/' . $view;
```

## Severity guide

| Who can trigger | Data/impact | Severity |
| --- | --- | --- |
| Unauthenticated | SQLi, RCE, file read, stored XSS | critical |
| Subscriber/customer | SQLi, privilege escalation, stored XSS | high |
| Any user via CSRF on admin | settings change, deletion | high |
| Admin only (unfiltered_html sites) | XSS | low |
| Reflected XSS needing a crafted link | session theft | medium/high |
