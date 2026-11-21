<?php
/**
 * Plugin Name: Vulnerable demo (test fixture, do not install)
 * echo $_GET['x'];  <- in a comment, must not be flagged
 */
add_action( 'wp_ajax_demo_save', 'demo_save' );

function demo_save() {
	global $wpdb;
	$id   = $_POST['id'];
	$name = sanitize_text_field( wp_unslash( $_POST['name'] ) );
	$wpdb->query( "DELETE FROM {$wpdb->posts} WHERE ID = " . $_POST['id'] );
	$rows = $wpdb->get_results( "SELECT * FROM {$wpdb->prefix}demo WHERE name = '$name'" );
	$ok   = $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE ID = %d", $id ) );
	$bad  = $wpdb->prepare( "SELECT * FROM t WHERE a = '%s'", $name );
	echo $_GET['msg'];
	echo esc_html( $_GET['msg'] );
	echo $name;
	$data = unserialize( $_COOKIE['prefs'] );
	include $_GET['tpl'] . '.php';
	extract( $_REQUEST );
	wp_redirect( $_GET['back'] );
	readfile( $_GET['file'] );
	system( 'ls ' . $id );
	eval( $code );
	$wpdb->get_results( "SELECT * FROM t ORDER BY $orderby" );
	$url = 'https://example.com/a//b'; // URL with slashes inside a string
	echo $_GET['ignored']; // wpsec-ignore
	wp_die();
}

add_action( 'rest_api_init', function () {
	register_rest_route( 'demo/v1', '/items', array(
		'methods'  => 'GET',
		'callback' => 'demo_items',
	) );
	register_rest_route( 'demo/v1', '/public', array(
		'methods'             => 'GET',
		'callback'            => 'demo_items',
		'permission_callback' => '__return_true',
	) );
} );
