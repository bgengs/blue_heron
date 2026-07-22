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
], $cfg);
