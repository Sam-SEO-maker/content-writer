# Stratégie : Réécriture E-E-A-T Maximale

## Déclencheur
- Contenu YMYL (Your Money Your Life)
- Score E-E-A-T faible
- Pénalité manuelle ou algorithmique suspectée
- Concurrence forte sur des requêtes d'expertise

## Objectif
Réécrire l'article avec un focus maximal sur les signaux E-E-A-T pour établir l'autorité et la confiance.

---

## Instructions

Tu dois effectuer une **réécriture complète E-E-A-T** avec :
1. Preuves d'expérience terrain
2. Démonstration d'expertise
3. Signaux d'autorité
4. Éléments de confiance

**OBLIGATIONS** :
- Si des données terrain authentiques sont disponibles, les intégrer naturellement dans le flux
- Minimum 3 sources institutionnelles (seuil rehaussé vs standard YMYL de 2)
- Au moins 1 citation d'expert avec credentials

---

## Les 4 Piliers E-E-A-T

### 1. Experience (Expérience)

**Ce que Google cherche :**
- Preuves que l'auteur a réellement vécu/testé ce qu'il décrit
- Anecdotes personnelles datées et localisées
- Photos/captures d'écran originales

**Comment l'intégrer :**

Intégrer les preuves d'expérience **naturellement dans le flux du contenu** (pas de section H2 dédiée). Démontrer l'expérience par des détails techniques pointus, des nuances de praticien, et du vocabulaire de terrain — pas par des anecdotes formatées.

### 2. Expertise

**Ce que Google cherche :**
- Qualifications vérifiables
- Connaissance approfondie du sujet
- Vocabulaire technique maîtrisé

**Comment l'intégrer :**

```html
<h2>Méthodologie et Approche</h2>

<p>Notre analyse repose sur :</p>
<ul>
  <li><strong>[Nombre] années</strong> de pratique dans [domaine]</li>
  <li><strong>[Certification/Diplôme]</strong> en [spécialité]</li>
  <li>Veille continue des publications de [organisme référent]</li>
</ul>

<h3>Notre Processus d'Évaluation</h3>
<ol>
  <li><strong>Étape 1 :</strong> [Description méthodologique]</li>
  <li><strong>Étape 2 :</strong> [Description méthodologique]</li>
  <li><strong>Étape 3 :</strong> [Description méthodologique]</li>
</ol>
```

### 3. Authoritativeness (Autorité)

**Ce que Google cherche :**
- Reconnaissance par des pairs/institutions
- Citations et backlinks de sources fiables
- Mentions dans des médias reconnus

**Comment l'intégrer :**

```html
<h2>Ce que Disent les Experts</h2>

<blockquote cite="[URL source]">
"[Citation exacte de l'expert]"
<footer>— <strong>[Nom]</strong>, [Titre], [Institution]</footer>
</blockquote>

<p>Selon une étude de <a href="[URL]">[Institution] ([année])</a>,
[statistique ou conclusion clé].</p>

<h3>Sources de Référence</h3>
<ul>
  <li><a href="https://eduscol.education.fr/...">Eduscol - [Titre]</a></li>
  <li><a href="https://www.education.gouv.fr/...">Ministère - [Titre]</a></li>
  <li><a href="https://www.has-sante.fr/...">HAS - [Titre]</a> (si santé)</li>
</ul>
```

### 4. Trustworthiness (Fiabilité)

**Ce que Google cherche :**
- Transparence sur l'auteur et le site
- Informations de contact
- Politique de mise à jour
- Absence de conflits d'intérêts déclarés

**Comment l'intégrer :**

La bio auteur, les informations de contact et la politique de mise à jour sont gérées par **WordPress au niveau du profil auteur**. Ne pas inclure de section "À Propos" dans le HTML généré.

Dans le contenu, intégrer la transparence naturellement :
- Mention d'affiliation Superprof via le callout CTA (vert)
- Disclaimer YMYL via le callout dédié (orange)
- Sources intégrées dans le flux du texte

---

## Structure Article E-E-A-T

Sections recommandées (ordre indicatif) :

1. **Introduction** (1 paragraphe `<p>`, 80-150 mots) — Réponse directe + mention de l'expérience terrain. Ce paragraphe est le PREMIER élément HTML, il précède tout `<h2>`.
2. **Tableau récapitulatif après l'introduction** — Immédiatement après le paragraphe d'introduction, insérer un `<table>` synthétique (3-5 lignes) résumant les points clés. En-tête `<thead>` avec fond coloré (`background-color: #1565c0; color: white`), lignes alternées (`background-color: #f5f5f5`).
3. **CTA Superprof (si présent)** — Le bloc CTA vert (`background-color: #4caf50`) se place à la **fin de la première section H2**, jamais en fin d'article ni dans l'introduction.
2. **Section thématique principale** — Contenu avec sources, données + preuves d'expérience terrain intégrées naturellement
3. **Ce que Disent les Études** — Citations et statistiques sourcées
4. **Avis d'Experts** — Citation nommée avec credentials (`<blockquote>`)
5. **Conseils Pratiques** — Recommandations actionnables basées sur l'expertise
6. **FAQ** — Questions avec réponses d'expert (format H3)

Les sources sont intégrées **naturellement dans le texte**. Pas de section "Sources" ou "À Propos" en fin d'article — WordPress gère l'auteur indépendamment.

---

## Sources Institutionnelles par Domaine

### Éducation
- eduscol.education.fr
- education.gouv.fr
- onisep.fr
- etudiant.gouv.fr

### Santé (YMYL)
- has-sante.fr
- ameli.fr
- inserm.fr
- santepubliquefrance.fr

### Finance (YMYL)
- economie.gouv.fr
- banque-france.fr
- amf-france.org

### Droit
- legifrance.gouv.fr
- service-public.fr

---

## Format de Sortie

HTML propre WordPress-ready (pas de wrappers, pas de H1, pas de footer) :

```html
<p><strong>En bref :</strong> [Réponse directe avec autorité]</p>

<p>Depuis <strong>[X] années</strong>, [contexte expérience terrain]...</p>

<h2>[Section thématique 1]</h2>
<p>[Contenu avec sources intégrées naturellement + storytelling récent dans le flux]</p>

<h2>[Section thématique 2]</h2>
<p>[Citations et statistiques sourcées avec liens]</p>

<blockquote>
  <p>[Citation exacte de l'expert]</p>
  <footer>— <strong>[Nom]</strong>, [Titre], [Institution]</footer>
</blockquote>

<h2>FAQ</h2>
<h3>[Question PAA] ?</h3>
<p>[Réponse directe + développement]</p>
```

---

## Checklist Validation E-E-A-T

### Experience
- [ ] Preuves d'expérience terrain intégrées naturellement (si disponibles)
- [ ] Détails concrets et spécifiques au sujet (pas de template formaté)

### Expertise
- [ ] Qualification de l'auteur mentionnée
- [ ] Méthodologie expliquée
- [ ] Vocabulaire technique approprié

### Authoritativeness
- [ ] Minimum 3 sources institutionnelles
- [ ] Au moins 1 citation d'expert nommé
- [ ] Liens vers études/rapports officiels

### Trustworthiness
- [ ] Sources intégrées dans le flux du texte (pas de section "Sources" en fin d'article)
- [ ] Transparence sur affiliations via callout CTA (si applicable)
- [ ] Disclaimer YMYL présent (si santé/sport)

### Assets
- [ ] Toutes images préservées avec `<figure>` + `<figcaption>` (reproduire la légende exacte de l'original)
- [ ] Tous liens internes préservés (exact URLs **ET** exact anchor text — ne JAMAIS injecter un lien interne qui n'existait pas dans l'article original)
- [ ] Liens existants conservés à une position naturelle, espacés de 150+ mots
- [ ] 0 ou 1 lien Superprof selon pertinence
- [ ] Aucun lien blacklisté

---

## Intégration des Sources (règles)

Les sources s'intègrent **dans le flux du texte**, jamais en liste finale.

✅ **Correct** :
```html
<p>Selon les données du <a href="https://www.inserm.fr/...">INSERM (2024)</a>,
le yoga réduit le cortisol de 35% chez les pratiquants réguliers.</p>
```

❌ **Interdit** : section "Sources" ou "Références" en fin d'article

**Ancres** : toujours descriptives ("étude de l'INSERM", "rapport ONISEP 2025") — jamais "cliquez ici" ou "voir la source".

**Fraîcheur** : privilégier 2024-2026. Si données antérieures indispensables, préciser explicitement l'année.
