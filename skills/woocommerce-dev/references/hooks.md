# WooCommerce hook map

Verify argument counts against the WooCommerce source of the version you target
(`grep -rn "do_action( 'hook_name'" wp-content/plugins/woocommerce/`).

## Orders

| Need | Hook | Args |
| --- | --- | --- |
| Order created (any channel) | `woocommerce_new_order` | `$order_id, $order` |
| Order saved/updated | `woocommerce_update_order` | `$order_id, $order` |
| Any status change | `woocommerce_order_status_changed` | `$order_id, $from, $to, $order` |
| Specific status | `woocommerce_order_status_{status}` e.g. `_completed` | `$order_id, $order` |
| Paid (gateway confirmed) | `woocommerce_payment_complete` | `$order_id` |
| Classic checkout created the order | `woocommerce_checkout_order_processed` | `$order_id, $posted_data, $order` |
| Block checkout created the order | `woocommerce_store_api_checkout_order_processed` | `$order` |
| Before order is saved (mutate) | `woocommerce_before_order_object_save` | `$order, $data_store` |
| Admin order form saved | `woocommerce_process_shop_order_meta` | `$order_id, $order` (HPOS) |
| Refund created | `woocommerce_order_refunded` | `$order_id, $refund_id` |
| Thank-you page | `woocommerce_thankyou` | `$order_id` |

Prefer status/payment hooks over `woocommerce_thankyou` for business logic: the
thank-you page may never load (closed tab, redirect gateway).

## Cart and checkout

| Need | Hook |
| --- | --- |
| Change prices in cart | `woocommerce_before_calculate_totals` (guard with `did_action()` count; runs many times) |
| Add a fee | `woocommerce_cart_calculate_fees` (`$cart->add_fee()`) |
| Validate add to cart | `woocommerce_add_to_cart_validation` (return false + `wc_add_notice()`) |
| Custom cart item data | `woocommerce_add_cart_item_data`, display with `woocommerce_get_item_data` |
| Copy cart item data to order item | `woocommerce_checkout_create_order_line_item` |
| Validate classic checkout | `woocommerce_after_checkout_validation` (`$data, $errors`) |
| Classic checkout fields | `woocommerce_checkout_fields` (not used by block checkout) |
| Block checkout fields | `woocommerce_register_additional_checkout_field()` (WC 8.9+) |
| Block checkout data / validation | Store API: `woocommerce_store_api_register_endpoint_data()`, `woocommerce_store_api_checkout_update_order_from_request` |

## Products

| Need | Hook / API |
| --- | --- |
| Product saved | `woocommerce_update_product`, `woocommerce_new_product` (`$product_id, $product`) |
| Admin product tab | `woocommerce_product_data_tabs` + `woocommerce_product_data_panels` |
| Save admin fields | `woocommerce_admin_process_product_object` (`$product`; call setters, Woo saves) |
| Price HTML | `woocommerce_get_price_html` |
| Stock change | `woocommerce_product_set_stock`, `woocommerce_variation_set_stock` |

## Emails

| Need | Hook |
| --- | --- |
| Register a custom email | `woocommerce_email_classes` (add a `WC_Email` subclass) |
| Add content to emails | `woocommerce_email_order_meta`, `woocommerce_email_after_order_table` (`$order, $sent_to_admin, $plain_text, $email`) |
| Change recipients | `woocommerce_email_recipient_{email_id}` |

## Scheduling work

Use Action Scheduler (bundled with WooCommerce) instead of WP-Cron for anything per order:

```php
as_enqueue_async_action( 'myplugin_sync_order', array( 'order_id' => $order_id ), 'myplugin' );
add_action( 'myplugin_sync_order', 'myplugin_sync_order_cb' );
```

Inspect at Tools > Scheduled Actions or `wp action-scheduler` commands.
