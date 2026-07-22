<?php
require __DIR__ . '/lib/data.php';
$rel = '';
$active = 'prints';
$page_title = 'Thank You';
$page_desc = 'Your great blue heron print order has been received.';
include __DIR__ . '/partials/head.php';
include __DIR__ . '/partials/nav.php';
?>
<section style="min-height:80vh; display:flex; align-items:center; justify-content:center; text-align:center; padding-top:5rem">
  <div>
    <p class="section-kicker">ORDER RECEIVED</p>
    <h1 class="section-title">Thank You</h1>
    <p class="section-sub" style="margin-bottom:2rem">Your print is being made to order.
    A receipt is on its way to your inbox, and we'll email tracking when it ships.</p>
    <a class="btn btn-solid" href="index.php#gallery">Back to the Gallery</a>
  </div>
</section>
<?php include __DIR__ . '/partials/footer.php'; ?>
