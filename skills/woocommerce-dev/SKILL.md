---
name: woocommerce-dev
description: Build and review WooCommerce extensions the current way - CRUD objects instead of post meta, HPOS (custom order tables) compatibility, Cart/Checkout blocks compatibility, the right hooks for orders, products, cart and checkout. Includes an HPOS scanner script that flags order code that breaks with custom order tables. Use when writing or reviewing WooCommerce plugin code, migrating an extension to HPOS, debugging "incompatible with HPOS" warnings, or choosing a WooCommerce hook.
license: MIT
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# WooCommerce extension development

Script paths below are relative to this skill's directory.

## When to use

- Writing a WooCommerce extension or snippet that touches orders, products, cart or checkout.
- WooCommerce shows "This plugin is incompatible with the enabled WooCommerce feature
  'High-Performance order storage'".
- Reviewing an extension before a release or a WooCommerce major update.

Not for: theme template overrides only (see WooCommerce template docs), store
configuration questions, payment gateway certification.

## Workflow: HPOS audit / migration

1. **Scan** (read-only):
   ```bash
   python3 scripts/hpos_check.py path/to/extension            # text report, exit 1 on medium+
   python3 scripts/hpos_check.py path/to/extension --json     # for further processing
   ```
   It flags post-meta access on orders, `get_post()` on orders, `WP_Query`/`get_posts`
   with `shop_order`, direct SQL on posts for orders, post lifecycle hooks, legacy
   order-list hooks without the HPOS equivalents, meta boxes bound to `shop_order`,
   and missing `declare_compatibility()` calls.
2. **Fix each finding** with the replacements in [references/hpos.md](references/hpos.md).
   Rule of thumb: get the object (`wc_get_order()`), use getters/setters, call `save()`.
3. **Declare compatibility** once everything uses CRUD (main plugin file):
   ```php
   add_action( 'before_woocommerce_init', function () {
       if ( class_exists( \Automattic\WooCommerce\Utilities\FeaturesUtil::class ) ) {
           \Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility( 'custom_order_tables', __FILE__, true );
           \Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility( 'cart_checkout_blocks', __FILE__, true );
       }
   } );
   ```
   `__FILE__` must be the main plugin file. Only declare `cart_checkout_blocks` after
   testing on the block-based Cart and Checkout pages.
4. **Test both storage modes.** WooCommerce > Settings > Advanced > Features: run with
   HPOS on and "compatibility mode" (sync) off, then with legacy posts storage.
   WP-CLI helpers:
   ```bash
   wp wc hpos status
   wp wc hpos count_unmigrated
   wp wc hpos verify_data --verbose      # compares posts and HPOS tables
   ```
   (Commands come with WooCommerce 8.x+; run `wp help wc hpos` to see what your version has.)
5. **Report** findings fixed, remaining items, and the declaration status.

## Writing new code: rules

- Orders: `wc_get_order()`, `wc_get_orders()`, `$order->get_meta()`,
  `$order->update_meta_data()`, `$order->save()`. Never `get_post_meta( $order_id ... )`.
- Products: `wc_get_product()`, `$product->get_price()`, `$product->set_*()` + `save()`.
  Use `wc_get_products()` instead of `WP_Query` for product lookups with Woo fields.
- Prices: `wc_price()` for display, `wc_get_price_to_display()` for tax-aware amounts;
  never format money manually.
- Admin order screen: screen id `wc_get_page_screen_id( 'shop-order' )`; order edit URL
  via `$order->get_edit_order_url()`.
- Checkout fields: the block checkout ignores `woocommerce_checkout_fields`; use the
  Additional Checkout Fields API (`woocommerce_register_additional_checkout_field`) or
  the Store API extension points when blocks must be supported.
- Escaping and security still apply: see the `wp-security-review` skill.
- Check `class_exists( 'WooCommerce' )` (or hook into `woocommerce_loaded`) before using
  Woo APIs; declare `Requires Plugins: woocommerce` in the plugin header (WP 6.5+) and
  `WC requires at least` / `WC tested up to`.

Hook map (orders, cart, checkout, products, emails, admin):
[references/hooks.md](references/hooks.md).

## Output format

For an audit: a table `file:line | rule | current code | replacement`, then the
declaration status, then test steps. For new code: complete, runnable snippets with
the hook, priority and argument count.
