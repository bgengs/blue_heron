<?php
/**
 * Reads the photo manifest and print catalog produced by the Python studio
 * tool. Pure reads — the PHP site never writes these.
 */

function bh_data_dir(): string {
    return dirname(__DIR__) . '/data';
}

function bh_load_json(string $file, $fallback) {
    $path = bh_data_dir() . '/' . $file;
    if (!is_file($path)) return $fallback;
    $data = json_decode(file_get_contents($path), true);
    return $data === null ? $fallback : $data;
}

/** All photos, or only the live ones, sorted by their sort field. */
function bh_photos(bool $active_only = true): array {
    $photos = bh_load_json('photos.json', []);
    if ($active_only) {
        $photos = array_filter($photos, fn($p) => !empty($p['active']));
    }
    usort($photos, fn($a, $b) => ($a['sort'] ?? 0) <=> ($b['sort'] ?? 0));
    return array_values($photos);
}

function bh_photo(string $slug): ?array {
    foreach (bh_load_json('photos.json', []) as $p) {
        if (($p['slug'] ?? null) === $slug) return $p;
    }
    return null;
}

function bh_catalog(): array {
    return bh_load_json('catalog.json', ['currency' => 'usd', 'formats' => []]);
}

/** Price in cents for a format+size, or null if not offered. */
function bh_price_cents(string $fmt, string $size): ?int {
    $catalog = bh_catalog();
    $f = $catalog['formats'][$fmt] ?? null;
    if (!$f) return null;
    $dollars = $f['sizes'][$size] ?? null;
    if ($dollars === null) return null;
    return (int) round(((float) $dollars) * 100);
}

function bh_money(int $cents): string {
    return '$' . number_format($cents / 100, ($cents % 100 === 0) ? 0 : 2);
}

/** HTML-escape shortcut. */
function e(?string $s): string {
    return htmlspecialchars($s ?? '', ENT_QUOTES, 'UTF-8');
}
