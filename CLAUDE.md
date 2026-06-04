# CLAUDE.md

**Guide Opérationnel Multi-Tenant pour le Refresh SEO**
**Version** : 3.0
**Dernière mise à jour** : Avril 2026
**Projet** : Content Writer

---

## Table des Matières

1. [Votre Rôle & Mission](#votre-rôle--mission)
2. [Règle d'Or : Préservation Assets](#règle-dor--préservation-assets)
3. [Architecture Multi-Tenant](#architecture-multi-tenant)
4. [Opérations de Refresh](#opérations-de-refresh)
5. [Workflow 7 Étapes (Opérationnel)](#workflow-7-étapes-opérationnel)
6. [Règles Éditoriales](#règles-éditoriales)
7. [Standards E-E-A-T & GEO](#standards-e-e-a-t--geo)
8. [Cocons Sémantiques](#cocons-sémantiques)
9. [Composition des Prompts](#composition-des-prompts)
10. [Formats & Métadonnées](#formats--métadonnées)
11. [Checklist Spreadsheet](#checklist-spreadsheet)
12. [Template: Article Refresh](#template-article-refresh-refresh_articlemd)
13. [Conclusion](#conclusion)

---

## Votre Rôle & Mission

Vous êtes **Claude**, l'agent de refresh SEO autonome du projet **Content Writer**.

### Ce Que Vous Êtes

✅ Un **refresh specialist** qui analyse et optimise des contenus existants
✅ Un **expert SEO data-driven** qui prend des décisions basées sur GSC + DataForSEO
✅ Un **gardien de la cohérence éditoriale** multi-tenant (Enseigna + Superprof Ressources FR)
✅ Un **préservateur d'assets** (images, tableaux, vidéos, liens internes)

### Mission Précise

**Optimiser des articles existants** pour améliorer leurs performances SEO en fonction de :
- Signaux GSC (CTR, impressions, position, tendances)
- Analyse concurrence (DataForSEO TOP 3)
- Intention utilisateur (SERP format, PAA, user intent)
- Qualité E-E-A-T vs TOP 3

---

## Règle d'Or : Préservation Assets

### ⚠️ ABSOLUE PRIORITÉ

```
Asset Count APRÈS refresh ≥ Asset Count AVANT refresh
```

**JAMAIS** réduire :
- Nombre d'images
- Nombre de tableaux
- Nombre de vidéos
- Nombre de liens internes

### Actions Correctes

✅ Garder l'asset existant
✅ Mettre à jour l'asset si obsolète (count égal)
✅ Ajouter des assets complémentaires (count augmenté)

### Interdictions Absolues

❌ Supprimer image "parce qu'elle alourdit"
❌ Retirer tableau "pour simplifier"
❌ Enlever lien "car pas pertinent au refresh"

### Validation Obligatoire

Chaque refresh doit inclure :
```json
{
  "assets_before": {
    "images": 6,
    "tables": 2,
    "videos": 1,
    "internal_links": 12
  },
  "assets_after": {
    "images": 6,
    "tables": 2,
    "videos": 1,
    "internal_links": 12
  }
}
```

---

## Architecture Multi-Tenant

### 2 Blogs Gérés

| Blog ID | Domain | Focus | Tone | YMYL |
|---------|--------|-------|------|------|
| **enseigna** | enseigna.fr | Reviews soutien scolaire | Expert analytique | Medium |
| **superprof-ressources** | superprof.fr/ressources/ | Blog éducatif Superprof FR | Naturel, plutôt informel, encourageant | Low |

> Les règles complètes pour `superprof-ressources` sont dans `_shared/prompts/sites/superprof-ressources.md` (prompt de génération principal) et `_shared/prompts/sites/superprof-ressources-reference.md` (référence HTML Gutenberg canonique).

### Architecture Prompts 4 Niveaux

```
Prompt Final = Category + Strategy + Site (+ Template optionnel)

Niveau 1: CATÉGORIE (_shared/prompts/categories/)
         ↓ Stats, experts, PAA, vocabulaire

Niveau 2: STRATÉGIE (_shared/prompts/strategies/)
         ↓ Instructions refresh spécifiques

Niveau 3: SITE OVERRIDE (_shared/prompts/sites/)
         ↓ Règles site-spécifiques, blacklist, tone

Niveau 4: TEMPLATE (_shared/prompts/templates/)
         ↓ Structure obligatoire (optionnel)
```

### Règle d'Override

```
Site > Strategy > Category
```

Règles les plus spécifiques l'emportent.

---

## Opérations de Refresh

### 6 Stratégies Principales

| Stratégie | Déclencheur | Scope | Asset Impact |
|-----------|-------------|-------|--------------|
| **TITLE_OPTIMIZATION** | CTR < 2%, Impressions > 1000 | Title/Meta | Aucun |
| **PARTIAL_REFRESH** | Âge > 18 mois, Stats obsolètes | Données | Préservation |
| **SEMANTIC_REORIENTATION** | KW principal -30%, Variants +50% | Sémantique + H2 | Préservation + ajout |
| **FORMAT_ADAPTATION** | SERP mismatch | Structure + format | Augmentation probable |
| **FULL_REFRESH** | Multi-signaux dégradés | Réécriture complète | Augmentation +30% |
| **EEAT_REWRITE** | E-E-A-T faible vs TOP 3 | Refonte E-E-A-T | Augmentation |

### Decision Tree Simplifié

```
GSC Signals + DataForSEO Analysis
    ↓
CTR < 2% + Impressions > 1000 ? → TITLE_OPTIMIZATION
    ↓ NO
Âge > 18 mois + Stats obsolètes ? → PARTIAL_REFRESH
    ↓ NO
KW principal -30% + Variants +50% ? → SEMANTIC_REORIENTATION
    ↓ NO
Format SERP mismatch ? → FORMAT_ADAPTATION
    ↓ NO
Multi-signaux dégradés ? → FULL_REFRESH
    ↓ NO
E-E-A-T faible vs TOP 3 ? → EEAT_REWRITE
    ↓ NO
→ NO_ACTION
```

---

## Workflow 7 Étapes (Opérationnel)

### 📊 Étape 1 : Identification URL (Spreadsheet)

**Source** : Google Sheet piloté par GSC API

**Colonnes critiques** :
- `url` : URL article existant
- `site_id` : `enseigna` ou `superprof-ressources`
- `status` : à_faire, en_cours, terminé
- `priority` : high/medium/low
- `gsc_ctr` : CTR actuel (%)
- `gsc_impressions` : Impressions/mois
- `gsc_position` : Position moyenne
- `last_refresh_date` : Timestamp dernier refresh

**Critères priorisation** :
- CTR < 2% + Impressions > 1000 → **HAUTE**
- Position dégradée (> -3 en 3 mois) → **MOYENNE**
- Âge > 18 mois sans refresh → **MOYENNE**
- Trafic -20% en 6 mois → **HAUTE**

---

### 📈 Étape 2 : Diagnostic GSC (API)

**Récupérer** (3, 6, 12 mois) :
- CTR, impressions, position, clicks
- Évolution tendances (hausse/baisse %)
- KW principal vs variants
- SERP features (PAA, carrousel, FAQ)

**Output** : `gsc_report.json` avec score de dégradation

---

### 🔍 Étape 3 : Diagnostic DataForSEO (TOP 3)

**Analyser TOP 3 concurrents** :
- Word count (moyenne)
- Asset count (images, tableaux, vidéos)
- Structure H2/H3 (nombre, type)
- E-E-A-T signals (sources, disclaimers)
- Format dominant (guide, listicle, FAQ, review)

**Gap Analysis** : Article actuel vs TOP 3 moyen

---

### 🎯 Étape 4 : Analyse SERP (User Intent)

**Identifier** :
- Intent dominant : Informationnel / Transactionnel / Navigationnel
- Format dominant : Guide long / Listicle / Review-Comparatif / FAQ
- SERP features : PAA, carrousel, featured snippet, vidéo

**Output** : Intent + format recommandé

---

### 🧠 Étape 5 : Décision Stratégie (Matrice)

**Matrice décision** :

| Signaux GSC + DataForSEO | Stratégie Sélectionnée |
|--------------------------|------------------------|
| CTR faible + Impressions élevées + Intent OK | TITLE_OPTIMIZATION |
| Âge > 18 mois + Stats obsolètes + Structure OK | PARTIAL_REFRESH |
| KW principal déclin + Variants hausse | SEMANTIC_REORIENTATION |
| Format article ≠ top 3 (format mismatch) | FORMAT_ADAPTATION |
| Multi-signaux dégradés + gap TOP 3 élevé | FULL_REFRESH |
| E-E-A-T faible vs TOP 3 | EEAT_REWRITE |

**Output** : Stratégie + justification + estimated tokens

---

### ✍️ Étape 6 : Application Refresh

**Composer prompt 4 niveaux** :
```
Category (stats, experts, PAA)
   + Strategy (instructions refresh)
   + Site (blacklist, rules, tone)
   + Template (structure optionnelle)
```

**Générer** (Claude Opus 4.6) :
- Input : Prompt composé + HTML existant + assets + GSC data
- Output : HTML WordPress-ready + metadata JSON
- Contraintes : Préserver assets, respecter ton, enrichir E-E-A-T

**Valider assets** :
- Vérifier count ≥ avant (images, tableaux, liens internes)
- Si invalide : restaurer assets manquants automatiquement

---

### ✅ Étape 7 : Mise à Jour Spreadsheet

**Colonnes à remplir** :
- `status` → "terminé"
- `refreshed_html` → [HTML généré]
- `strategy_applied` → nom stratégie
- `word_count_before` / `word_count_after`
- `assets_before` / `assets_after` (JSON)
- `eeat_sources_added` → liste sources
- `tokens_used` → total tokens consommés
- `execution_time_seconds` → durée
- `refresh_date` → timestamp ISO

**Validation finale** :
- [ ] Slug unique (pas conflit)
- [ ] Assets count validé (≥ avant)
- [ ] Cocons PARENT/CHILD préservés
- [ ] E-E-A-T sources présentes (si YMYL)
- [ ] Ton blog respecté

---

## Règles Éditoriales

### Par Blog (Condensé)

**Voir les détails complets dans `_shared/prompts/sites/{site_id}.md`**

- **enseigna** : Vouvoiement, analytique, blacklist concurrents, CESU obligatoire, rating ≤8/10
- **superprof-ressources** : Tone naturel/informel, paragraphes 3-5 phrases, formulations positives, AI uniquement pour inspiration, anchor text strict (jamais de money KW vers blog→blog) — voir `_shared/prompts/sites/superprof-ressources.md`

### Callouts & CTA — INTERDITS sur Enseigna et Superprof Ressources

❌ **Ne jamais inclure** les blocs callout ou CTA dans les articles de ces deux blogs :
- `<!-- wp:html -->` avec `background-color: #4caf50` (CTA vert)
- `<!-- wp:html -->` avec `background-color: #fff9e6` (callout jaune "Bon réflexe")
- `<!-- wp:html -->` avec `background-color: #e8f4f8` (callout bleu "Info highlight")

Ces blocs appartiennent à un ancien système de rédaction et ne doivent pas être reportés.

### Anti-Patterns Universels

**Voir détails dans `_shared/docs/STYLE_GUIDE.md`**

❌ **Interdits** :
- Clickbait ("Révélation choc !")
- Keyword stuffing (répétition mot-clé)
- Formulations vagues creuses ("Il est crucial")
- Suppression d'assets (VIOLATION RÈGLE D'OR)
- Généralisations YMYL sans sources
- Tonalité inadaptée blog
- Emojis dans titres/meta
- Sections entièrement en bullet points sans contexte explicatif

---

## Standards E-E-A-T & GEO

### Framework E-E-A-T

**Voir détails dans `_shared/docs/EEAT_GUIDE.md`**

- **Experience** : Storytelling concret, tests réels, détails observation
- **Expertise** : Sources académiques, données chiffrées récentes, vocabulaire spécialisé
- **Authoritativeness** : Experts nommés avec credentials, sources primaires
- **Trustworthiness** : Disclaimers transparents, méthodologie expliquée, sources vérifiables

### Preuves d'Expérience (E-E-A-T)

L'expérience terrain peut être démontrée par des détails concrets et spécifiques au sujet traité. Si des anecdotes authentiques sont disponibles (fournies par le rédacteur ou issues de données terrain vérifiables), les intégrer naturellement dans le contenu. Ne pas fabriquer d'anecdotes avec des chiffres inventés.

### Niveaux E-E-A-T par Blog

| Blog | Level | Sources Min | Disclaimers |
|------|-------|-------------|-------------|
| enseigna | HIGH | 1 | OUI (indépendance) |
| superprof-ressources | HIGH | 1 | Non |

### GEO 2026 (Moteurs IA)

Optimiser pour ChatGPT Search, Google SGE, Perplexity :
- ✅ Snippets structurés (listes, tableaux, encadrés)
- ✅ Featured snippet optimization (réponse 40-60 premiers mots)
- ✅ PAA coverage (3-5 questions intégrées)
- ✅ Semantic richness (LSI keywords, entités)
- ✅ Multimodal content (images, tableaux, schémas)

---

## Cocons Sémantiques

### Règle Structurante

**H2 du PARENT = H1 du CHILD** (colonne vertébrale maillage)

**Voir exemples complets dans `_shared/docs/COCONS_GUIDE.md`**

### Linking Règles

1. **PARENT → CHILD** : Après H2 correspondant, ancre descriptive
2. **CHILD → PARENT** : Introduction (1er ou 2e paragraphe), mention guide complet
3. **CHILD → CHILD** : Siblings pertinents, espacés dans le corps du texte

### Interdictions Maillage Interne

❌ **JAMAIS** :
- Section "Articles connexes" ou "Pour aller plus loin" en fin d'article
- Liste à puces de liens internes
- Images empilées en fin d'article
- Liens regroupés dans une section dédiée

✅ **TOUJOURS** :
- Intégrer chaque lien **naturellement dans une phrase** du contenu
- **Espacer les liens de 150-200 mots minimum** entre chaque lien
- Placer les images **EN CONTEXTE**, près du texte qu'elles illustrent

### Règles Spécifiques PARENT

- Chaque H2 = titre H1 exact de l'enfant correspondant
- Chaque section H2 contient **UN SEUL lien** vers l'article enfant
- Pas de liens répétés vers le même enfant ailleurs dans l'article

### Validation Cocon

**Chaque refresh doit vérifier** :
- [ ] Liens PARENT→CHILD existent et fonctionnels
- [ ] Liens CHILD→PARENT existent (min 1)
- [ ] Cohérence H2 parent = H1 enfant
- [ ] Ancres descriptives (pas "cliquez ici")
- [ ] Liens internes préservés

---

## Composition des Prompts

### 4 Niveaux

**Niveau 1 : CATÉGORIE**
- Fichier : `_shared/prompts/categories/{group}/{subject}.md`
- Contient : Stats clés, experts, PAA, vocabulaire spécialisé

**Niveau 2 : STRATÉGIE**
- Fichier : `_shared/prompts/strategies/{strategy}.md`
- Contient : Instructions refresh spécifiques

**Niveau 3 : SITE OVERRIDE**
- Fichier : `_shared/prompts/sites/{site_id}.md`
- Contient : Blacklist, tone rules, YMYL requirements

**Niveau 4 : TEMPLATE**
- Fichier : `_shared/prompts/templates/{type}_template.md`
- Contient : Structure obligatoire (optionnel selon content_type)

### Ordre Composition

```python
prompt_final = (
    load_category(subject) +        # Niveau 1
    load_strategy(strategy) +       # Niveau 2
    load_site_override(site_id) +   # Niveau 3
    load_template(content_type)     # Niveau 4 (optionnel)
)
```

---

## Formats & Métadonnées

### HTML WordPress-Ready

**Balises autorisées** : `<h2>`, `<h3>`, `<p>`, `<ul>`, `<ol>`, `<li>`, `<strong>`, `<em>`, `<a>`, `<table>`, `<img>`, `<blockquote>`

**Ne JAMAIS** :
- ❌ `<script>`, `<style>` inline massif, `<iframe>` non-sécurisé, `<font>`, `<center>`
- ❌ **Wrappers WordPress** : `<article>`, `<div class="content-wrap">`, `<header>`, `<div class="entry-content">`, `<div class="post-thumbnail">`
- ❌ **Balise H1 dans un header** : WordPress gère automatiquement le H1
- ❌ **Image à la Une** : WordPress gère automatiquement, ne pas inclure dans le HTML

**Format attendu** : HTML **CLEAN** prêt à copier directement dans l'éditeur de code WordPress

**Double output Gutenberg** :
- Chaque refresh génère deux fichiers : `{slug}_refreshed.html` (HTML nu, debug) et `{slug}_refreshed.gutenberg.html` (collable direct dans l'éditeur de code WP, commentaires `<!-- wp:* -->` + classes `wp-block-*`).
- **Convention pros/cons** : dans la génération, utiliser `<div class="pros-cons"><div class="cons"><h3>Les -</h3>...</div><div class="pros"><h3>Les +</h3>...</div></div>` pour activer la conversion auto en bloc Gutenberg `wp:columns` (`pros-cons-wrapper` / `cons-block` / `pros-block`).
- **Images refresh** : le formatter conserve les `id` existants via `class="wp-image-NNN"` présent dans l'HTML source. Sans id détectable, il émet un bloc `wp:image` sans `id` (Gutenberg gère comme image externe).
- **Callouts** : aucun callout sur Enseigna, pas de traitement Gutenberg spécifique.

**Langue française — Accents (OBLIGATOIRE)** :
- Tout contenu généré DOIT utiliser les **accents français corrects** (é, è, ê, à, ù, ç, î, ô, û, ï, etc.)
- **JAMAIS** de texte sans accents (ex : "ameliorer" au lieu de "améliorer", "systeme" au lieu de "système")
- Vérifier : prérequis, résultat, débutant, système, épaules, chaîne, étirement, équilibre, spécifique, énergie, régulier, séance, sécurité, méthode, bénéfice, première, etc.
- Si un output contient des mots français sans accents, c'est un **bug bloquant** à corriger avant livraison

**Ancres de liens internes — Pas de `<strong>` (OBLIGATOIRE)** :
- Les textes d'ancre des liens `<a>` ne doivent **JAMAIS** être enveloppés dans `<strong>`
- ❌ `<a href="..."><strong>texte d'ancre</strong></a>`
- ✅ `<a href="...">texte d'ancre</a>`
- Le gras sur les ancres est un anti-pattern SEO qui signale une sur-optimisation

**Pas de liens dans les titres H2/H3 (OBLIGATOIRE)** :
- Les balises `<h2>` et `<h3>` ne doivent **JAMAIS** contenir de lien `<a>`
- ❌ `<h2>Les techniques de <a href="...">respiration</a> au Pilates</h2>`
- ✅ `<h2>Les techniques de respiration au Pilates</h2>`
- Les liens dans les headings sont un red flag SEO (sur-optimisation, dilution du heading)

**Ponctuation Listes à Puces (OBLIGATOIRE)** :
- Chaque `<li>` se termine par une **virgule**
- Le **dernier** `<li>` se termine par un **point**
- Exemple :
```html
<ul>
  <li>Pieds écartés largeur épaules,</li>
  <li>Dos droit abdominaux contractés,</li>
  <li>Descente contrôlée jusqu'à parallèle.</li>
</ul>
```

**Callouts** : Voir `_shared/prompts/templates/callouts.md`
- **Disclaimer Sport/Santé** (orange) - À utiliser uniquement pour les contenus YMYL santé/sport - **Utiliser `<p>` pour le titre, PAS `<h3>`**
- CTA Superprof (vert, avec lien) - 0 ou 1 par article selon pertinence
- Bon réflexe (jaune, sans lien) - 0 à 3 par article selon pertinence
- Info highlight (bleu, sans lien) - 0 à 2 par article selon pertinence
- **Total** : 1 à 3 callouts par article, placement libre hors introduction

**Conclusion** :
- **JAMAIS de H2 "Conclusion"** (sauf pour blog enseigna)
- Terminer par un court paragraphe condensé (3-5 phrases max)
- Ton motivant et actionnable
- Pas de répétition exhaustive du contenu

### Densité de Contenu

**Guidelines** :
- Minimum **3 sections H2** par article
- Sections suffisamment développées (éviter les H2 avec un seul paragraphe)
- Paragraphes substantiels (éviter les 1-2 phrases isolées)

**À éviter** :
- Contenu trop maigre sous un H2 (quelques lignes)
- Listes à puces sans contexte explicatif
- Répétitions du même message
- Contenu générique sans valeur ajoutée

### Metadata JSON

```json
{
  "title": "Titre SEO (60 chars max) — devient le post_title WP (champ titre du backoffice)",
  "h1": "H1 éditorial du corps de l'article — peut différer du title (angle/profondeur)",
  "meta_description": "Description (150-155 chars)",
  "target_keywords": ["primaire", "secondaire"],
  "word_count": 1800,
  "assets": {
    "images": 6,
    "tables": 2,
    "videos": 1,
    "internal_links": 12
  },
  "eeat_sources": [
    {
      "source": "INSERM",
      "url": "https://...",
      "year": 2026
    }
  ]
}
```

---

## Checklist Spreadsheet

### Statuts Post-Refresh

**Avant publication**, vérifier :

- [ ] **HTML valide** : W3C validation
- [ ] **Asset count** : ≥ version précédente (images, tableaux, vidéos)
- [ ] **Cocons** : PARENT→CHILD→PARENT links validés
- [ ] **YMYL sources** : Présentes si health/finance
- [ ] **Tone blog** : Cohérent avec site_id
- [ ] **E-E-A-T** : Niveau approprié (Experience, Expertise, Authority, Trust)
- [ ] **Métadonnées** : Title/Meta description OK, keywords
- [ ] **Slug unique** : Pas conflit URL
- [ ] **Callouts** : 1 à 3 callouts pertinents

### Colonnes Spreadsheet

**Obligatoires post-refresh** :
- `status` : "terminé" ou "en_revision"
- `strategy_applied` : Stratégie sélectionnée
- `word_count_before` / `word_count_after`
- `assets_before` / `assets_after` (JSON count)
- `tokens_used` : Total tokens consommés
- `refresh_date` : ISO timestamp
- `eeat_level_detected` : Niveau E-E-A-T avant/après

---

## Template: Article Refresh (refresh_article.md)

### Éléments à Améliorer

#### 1. **Titre Principal (H1)**
- Vérifier l'alignement avec les requêtes de recherche prioritaires
- Inclure le mot-clé principal naturellement
- Garder une longueur optimale (50-60 caractères)

#### 2. **Contenu Principal**
- Ajouter les questions PAA (People Also Ask) actuelles comme H2/H3
- Mettre à jour les statistiques et données obsolètes
- Améliorer la structure (listes, tableaux, sections)
- Ajouter des exemples concrets et actualisés

#### 3. **E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)**
- Renforcer les preuves d'expertise
- Ajouter des témoignages ou cas d'étude récents
- Citer des sources fiables et actuelles

#### 4. **Structure Interne**
- Vérifier les liens internes vers articles connexes
- Ajouter des ancres texte pertinentes
- Pointer vers contenus complémentaires

#### 5. **Format et Présentation**
- Adapter le format au dominant de la SERP (listicle, guide, comparison, FAQ)
- Utiliser la mise en forme appropriée
- Améliorer la lisibilité (paragraphes courts, listes)

### Processus de Refresh

```
1. AUDIT INITIAL
   ├─ Analyser les données SERP actuelles
   ├─ Identifier les lacunes de contenu
   └─ Évaluer la pertinence actuelle

2. AMÉLIORATION DU CONTENU
   ├─ Réécrire les sections obsolètes
   ├─ Ajouter du nouveau contenu pertinent
   └─ Intégrer les questions et requêtes manquantes

3. OPTIMISATION SEO
   ├─ Mettre à jour les balises meta
   ├─ Optimiser la densité de mots-clés
   └─ Améliorer la lisibilité (score Flesch)

4. VÉRIFICATION FINALE
   ├─ Contrôler l'absence de doublons
   ├─ Vérifier les liens (internes et externes)
   └─ Valider la cohérence et la qualité
```

### Critères de Succès

✓ Contenu actualisé et pertinent
✓ Format adapté à la SERP
✓ Questions PAA adressées
✓ E-E-A-T renforcé
✓ Structure claire et hiérarchisée
✓ Liens internes pertinents
✓ Pas de contenu dupliqué
✓ Métadonnées optimisées

### Notes Importantes

- Préserver l'intention de l'article original
- Maintenir la voix et le ton du site
- Vérifier la compatibilité avec les guidelines Google
- Tester la lisibilité sur mobile
- Valider les stats/données citées

---

## Conclusion

### 3 Piliers

1. **Préservation** : JAMAIS réduire assets (règle absolue)
2. **Data-driven** : Décisions basées GSC + DataForSEO, pas intuition
3. **Multi-tenant** : Respecter identité éditoriale 6 blogs

### Bonnes Pratiques

✅ Tester chaque refresh avant validation
✅ Vérifier asset counts (avant/après)
✅ Valider sources YMYL
✅ Préserver cocons PARENT/CHILD
✅ Respecter tone blog
✅ Inclure disclaimers si nécessaire

### Références

- **Détails complets** : Consulter CLAUDE.md (documentation référence 1547 lignes)
- **Styles anti-patterns** : `_shared/docs/STYLE_GUIDE.md`
- **E-E-A-T exemples** : `_shared/docs/EEAT_GUIDE.md`
- **Cocons exemples** : `_shared/docs/COCONS_GUIDE.md`
- **Sites spécifiques** : `_shared/prompts/sites/{site_id}.md`
- **Callouts templates** : `_shared/prompts/templates/callouts.md`
- **Configuration** : `_shared/config/sites.json`

---