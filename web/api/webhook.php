<?php
/** Stripe webhook — verifies the signature and records completed orders. */

$cfg = require dirname(__DIR__) . '/config.php';
require dirname(__DIR__) . '/lib/db.php';
require dirname(__DIR__) . '/vendor/autoload.php';

$payload = file_get_contents('php://input');
$sig = $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '';

if (empty($cfg['stripe_secret'])) { http_response_code(503); exit; }

try {
    if (!empty($cfg['stripe_webhook_secret'])) {
        $event = \Stripe\Webhook::constructEvent($payload, $sig, $cfg['stripe_webhook_secret']);
        $event = $event->toArray();
    } else {
        // Dev fallback (stripe listen without a configured secret): trust payload.
        $event = json_decode($payload, true);
    }
} catch (\Throwable $e) {
    http_response_code(400); exit;
}

if (($event['type'] ?? '') === 'checkout.session.completed') {
    bh_record_order($event['data']['object'] ?? []);
}
http_response_code(200);
echo json_encode(['received' => true]);
