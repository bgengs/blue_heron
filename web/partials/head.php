<?php
/**
 * Shared page head + opening body. Before including, a page may set:
 *   $rel        relative path to web root ("" for root pages, "../" for guide/)
 *   $page_title
 *   $page_desc
 *   $extra_css  (array of extra stylesheet hrefs, relative to $rel)
 */
$rel = $rel ?? '';
$page_title = $page_title ?? 'The Great Blue Heron';
$page_desc = $page_desc ?? 'Fine art prints and a field guide to the great blue heron.';
$extra_css = $extra_css ?? [];
?><!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title><?= e($page_title) ?> — blueheron.gallery</title>
<meta name="description" content="<?= e($page_desc) ?>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="<?= $rel ?>assets/styles.css">
<?php foreach ($extra_css as $css): ?>
<link rel="stylesheet" href="<?= $rel . $css ?>">
<?php endforeach; ?>
</head>
<body>
