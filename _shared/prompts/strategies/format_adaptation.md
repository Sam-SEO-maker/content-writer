# FORMAT_ADAPTATION : Adaptation au format SERP

## Quand
Le format de l'article ≠ format dominant de la SERP (ex. guide long → listicle,
article → FAQ, texte → tableau).

## Scope
**Restructurer** vers le format SERP dominant : changer la STRUCTURE, pas le fond.
Conserver toutes les informations et tous les assets (aucune perte, aucune réduction).

## Delta propre : les 5 gabarits de format

### 1. Listicle (« X méthodes », « Top Y »)
H1 `[Nombre] [Sujet] [Année]` → résumé rapide → un H2 numéroté par élément
(description 100-150 mots + puces) → tableau récapitulatif → FAQ.

### 2. Guide / How-to (« Comment », « Tutoriel »)
H1 `Comment [Action] : Guide [Année]` → prérequis (temps, difficulté, matériel) →
un H2 par étape séquentielle (+ image d'étape) → H2 « Erreurs courantes à éviter »
(erreur → solution) → FAQ.

### 3. Comparatif / Versus (« vs », « meilleur »)
H1 `[A] vs [B] : Comparatif [Année]` → verdict direct (1-2 phrases) → tableau
comparatif par critère → « [A] en détail » (H3 avantages/inconvénients) → idem [B] →
« Lequel choisir ? » (conditions par option) → FAQ.

### 4. FAQ étendue (SERP dominée par les PAA)
H1 `[Sujet] : réponses à vos questions` → intro courte → H2 « Questions fréquentes »
→ un H3 par question (formulée comme une recherche Google) : réponse directe en gras
+ développement 50-100 mots → ressources complémentaires. FAQ étendue = plus de
questions que le défaut (le nb par défaut vit dans `edito-refresh`).

### 5. Définition / Explication (« Qu'est-ce que »)
H1 `Qu'est-ce que [Sujet] ?` → définition en 1-2 phrases (featured snippet) →
« Définition complète » → « Comment ça fonctionne ? » → exemples concrets →
avantages/inconvénients (tableau) → FAQ.

## Règles de conversion

- **Guide → Listicle** : extraire les points clés, les numéroter, ajouter un tableau récap, garder le détail par point.
- **Listicle → Guide** : transformer les points en étapes séquentielles, ajouter transitions + prérequis + « erreurs à éviter ».
- **Vers FAQ** : extraire l'info en Q&A, formuler les questions comme des recherches Google, réponse directe en gras + développement, compléter avec les PAA manquants.

## Règles héritées (ne pas redéfinir ici)
- **Fond** (réponse directe, FAQ, sources, E-E-A-T) → skill `edito-refresh`.
- **Forme** (préservation des assets, HTML clean, tableaux, métadonnées, callouts
  colorés interdits) → skill `format-wordpress`.
- **Structure d'ensemble et couleurs** → skill du tenant. Ne pas coder de couleurs
  en dur ici. Les gabarits ci-dessus décrivent l'ORDRE des sections, pas leur style.
