<?php
/**
 * Central config. Secrets live in config.local.php (git-ignored, never
 * deployed to a public repo). Environment variables override everything.
 * Copy config.local.php.example -> config.local.php and fill it in.
 */

$local = __DIR__ . '/config.local.php';
$cfg = file_exists($local) ? (require $local) : [];

return array_merge([
    'admin_password'        => getenv('BH_ADMIN_PASSWORD') ?: '',
    'stripe_secret'         => getenv('STRIPE_SECRET_KEY') ?: '',
    'stripe_publishable'    => getenv('STRIPE_PUBLISHABLE_KEY') ?: '',
    'stripe_webhook_secret' => getenv('STRIPE_WEBHOOK_SECRET') ?: '',
    'site_url'              => getenv('SITE_URL') ?: 'http://localhost:8808',
    'currency'              => 'usd',
    'contact_email'         => 'hello@blueheron.gallery',
    // Prodigi Print API — auto-create print orders after Stripe payment.
    'prodigi_api_key'           => getenv('PRODIGI_API_KEY') ?: '',
    'prodigi_sandbox'           => filter_var(getenv('PRODIGI_SANDBOX') ?: 'true', FILTER_VALIDATE_BOOLEAN),
    'prodigi_shipping_method'   => getenv('PRODIGI_SHIPPING_METHOD') ?: 'Budget',
    // Retail = ceil(Prodigi wholesale × markup). Refresh from Admin → Prices.
    'markup_multiplier'         => (float)(getenv('MARKUP_MULTIPLIER') ?: 2.5),
    'markup_quote_country'      => getenv('MARKUP_QUOTE_COUNTRY') ?: 'US',
    // Signs /api/print-asset.php URLs that Prodigi downloads.
    'asset_signing_secret'      => getenv('BH_ASSET_SECRET') ?: '',
], $cfg);
