<?php
/** Stripe webhook — record the order, then create it in Prodigi. */

$cfg = require dirname(__DIR__) . '/config.php';
require dirname(__DIR__) . '/lib/db.php';
require dirname(__DIR__) . '/lib/prodigi.php';
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
    $session = $event['data']['object'] ?? [];
    $id = bh_record_order($session);
    if ($id > 0) {
        $order = bh_order($id);
        // Idempotent: skip if we already submitted to Prodigi.
        if ($order && empty($order['prodigi_order_id'])) {
            if (bh_prodigi_configured()) {
                $res = bh_prodigi_create_order($order);
                if ($res['ok']) {
                    bh_set_prodigi_result($id, $res['id'], null);
                } else {
                    bh_set_prodigi_result($id, null, $res['error'] ?? 'unknown');
                }
            }
            // No API key → leave fulfillment = new (manual Prodigi dashboard).
        }
    }
}
http_response_code(200);
echo json_encode(['received' => true]);
