<?php
/**
 * Serve print-ready JPGs to Prodigi (signed URL only).
 * Prodigi downloads this after we POST an order — must be reachable at site_url.
 */

require dirname(__DIR__) . '/lib/prodigi.php';

$slug = (string)($_GET['slug'] ?? '');
$ref  = (string)($_GET['ref'] ?? '');
$t    = (string)($_GET['t'] ?? '');

if ($slug === '' || $ref === '' || $t === '') {
    http_response_code(400); echo 'bad request'; exit;
}
if (!hash_equals(bh_print_asset_token($slug, $ref), $t)) {
    http_response_code(403); echo 'forbidden'; exit;
}

$path = bh_print_file_path($slug);
if (!$path) {
    http_response_code(404); echo 'print file not found'; exit;
}

header('Content-Type: image/jpeg');
header('Content-Length: ' . filesize($path));
header('Cache-Control: private, max-age=3600');
readfile($path);
