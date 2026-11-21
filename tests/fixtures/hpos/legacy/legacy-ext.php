<?php
/**
 * Plugin Name: Legacy order extension (test fixture)
 */
add_action( 'save_post_shop_order', 'legacy_save', 10, 2 );
add_filter( 'manage_edit-shop_order_columns', 'legacy_columns' );

function legacy_save( $order_id ) {
	$tracking = get_post_meta( $order_id, '_tracking', true );
	update_post_meta( $order_id, '_tracking', 'X123' );
	$post = get_post( $order_id );
	if ( 'shop_order' === get_post_type( $order_id ) ) {
		wp_update_post( array( 'ID' => $order_id ) );
	}
	$orders = get_posts( array( 'post_type' => 'shop_order', 'numberposts' => 5 ) );
	global $wpdb;
	$count = $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'shop_order'" );
	add_meta_box( 'legacy', 'Legacy', 'cb', 'shop_order', 'side' );
	// get_post_meta( $order_id, '_in_comment' ) must not be flagged
	get_post_meta( $order_id, '_ignored' ); // hpos-ignore
}
