<?php
require __DIR__ . '/lib/data.php';
$rel = '';
$active = '';
$page_title = 'The Great Blue Heron';
$page_desc = 'Fine art prints of great blue herons photographed in the rookery — '
    . 'nesting pairs, families, and fledglings in the Montana cottonwoods.';
$photos = bh_photos(true);
include __DIR__ . '/partials/head.php';
include __DIR__ . '/partials/nav.php';
?>

<header class="hero" id="top">
  <div class="hero-inner">
    <p class="hero-kicker">BLUEHERON.GALLERY</p>
    <h1>The Great<br>Blue Heron</h1>
    <div class="hero-rule"></div>
    <p class="hero-sub">A season in the rookery — nesting pairs, families, and first
    flights among the Montana cottonwoods, photographed from the air.</p>
    <div class="hero-actions">
      <a class="btn btn-solid" href="order.php">Shop the Collection</a>
      <a class="btn btn-ghost" href="#facts">Meet the Herons</a>
    </div>
  </div>
  <?php if ($photos): $h = $photos[0]; ?>
  <figure class="hero-photo">
    <img src="images/web/<?= e($h['file']) ?>" alt="<?= e($h['caption'] ?: $h['title']) ?>">
  </figure>
  <?php endif; ?>
</header>

<section class="story" id="story">
  <p class="story-text">Most people meet the great blue heron alone — a solitary
  silhouette at the edge of the water, motionless, patient. But every spring these
  quiet hunters gather in the treetops to do something remarkable: they build a
  neighborhood. For one season I photographed a single rookery in the Montana
  cottonwoods — the courtships, the stick ceremonies, the crowded nests, the
  awkward teenagers testing their wings. Every photograph is an invitation to look
  closer, to learn, and to protect the wetlands these birds depend on.</p>
  <p class="story-sig">— Bernie Gengel, photographer</p>
</section>

<section class="facts" id="facts">
  <p class="section-kicker">DISCOVER</p>
  <h2 class="section-title">Facts</h2>
  <div class="facts-grid">
    <?php
    $facts = [
        ['01', 'A Giant Made of Air', 'Standing four feet tall with a wingspan over six feet, a great blue heron looks enormous — yet the whole bird weighs just five to six pounds. Like all birds, its bones are hollow, a skeleton built for flight.'],
        ['02', 'The Folded Neck', 'In flight, a heron tucks its long neck into a tight “S” and trails its legs straight behind. That silhouette is the easiest way to tell a heron from a crane, which flies with its neck fully extended.'],
        ['03', 'Built Like a Spear', 'Specially shaped neck vertebrae let the heron coil its neck and strike with astonishing speed and precision — spearing or grabbing fish faster than the eye can follow.'],
        ['04', 'A Comb on Its Toe', 'Herons grow “powder down” feathers that crumble into a fine powder. They rub it into their plumage to soak up fish slime, then comb it out with a fringed claw on the middle toe.'],
        ['05', 'The Rookery', 'Great blue herons nest in treetop colonies called rookeries — sometimes a few nests, sometimes hundreds. Colonies return to the same grove year after year.'],
        ['06', 'The Stick Ceremony', 'Courtship revolves around sticks: the male gathers them one by one and presents each to the female, who works it into the nest — one of the great rituals of spring.'],
    ];
    foreach ($facts as [$num, $title, $body]): ?>
    <article class="fact">
      <span class="fact-num"><?= $num ?></span>
      <h3><?= e($title) ?></h3>
      <p><?= e($body) ?></p>
    </article>
    <?php endforeach; ?>
  </div>
  <div class="facts-cta">
    <a class="btn btn-solid" href="guide/index.php">Read the Full Field Guide</a>
  </div>
</section>

<section class="conservation-strip">
  <p>A portion of every print sale supports wetland and riparian habitat
  conservation — the waters these birds cannot live without.</p>
</section>

<section class="gallery" id="gallery">
  <p class="section-kicker">PORTFOLIO</p>
  <h2 class="section-title">The Gallery</h2>
  <p class="section-sub">One rookery, one season — click any photograph to view it large</p>

  <div class="gallery-grid" id="galleryGrid">
    <?php foreach ($photos as $i => $p): ?>
    <figure class="gallery-item"
            data-full="images/web/<?= e($p['file']) ?>"
            data-title="<?= e($p['title']) ?>"
            data-caption="<?= e($p['caption'] ?? '') ?>"
            data-slug="<?= e($p['slug']) ?>">
      <img loading="lazy" src="images/thumb/<?= e($p['file']) ?>"
           onerror="this.src='images/web/<?= e($p['file']) ?>'"
           alt="<?= e($p['caption'] ?: $p['title']) ?>">
      <figcaption>
        <span class="g-title"><?= e($p['title']) ?></span>
        <span class="g-loc"><?= e($p['location'] ?? 'MONTANA') ?></span>
      </figcaption>
    </figure>
    <?php endforeach; ?>
    <?php if (!$photos): ?>
      <p class="section-sub">Photographs coming soon.</p>
    <?php endif; ?>
  </div>
</section>

<section class="prints" id="prints">
  <p class="section-kicker">FINE ART PRINTS</p>
  <h2 class="section-title">Bring the Rookery Home</h2>
  <p class="section-sub">Pick a photograph, then choose how it is made.
  Museum-quality production, printed to order.</p>
  <div class="formats-grid">
    <?php foreach (bh_catalog()['formats'] as $f): ?>
    <div class="format">
      <h3><?= e($f['label']) ?></h3>
      <p><?= e($f['blurb'] ?? '') ?></p>
    </div>
    <?php endforeach; ?>
  </div>
  <div class="prints-cta">
    <a class="btn btn-solid" href="order.php">Order a Print</a>
    <p class="prints-note">Pick your photograph, format, and size — secure checkout
    by Stripe. Bespoke sizes available on request.</p>
  </div>
</section>

<section class="quote">
  <blockquote>“The heron teaches a kind of patience the river already knows —
  stand still long enough, and everything you need comes to you.”</blockquote>
</section>

<div class="lightbox" id="lightbox" aria-hidden="true">
  <button class="lightbox-close" id="lightboxClose" aria-label="Close">×</button>
  <img id="lightboxImg" src="" alt="">
  <p class="lightbox-caption" id="lightboxCaption"></p>
</div>

<script>
// Lightbox — reads the data-* attributes PHP rendered onto each figure.
(function(){
  var lb=document.getElementById('lightbox'), img=document.getElementById('lightboxImg'),
      cap=document.getElementById('lightboxCaption');
  document.querySelectorAll('.gallery-item').forEach(function(fig){
    fig.addEventListener('click', function(){
      img.src=fig.dataset.full; img.alt=fig.dataset.caption||fig.dataset.title;
      cap.innerHTML=fig.dataset.title+(fig.dataset.caption?' — '+fig.dataset.caption:'')+
        ' &nbsp;·&nbsp; <a href="order.php?photo='+encodeURIComponent(fig.dataset.slug)+'" style="color:inherit">Order this print</a>';
      lb.classList.add('open'); lb.setAttribute('aria-hidden','false');
    });
  });
  function close(){ lb.classList.remove('open'); lb.setAttribute('aria-hidden','true'); img.src=''; }
  document.getElementById('lightboxClose').addEventListener('click', close);
  lb.addEventListener('click', function(e){ if(e.target===lb) close(); });
  addEventListener('keydown', function(e){ if(e.key==='Escape') close(); });
})();
</script>

<?php include __DIR__ . '/partials/footer.php'; ?>
