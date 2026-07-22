<?php
/** Admin: order fulfillment. Payments arrive via the Stripe webhook; you place
 *  the actual print order in the Prodigi dashboard, then mark it here. */

require dirname(__DIR__) . '/lib/data.php';
require dirname(__DIR__) . '/lib/db.php';
require dirname(__DIR__) . '/lib/auth.php';

$err = '';
if (($_POST['action'] ?? '') === 'login') {
    if (bh_admin_login($_POST['password'] ?? '')) { header('Location: index.php'); exit; }
    $err = 'Wrong password.';
}
if (($_GET['logout'] ?? '') === '1') { bh_admin_logout(); header('Location: index.php'); exit; }

if (!bh_is_admin()):
    $rel = '../'; $active = ''; $page_title = 'Admin Login';
    include dirname(__DIR__) . '/partials/head.php'; ?>
    <div style="min-height:100vh; display:flex; align-items:center; justify-content:center">
      <form method="post" style="background:#fff; border:1px solid var(--line); padding:2.4rem; width:min(92vw,360px); text-align:center">
        <input type="hidden" name="action" value="login">
        <h1 style="color:var(--navy); letter-spacing:.16em; font-size:1.1rem; margin-bottom:1.4rem">BLUEHERON.GALLERY</h1>
        <input type="password" name="password" placeholder="Admin password" autofocus required
               style="width:100%; padding:.65rem .8rem; border:1px solid var(--line); box-sizing:border-box">
        <button class="btn btn-solid" style="width:100%; margin-top:1rem; border:none; cursor:pointer">LOG IN</button>
        <?php if ($err): ?><p style="color:#a33; margin-top:.8rem; font-size:.85rem"><?= e($err) ?></p><?php endif; ?>
      </form>
    </div>
    </body></html>
    <?php exit;
endif;

// --- logged in ---
if (($_POST['action'] ?? '') === 'fulfill') {
    bh_set_fulfillment((int)$_POST['id'], $_POST['fulfillment'] ?? 'new', $_POST['notes'] ?? '');
    header('Location: index.php'); exit;
}

$orders = bh_orders();
$rel = '../'; $active = ''; $page_title = 'Orders';
include dirname(__DIR__) . '/partials/head.php';
?>
<div style="max-width:1100px; margin:0 auto; padding:2rem 1.4rem">
  <div style="display:flex; align-items:center; gap:1rem; margin-bottom:1.4rem">
    <h1 style="color:var(--navy); font-size:1.5rem; flex:1">Orders</h1>
    <a href="../index.php" target="_blank">View site ↗</a>
    <a href="?logout=1">Log out</a>
  </div>
  <p class="muted" style="color:var(--slate); font-size:.9rem">Payments arrive via Stripe.
  Place the print order in the <a href="https://dashboard.prodigi.com" target="_blank">Prodigi
  dashboard</a> using the details below (print file in <code>output/print/</code>), then mark it fulfilled.</p>

  <table style="width:100%; border-collapse:collapse; background:#fff; margin-top:1rem; font-size:.88rem">
    <tr style="background:var(--navy); color:var(--cream)">
      <th style="padding:.5rem .7rem; text-align:left">#</th>
      <th style="padding:.5rem .7rem; text-align:left">When</th>
      <th style="padding:.5rem .7rem; text-align:left">Item</th>
      <th style="padding:.5rem .7rem; text-align:left">Amount</th>
      <th style="padding:.5rem .7rem; text-align:left">Fulfillment details</th>
      <th style="padding:.5rem .7rem; text-align:left">Status</th>
    </tr>
    <?php foreach ($orders as $o): ?>
    <tr style="border-bottom:1px solid var(--line); vertical-align:top">
      <td style="padding:.5rem .7rem"><?= (int)$o['id'] ?></td>
      <td style="padding:.5rem .7rem; color:var(--slate)"><?= e(substr($o['created'], 0, 10)) ?></td>
      <td style="padding:.5rem .7rem"><?= e($o['photo']) ?><br>
          <span style="color:var(--slate)"><?= e($o['format']) ?> <?= e($o['size']) ?>" ×<?= (int)$o['qty'] ?></span></td>
      <td style="padding:.5rem .7rem"><?= bh_money((int)$o['amount_total']) ?></td>
      <td style="padding:.5rem .7rem"><pre style="white-space:pre-wrap; margin:0; font-size:.78rem; background:var(--cream); padding:.5rem"><?= e(bh_fulfill_hint($o)) ?></pre></td>
      <td style="padding:.5rem .7rem">
        <form method="post">
          <input type="hidden" name="action" value="fulfill">
          <input type="hidden" name="id" value="<?= (int)$o['id'] ?>">
          <select name="fulfillment">
            <?php foreach (['new','placed-with-prodigi','shipped','complete','refunded'] as $s): ?>
              <option value="<?= $s ?>" <?= $o['fulfillment'] === $s ? 'selected' : '' ?>><?= $s ?></option>
            <?php endforeach; ?>
          </select><br>
          <input type="text" name="notes" value="<?= e($o['notes']) ?>" placeholder="Prodigi order id / notes"
                 style="margin-top:.3rem; width:150px; padding:.3rem">
          <button class="btn btn-solid" style="margin-top:.3rem; border:none; cursor:pointer; padding:.3rem .8rem">Save</button>
        </form>
      </td>
    </tr>
    <?php endforeach; ?>
    <?php if (!$orders): ?><tr><td colspan="6" style="padding:1rem; color:var(--slate)">No orders yet.</td></tr><?php endif; ?>
  </table>
</div>
</body></html>
