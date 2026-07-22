<?php
require __DIR__ . '/lib/data.php';
$rel = '';
$active = 'prints';
$page_title = 'Order a Print';
$page_desc = 'Order a great blue heron fine art print — paper, framed, canvas, metal, or wood.';
$photos = bh_photos(true);
$catalog = bh_catalog();
$pre = $_GET['photo'] ?? '';
$extra_css = ['assets/order.css'];
include __DIR__ . '/partials/head.php';
include __DIR__ . '/partials/nav.php';
?>

<div class="order-wrap">
  <figure class="order-preview">
    <img id="preview" src="" alt="Selected photograph">
    <figcaption id="previewTitle"></figcaption>
  </figure>

  <form class="order-form" id="orderForm">
    <p class="section-kicker" style="text-align:left">FINE ART PRINTS</p>
    <h1 class="section-title" style="text-align:left; font-size:2.2rem">Order a Print</h1>

    <label for="photo">Photograph</label>
    <select id="photo" name="photo">
      <?php foreach ($photos as $p): ?>
        <option value="<?= e($p['slug']) ?>" data-img="images/web/<?= e($p['file']) ?>"
          <?= $p['slug'] === $pre ? 'selected' : '' ?>><?= e($p['title']) ?></option>
      <?php endforeach; ?>
    </select>

    <label for="format">Product</label>
    <select id="format" name="format">
      <?php foreach (bh_categories_with_formats() as $group): ?>
        <optgroup label="<?= e($group['label']) ?>">
          <?php foreach ($group['formats'] as $key => $f): ?>
            <option value="<?= e($key) ?>"><?= e($f['label']) ?></option>
          <?php endforeach; ?>
        </optgroup>
      <?php endforeach; ?>
    </select>

    <label for="size" id="sizeLabel">Size</label>
    <select id="size" name="size"></select>

    <label for="qty">Quantity</label>
    <input id="qty" name="qty" type="number" min="1" max="10" value="1">

    <div class="order-total">
      <span class="muted" style="font-size:.8rem; letter-spacing:.2em">TOTAL</span>
      <span class="amt" id="total">—</span>
    </div>

    <button class="btn btn-solid" type="submit" id="checkoutBtn">Continue to Secure Checkout</button>
    <p class="order-msg" id="msg">Payment is handled by Stripe. Prints are made to
    order and ship in 5–7 business days.</p>
  </form>
</div>

<script>
// Catalog is emitted by PHP so pricing is instant and matches the server.
var CATALOG = <?= json_encode($catalog, JSON_UNESCAPED_SLASHES) ?>;
var CONTACT = <?= json_encode((require __DIR__ . '/config.php')['contact_email']) ?>;
var $ = function(id){ return document.getElementById(id); };

function money(d){ return '$' + d.toLocaleString('en-US'); }
function qty(){ return Math.max(1, Math.min(10, parseInt($('qty').value)||1)); }

function optLabel(s){
  // Turn "24x16" into "24 × 16"; leave "11 oz", "iPhone 15", "Set of 4" as-is.
  return /^\d+x\d+$/.test(s) ? s.replace('x', ' × ') : s;
}
function refreshSizes(){
  var f = CATALOG.formats[$('format').value];
  $('sizeLabel').textContent = f.unit || 'Option';
  $('size').innerHTML = Object.keys(f.sizes).map(function(s){
    return '<option value="'+s+'">'+optLabel(s)+' — '+money(f.sizes[s])+'</option>';
  }).join('');
  refreshTotal();
}
function refreshTotal(){
  var f = CATALOG.formats[$('format').value];
  var d = f ? f.sizes[$('size').value] : null;
  $('total').textContent = d ? money(d * qty()) : '—';
}
function refreshPreview(){
  var opt = $('photo').selectedOptions[0];
  if(!opt) return;
  $('preview').src = opt.dataset.img;
  $('previewTitle').textContent = opt.textContent;
}

$('photo').addEventListener('change', refreshPreview);
$('format').addEventListener('change', refreshSizes);
$('size').addEventListener('change', refreshTotal);
$('qty').addEventListener('input', refreshTotal);
refreshSizes(); refreshPreview();

$('orderForm').addEventListener('submit', async function(e){
  e.preventDefault();
  $('checkoutBtn').disabled = true; $('checkoutBtn').textContent = 'OPENING CHECKOUT…';
  try {
    var r = await fetch('api/checkout.php', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ photo:$('photo').value, format:$('format').value, size:$('size').value, qty:qty() })
    });
    var j = await r.json();
    if(r.ok && j.url){ location.href = j.url; return; }
    var item = $('photo').value+' — '+$('format').value+' '+$('size').value+' ×'+qty();
    $('msg').innerHTML = 'Online checkout isn\'t available yet — email '+
      '<a href="mailto:'+CONTACT+'?subject=Print%20order&body='+encodeURIComponent(item)+'">'+CONTACT+'</a> with: <em>'+item+'</em>';
  } catch(err){ $('msg').textContent = 'Something went wrong — please try again.'; }
  $('checkoutBtn').disabled = false; $('checkoutBtn').textContent = 'Continue to Secure Checkout';
});
</script>

<?php include __DIR__ . '/partials/footer.php'; ?>
