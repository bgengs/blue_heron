<?php
/**
 * THE shared navigation. Every page includes this, so the menu is written
 * once and can never drift. Set $active (one of: gallery, guide, prints,
 * contact) and $rel (path to web root) before including.
 */
$rel = $rel ?? '';
$active = $active ?? '';

$links = [
    'gallery' => [$rel . 'index.php#gallery', 'Gallery'],
    'guide'   => [$rel . 'guide/index.php',   'Field Guide'],
    'prints'  => [$rel . 'order.php',          'Prints'],
    'contact' => [$rel . 'index.php#contact',  'Contact'],
];
?>
<nav class="nav<?= $active ? ' scrolled' : '' ?>" id="nav">
  <a class="nav-brand" href="<?= $rel ?>index.php">BLUEHERON<span>.GALLERY</span></a>
  <button class="nav-toggle" id="navToggle" aria-label="Menu">☰</button>
  <div class="nav-links" id="navLinks">
    <?php foreach ($links as $key => [$href, $label]): ?>
      <a href="<?= e($href) ?>"<?= $key === $active ? ' class="active"' : '' ?>><?= e($label) ?></a>
    <?php endforeach; ?>
  </div>
</nav>
<script>
// Mobile menu + scroll shadow (tiny, shared).
(function(){
  var t=document.getElementById('navToggle'), l=document.getElementById('navLinks'), n=document.getElementById('nav');
  if(t) t.addEventListener('click', function(){ l.classList.toggle('open'); });
  addEventListener('scroll', function(){ n.classList.toggle('scrolled', scrollY>40); }, {passive:true});
})();
</script>
