<?php
/**
 * Prodigi Print API v4 — create orders after Stripe payment.
 *
 * Docs: https://www.prodigi.com/print-api/docs/reference/
 * Sandbox: https://api.sandbox.prodigi.com/v4.0
 * Live:    https://api.prodigi.com/v4.0
 */

require_once __DIR__ . '/data.php';

function bh_prodigi_cfg(): array {
    static $cfg;
    if ($cfg === null) $cfg = require dirname(__DIR__) . '/config.php';
    return $cfg;
}

function bh_prodigi_configured(): bool {
    return trim((string)(bh_prodigi_cfg()['prodigi_api_key'] ?? '')) !== '';
}

function bh_prodigi_base(): string {
    $cfg = bh_prodigi_cfg();
    return !empty($cfg['prodigi_sandbox'])
        ? 'https://api.sandbox.prodigi.com/v4.0'
        : 'https://api.prodigi.com/v4.0';
}

/** Look up Prodigi SKU (+ optional attributes) for a catalog format/size. */
function bh_prodigi_sku(string $fmt, string $size): ?array {
    $catalog = bh_catalog();
    $f = $catalog['formats'][$fmt] ?? null;
    if (!$f) return null;
    $map = $f['prodigi'][$size] ?? null;
    if (!$map || empty($map['sku'])) return null;
    return [
        'sku' => (string)$map['sku'],
        'attributes' => is_array($map['attributes'] ?? null) ? $map['attributes'] : [],
        'sizing' => (string)($map['sizing'] ?? 'fillPrintArea'),
    ];
}

/** HMAC token so Prodigi can download the print file without a public gallery. */
function bh_print_asset_token(string $slug, string $ref): string {
    $cfg = bh_prodigi_cfg();
    $secret = (string)($cfg['asset_signing_secret'] ?? $cfg['admin_password'] ?? 'blueheron');
    return hash_hmac('sha256', $slug . '|' . $ref, $secret);
}

function bh_print_asset_url(string $slug, string $ref): string {
    $cfg = bh_prodigi_cfg();
    $base = rtrim((string)$cfg['site_url'], '/');
    $t = bh_print_asset_token($slug, $ref);
    return $base . '/api/print-asset.php?slug=' . rawurlencode($slug)
         . '&ref=' . rawurlencode($ref) . '&t=' . rawurlencode($t);
}

/**
 * Absolute path to the print-ready JPG for a photo slug, or null.
 * Prefers web/images/print/ (deployed), then ../output/print/ (local studio).
 */
function bh_print_file_path(string $slug): ?string {
    $photo = bh_photo($slug);
    if (!$photo) return null;
    $file = (string)($photo['file'] ?? ($slug . '.jpg'));
    $candidates = [
        dirname(__DIR__) . '/images/print/' . $file,
        dirname(__DIR__) . '/images/print/' . $slug . '.jpg',
        dirname(__DIR__, 2) . '/output/print/' . $file,
        dirname(__DIR__, 2) . '/output/print/' . $slug . '.jpg',
    ];
    foreach ($candidates as $p) {
        if (is_file($p)) return $p;
    }
    return null;
}

/** Map a Stripe Checkout Session (+ our order row) into a Prodigi recipient. */
function bh_prodigi_recipient(array $order): array {
    $ship = json_decode($order['shipping_json'] ?? '{}', true) ?: [];
    $addr = $ship['address'] ?? [];
    return [
        'name'  => (string)($ship['name'] ?? $order['name'] ?? 'Customer'),
        'email' => (string)($order['email'] ?? ''),
        'address' => [
            'line1'           => (string)($addr['line1'] ?? ''),
            'line2'           => (string)($addr['line2'] ?? ''),
            'postalOrZipCode' => (string)($addr['postal_code'] ?? ''),
            'countryCode'     => (string)($addr['country'] ?? 'US'),
            'townOrCity'      => (string)($addr['city'] ?? ''),
            'stateOrCounty'   => (string)($addr['state'] ?? ''),
        ],
    ];
}

/**
 * Create a Prodigi order for a recorded Stripe order.
 * Returns ['ok'=>true, 'id'=>..., 'raw'=>...] or ['ok'=>false, 'error'=>...].
 */
function bh_prodigi_create_order(array $order): array {
    if (!bh_prodigi_configured()) {
        return ['ok' => false, 'error' => 'Prodigi API key not configured'];
    }

    $fmt  = (string)($order['format'] ?? '');
    $size = (string)($order['size'] ?? '');
    $slug = (string)($order['photo'] ?? '');
    $qty  = max(1, (int)($order['qty'] ?? 1));
    $sku  = bh_prodigi_sku($fmt, $size);
    if (!$sku) {
        return ['ok' => false, 'error' => "No Prodigi SKU mapped for {$fmt}/{$size}"];
    }
    if (!bh_print_file_path($slug)) {
        return ['ok' => false, 'error' => "Print file missing for photo '{$slug}' (need images/print or output/print)"];
    }

    $ref = (string)($order['stripe_session_id'] ?? ('order-' . ($order['id'] ?? time())));
    $item = [
        'merchantReference' => $ref . ':' . $slug,
        'sku'    => $sku['sku'],
        'copies' => $qty,
        'sizing' => $sku['sizing'],
        'assets' => [[
            'printArea' => 'default',
            'url'       => bh_print_asset_url($slug, $ref),
        ]],
    ];
    if ($sku['attributes']) {
        $item['attributes'] = $sku['attributes'];
    }

    $cfg = bh_prodigi_cfg();
    $payload = [
        'merchantReference' => $ref,
        'shippingMethod'    => (string)($cfg['prodigi_shipping_method'] ?? 'Budget'),
        'recipient'         => bh_prodigi_recipient($order),
        'items'             => [$item],
        'metadata'          => [
            'stripe_session' => (string)($order['stripe_session_id'] ?? ''),
            'photo'          => $slug,
            'format'         => $fmt,
            'size'           => $size,
        ],
    ];

    $res = bh_prodigi_request('POST', '/Orders', $payload);
    if (!$res['ok']) return $res;

    $id = $res['json']['order']['id']
       ?? $res['json']['id']
       ?? null;
    if (!$id) {
        return ['ok' => false, 'error' => 'Prodigi response missing order id', 'raw' => $res['json']];
    }
    return ['ok' => true, 'id' => (string)$id, 'raw' => $res['json']];
}

/** Low-level HTTP to Prodigi (PHP streams — no curl extension required). */
function bh_prodigi_request(string $method, string $path, ?array $body = null): array {
    $cfg = bh_prodigi_cfg();
    $url = bh_prodigi_base() . $path;
    $headers = [
        'X-API-Key: ' . $cfg['prodigi_api_key'],
        'Content-Type: application/json',
        'Accept: application/json',
    ];
    $opts = [
        'http' => [
            'method'        => $method,
            'header'        => implode("\r\n", $headers),
            'timeout'       => 60,
            'ignore_errors' => true,
        ],
    ];
    if ($body !== null) {
        $opts['http']['content'] = json_encode($body);
    }
    $raw = @file_get_contents($url, false, stream_context_create($opts));
    if ($raw === false) {
        return ['ok' => false, 'error' => 'Prodigi HTTP request failed (network or allow_url_fopen)'];
    }
    $code = 0;
    if (!empty($http_response_header[0]) && preg_match('/\s(\d{3})\s/', $http_response_header[0], $m)) {
        $code = (int)$m[1];
    }
    $json = json_decode($raw, true);
    if ($code < 200 || $code >= 300) {
        $msg = is_array($json)
            ? ($json['message'] ?? $json['error'] ?? null)
            : null;
        if (is_array($msg)) $msg = json_encode($msg);
        if (!$msg && is_array($json) && !empty($json['failures'][0]['errorMessage'])) {
            $msg = $json['failures'][0]['errorMessage'];
        }
        if (!$msg) $msg = $raw;
        return ['ok' => false, 'error' => "Prodigi {$code}: {$msg}", 'raw' => $json];
    }
    return ['ok' => true, 'json' => $json, 'code' => $code];
}

/** Round retail up to a friendly dollar amount (never below cost). */
function bh_apply_markup(float $wholesaleUsd, ?float $multiplier = null): float {
    $cfg = bh_prodigi_cfg();
    $m = $multiplier ?? (float)($cfg['markup_multiplier'] ?? 2.5);
    if ($m < 1) $m = 1;
    $raw = $wholesaleUsd * $m;
    // Nearest whole dollar, always round up so margin isn't eroded.
    $retail = (float)ceil($raw);
    if ($retail < $wholesaleUsd) $retail = (float)ceil($wholesaleUsd);
    return $retail;
}

/**
 * Quote one SKU via Prodigi and return wholesale product cost in USD (ex-shipping).
 * Returns null on failure.
 */
function bh_prodigi_quote_cost(string $sku, array $attributes = []): ?array {
    $cfg = bh_prodigi_cfg();
    $item = [
        'sku' => $sku,
        'copies' => 1,
        'sizing' => 'fillPrintArea',
    ];
    if ($attributes) $item['attributes'] = $attributes;

    $body = [
        'shippingMethod' => (string)($cfg['prodigi_shipping_method'] ?? 'Budget'),
        'destinationCountryCode' => (string)($cfg['markup_quote_country'] ?? 'US'),
        'currencyCode' => 'USD',
        'items' => [$item],
    ];
    $res = bh_prodigi_request('POST', '/quotes', $body);
    if (!$res['ok']) {
        return ['ok' => false, 'error' => $res['error'] ?? 'quote failed'];
    }

    $json = $res['json'] ?? [];
    // v4 quotes usually nest under quotes[0]
    $quote = $json['quotes'][0] ?? $json['quote'] ?? $json;
    $items = $quote['items'] ?? [];
    $product = 0.0;
    $shipping = 0.0;
    $currency = strtoupper((string)($quote['currencyCode']
        ?? $quote['cost']['currency']
        ?? $json['currencyCode']
        ?? 'USD'));

    foreach ($items as $it) {
        $c = $it['cost'] ?? $it['unitCost'] ?? null;
        if (is_array($c)) {
            $product += (float)($c['amount'] ?? $c['value'] ?? 0);
        } elseif (is_numeric($c)) {
            $product += (float)$c;
        }
    }
    $shipCost = $quote['shipping']['cost']
        ?? $quote['shipment']['cost']
        ?? $quote['cost']['shipping']
        ?? null;
    if (is_array($shipCost)) {
        $shipping = (float)($shipCost['amount'] ?? $shipCost['value'] ?? 0);
    } elseif (is_numeric($shipCost)) {
        $shipping = (float)$shipCost;
    }

    // Fallback: some responses only expose a total.
    if ($product <= 0) {
        $total = $quote['cost']['amount'] ?? $quote['totalCost']['amount'] ?? null;
        if (is_numeric($total)) $product = (float)$total - $shipping;
    }
    if ($product <= 0) {
        return ['ok' => false, 'error' => 'Could not parse product cost from quote', 'raw' => $json];
    }

    return [
        'ok' => true,
        'product' => round($product, 2),
        'shipping' => round($shipping, 2),
        'currency' => $currency,
        'raw' => $json,
    ];
}

/**
 * Refresh every catalog option that has a Prodigi SKU:
 * quote wholesale → apply markup → write retail into sizes + cost into prodigi map.
 *
 * @return array{ok:bool,updated:int,failed:int,rows:array,error?:string}
 */
function bh_prodigi_refresh_prices(): array {
    if (!bh_prodigi_configured()) {
        return ['ok' => false, 'updated' => 0, 'failed' => 0, 'rows' => [], 'error' => 'Prodigi API key not set'];
    }
    $path = bh_data_dir() . '/catalog.json';
    $catalog = bh_catalog();
    if (empty($catalog['formats'])) {
        return ['ok' => false, 'updated' => 0, 'failed' => 0, 'rows' => [], 'error' => 'Empty catalog'];
    }

    $updated = 0;
    $failed = 0;
    $rows = [];

    foreach ($catalog['formats'] as $fmtKey => &$fmt) {
        $sizes = $fmt['sizes'] ?? [];
        $prodigi = $fmt['prodigi'] ?? [];
        foreach ($prodigi as $opt => $map) {
            $sku = (string)($map['sku'] ?? '');
            if ($sku === '') continue;
            $attrs = is_array($map['attributes'] ?? null) ? $map['attributes'] : [];
            $q = bh_prodigi_quote_cost($sku, $attrs);
            if (empty($q['ok'])) {
                $failed++;
                $rows[] = [
                    'format' => $fmtKey, 'option' => $opt, 'sku' => $sku,
                    'ok' => false, 'error' => $q['error'] ?? 'failed',
                ];
                continue;
            }
            $cost = (float)$q['product'];
            $retail = bh_apply_markup($cost);
            $fmt['sizes'][$opt] = $retail;
            $fmt['prodigi'][$opt]['cost'] = $cost;
            $fmt['prodigi'][$opt]['cost_currency'] = $q['currency'] ?? 'USD';
            $fmt['prodigi'][$opt]['cost_updated'] = gmdate('c');
            $updated++;
            $rows[] = [
                'format' => $fmtKey, 'option' => $opt, 'sku' => $sku,
                'ok' => true, 'cost' => $cost, 'retail' => $retail,
            ];
            // Be gentle on the API.
            usleep(150000);
        }
        unset($fmt);
    }

    $catalog['_prices_refreshed'] = gmdate('c');
    $catalog['_markup_multiplier'] = (float)(bh_prodigi_cfg()['markup_multiplier'] ?? 2.5);
    $json = json_encode($catalog, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if ($json === false || file_put_contents($path, $json . "\n") === false) {
        return ['ok' => false, 'updated' => $updated, 'failed' => $failed, 'rows' => $rows, 'error' => 'Could not write catalog.json'];
    }
    return ['ok' => true, 'updated' => $updated, 'failed' => $failed, 'rows' => $rows];
}
