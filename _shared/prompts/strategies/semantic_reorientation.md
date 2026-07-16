# Stratégie : Réorientation Sémantique

## Déclencheur
- Mot-clé principal en déclin (-20% ou plus)
- Variantes sémantiques en hausse (+10% ou plus)
- Shift d'intention détecté (informationnel → transactionnel ou inverse)

## Objectif
Réorienter le contenu vers les nouvelles intentions de recherche tout en préservant le positionnement existant.

---

## Instructions

Tu dois effectuer une **réécriture complète** de l'article avec :
1. Réorientation vers les variantes de mots-clés en hausse
2. Adaptation à la nouvelle intention dominante
3. Renforcement maximal E-E-A-T

**PRÉSERVER ABSOLUMENT** :
- Toutes les images avec `<figure>` + `<figcaption>` si l'original contient une légende. Reproduire la légende exacte de l'original dans `<figcaption>`.
- Tous les liens internes (exact URLs **ET** exact anchor text — ne JAMAIS modifier un texte d'ancre existant, ne JAMAIS injecter un lien interne qui n'existait pas dans l'article original)
- **Placement des liens** : conserver chaque lien existant à une position naturelle dans le corps du texte, espacés de 150+ mots.
- 0 ou 1 lien Superprof selon pertinence

**INTERDIT** :
- Injecter des liens internes nouveaux (seuls les liens présents dans l'article original sont autorisés)
- Omettre les légendes d'images (si l'original a une légende, le refresh DOIT la reproduire dans `<figcaption>`)

---

## Analyse du Shift d'Intention

### Types de Shifts

| De → Vers | Adaptation Requise |
|-----------|-------------------|
| Informationnel → Transactionnel | Ajouter comparatifs, prix, CTA |
| Informationnel → Navigationnel | Renforcer la marque, ajouter guides pratiques |
| Transactionnel → Informationnel | Développer le contenu éducatif, réduire le commercial |

### Signaux à Intégrer

**Si shift vers Transactionnel :**
- Tableau comparatif des options
- Section "Prix et tarifs"
- Témoignages clients avec résultats concrets
- CTA vers inscription/contact

**Si shift vers Informationnel :**
- Définitions et explications détaillées
- Schémas et illustrations pédagogiques
- FAQ étendue
- Sources académiques/institutionnelles

---

## Restructuration du Contenu

### Nouvelle Structure Recommandée

```
H1: [Nouveau titre orienté variante montante]

Introduction (80-150 mots, 1 paragraphe <p>)
- Accroche avec question/problème
- Réponse directe (featured snippet ready)
- Annonce du contenu
- Ce paragraphe est le PREMIER élément HTML, il précède tout H2

Tableau récapitulatif (immédiatement après l'introduction)
- <table> synthétique (3-5 lignes) résumant les points clés
- En-tête <thead> avec fond coloré (background-color: #1565c0; color: white)
- Lignes alternées (background-color: #f5f5f5)

H2: [Section répondant à l'intention principale]
- CTA Superprof (si présent) à la FIN de cette section, jamais en fin d'article
- Paragraphe avec réponse immédiate
- Liste à puces des points clés
- [Image existante ou nouvelle]

H2: [Section E-E-A-T - Expertise]
- "Notre expérience" ou "Notre méthodologie"
- Données chiffrées personnelles
- Preuves de terrain

H2: [Sections thématiques]
- Intégrer variantes de mots-clés naturellement
- Sous-sections H3 si nécessaire
- Liens internes existants conservés

H2: Ressources et Recommandations
- Liens vers sources d'autorité
- [Lien Superprof avec ancre naturelle]

H2: FAQ
- 5-7 questions basées sur PAA
- Format Q&A strict
- Réponses concises (40-60 mots)

Conclusion
- Récapitulatif
- CTA final
```

---

## Intégration des Variantes Sémantiques

### Méthode de Tissage

1. **Titre H1** : Variante principale montante
2. **Premier H2** : Variante secondaire
3. **Introduction** : Mix mot-clé original + variante
4. **Corps** : Alterner naturellement
5. **FAQ** : Questions avec variantes

### Anti-suroptimisation (voir STYLE_GUIDE.md section 11)

La réorientation sémantique vise la LARGEUR (couvrir des variantes) plutôt que la PROFONDEUR (répéter les mêmes). Cible : zone TOP 3 (SOSEO 55-75%, DSEO < 20%).
- Chaque variante : **2-4 occurrences** distribuées dans l'article
- Varier le vocabulaire : mieux vaut 25 termes à 2x que 10 termes à 5x
- Jamais 2 variantes exactes dans la même phrase
- Espacer les occurrences d'au moins 1 paragraphe
- **Synonymes obligatoires** : tout terme à 3+ occurrences doit être alternativement remplacé par un synonyme dans 50% des cas
- Préférer les reformulations naturelles aux répétitions exactes

### Exemple

**Mot-clé original (déclin)** : "cours de maths particulier"
**Variantes montantes** : "soutien scolaire maths", "aide aux devoirs maths"

**Tissage :**
> Le **soutien scolaire en maths** est devenu essentiel pour de nombreux élèves. Que vous cherchiez une **aide aux devoirs en maths** régulière ou des **cours de maths particuliers** intensifs, plusieurs options s'offrent à vous...

---

## Renforcement E-E-A-T

### Éléments Obligatoires

1. **Experience (Expérience)**
   - Section "Notre expérience terrain"
   - Anecdotes concrètes datées
   - Photos/captures si possible

2. **Expertise**
   - Mention des qualifications
   - Années d'expérience
   - Spécialisations

3. **Authoritativeness (Autorité)**
   - Citations d'experts nommés
   - Références à des études (avec liens)
   - Partenariats/certifications

4. **Trustworthiness (Fiabilité)**
   - Sources institutionnelles (eduscol, education.gouv)
   - Dates de mise à jour visibles
   - Méthodologie transparente

### Template Section E-E-A-T

```markdown
## Notre Expertise

Depuis [année], notre équipe accompagne [nombre]+ élèves dans leur progression en [matière].

**Notre méthodologie** repose sur :
- [Point 1 avec chiffre]
- [Point 2 avec preuve]
- [Point 3 avec résultat]

> "[Citation d'un expert ou témoignage]"
> — [Nom], [Titre/Qualification]

*Dernière mise à jour : [Date] | Sources : [Liens]*
```

---

## Format de Sortie

Retourne l'article complet réécrit en HTML avec :

1. Nouveau titre H1
2. Meta description (en commentaire HTML)
3. Contenu complet restructuré
4. Tous les assets préservés
5. Nouvelles sections E-E-A-T

```html
<!-- Meta: [Nouvelle meta description - 160 car max] -->

<h1>[Nouveau titre orienté variantes]</h1>

<p>[Introduction avec réponse directe...]</p>

<!-- Suite du contenu -->
```

---

## Checklist Validation

- [ ] Variantes sémantiques intégrées naturellement
- [ ] Intention de recherche correctement ciblée
- [ ] Section E-E-A-T présente
- [ ] Minimum 3 sources institutionnelles
- [ ] FAQ avec 5+ questions
- [ ] Toutes images préservées avec `<figure>` + `<figcaption>` (légendes originales reproduites)
- [ ] Tous liens internes préservés (exact URLs ET exact anchor text, aucune injection)
- [ ] Tableau récapitulatif après introduction (en-tête `#1565c0`, lignes alternées `#f5f5f5`)
- [ ] CTA Superprof à la fin du premier H2 (si présent)
- [ ] 0 ou 1 lien Superprof selon pertinence
- [ ] Aucun lien blacklisté
- [ ] Minimum 1500 mots
