<?php
/** Admin: refresh retail prices from Prodigi wholesale × markup. */

require dirname(__DIR__) . '/lib/data.php';
require dirname(__DIR__) . '/lib/auth.php';
require dirname(__DIR__) . '/lib/prodigi.php';

if (!bh_is_admin()) {
    header('Location: index.php');
    exit;
}

$cfg = bh_prodigi_cfg();
$result = null;
if (($_POST['action'] ?? '') === 'refresh') {
    // Long-running: quote every SKU.
    set_time_limit(300);
    $result = bh_prodigi_refresh_prices();
}

$catalog = bh_catalog();
$mult = (float)($cfg['markup_multiplier'] ?? 2.5);
$rel = '../'; $active = ''; $page_title = 'Prices';
include dirname(__DIR__) . '/partials/head.php';
?>
<div style="max-width:1100px; margin:0 auto; padding:2rem 1.4rem">
  <div style="display:flex; align-items:center; gap:1rem; margin-bottom:1.4rem; flex-wrap:wrap">
    <h1 style="color:var(--navy); font-size:1.5rem; flex:1">Prices</h1>
    <a href="index.php">Orders</a>
    <a href="../order.php" target="_blank">Order page ↗</a>
    <a href="index.php?logout=1">Log out</a>
  </div>

  <p class="muted" style="color:var(--slate); font-size:.9rem; max-width:42rem">
    Retail on the site is <code>ceil(Prodigi wholesale × <?= e((string)$mult) ?>)</code>.
    Refresh quotes each SKU from Prodigi and writes cost + retail into
    <code>data/catalog.json</code>. Same products can be listed on Etsy via
    Prodigi’s Etsy channel — keep SKUs in sync here.
  </p>

  <form method="post" style="margin:1.2rem 0">
    <input type="hidden" name="action" value="refresh">
    <button class="btn btn-solid" type="submit" <?= bh_prodigi_configured() ? '' : 'disabled' ?>
            style="border:none; cursor:pointer">
      Refresh prices from Prodigi
    </button>
    <?php if (!bh_prodigi_configured()): ?>
      <span style="color:#a33; margin-left:.8rem; font-size:.85rem">Set prodigi_api_key first</span>
    <?php endif; ?>
  </form>

  <?php if ($result): ?>
    <div style="background:#fff; border:1px solid var(--line); padding:1rem 1.2rem; margin-bottom:1.4rem">
      <?php if (!empty($result['ok'])): ?>
        <strong style="color:#2e7d4f">Updated <?= (int)$result['updated'] ?></strong>
        <?php if ($result['failed']): ?>
          · <span style="color:#a33"><?= (int)$result['failed'] ?> failed</span>
        <?php endif; ?>
      <?php else: ?>
        <strong style="color:#a33"><?= e($result['error'] ?? 'Refresh failed') ?></strong>
      <?php endif; ?>
    </div>
  <?php endif; ?>

  <?php if (!empty($catalog['_prices_refreshed'])): ?>
    <p class="muted" style="font-size:.8rem; color:var(--slate)">
      Last refresh: <?= e($catalog['_prices_refreshed']) ?>
      · markup ×<?= e((string)($catalog['_markup_multiplier'] ?? $mult)) ?>
    </p>
  <?php endif; ?>

  <table style="width:100%; border-collapse:collapse; background:#fff; margin-top:1rem; font-size:.85rem">
    <tr style="background:var(--navy); color:var(--cream)">
      <th style="padding:.45rem .6rem; text-align:left">Product</th>
      <th style="padding:.45rem .6rem; text-align:left">Option</th>
      <th style="padding:.45rem .6rem; text-align:left">SKU</th>
      <th style="padding:.45rem .6rem; text-align:right">Wholesale</th>
      <th style="padding:.45rem .6rem; text-align:right">Retail</th>
    </tr>
    <?php foreach ($catalog['formats'] as $fkey => $f): ?>
      <?php foreach (($f['sizes'] ?? []) as $opt => $retail):
        $map = $f['prodigi'][$opt] ?? [];
        $cost = $map['cost'] ?? null;
      ?>
      <tr style="border-bottom:1px solid var(--line)">
        <td style="padding:.4rem .6rem"><?= e($f['label'] ?? $fkey) ?></td>
        <td style="padding:.4rem .6rem"><?= e((string)$opt) ?></td>
        <td style="padding:.4rem .6rem; font-family:monospace; font-size:.78rem"><?= e($map['sku'] ?? '—') ?></td>
        <td style="padding:.4rem .6rem; text-align:right; color:var(--slate)">
          <?= $cost !== null ? '$' . number_format((float)$cost, 2) : '—' ?>
        </td>
        <td style="padding:.4rem .6rem; text-align:right; font-weight:600">
          $<?= number_format((float)$retail, (floor($retail) == $retail) ? 0 : 2) ?>
        </td>
      </tr>
      <?php endforeach; ?>
    <?php endforeach; ?>
  </table>

  <?php if ($result && !empty($result['rows'])): ?>
    <h2 style="color:var(--navy); margin-top:2rem; font-size:1.1rem">Last run detail</h2>
    <ul style="font-size:.82rem; color:var(--slate); line-height:1.6">
      <?php foreach ($result['rows'] as $r): ?>
        <li>
          <?= e($r['format'] . ' / ' . $r['option']) ?>
          <?php if (!empty($r['ok'])): ?>
            — cost $<?= number_format((float)$r['cost'], 2) ?> → retail $<?= number_format((float)$r['retail'], 0) ?>
          <?php else: ?>
            — <span style="color:#a33"><?= e($r['error'] ?? 'failed') ?></span>
          <?php endif; ?>
        </li>
      <?php endforeach; ?>
    </ul>
  <?php endif; ?>
</div>
</body></html>
