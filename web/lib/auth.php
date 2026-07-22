<?php
/** Simple session auth for /admin. */

function bh_admin_login(string $password): bool {
    $cfg = require dirname(__DIR__) . '/config.php';
    $stored = $cfg['admin_password'] ?? '';
    if ($stored === '' ) return false;
    if (hash_equals($stored, $password)) {
        if (session_status() !== PHP_SESSION_ACTIVE) session_start();
        session_regenerate_id(true);
        $_SESSION['bh_admin'] = true;
        return true;
    }
    return false;
}

function bh_is_admin(): bool {
    if (session_status() !== PHP_SESSION_ACTIVE) session_start();
    return !empty($_SESSION['bh_admin']);
}

function bh_admin_logout(): void {
    if (session_status() !== PHP_SESSION_ACTIVE) session_start();
    $_SESSION = [];
    session_destroy();
}

function bh_require_admin(): void {
    if (!bh_is_admin()) {
        header('Location: index.php?login=1');
        exit;
    }
}
