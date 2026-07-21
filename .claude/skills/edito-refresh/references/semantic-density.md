# Densité sémantique : modèle par occurrences (SOSEO / DSEO)

Référence chargée à la demande depuis `edito-refresh`. **Ne jamais raisonner en
« densité % »** : raisonner en couverture + occurrences.

## Principe : deux axes

1. **Couverture (LARGEUR)** : utiliser un maximum de termes du champ sémantique. Les articles TOP 3 couvrent ~90% des termes pertinents.
2. **Modération (PROFONDEUR)** : ne pas répéter excessivement les mêmes termes.

L'erreur courante n'est PAS d'utiliser trop de termes différents, c'est de
**répéter les mêmes 5-6 termes trop souvent**. Viser la largeur, pas la profondeur.

## Plafonds de répétition (article ~1800 mots)

| Élément | Limite |
|---------|--------|
| Mot-clé principal (exact match) | **3-6 occurrences** (H1 + intro + 1-2 H2 + conclusion) |
| Top 10 termes importants du sujet | 2-5 occurrences chacun, distribués |
| Autres termes du champ sémantique | 1-3 occurrences chacun |
| Espacement | pas le même terme dans 2 paragraphes consécutifs |

## Règle de synonymie obligatoire

Tout terme apparaissant **3 fois ou plus** → remplacé par un synonyme/périphrase
dans ≥ 50% de ses occurrences. Exemples :
- « musculation » → « renforcement musculaire », « travail en salle »
- « coach » → « entraîneur », « préparateur physique »
- « séance » → « session », « créneau », « entraînement »

## Cible SOSEO / DSEO (YourTextGuru)

La cible est **variable : elle dépend de la SERP de chaque requête**, jamais d'un
seuil uniforme. Le guide YTG fournit les scores moyens des concurrents
(`top3_soseo`/`top3_dseo` et `top10_soseo`/`top10_dseo`) ; la règle :

| Métrique | Règle vs moyenne TOP 3 | Règle vs moyenne TOP 10 |
|----------|------------------------|--------------------------|
| **SOSEO** (couverture) | article **> moyenne** (ex. moyenne 60% → viser > 60%) | article **> moyenne** |
| **DSEO** (danger) | article **strictement < moyenne** (ex. moyenne 5% → rester < 5%) | article **strictement < moyenne** |

Battre la moyenne, pas l'exploser : un article à 116% SOSEO / 37% DSEO est
inexploitable (suroptimisation). Dépasser la moyenne SOSEO de quelques points
suffit ; le DSEO doit toujours rester sous les deux moyennes.

## ❌ Interdit / ✅ Correct

Interdit : empiler 3+ termes techniques dans une phrase ; répéter un terme dans 2
paragraphes consécutifs ; phrases « catalogue » de vocabulaire ; forcer un terme
technique là où un mot courant suffit ; concentrer le vocabulaire dans une section.

Correct : vocabulaire spécialisé quand il précise ; périphrases plutôt que
répétitions ; distribution uniforme ; écrire pour le lecteur d'abord ; laisser des
paragraphes « respirer » en prose naturelle.

## Exemple

```
❌ SUROPTIMISÉ :
"Le squat, exercice polyarticulaire d'hypertrophie, sollicite les quadriceps...
La charge progressive en squat permet l'hypertrophie des quadriceps..."
→ 3x "squat", 2x "hypertrophie", 2x "quadriceps" en 3 phrases

✅ OPTIMAL :
"Le squat sollicite simultanément plusieurs groupes musculaires majeurs :
quadriceps, fessiers et ischio-jambiers. C'est un mouvement fondamental pour
développer la force du bas du corps. En augmentant progressivement la charge,
vous stimulez une croissance musculaire durable."
→ 1x "squat", termes variés, lecture fluide
```

*Référence canonique du modèle SOSEO/DSEO (migré depuis l'ancien STYLE_GUIDE.md §11,
supprimé). Cité par les strategies full_refresh et semantic_reorientation.*
