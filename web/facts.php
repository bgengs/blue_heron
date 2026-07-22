<?php
require __DIR__ . '/lib/data.php';
$rel = '';
$active = 'guide';
$page_title = 'Quick Facts';
$page_desc = 'Quick facts about the great blue heron — anatomy, hunting, courtship, and survival.';
include __DIR__ . '/partials/head.php';
include __DIR__ . '/partials/nav.php';

$groups = [
  'The Bird Itself' => [
    ['A Giant Made of Air', 'Four feet tall, a wingspan over six feet — and a body weight of only five to six pounds. Hollow bones make the giant possible.'],
    ['Blue-Gray, Not Blue', 'Despite the name, the plumage is mostly slate gray with a chestnut-and-black shoulder, a white face, and a black plume above the eye.'],
    ['The Folded Neck', 'Herons fly with the neck coiled into an “S” and legs trailing behind. Cranes fly neck-out. It is the quickest way to tell them apart.'],
    ['A Comb on Its Toe', 'Powder-down feathers crumble into a cleansing powder that soaks up fish slime; the heron combs it through with a fringed claw.'],
  ],
  'The Hunter' => [
    ['Built Like a Spear', 'Modified neck vertebrae give the strike its speed — the neck coils and fires like a loaded spring.'],
    ['The Statue Act', 'A hunting heron may stand motionless for minutes, letting fish forget it is there. Patience is the whole strategy.'],
    ['Not Just Fish', 'Fish lead the menu, but herons also take frogs, snakes, crayfish, insects, small birds, and a surprising number of gophers and voles.'],
    ['Cold Water Specialist', 'Great blues winter farther north than any other heron, needing only open water to fish.'],
  ],
  'Courtship & the Rookery' => [
    ['The Neighborhood', 'Herons nest in treetop colonies — rookeries — from a handful of nests to several hundred, often on islands or flooded groves.'],
    ['The Stick Ceremony', 'The male gathers sticks one at a time and presents each to the female, who weaves them into the nest.'],
    ['Pale Blue Beginnings', 'The female lays two to six pale, dusty-blue eggs. Both parents incubate for about four weeks.'],
    ['Sixty Days to the Sky', 'Young herons make their first flights at about two months old, then return for a few more weeks of free meals.'],
  ],
  'Survival' => [
    ['Everywhere There\'s Water', 'The great blue is North America\'s largest and most widespread heron, from Alaska to the Caribbean.'],
    ['The Hard First Year', 'More than half of young herons don\'t survive their first year. Those that make it can live 20 years or more.'],
    ['Eagle Trouble', 'Bald eagles raid rookeries for eggs and chicks — and can drive a whole colony to relocate.'],
    ['Wetlands Are Everything', 'The heron\'s future rides on wetlands. Protect the marshes and river bottoms, and you protect the heron.'],
  ],
];
?>
<main class="facts-page">
  <p class="section-kicker">QUICK FACTS</p>
  <h1 class="section-title">The Great Blue Heron</h1>
  <p class="section-sub">The short version — for the full story, see the
  <a href="guide/index.php" style="color:var(--navy)">Field Guide</a>.</p>

  <?php foreach ($groups as $group => $facts): ?>
  <h2 class="facts-group-title"><?= e($group) ?></h2>
  <div class="facts-grid">
    <?php foreach ($facts as $i => [$title, $body]): ?>
    <article class="fact">
      <span class="fact-num"><?= str_pad((string)($i + 1), 2, '0', STR_PAD_LEFT) ?></span>
      <h3><?= e($title) ?></h3>
      <p><?= e($body) ?></p>
    </article>
    <?php endforeach; ?>
  </div>
  <?php endforeach; ?>

  <div class="back-home" style="margin-top:3rem">
    <a class="btn btn-solid" href="guide/index.php">Read the Full Field Guide</a>
  </div>
</main>
<?php include __DIR__ . '/partials/footer.php'; ?>
