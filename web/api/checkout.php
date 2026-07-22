<?php
/** Create a Stripe Checkout Session. Prices are computed server-side from the
 *  catalog, never trusted from the client. Returns JSON {url} or an error. */

require dirname(__DIR__) . '/lib/data.php';
$cfg = require dirname(__DIR__) . '/config.php';
header('Content-Type: application/json');

$input = json_decode(file_get_contents('php://input'), true) ?: [];
$slug = (string)($input['photo'] ?? '');
$fmt  = (string)($input['format'] ?? '');
$size = (string)($input['size'] ?? '');
$qty  = max(1, min(10, (int)($input['qty'] ?? 1)));

$photo = bh_photo($slug);
if (!$photo || empty($photo['active'])) {
    http_response_code(400); echo json_encode(['error' => 'Unknown photo']); exit;
}
$catalog = bh_catalog();
$fmt_def = $catalog['formats'][$fmt] ?? null;
$unit = bh_price_cents($fmt, $size);
if (!$fmt_def || $unit === null) {
    http_response_code(400); echo json_encode(['error' => 'Unknown format or size']); exit;
}
if (empty($cfg['stripe_secret'])) {
    http_response_code(503);
    echo json_encode(['error' => 'Stripe not configured', 'fallback' => 'email']); exit;
}

require dirname(__DIR__) . '/vendor/autoload.php';
try {
    \Stripe\Stripe::setApiKey($cfg['stripe_secret']);
    $session = \Stripe\Checkout\Session::create([
        'mode' => 'payment',
        'line_items' => [[
            'quantity' => $qty,
            'price_data' => [
                'currency' => $catalog['currency'] ?? 'usd',
                'unit_amount' => $unit,
                'product_data' => [
                    'name' => $photo['title'] . ' — ' . $fmt_def['label'] . ', ' . $size,
                    'description' => 'Great blue heron — blueheron.gallery',
                ],
            ],
        ]],
        'shipping_address_collection' => ['allowed_countries' => ['US', 'CA']],
        'metadata' => ['photo' => $slug, 'format' => $fmt, 'size' => $size, 'qty' => (string)$qty],
        'success_url' => rtrim($cfg['site_url'], '/') . '/order-success.php',
        'cancel_url'  => rtrim($cfg['site_url'], '/') . '/order.php?cancelled=1',
    ]);
    echo json_encode(['url' => $session->url]);
} catch (\Throwable $e) {
    http_response_code(502);
    echo json_encode(['error' => 'Checkout failed', 'fallback' => 'email']);
}
