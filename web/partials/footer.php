<?php
/** Shared footer + closing body. Set $rel before including. */
$rel = $rel ?? '';
?>
<footer class="footer" id="contact">
  <div class="footer-brand">
    <p class="footer-word">BLUEHERON<span>.GALLERY</span></p>
    <p>Bernie Gengel — Wildlife Photographer &amp; Drone Pilot</p>
    <p>Based in Montana</p>
  </div>
  <div class="footer-links">
    <a href="<?= $rel ?>index.php#gallery">Gallery</a>
    <a href="<?= $rel ?>guide/index.php">Field Guide</a>
    <a href="<?= $rel ?>facts.php">Quick Facts</a>
    <a href="<?= $rel ?>order.php">Prints</a>
    <a href="https://eagle.mt">Eagle.MT</a>
  </div>
  <p class="footer-fine">© <?= date('Y') ?> Bernie Gengel. All photographs are the
  property of the photographer and may not be reproduced without permission.</p>
</footer>
</body>
</html>
