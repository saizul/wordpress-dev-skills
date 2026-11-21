<?php
/**
 * Plugin Name: Modern order extension (test fixture)
 */
use Automattic\WooCommerce\Utilities\FeaturesUtil;

add_action( 'before_woocommerce_init', function () {
	if ( class_exists( FeaturesUtil::class ) ) {
		FeaturesUtil::declare_compatibility( 'custom_order_tables', __FILE__, true );
		FeaturesUtil::declare_compatibility( 'cart_checkout_blocks', __FILE__, true );
	}
} );
add_filter( 'manage_edit-shop_order_columns', 'modern_columns' );
add_filter( 'manage_woocommerce_page_wc-orders_columns', 'modern_columns' );

function modern_save( $order_id ) {
	$order = wc_get_order( $order_id );
	$order->update_meta_data( '_tracking', 'X123' );
	$order->save();
	$orders = wc_get_orders( array( 'limit' => 5 ) );
	add_meta_box( 'modern', 'Modern', 'cb', wc_get_page_screen_id( 'shop-order' ), 'side' );
}
