---
name: format-wordpress
description: >-
  Règles transverses de formatage HTML/WordPress pour tous les blogs : balises
  autorisées, HTML clean sans wrappers WP, double output Gutenberg, accents
  français obligatoires, interdiction du tiret cadratin, ancres sans <strong>,
  pas de lien dans les H2/H3, ponctuation des listes. Référencée par les autres
  skills de rédaction. Lecture seule (guide de formatage).
disable-model-invocation: false
---

# Format WordPress — règles de sortie transverses

Règles de **forme** communes à toutes les skills de rédaction
(`generate-enseigna-avis`, `sp-ressources-gutenberg`). Les skills spécifiques
site ajoutent leurs blocs/tons ; ce guide fixe les invariants HTML/WP.

## Balises autorisées

`<h2>`, `<h3>`, `<p>`, `<ul>`, `<ol>`, `<li>`, `<strong>`, `<em>`, `<a>`,
`<table>`, `<img>`, `<blockquote>`.

**Jamais** : `<script>`, `<style>` inline massif, `<iframe>` non sécurisé,
`<font>`, `<center>`.

## Pas de wrappers WordPress

Le HTML est une **liste plate de blocs**. Ne jamais émettre :
`<article>`, `<div class="content-wrap">`, `<header>`,
`<div class="entry-content">`, `<div class="post-thumbnail">`.

- **Pas de H1 dans un `<header>`** : WordPress gère le H1 selon le contexte du
  blog (Enseigna : H1 = champ ACF, aucun H1 dans le corps ; Superprof Ressources :
  H1 = premier bloc `wp:heading {"level":1}`). Voir la skill du site.
- **Pas d'image à la Une** dans le HTML : WordPress la gère.

## Double output Gutenberg

Chaque refresh produit deux fichiers : `{slug}_refreshed.html` (HTML nu, debug)
et `{slug}_refreshed.gutenberg.html` (collable dans l'éditeur de code WP,
commentaires `<!-- wp:* -->` + classes `wp-block-*`). **Seul le `.gutenberg.html`
sert à la publication** ; supprimer le nu après génération. Réf.
[[feedback-delete-nu-html-keep-gutenberg]].

- **Images refresh** : conserver les `id` existants via `class="wp-image-NNN"`.
  Sans id détectable, émettre un `wp:image` sans `id`.
- **Convention pros/cons** (Enseigna) : `<div class="pros-cons"><div class="cons">…</div><div class="pros">…</div></div>`
  → conversion auto en `wp:columns`.

## Langue française — accents (OBLIGATOIRE)

Tout contenu (HTML **et** JSON) utilise les accents corrects (é è ê à ù ç î ô û ï).
Jamais « ameliorer », « systeme », « debutant ». Un mot français sans accent est
un **bug bloquant** à corriger avant livraison.

## Tiret cadratin interdit

Ne jamais utiliser `—`. Pour les incises : virgules, parenthèses, ou tiret
demi-cadratin `–` si un séparateur visuel est indispensable. Tous blogs. Réf.
[[feedback-no-em-dash]].

## Liens

- **Ancres sans `<strong>`** : `<a href="…">texte</a>`, jamais
  `<a href="…"><strong>texte</strong></a>` (anti-pattern sur-optimisation).
- **Pas de lien dans les H2/H3** : un `<a>` dans un heading est un red flag SEO.
- **Sources** : pas de « Consulté le [date] » — [[feedback-no-consulte-le]].

## Ponctuation des listes à puces

Chaque `<li>` finit par une **virgule** ; le **dernier** `<li>` finit par un
**point**.

```html
<ul>
  <li>Premier élément,</li>
  <li>Deuxième élément,</li>
  <li>Dernier élément.</li>
</ul>
```

## Densité & conclusion

- Minimum **3 sections H2**, sections développées (pas de H2 à un seul paragraphe).
- **Pas de H2 « Conclusion »** (sauf blog Enseigna) : terminer par un court
  paragraphe condensé (3-5 phrases), ton actionnable, sans répétition exhaustive.
- Pas de section « Articles connexes / Pour aller plus loin » : les liens internes
  sont intégrés **naturellement dans une phrase**, espacés de 150-200 mots.

## Tableaux

Chaque `<table>` → un **CSV** dans `csv/` (`{slug}_tableau_{descriptif}.csv`),
max 3/article, **aucun shortcode** `[table id=X /]` dans le HTML. Réf.
[[feedback-csv-naming-tablepress]].

## Métadonnées JSON

`title` (post_title WP, ≤ 60 car.), `h1` (H1 éditorial du corps, peut différer),
`meta_description` (150-155 car.), `target_keywords`, `word_count`, `assets`
(count images/tables/videos/internal_links), `eeat_sources` (source/url/year).

## Callouts colorés interdits

Pas de `wp:html` avec `#4caf50` (CTA vert), `#fff9e6` (jaune), `#e8f4f8` (bleu)
sur Enseigna ni Superprof Ressources — ancien système. Réf.
[[feedback-no-callouts-cta]]. (Les blocs AdvGB `advgb/infobox` autorisés sur
Superprof Ressources sont un mécanisme distinct — voir [[sp-ressources-gutenberg]].)
