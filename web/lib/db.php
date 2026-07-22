<?php
/**
 * Orders storage — SQLite via PDO. The DB lives in web/storage/, which is
 * denied to the web by .htaccess. Created on first write (the Stripe webhook).
 */

function bh_db(): PDO {
    $dir = dirname(__DIR__) . '/storage';
    if (!is_dir($dir)) mkdir($dir, 0775, true);
    $pdo = new PDO('sqlite:' . $dir . '/orders.db');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->exec("CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created TEXT NOT NULL,
        stripe_session_id TEXT UNIQUE,
        payment_intent TEXT,
        email TEXT,
        name TEXT,
        amount_total INTEGER,
        currency TEXT,
        photo TEXT,
        format TEXT,
        size TEXT,
        qty INTEGER,
        shipping_json TEXT,
        status TEXT DEFAULT 'paid',
        fulfillment TEXT DEFAULT 'new',
        notes TEXT DEFAULT ''
    )");
    return $pdo;
}

/** Insert an order from a Stripe Checkout Session object (array). */
function bh_record_order(array $s): void {
    $md = $s['metadata'] ?? [];
    $details = $s['customer_details'] ?? [];
    $shipping = $s['shipping_details']
        ?? ($s['collected_information']['shipping_details'] ?? []);
    $db = bh_db();
    $stmt = $db->prepare("INSERT OR IGNORE INTO orders
        (created, stripe_session_id, payment_intent, email, name,
         amount_total, currency, photo, format, size, qty, shipping_json)
        VALUES (:created,:sid,:pi,:email,:name,:amt,:cur,:photo,:fmt,:size,:qty,:ship)");
    $stmt->execute([
        ':created' => gmdate('c'),
        ':sid'   => $s['id'] ?? null,
        ':pi'    => is_array($s['payment_intent'] ?? null) ? ($s['payment_intent']['id'] ?? null) : ($s['payment_intent'] ?? null),
        ':email' => $details['email'] ?? ($s['customer_email'] ?? null),
        ':name'  => $details['name'] ?? null,
        ':amt'   => $s['amount_total'] ?? null,
        ':cur'   => $s['currency'] ?? null,
        ':photo' => $md['photo'] ?? null,
        ':fmt'   => $md['format'] ?? null,
        ':size'  => $md['size'] ?? null,
        ':qty'   => (int) ($md['qty'] ?? 1),
        ':ship'  => json_encode($shipping),
    ]);
}

function bh_orders(int $limit = 200): array {
    $stmt = bh_db()->prepare("SELECT * FROM orders ORDER BY id DESC LIMIT :n");
    $stmt->bindValue(':n', $limit, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

function bh_set_fulfillment(int $id, string $fulfillment, string $notes): void {
    $stmt = bh_db()->prepare("UPDATE orders SET fulfillment=:f, notes=:n WHERE id=:id");
    $stmt->execute([':f' => $fulfillment, ':n' => $notes, ':id' => $id]);
}

/** Everything needed to place this order by hand in the Prodigi dashboard. */
function bh_fulfill_hint(array $o): string {
    $ship = json_decode($o['shipping_json'] ?? '{}', true) ?: [];
    $addr = $ship['address'] ?? [];
    $lines = [
        "Photo: {$o['photo']}  |  {$o['format']} {$o['size']}\"  x{$o['qty']}",
        "Print file: output/print/{$o['photo']}.jpg  (300 DPI, full res)",
        "Ship to: " . ($ship['name'] ?? $o['name'] ?? ''),
        "  " . trim(($addr['line1'] ?? '') . ' ' . ($addr['line2'] ?? '')),
        "  " . ($addr['city'] ?? '') . ", " . ($addr['state'] ?? '') . " "
             . ($addr['postal_code'] ?? '') . " " . ($addr['country'] ?? ''),
        "Customer: {$o['email']}",
    ];
    return implode("\n", $lines);
}
