---
name: generate-enseigna-avis
description: >-
  Rédige/refreshe un article d'avis Enseigna (review d'un service de soutien
  scolaire). Impose la structure canonique (intro → H2 d'analyse → pros/cons →
  note → verdict rapide en fin → FAQ), l'export des données structurées en ACF
  JSON, les tableaux en CSV, et les interdits Enseigna. Transformation lourde,
  déléguée au subagent de génération. Invoquer via /generate-enseigna-avis.
disable-model-invocation: true
---

# Génération article avis — Enseigna

Produit un article **avis/review** pour `enseigna.fr` (soutien scolaire). Ton :
vouvoiement, expert analytique. YMYL medium. Cette skill porte la **structure et
les interdits** ; le fond (stats, experts, vocabulaire) vient du prompt site.

> **Source de vérité (à référencer, pas dupliquer)** :
> `_shared/prompts/sites/enseigna.md` (prompt principal),
> `_shared/prompts/sites/enseigna/acf-fields-template.md` (template ACF),
> `_shared/prompts/sites/enseigna/*.html` (blocs de référence : pros-cons,
> references, blockquote…). Articles de référence publiés :
> `_shared/outputs/enseigna/html/` (GoStudent, Complétude).

## Livrables (3 fichiers par article)

1. `_shared/outputs/enseigna/html/{slug}_refreshed.gutenberg.html` — **corps**,
   liste plate de blocs Gutenberg. **PAS de `<h1>` dans le corps** (le H1 est un
   champ ACF sur Enseigna) : le corps commence par le paragraphe d'introduction.
   Pas de fiche technique dans le corps.
2. `_shared/outputs/enseigna/acf/{slug}_acf.json` — **données structurées** ACF
   (voir template). Champs clés : `h1` (style « Avis {Site} : mon test des cours
   de … sur {Site} »), `nom_du_site`, `note_globale_5` (= verdict /10 ÷ 2 ;
   **concurrent plafonné à 4/5**), `note_service_client`, `annee_creation`,
   `prix_mensuel_moyen`, avis positif/neutre/négatif (date + texte), etc.
   `note_globale_5` **doit** correspondre au verdict /10 du corps (cohérence rich
   snippet).
3. `_shared/outputs/enseigna/csv/{slug-à-tirets}_tableau_{descriptif}.csv` — chaque
   `<table>` du corps exporté en CSV (dossier **`csv/`**, jamais `tables/`), **max
   3/article**. Aucun shortcode `[table id=X /]` dans le HTML : les rédacteurs
   importent le CSV dans TablePress puis insèrent en mode code. Réf.
   [[feedback-csv-naming-tablepress]].

> `push_to_wp.py` lit encore `metadata/{slug}_metadata.json` pour les meta
> SEOPress (title/desc) — le conserver tant que le push REST l'utilise, même si
> la fiche technique Gutenberg, elle, est supprimée. Réf.
> [[feedback-fiche-technique-separation]].

## Structure de l'article (ordre canonique)

Suivre les **articles de référence publiés**, PAS `review_template.md` :

1. **Intro** : 2-3 `<!-- wp:paragraph --><p>…</p>` sans classe.
2. **Premier H2 structurant** (« Ce que nous avons évalué » / « Ce que disent les
   avis »), puis les H2 d'analyse.
3. **Fin d'article** : pros/cons (`wp:columns`) → note finale → **verdict rapide**
   (`<!-- wp:html --><div class="verdict-rapide">…</div>`) → **FAQ**.
   Le verdict rapide va à la **FIN, avant la FAQ** — jamais au début. Réf.
   [[feedback-enseigna-verdict-rapide-position]].

**Convention pros/cons** (pour la conversion Gutenberg auto en `wp:columns`) :
`<div class="pros-cons"><div class="cons"><h3>Les -</h3>…</div><div class="pros"><h3>Les +</h3>…</div></div>`.

## Interdits Enseigna (ne jamais produire)

- ❌ **Déclaration d'indépendance éditoriale** (`div.independence-statement`) —
  ignorer la section 8 de `review_template.md`. Réf.
  [[feedback-no-independence-declaration]].
- ❌ **Callouts / CTA colorés** (`wp:html` avec `#4caf50` / `#fff9e6` / `#e8f4f8`)
  — ancien système. Réf. [[feedback-no-callouts-cta]].
- ❌ **H1 dans le corps** (H1 = champ ACF).
- ❌ Note concurrent > 8/10 (→ > 4/5 en ACF).

## Règles transverses

- **Refresh = jamais supprimer d'asset ni de lien** (Règle d'Or), y compris les
  liens vers concurrents (superprof.fr) — [[feedback-refresh-no-link-removal]].
- **H2 optimisés**, pas recopiés de l'article source (sauf H2 = H1 d'un enfant de
  cocon) — [[feedback-h2-optimization]].
- **Accents corrects** partout (HTML et JSON ACF).
- **Pas de tiret cadratin `—`** — [[feedback-no-em-dash]].
- **Pas de « Consulté le [date] »** dans les sources — [[feedback-no-consulte-le]].
- **Pas de `<strong>` dans les ancres de liens**, pas de lien dans les H2/H3.
- **Listes à puces** : chaque `<li>` finit par une virgule, le dernier par un point.

## Exécution

Générer via **subagent Claude Code** (abonnement Max), jamais l'API payante.
Le subagent lit ce SKILL.md + `enseigna.md` + le HTML source + les données GSC,
écrit directement les 3 fichiers, et ne renvoie pas de HTML dans le chat.

## Sources de vérité

- Structure/interdits : mémoires liées ci-dessus.
- Prompt & ACF : `_shared/prompts/sites/enseigna.md`,
  `_shared/prompts/sites/enseigna/acf-fields-template.md`.
- Référence visuelle : `_shared/outputs/enseigna/html/`.
