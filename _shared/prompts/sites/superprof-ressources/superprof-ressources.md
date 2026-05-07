# Site Override : Superprof Ressources FR

**Domain** : https://www.superprof.fr/ressources/
**Language** : Français
**YMYL Level** : Low
**Tone profile** : Naturel, plutôt informel, encourageant, respectueux

> ⚠️ **TODO Tone & Voice définitif** : en attente de la Product Owner Manager. En attendant, appliquer strictement le Guide 1 (section "Our Voice & Tone").

## Règles éditoriales (sources)

Toutes les règles d'écriture, SEO, formatage et refresh sont définies dans les 3 guides officiels Superprof, à charger AVANT toute génération :

1. [Guide 1 — Blog Writing Foundations](./superprof-ressources/guide-1-blog-writing-foundations.md)
   *Brand values, voice & tone, public, qualité, AI guidelines, images*
2. [Guide 2 — Blog Writing Reference](./superprof-ressources/guide-2-blog-writing-reference.md)
   *SEO elements, linking & anchor text, titres, images, blocs WordPress, formatage, checklist publication*
3. [Guide 3 — Working with Refreshes](./superprof-ressources/guide-3-working-with-refreshes.md)
   *Process refresh, règles critiques, checklist refresh, exemples*

Le pipeline de prompt composer DOIT injecter le contenu intégral de ces 3 guides (ou au minimum Guide 1 + Guide 3 pour les refresh) dans le prompt de génération.

## Règles non-négociables (résumé exécutif)

### Longueur cible par type de contenu

Deux typologies coexistent sur Superprof Ressources :

| Type       | Cible mots | Usage                                                        |
|------------|------------|--------------------------------------------------------------|
| **théorie**    | 1 200 – 1 600 | Cours, définitions, fiches de rappel, biographies, contextes historiques |
| **exercices**  | 600 – 1 000   | Entraînements, corrigés types, problèmes résolus, méthodologie appliquée |

Par défaut (si le type n'est pas précisé), utiliser la cible **théorie**. Le type doit venir du brief ou de la spreadsheet (colonne dédiée à ajouter par Andra). Ne pas gonfler artificiellement pour atteindre le haut de la cible — viser la concision utile.

### Identité de marque
- ✅ **Superprof** (un seul mot, S majuscule, p minuscule)
- ❌ JAMAIS : "Super Prof", "SuperProf", "SP"
- Superprof n'est ni "il" ni "elle" — pas de pronom personnel

### Voice & Tone
- Naturel, plutôt informel, conversationnel sans être négligé
- **Formuler positivement** (opportunité > manque/échec)
- Inspirer, ne pas décourager
- Phrases courtes (< 20 mots), une idée par phrase, voix active
- Paragraphes de **3 à 5 phrases** (jamais de phrases flottantes)
- Intros courtes (1-2 paragraphes max), directes et engageantes

### Anchor text & linking (CRITIQUE SEO)
- **JAMAIS** de money keywords en anchor text vers un blog article
- Liens blog→blog : warm/cold keywords uniquement
- Liens blog→landing (`/lessons/`) : money keywords autorisés
- Cf. Guide 2 — section "Linking" pour les règles complètes

### AI usage
- ✅ Inspiration, structure, titres, CTA, grammaire
- ❌ JAMAIS de copier-coller direct de texte généré par IA
- La voix et le jugement restent humains. Audits aléatoires de plagiat/AI-detection.

### Images
- Sens > esthétique. Chaque image doit ajouter quelque chose à la compréhension.
- Préférer Unsplash et photos authentiques aux stocks caricaturaux
- Légendes contextuelles (lieu, sujet, photographe le cas échéant)

### Refresh (Guide 3)
- Préserver l'intention originale et l'URL
- Mettre à jour stats, exemples, structure, visuels selon le brief
- Respecter les blocs Gutenberg obligatoires (cf. Guide 2)
- Utiliser le bon éditeur WordPress (cf. Guide 3 — "Critical Rules")

## Structure HTML obligatoire

### H1 dans le corps de texte (OBLIGATOIRE)
- Chaque article Superprof Ressources doit avoir un `<h1>` comme **première balise du corps de texte**, avant la section d'introduction
- Placement : juste avant `<section class="introduction">`, à l'intérieur du wrapper `<article>`
- Le texte du H1 doit **contenir le mot-clé principal** et être descriptif/complémentaire au titre SEO (pas une répétition exacte)
- Si un H1 existe déjà dans le contenu, ne pas en ajouter un second

```html
<article class="blog-post" lang="fr">

<h1>[Titre descriptif du corps de l'article]</h1>

<section class="introduction">
  ...
</section>
```

## Anti-patterns à proscrire

- ❌ Sujets controversés / positions politiques
- ❌ Langage sensationnel ("incredible", "amazing", "révolutionnaire")
- ❌ Tangentes hors-sujet
- ❌ Références/stats non valables pour le marché FR
- ❌ Bold sur des phrases entières (réservé aux termes-clés)
- ❌ Money keywords en anchor text vers du blog
- ❌ Sentences flottantes hors paragraphes
