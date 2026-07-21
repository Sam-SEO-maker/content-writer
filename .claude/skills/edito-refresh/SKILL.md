---
name: edito-refresh
description: >-
  Règles éditoriales SEO/GEO/E-E-A-T transverses pour faire ranker les articles
  (tous tenants). Consignes actionnables appliquées à chaque refresh : réponse
  directe en début de H2, statistiques et citations sourcées, densité sémantique
  par occurrences (pas en %), sources institutionnelles, structure GEO-ready,
  fraîcheur. Le détail (9 stratégies GEO, paires ❌/✅ E-E-A-T, SOSEO/DSEO) vit
  dans references/, chargé à la demande. Complète format-wordpress (forme) et la
  skill du tenant (structure/ton spécifiques).
disable-model-invocation: false
---

# Règles éditoriales : SEO / GEO / E-E-A-T (transverses)

Règles de **fond** communes à tous les tenants, appliquées à chaque refresh pour
maximiser le ranking (SERP + moteurs génératifs). Ce fichier porte l'actionnable ;
le détail et les exemples vivent dans `references/` (à lire au besoin) :

- `references/geo-strategies.md`, les 9 stratégies GEO 2026 détaillées + exemples.
- `references/eeat-framework.md`, les 4 piliers E-E-A-T avec paires ❌/✅ et signaux.
- `references/semantic-density.md`, modèle SOSEO/DSEO (densité par occurrences).

> Les **valeurs chiffrées par tenant** (longueur min/max, nb de liens externes)
> vivent dans `config/tenant.json` (`seo_settings`). Ce guide fixe les règles
> transverses ; il ne redéfinit pas ces chiffres.

## 1. Réponse directe (extraction IA)

Les moteurs génératifs extraient **les premières phrases** de chaque section.
Chaque `<h2>` est suivi d'une **réponse directe en 1-2 phrases** (40-60 mots),
avant tout développement. Idem pour chaque question de FAQ (réponse 50-100 mots).

## 2. Preuves : statistiques et citations sourcées

- **≥ 2 statistiques** chiffrées récentes (2025-2026), au format `[chiffre] + [source] + [date]`.
  Ex. ✅ « Selon le DEPP (2026), 40% des collégiens bénéficient d'un soutien scolaire. »
- **≥ 1 citation d'expert** avec credentials vérifiables (nom, titre, institution).
- Jamais de statistique sans date (considéré obsolète par les LLMs).

## 3. Sources institutionnelles

- **≥ 3 sources institutionnelles** citées avec lien (uniforme, tous tenants).
- Les **domaines d'autorité** sont un savoir **par marché/tenant**, pas transverse :
  annuaire du tenant `tenants/{id}/sources/authority-map.md` (par matière + socle
  transverse), consommé via la skill `recherche-sources`. Les *types* de domaines à
  viser (gouvernemental, académique, statistique) : `references/eeat-framework.md`.
- **Jamais de lien vers Wikipédia** (tous tenants) : citer la source primaire que
  Wikipédia agrège (étude, texte officiel, institution), jamais l'article encyclopédique.
  Wikipédia n'est pas une source d'autorité E-E-A-T et affaiblit le signal.
- **Pas de bloc « Sources » / bio auteur dans le HTML** : l'auteur et ses credentials
  sont gérés par WordPress (profil), hors du corps de l'article. (Exception format
  tenant : Superprof Ressources a son propre bloc Sources Gutenberg, voir sa skill.)

## 4. Densité sémantique : par occurrences, PAS en pourcentage

Ne jamais raisonner en « densité % ». Viser la **couverture** (largeur du champ
sémantique) sans **suroptimiser** (répétition). Plafonds :

- Mot-clé principal (exact) : **3-6 occurrences** (H1 + intro + 1-2 H2 + conclusion).
- Top termes du sujet : 2-5 occurrences chacun, distribués.
- Tout terme ≥ 3 occurrences → varier par synonyme/périphrase dans ≥ 50% des cas.
- Cible SOSEO/DSEO : **variable selon la SERP de chaque requête**, jamais uniforme.
  Calculer la **moyenne des scores du TOP 3** et celle du **TOP 10** (guide YTG :
  `top3_soseo`/`top3_dseo`, `top10_soseo`/`top10_dseo`) ; l'article doit avoir un
  **SOSEO supérieur** à ces moyennes et un **DSEO strictement inférieur** à ces
  moyennes. Détail + exemples : `references/semantic-density.md`.

## 5. Formats extractibles par l'IA

- Listes à puces pour les énumérations, tableaux comparatifs pour les synthèses.
- Format Q&A explicite en FAQ (**3-5 questions** PAA par défaut ; FAQ étendue possible
  si le type d'article le justifie).
- Phrases courtes (15-20 mots), structure sujet-verbe-complément, jargon défini.

## 6. Fraîcheur

- Statistiques et dates actualisées (sources 2025-2026), années obsolètes corrigées
  dans les titres et le corps.
- **Jamais** changer la date sans modification substantielle (pénalisé par Google).
- Ne pas modifier les URLs ni les citations académiques existantes.

## 7. Structure GEO-ready (rappel)

Réponse directe post-H2 → développement sourcé → citation d'expert → liste de points.
Template de paragraphe et structure d'article complète : `references/geo-strategies.md`.
La **structure d'ensemble** (blocs, ordre, intro) est définie par la skill du tenant,
qui prime sur ce rappel.

## 8. Structure du plan (renvoi)

La **construction de l'outline** (mapping PAA→sections, placement des preuves, gap
concurrentiel) et les **invariants de hiérarchie des titres** (≥ 3 H2, pas de H2/H3
orphelin, 2-4 H3 par H2 au-delà de 150 mots, `?` sur les titres interrogatifs)
vivent dans la skill dédiée **`seo-outline`**, invoquée à l'étape 2bis de `/refresh`
avant la génération. Cette skill-ci porte le *fond* de chaque section ; `seo-outline`
porte leur *agencement*.
