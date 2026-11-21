<?php
add_action( 'wp_ajax_demo_safe', 'demo_safe' );

function demo_safe() {
	check_ajax_referer( 'demo_safe' );
	if ( ! current_user_can( 'manage_options' ) ) {
		wp_send_json_error( null, 403 );
	}
	global $wpdb;
	$id   = isset( $_POST['id'] ) ? absint( $_POST['id'] ) : 0;
	$row  = $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$wpdb->posts} WHERE ID = %d", $id ) );
	$all  = $wpdb->get_results( "SELECT ID FROM {$wpdb->posts} LIMIT 10" );
	echo esc_html( $row->post_title );
	wp_safe_redirect( admin_url() );
	exit;
}
