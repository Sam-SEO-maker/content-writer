# Stratégie : Adaptation de Format

## Déclencheur
- Format actuel de l'article ≠ Format dominant de la SERP
- Exemples : Guide long → Listicle, Article → FAQ, Texte → Tableau

## Objectif
Restructurer le contenu pour correspondre au format que Google privilégie pour cette requête.

---

## Instructions

Tu dois **restructurer** l'article vers le format SERP dominant :
- Conserver TOUTES les informations
- Changer la STRUCTURE, pas le fond
- Préserver tous les assets
- **Toutes les images** avec `<figure>` + `<figcaption>` si l'original contient une légende. Reproduire la légende exacte de l'original dans `<figcaption>`.
- **Tous les liens internes** (exact URLs **ET** exact anchor text — ne JAMAIS modifier un texte d'ancre existant, ne JAMAIS injecter un lien interne qui n'existait pas dans l'article original)
- **Placement des liens** : conserver chaque lien existant à une position naturelle dans le corps du texte, espacés de 150+ mots.

**NE PAS** :
- Supprimer d'informations
- Réduire la longueur
- Retirer des assets
- Injecter des liens internes nouveaux (seuls les liens présents dans l'article original sont autorisés)
- Omettre les légendes d'images (si l'original a une légende, le refresh DOIT la reproduire dans `<figcaption>`)

---

## Formats SERP et Structures

### 1. Listicle (Liste Numérotée)

**Quand l'utiliser :**
- SERP dominée par "X méthodes", "Top Y", "Z conseils"
- Intent : cherche des options, comparaison rapide

**Structure :**

```html
<h1>[Nombre] [Sujet] [Qualificatif] [Année]</h1>

<p><strong>En résumé :</strong> [Liste rapide des X éléments]</p>

<h2>1. [Premier élément]</h2>
<p>[Description 100-150 mots]</p>
<ul>
  <li>Avantage 1</li>
  <li>Avantage 2</li>
</ul>

<h2>2. [Deuxième élément]</h2>
<!-- Répéter le pattern -->

<h2>Tableau Récapitulatif</h2>
<table>
  <tr><th>Option</th><th>Avantages</th><th>Inconvénients</th><th>Prix</th></tr>
  <!-- Lignes -->
</table>

<h2>FAQ</h2>
<!-- Questions -->
```

### 2. Guide Complet (How-to)

**Quand l'utiliser :**
- SERP avec "Comment", "Guide", "Tutoriel"
- Intent : apprendre à faire quelque chose

**Structure :**

```html
<h1>Comment [Action] : Guide Complet [Année]</h1>

<p><strong>Temps nécessaire :</strong> [durée]</p>
<p><strong>Difficulté :</strong> [niveau]</p>
<p><strong>Ce dont vous avez besoin :</strong> [liste]</p>

<h2>Étape 1 : [Titre action]</h2>
<p>[Instructions détaillées]</p>
<img src="..." alt="Étape 1 - ...">

<h2>Étape 2 : [Titre action]</h2>
<!-- Répéter -->

<h2>Erreurs Courantes à Éviter</h2>
<ul>
  <li>❌ [Erreur 1] → ✅ [Solution]</li>
  <li>❌ [Erreur 2] → ✅ [Solution]</li>
</ul>

<h2>FAQ</h2>
```

### 3. Comparatif / Versus

**Quand l'utiliser :**
- SERP avec "vs", "comparatif", "meilleur"
- Intent : choisir entre options

**Structure :**

```html
<h1>[Option A] vs [Option B] : Comparatif [Année]</h1>

<p><strong>Notre verdict :</strong> [Recommandation directe en 1-2 phrases]</p>

<h2>Tableau Comparatif</h2>
<table>
  <tr><th>Critère</th><th>[Option A]</th><th>[Option B]</th></tr>
  <tr><td>Prix</td><td>...</td><td>...</td></tr>
  <tr><td>Qualité</td><td>...</td><td>...</td></tr>
  <!-- Plus de critères -->
</table>

<h2>[Option A] en détail</h2>
<h3>Avantages</h3>
<h3>Inconvénients</h3>

<h2>[Option B] en détail</h2>
<h3>Avantages</h3>
<h3>Inconvénients</h3>

<h2>Lequel Choisir ?</h2>
<ul>
  <li><strong>Choisissez [A] si :</strong> [conditions]</li>
  <li><strong>Choisissez [B] si :</strong> [conditions]</li>
</ul>

<h2>FAQ</h2>
```

### 4. FAQ Étendue

**Quand l'utiliser :**
- SERP dominée par PAA (People Also Ask)
- Featured snippets de type Q&A

**Structure :**

```html
<h1>[Sujet] : Réponses à Toutes Vos Questions</h1>

<p>[Introduction courte avec réponse principale]</p>

<h2>Questions Fréquentes</h2>

<h3>1. [Question exacte du PAA] ?</h3>
<p><strong>[Réponse directe en 1 phrase].</strong> [Développement 50-100 mots]</p>

<h3>2. [Question suivante] ?</h3>
<p><strong>[Réponse directe].</strong> [Développement]</p>

<!-- 10-15 questions minimum -->

<h2>Ressources Complémentaires</h2>
<ul>
  <li><a href="...">Lien interne 1</a></li>
  <li><a href="...">Lien interne 2</a></li>
</ul>
```

### 5. Définition / Explication

**Quand l'utiliser :**
- SERP avec "Qu'est-ce que", "Définition", "C'est quoi"
- Featured snippet de type paragraphe

**Structure :**

```html
<h1>Qu'est-ce que [Sujet] ? Définition et Explication</h1>

<p><strong>[Sujet]</strong> désigne [définition en 1-2 phrases].
[Contexte additionnel].</p>

<h2>Définition Complète</h2>
<p>[Explication détaillée]</p>

<h2>Comment ça Fonctionne ?</h2>
<p>[Mécanisme / processus]</p>

<h2>Exemples Concrets</h2>
<ul>
  <li><strong>Exemple 1 :</strong> [description]</li>
  <li><strong>Exemple 2 :</strong> [description]</li>
</ul>

<h2>Avantages et Inconvénients</h2>
<table>
  <tr><th>Avantages</th><th>Inconvénients</th></tr>
  <!-- Lignes -->
</table>

<h2>FAQ</h2>
```

---

## Règles de Conversion

### Du Guide vers Listicle

1. Identifier les points clés du guide
2. Les numéroter de façon logique
3. Ajouter un tableau récapitulatif
4. Garder le détail dans chaque point

### Du Listicle vers Guide

1. Transformer les points en étapes séquentielles
2. Ajouter les transitions entre étapes
3. Inclure "Temps nécessaire" et "Difficulté"
4. Ajouter section "Erreurs à éviter"

### Vers FAQ

1. Extraire toutes les informations sous forme de Q&A
2. Formuler les questions comme des recherches Google
3. Réponse directe en gras + développement
4. Ajouter les questions PAA manquantes

---

## Format de Sortie

Retourne l'article complet restructuré :

```html
<!-- Format: [Nouveau format] -->
<!-- Meta: [Meta description adaptée] -->

<h1>[Titre adapté au format]</h1>

<!-- Contenu restructuré selon le format cible -->

<!-- Tous les assets originaux préservés -->
```

---

## Structure Obligatoire

- **Introduction AVANT le premier H2** (1 paragraphe `<p>`, 80-150 mots) : accroche concrète + mot-clé principal en `<strong>` + promesse de l'article. Ce paragraphe est le PREMIER élément HTML, il précède tout `<h2>`.
- **Tableau récapitulatif après l'introduction** : immédiatement après le paragraphe d'introduction, insérer un `<table>` synthétique (3-5 lignes) résumant les points clés. En-tête `<thead>` avec fond coloré (`background-color: #1565c0; color: white`), lignes alternées (`background-color: #f5f5f5`).
- **CTA Superprof (si présent)** : le bloc CTA vert (`background-color: #4caf50`) se place à la **fin de la première section H2**, jamais en fin d'article ni dans l'introduction.

---

## Checklist Validation

- [ ] Format correspond au format SERP dominant
- [ ] Toutes les informations originales préservées
- [ ] Structure claire avec H2/H3 appropriés
- [ ] Tableau récapitulatif après introduction (en-tête `#1565c0`, lignes alternées `#f5f5f5`)
- [ ] FAQ présente (5+ questions)
- [ ] Featured snippet ready (réponse directe visible)
- [ ] Toutes images préservées avec `<figure>` + `<figcaption>` (légendes originales reproduites)
- [ ] Tous liens internes préservés (exact URLs ET exact anchor text, aucune injection)
- [ ] 0 ou 1 lien Superprof selon pertinence
- [ ] CTA Superprof à la fin du premier H2 (si présent)
- [ ] Minimum 1500 mots conservés
