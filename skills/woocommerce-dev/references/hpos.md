# HPOS compatibility checklist

High-Performance Order Storage keeps orders in `{prefix}wc_orders`,
`{prefix}wc_orders_meta`, `{prefix}wc_order_addresses` and
`{prefix}wc_order_operational_data`. It is the default for new stores since
WooCommerce 8.2. With "compatibility mode" on, data is synced to posts too,
but code must not rely on it.

## Replacements (scanner rule -> fix)

| Rule | Legacy code | HPOS-safe code |
| --- | --- | --- |
| HPOS001 | `get_post_meta( $order_id, '_key', true )` | `wc_get_order( $order_id )->get_meta( '_key' )` |
| HPOS001 | `update_post_meta( $order_id, '_key', $v )` | `$order->update_meta_data( '_key', $v ); $order->save();` |
| HPOS001 | `delete_post_meta( $order_id, '_key' )` | `$order->delete_meta_data( '_key' ); $order->save();` |
| HPOS002 | `get_post( $order_id )` | `wc_get_order( $order_id )` |
| HPOS003 | `new WP_Query( array( 'post_type' => 'shop_order', ... ) )` | `wc_get_orders( array( 'status' => array( 'wc-processing' ), 'limit' => 50, 'meta_query' => array( ... ) ) )` |
| HPOS004 | `$wpdb->get_results( "... {$wpdb->posts} ... shop_order" )` | `wc_get_orders()`; if SQL is unavoidable use `OrderUtil::get_table_for_orders()` / `OrderUtil::get_table_for_order_meta()` and branch on `OrderUtil::custom_orders_table_usage_is_enabled()` |
| HPOS005 | `wp_update_post( array( 'ID' => $order_id, 'post_status' => 'wc-completed' ) )` | `$order->update_status( 'completed', 'Note' );` |
| HPOS005 | `wp_delete_post( $order_id, true )` | `$order->delete( true );` |
| HPOS006 | `get_post_type( $order_id ) === 'shop_order'` | `OrderUtil::get_order_type( $order_id ) === 'shop_order'` or `$order instanceof WC_Order` |
| HPOS007 | `add_action( 'save_post_shop_order', ... )` | `woocommerce_new_order`, `woocommerce_update_order` (args: `$order_id, $order`), or `woocommerce_process_shop_order_meta` for the admin form |
| HPOS008 | `add_meta_box( 'id', 'Title', 'cb', 'shop_order' )` | screen `wc_get_page_screen_id( 'shop-order' )`; the callback receives a `WP_Post` (legacy) or `WC_Order` (HPOS): `$order = $post_or_order instanceof WP_Post ? wc_get_order( $post_or_order->ID ) : $post_or_order;` |
| HPOS009 | `metadata_exists( 'post', $order_id, '_key' )` | `$order->meta_exists( '_key' )` |
| HPOS010 | `manage_edit-shop_order_columns` only | also `manage_woocommerce_page_wc-orders_columns` and `manage_woocommerce_page_wc-orders_custom_column` (args: `$column, $order`) |
| HPOS011 | `"SELECT ... FROM {$wpdb->posts} p JOIN {$wpdb->postmeta} pm ... WHERE pm.meta_key = '_billing_email'"` (also across several lines) | `wc_get_orders( array( 'meta_query' => array( ... ) ) )` or `$order->get_meta()`; for unavoidable SQL use `OrderUtil::get_table_for_order_meta()` |
| HPOS100 | no declaration | `FeaturesUtil::declare_compatibility( 'custom_order_tables', __FILE__, true )` on `before_woocommerce_init` |

`OrderUtil` is `Automattic\WooCommerce\Utilities\OrderUtil`.

## Order list columns for both screens

```php
use Automattic\WooCommerce\Utilities\OrderUtil;

$hook_suffix = OrderUtil::custom_orders_table_usage_is_enabled() ? 'woocommerce_page_wc-orders' : 'shop_order_posts';

add_filter( 'manage_edit-shop_order_columns', 'myplugin_add_column' );               // legacy
add_filter( 'manage_woocommerce_page_wc-orders_columns', 'myplugin_add_column' );     // HPOS
add_action( 'manage_shop_order_posts_custom_column', function ( $column, $post_id ) {
	myplugin_render_column( $column, wc_get_order( $post_id ) );
}, 10, 2 );
add_action( 'manage_woocommerce_page_wc-orders_custom_column', function ( $column, $order ) {
	myplugin_render_column( $column, $order );
}, 10, 2 );
```

## Query orders

```php
$orders = wc_get_orders( array(
	'status'       => array( 'wc-processing', 'wc-on-hold' ),
	'date_created' => '>' . ( time() - DAY_IN_SECONDS ),
	'limit'        => 100,
	'return'       => 'ids',
	'meta_query'   => array( array( 'key' => '_tracking', 'compare' => 'NOT EXISTS' ) ),
) );
```

`meta_query`, `field_query` and `date_query` arguments are supported by the HPOS
datastore. Always pass `limit` (default is the `posts_per_page` setting).

## Testing matrix

| Storage | Compatibility mode | Expected |
| --- | --- | --- |
| HPOS | off | Everything works; nothing reads wp_posts for orders |
| HPOS | on | Works; sync keeps posts tables updated |
| Posts (legacy) | n/a | Works (back-compat for older stores) |

Useful commands: `wp wc hpos status`, `wp wc hpos count_unmigrated`,
`wp wc hpos sync`, `wp wc hpos verify_data`, `wp wc hpos diff <order_id>`.
