# SEO Guidelines 2026

## Vue d'ensemble

Ce document définit les meilleures pratiques SEO pour la rédaction d'articles sur les 6 sites web gérés par ce workflow.

### Documentation Complémentaire

| Guide | Description | Fichier |
|-------|-------------|---------|
| GEO 2026 | Optimisation pour moteurs génératifs (IA) | [docs/GEO_2026_GUIDELINES.md](docs/GEO_2026_GUIDELINES.md) |
| E-E-A-T 2026 | Experience, Expertise, Authority, Trust | [docs/EEAT_GUIDE.md](docs/EEAT_GUIDE.md) |
| Content Refresh | Guide de rafraîchissement de contenu | [docs/CONTENT_REFRESH_GUIDE.md](docs/CONTENT_REFRESH_GUIDE.md) |

---

## 1. Recherche de mots-clés

### Critères de sélection
- **Volume**: > 20 recherches/mois (longue traîne)
- **Difficulté**: ≤ 40 (opportunités accessibles)
- **Intent**: Informationnel principalement

### Outils
- **DataforSEO API**: Recherche principale
- **Google Search Console**: Validation des opportunités existantes

---

## 2. Structure des articles

### Longueur
- **Minimum**: 1500 mots
- **Idéal**: 1800-2200 mots
- **Maximum**: 2500 mots

### Hiérarchie des titres
```
# H1 - Titre principal (1 seul)
## H2 - Sections principales (minimum 3)
### H3 - Sous-sections (optionnel)
```

### Structure obligatoire

1. **Titre H1**
   - Inclure le mot-clé principal
   - Maximum 60 caractères recommandé
   - Accrocheur et descriptif

2. **Introduction** (150-200 mots)
   - Mot-clé principal dans la première phrase
   - Statistique sourcée
   - Citation d'autorité ou référence à une étude
   - Accroche pour le lecteur

3. **Tableau récapitulatif**
   ```markdown
   | Élément | Détail |
   |---------|--------|
   | Sujet | ... |
   | Temps de lecture | X minutes |
   | Points clés | ... |
   ```

4. **Corps de l'article**
   - Minimum 3 sections H2
   - 300-400 mots par section
   - Listes à puces (2-3 par article)
   - Phrases de transition entre sections

5. **CTA Superprof**
   - 1 seul lien par article
   - Ancre naturelle et variée
   - Placement contextuel

6. **Section FAQ**
   - 3-5 questions PAA
   - Réponses de 50-100 mots

7. **Conclusion** (100-150 mots)
   - Résumé des points clés
   - Pas de lien Superprof supplémentaire

8. **Meta description**
   - 150-155 caractères
   - Inclure le mot-clé principal

---

## 3. Règles de liens

### Lien Superprof (employeur)
- **Quantité**: 1 seul lien par article
- **Format URL**: `superprof.fr/cours/[matière]/[ville ou france]/`
- **Ancre**: Variée à chaque article
  - ✅ "trouver un professeur particulier"
  - ✅ "accompagnement personnalisé"
  - ✅ "cours à domicile près de chez vous"
  - ❌ "Superprof" (mot-clé exact)
  - ❌ "cliquez ici" (non descriptif)

### Liens externes (autorité)
- **Quantité**: 1-2 par article
- **Sources privilégiées** (whitelist):
  - eduscol.education.fr
  - education.gouv.fr
  - onisep.fr
  - cned.fr
  - sports.gouv.fr
  - culture.gouv.fr
  - has-sante.fr
  - inserm.fr

### Concurrents INTERDITS (blacklist)
- ❌ acadomia.fr
- ❌ kelprof.com
- ❌ apprentus.fr
- ❌ voscours.fr
- ❌ completchude.com

### Liens internes (cocons sémantiques)

**Article parent**:
- 1 lien vers chaque enfant dans le H2 correspondant

**Article enfant**:
- 1 lien vers le parent dans l'introduction
- 1 lien vers chaque article frère dans le corps

---

## 4. Cocons sémantiques

### Structure
```
Article Parent
├── H2 = H1 Enfant 1
├── H2 = H1 Enfant 2
└── H2 = H1 Enfant 3-5
```

### Règles
- Parent: 3-5 enfants maximum
- Les H2 du parent = les H1 des enfants
- Maillage bidirectionnel complet

---

## 5. Spécificités par site

### Enseigna.fr (Review/Comparatif)
- Ton: Testeur expert, analytique, objectif
- **OBLIGATOIRE**:
  - Tableau comparatif avec scoring
  - Section "Notre verdict"
- Format titre: "Avis sur X" ou "X vs Y : comparatif"

### Autres sites
- Ton selon profil défini dans `tone_profiles.json`
- Structure article standard

---

## 6. Optimisation on-page

### Mots-clés
- Densité: 1-2% (naturelle)
- Placement prioritaire:
  1. Titre H1
  2. Première phrase introduction
  3. Au moins 1 H2
  4. Meta description

### Images
- 1 image à la Une
- 2 images dans le corps
- Alt text descriptif avec mot-clé si pertinent

### URL
- Courte et descriptive
- Inclure le mot-clé principal
- Format: `/mot-cle-principal/`

---

## 7. Fraîcheur du contenu

**Statistique clé**: ChatGPT cite préférentiellement les pages mises à jour dans les 30 derniers jours (76.4% des citations).

> **Voir le guide complet**: [docs/CONTENT_REFRESH_GUIDE.md](docs/CONTENT_REFRESH_GUIDE.md)

### Politique de rafraîchissement
| Âge du contenu | Action | Priorité |
|----------------|--------|----------|
| < 6 mois | À jour | - |
| 6-12 mois | Vérification nécessaire | Basse |
| 12-18 mois | Rafraîchissement recommandé | Moyenne |
| > 18 mois | Rafraîchissement prioritaire | Haute |

### Signaux de Refresh Urgent
- Baisse de position > 5 places
- Chute de trafic > 30% sur 3 mois
- CTR < 2% avec impressions > 500
- Liens cassés détectés

### Éléments à mettre à jour
- Statistiques et données (sources 2025-2026)
- Liens (vérifier les liens morts, remplacer par équivalents récents)
- Dates et références temporelles
- Citations d'experts (ajouter si absentes)
- Section FAQ (nouvelles PAA)

### Règle d'Or des Assets
**Ne JAMAIS appauvrir** - seulement maintenir ou enrichir:
- `count(<img>)` après >= avant
- `count(<a>)` après >= avant
- 0 ou 1 lien Superprof selon pertinence

### Ce qu'il NE FAUT PAS Faire
- ❌ Changer la date sans modification substantielle (pénalisé par Google)
- ❌ Supprimer des images ou liens internes
- ❌ Republier immédiatement après refresh (attendre 4 semaines)

---

## 8. Standards E-E-A-T 2026

**Principe**: La Confiance (Trust) est l'élément le plus important. Sans confiance, les autres signaux sont insuffisants.

> **Voir le guide complet**: [docs/EEAT_GUIDE.md](docs/EEAT_GUIDE.md)

### Les 4 Piliers

| Pilier | Signaux à Inclure |
|--------|-------------------|
| **Experience** | Sections "Notre expérience", cas concrets, photos originales |
| **Expertise** | Explications approfondies, termes techniques définis, sources citées |
| **Authoritativeness** | Auteur identifié, backlinks de sites .edu/.gov, mentions tierces |
| **Trustworthiness** | Page "À propos", HTTPS, liens fonctionnels, informations à jour |

### Exigences YMYL par Blog

| Blog | Catégorie YMYL | Exigence |
|------|----------------|----------|
| enseigna.fr | Éducation/Finance | Méthodologie de test, indépendance |
| superprof.fr/ressources/ | Éducation | Sources institutionnelles, suivre les 3 guides Superprof |

### Auteur Obligatoire

```markdown
**[Prénom Nom]** est [titre] avec [X] années d'expérience dans [domaine].
**Expertise**: [domaines] | **Formation**: [diplômes]
```

---

## 9. Checklist pré-publication

### SEO de Base
- [ ] H1 avec mot-clé principal (max 60 caractères)
- [ ] Mot-clé dans première phrase introduction
- [ ] Minimum 1500 mots
- [ ] Minimum 3 sections H2
- [ ] Tableau récapitulatif présent
- [ ] 1 seul lien Superprof (ancre variée)
- [ ] 1-2 liens externes (sources d'autorité uniquement)
- [ ] Aucun lien concurrent (blacklist)
- [ ] Section FAQ avec PAA actuels
- [ ] Meta description (150-155 car.)
- [ ] Images avec alt text descriptif

### GEO 2026
- [ ] Au moins 2 statistiques sourcées (2025-2026)
- [ ] Au moins 1 citation d'expert avec credentials
- [ ] Réponse directe en début de chaque H2
- [ ] Listes à puces pour informations clés
- [ ] Tableau de synthèse présent

### E-E-A-T
- [ ] Auteur identifié avec bio/credentials
- [ ] Date de publication visible
- [ ] Date de mise à jour si applicable
- [ ] Sources institutionnelles citées
- [ ] Section "Notre expérience" si applicable

---

## 9. Critères GEO (Generative Engine Optimization)

**Contexte 2026**: Gartner prévoit -25% de trafic de recherche conventionnel. 50% des consommateurs utilisent l'IA comme méthode principale de recherche. Les AI Overviews ne citent que **3 sources** au lieu de 10 liens traditionnels.

> **Voir le guide complet**: [docs/GEO_2026_GUIDELINES.md](docs/GEO_2026_GUIDELINES.md)

### Stratégies GEO Obligatoires

| Stratégie | Impact | Exemple |
|-----------|--------|---------|
| Ajout de statistiques | +41% visibilité | "Selon l'INSEE 2026, 18% des élèves..." |
| Citations d'experts | +28% impression | "...explique Dr. Dupont, chercheur à l'ENS" |
| Réponse directe | Extraction IA | Première phrase de chaque H2 = réponse |

### Structure GEO-Optimisée

```
## [Question H2]

[Réponse directe en 1-2 phrases] ← L'IA extrait ceci

[Développement avec statistiques sourcées (2025-2026)]

> "Citation d'expert" - [Nom], [Credentials]

- Point clé 1
- Point clé 2
- Point clé 3
```

### Éléments de Crédibilité (obligatoires)
- **Statistiques**: Minimum 2 par article, sources 2025-2026
- **Citations d'experts**: Minimum 1, avec credentials vérifiables
- **Sources institutionnelles**: eduscol, education.gouv, has-sante, inserm
- **Auteur identifié**: Nom + bio + credentials

### Formats Extractibles par IA
- Listes à puces pour énumérations
- Tableaux de synthèse comparatifs
- Sections FAQ avec questions PAA exactes
- Définitions claires en début de section

### Ce qu'il NE FAUT PAS Faire
- ❌ Keyword stuffing (moins efficace en GEO)
- ❌ Statistiques sans dates (considéré obsolète)
- ❌ Contenu générique sans sources (non cité)
- ❌ Absence d'auteur identifié

---

## 10. Workflow recommandé

1. **Recherche**: DataforSEO → mots-clés + PAA
2. **Analyse**: SERP → intent + opportunités
3. **Planification**: Cocon sémantique si applicable
4. **Rédaction**: Template approprié
5. **Validation**: SEOValidator
6. **Publication**: WordPress/CMS
7. **Tracking**: Google Sheet
8. **Monitoring**: GSC après 2-4 semaines
