---
name: sp-ressources-gutenberg
description: >-
  Rédige/refreshe un article Superprof Ressources au format Gutenberg maison
  complet (jamais du "HTML clean"). Impose les 5 blocs obligatoires (2 infobox,
  count-up, citation, sources), le ton "tu" + emojis, le H1 en premier bloc, et
  le placement/dispersion des blocs. Transformation lourde, déléguée au subagent.
  Invoquer via /sp-ressources-gutenberg.
disable-model-invocation: true
---

# Génération article — Superprof Ressources (Gutenberg maison)

Produit un article éducatif pour `superprof.fr/ressources/` au **format Gutenberg
maison complet**. Ton naturel, informel, encourageant, **tutoiement**, emojis
dans les H2/H3. YMYL low.

> ⚠️ **Jamais de "HTML clean / sans Gutenberg".** Confusion historique (lot
> 2026-06-15) : les callouts colorés interdits (`wp:html` #4caf50/#fff9e6/#e8f4f8)
> ne sont PAS les blocs AdvGB obligatoires. 49 articles ont dû être régénérés
> pour cette raison. Réf. [[feedback-sp-ressources-gutenberg-house-format]].
>
> **Source de vérité canonique** :
> `_shared/prompts/sites/superprof-ressources-reference.md` (fait foi) +
> `_shared/prompts/sites/superprof-ressources.md` (prompt principal) +
> `_shared/outputs/superprof-ressources/batches/REGEN_BRIEF.md` (brief réutilisable).

## Livrable

`_shared/outputs/superprof-ressources/html/{slug}_refreshed.gutenberg.html` —
liste **plate** de blocs Gutenberg (pas de wrapper `<article>`/`<section>`).
Le fichier nu `{slug}_refreshed.html` de debug est supprimé après génération
([[feedback-delete-nu-html-keep-gutenberg]]).

- **H1 = premier bloc** : `<!-- wp:heading {"level":1} --><h1 class="wp-block-heading">…</h1><!-- /wp:heading -->`.
  Le `post_title` WP et le H1 du corps sont distincts ; le H1 peut reformuler le
  title. Réf. [[feedback-superprof-h1-body]].
- **Intro** : 2 paragraphes de hook, **aucun bloc spécial**, aucune infobox.

## Les 5 blocs obligatoires (dans le corps, après le 1er H2)

1. **Info Box bleue** (`wp:advgb/infobox`, `#e8f2ff`/`#157dfe`).
2. **Info Box jaune** « bon réflexe » (`wp:advgb/infobox`, `#fffbf0`/`#ffcf3b`).
3. **Count-Up** (`wp:advgb/count-up`) — `countUpNumber` **commence par un chiffre**.
4. **Citation** (`wp:superprof/quote-block`).
5. **Bloc Sources** (`wp:group` → `wp-block-wp-sp-gutenberg-blocks-block-sources`,
   titre `Sources 📚`, `<ol class="references">`). Format exact validé (Andra,
   mai 2026) : [[feedback-sp-sources-block-format]].

**Format AdvGB exact** (sinon Gutenberg affiche le HTML brut) : commentaires
`<!-- wp:advgb/* -->`, **HTML sur une seule ligne**, `{uuid}` identique entre le
JSON (`blockIDX`/`id`) et la classe CSS. Jamais de `<!-- wp:html -->` autour de
ces blocs. Réf. [[feedback-advgb-block-format]].

## Placement & dispersion des blocs

- **1 bloc spécial = 1 section H2 maximum.** Jamais deux blocs du même type
  adjacents. Disperser : jaune en section 1, bleue en section 2/3, citation en 3,
  count-up en 4, sources à la fin. Réf. [[feedback-seraphine-no-adjacent-blocks]]
  (règle transposée), [[feedback-seraphine-infobox-placement]].
- **Aucun bloc dans l'intro.**
- Vérif post-traitement : `grep -A1 '<!-- /wp:advgb/infobox -->' f | grep '<!-- wp:advgb/infobox'`
  → si match, violation.

## Contenu spécifique

- **Chronologies → bloc Timeline** (`wp:superprof/timeline-block`,
  `superprof-ressources.md` ~l. 298), pas infobox/liste/tableau. Si un timeline
  remplace une infobox, garder 1 bleue + 1 jaune.
- **FAQ** : chaque question (H3) commence par un **emoji** (palette 🤔💡🔍📌🧐📖❓💬)
  et finit par « ?». Réf. [[feedback-faq-question-emoji]].
- **Tableaux → CSV** dans `csv/`, max 3/article (exception lexique/grammaire),
  aucun shortcode dans le HTML. Réf. [[feedback-csv-naming-tablepress]].
- **Articles sur un ouvrage littéraire** → ACF fiche de lecture
  `acf/{slug}_acf.json` (book_name/author_name/genre/date_published).
  Réf. [[feedback-sp-ressources-acf-fiche-lecture]].
- **LaTeX/MathJax NON supporté** → rester en `<code>` + Unicode.
  Réf. [[feedback-latex-scientific-articles]].
- **Noms de temps verbaux en anglais** pour la grammaire anglaise
  ([[feedback-english-tense-names]]).

## Interdits & rappels transverses

- ❌ Callouts colorés `wp:html` (#4caf50/#fff9e6/#e8f4f8) — [[feedback-no-callouts-cta]].
- ❌ Tiret cadratin `—` — [[feedback-no-em-dash]].
- ❌ Formulations négatives (« pas de panique », « dans ce cours ») → toujours
  positif — [[feedback-language-tone-sp-ressources]].
- ❌ « Consulté le [date] » dans les sources — [[feedback-no-consulte-le]].
- Accents corrects partout (y compris JSON). Ancres sans `<strong>`, pas de lien
  dans les H2/H3. Listes : `<li>` en virgule, dernier en point.

## QC post-génération

Passer [[qc-sp-ressources]] (checklist déterministe) avant push WP.

## Exécution

Générer via **subagent Claude Code** (Max), jamais l'API payante. Le subagent
écrit directement le fichier, ne renvoie pas de HTML dans le chat. Le convertisseur
mécanique `refresh_to_gutenberg_batch.py` **n'ajoute pas** les 5 blocs (il emballe
seulement paragraphes/headings) — il ne suffit donc pas.
