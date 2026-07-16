# FULL_REFRESH - Réécriture Complète

## Mission

Réécrire l'article complet avec une amélioration substantielle du contenu, de la structure et de l'E-E-A-T, tout en préservant tous les assets existants.

---

## ⚠️ RÈGLES ABSOLUES (Non-négociables)

### Préservation Assets (RÈGLE D'OR)

**OBLIGATOIRE** : Asset Count APRÈS ≥ Asset Count AVANT

✅ **À conserver** :
- **Tous les liens internes** (exact URLs **ET** exact anchor text de l'original — ne JAMAIS modifier un texte d'ancre existant, ne JAMAIS injecter un lien interne qui n'existait pas dans l'article original)
- **Placement des liens** : conserver chaque lien existant à une position naturelle dans le corps du texte, distribués avec 150-200 mots d'espacement
- **Toutes les images** avec `<figure>` + `<figcaption>` si l'original contient une légende. Reproduire la légende exacte de l'original dans `<figcaption>`.
- **Tous les tableaux** (structure + données actualisées)
- **Toutes les vidéos** (embeds YouTube/Vimeo)
- **0 ou 1 lien Superprof** selon pertinence
- **Callouts existants** ("Bon réflexe", disclaimers)

❌ **Interdit** :
- Supprimer une image "car elle alourdit"
- Retirer un tableau "pour simplifier"
- Enlever un lien interne "car pas pertinent"
- Réduire le nombre d'assets
- **Injecter des liens internes nouveaux** (seuls les liens présents dans l'article original sont autorisés)
- **Omettre les légendes d'images** (si l'original a une légende, le refresh DOIT la reproduire dans `<figcaption>`)

### Format Rédactionnel (CRITIQUE)

**ÉVITER** : Style annuaire avec listes à puces excessives

✅ **Rédaction narrative privilégiée** :
- Paragraphes développés (éviter les 1-2 phrases isolées)
- Explications détaillées et contextualisées
- Transitions naturelles entre sections
- Style éditorial et engageant

❌ **Pas de sections en bullet points uniquement**

### Exemple FORMAT INTERDIT vs ATTENDU

**❌ MAUVAIS (à éviter)** :
```
## Bénéfices du squat
- Renforce jambes
- Améliore équilibre
- Brûle calories
- Développe force
- Augmente masse musculaire
- Protège articulations
- Stimule métabolisme
- Améliore posture
[... 15 bullet points]
```

**✅ BON (format narratif attendu)** :
```
## Bénéfices du squat sur la santé et la performance

Le squat est bien plus qu'un simple exercice de jambes. Il sollicite
simultanément plusieurs groupes musculaires majeurs (quadriceps, fessiers,
ischio-jambiers), ce qui en fait un mouvement particulièrement efficace
pour développer la force globale du bas du corps.

Au-delà du développement musculaire, le squat améliore significativement
l'équilibre et la proprioception. Cette amélioration de la stabilité se
transfère directement aux activités quotidiennes comme monter des escaliers
ou porter des charges lourdes.

Sur le plan métabolique, le squat est un exercice extrêmement énergivore.
La sollicitation de larges masses musculaires stimule le métabolisme et
favorise la dépense calorique, même plusieurs heures après l'entraînement
(effet afterburn).
```

---

## Objectifs Refresh

### 1. Amélioration Contenu

**Enrichir** :
- Statistiques récentes (2025-2026)
- Citations d'experts avec sources
- Études scientifiques peer-reviewed
- Exemples concrets et cas pratiques
- Contexte actionnable

**Supprimer** :
- Généralités vagues ("il est important de...")
- Données obsolètes (> 2 ans)
- Répétitions inutiles
- Formulations creuses

### 2. Structure Optimisée

**Format attendu** :
- **Introduction AVANT le premier H2** (1 paragraphe `<p>`, 80-150 mots) : accroche concrète (chiffre, question, constat terrain) + mot-clé principal en `<strong>` + promesse de l'article. Ce paragraphe est le PREMIER élément HTML généré, il précède tout `<h2>`. **Réécrire l'accroche à partir de zéro** : ne PAS paraphraser l'introduction de l'original (même angle, même scène, même anecdote reformulée). Changer d'angle d'entrée. Si l'intro générée pourrait s'obtenir en passant l'intro originale dans un reformulateur, elle est à refaire.
- **Tableau récapitulatif après l'introduction** : immédiatement après le paragraphe d'introduction, insérer un `<table>` synthétique (3-5 lignes) résumant les points clés de l'article. En-tête `<thead>` avec fond coloré (`background-color: #1565c0; color: white`), lignes alternées (`background-color: #f5f5f5`). Ce tableau donne une vue d'ensemble avant la lecture détaillée.
- **CTA Superprof (si présent)** : le bloc CTA vert (`background-color: #4caf50`) se place à la **fin de la première section H2**, jamais en fin d'article ni dans l'introduction.
- Minimum 3 sections H2 thématiques
- Paragraphes développés (éviter les 1-2 phrases isolées)
- Transitions fluides entre sections
- Conclusion actionnable

**Éviter** :
- Sections isolées sans contexte
- Énumérations exhaustives
- Bullet points excessifs
- Sauts de logique

### 3. E-E-A-T Renforcé

**Experience** :
- Storytelling concret
- Détails pratiques
- Observations terrain

**Expertise** :
- Vocabulaire spécialisé approprié
- Précision technique
- Nuances importantes

**Authoritativeness** :
- Sources académiques/officielles
- Citations d'experts reconnus
- Données chiffrées récentes

**Trustworthiness** :
- Disclaimers transparents (si YMYL)
- Méthodologie expliquée
- Limitations évoquées honnêtement

### 4. SEO & GEO 2026

**Optimisations** :
- Réponse directe aux PAA (People Also Ask)
- Featured snippet optimization (40-60 premiers mots)
- **Couverture sémantique mesurée** : couvrir les termes pertinents du sujet, mais viser la zone TOP 3 (~60-75% SOSEO), PAS le maximum. Un SOSEO > 80% est synonyme de suroptimisation.
- Multimodal content (images, tableaux, vidéos)
- Structured data hints (tableaux bien formatés)

**Équilibre couverture / suroptimisation** (voir STYLE_GUIDE.md section 11) :
- Privilégier la LARGEUR du vocabulaire (beaucoup de termes différents) plutôt que la répétition des mêmes termes
- Mot-clé principal (exact match) : **3-6 occurrences** dans l'article (H1 + intro + 1-2 H2 + conclusion)
- Termes importants du sujet : **2-5 occurrences** chacun, distribués uniformément
- Termes secondaires : **1-3 occurrences** chacun
- Jamais 3+ termes techniques/sémantiques dans la même phrase
- Distribuer le vocabulaire uniformément dans toutes les sections
- **Synonymes obligatoires** : pour chaque terme répété 3+ fois, utiliser au moins 1 synonyme ou périphrase en alternance (ex : "musculation" → "renforcement", "travail en salle" ; "coach" → "entraîneur", "préparateur")

---

## Processus Détaillé

### Étape 1 : Analyse Article Existant

1. **Identifier assets à préserver** :
   - Compter images, tableaux, vidéos, liens
   - Noter URLs exactes des liens internes
   - Repérer callouts et encadrés

2. **Analyser structure actuelle** :
   - H2/H3 existants
   - Progression logique
   - Forces et faiblesses

3. **Évaluer contenu** :
   - Sections obsolètes à actualiser
   - Données à mettre à jour
   - Lacunes à combler

### Étape 2 : Réécriture Section par Section

Pour chaque H2 :
1. **Conserver l'asset associé** (image/tableau si présent)
2. **Réécrire en paragraphes narratifs** (pas en liste)
3. **Enrichir avec sources récentes** (études 2024-2026)
4. **Ajouter contexte actionnable** (conseils pratiques)
5. **Intégrer transitions** vers section suivante

### Étape 3 : Vérification Finale

**Checklist obligatoire** :
- [ ] Asset count APRÈS ≥ Asset count AVANT
- [ ] Sources E-E-A-T présentes (si YMYL)
- [ ] Callouts pertinents ajoutés (1-3 selon sujet)
- [ ] Liens internes maintenus
- [ ] Ton cohérent avec site_id
- [ ] Disclaimers présents (si sport/santé)

---

## Exemples Transformation Complète

### Section AVANT (à éviter)

```markdown
## Muscles sollicités

Le squat sollicite :
- Quadriceps
- Fessiers
- Ischio-jambiers
- Mollets
- Abdominaux
- Érecteurs du rachis
- Adducteurs
```

### Section APRÈS (format attendu)

```markdown
## Muscles sollicités pendant le squat

Le squat est un exercice polyarticulaire qui recrute simultanément plusieurs
groupes musculaires majeurs. Les quadriceps, situés à l'avant des cuisses,
assurent l'extension du genou et sont particulièrement sollicités lors de la
phase de remontée. Les fessiers (grand, moyen et petit glutéal) interviennent
pour l'extension de la hanche, surtout en fin de mouvement.

Les ischio-jambiers, à l'arrière des cuisses, jouent un rôle stabilisateur
important en contrôlant la descente et en protégeant l'articulation du genou.
Les adducteurs (muscles internes des cuisses) contribuent à maintenir la
stabilité latérale durant tout le mouvement.

Au-delà des jambes, le squat engage fortement la ceinture abdominale et les
érecteurs du rachis (muscles profonds du dos). Cette activation du tronc est
essentielle pour maintenir une colonne vertébrale en position neutre et prévenir
les blessures.
```

---

## Résultat Attendu

Un article :
- **Narratif et fluide** (pas un catalogue)
- **Riche en contenu actionnable** (pas vague)
- **Sourcé et crédible** (E-E-A-T fort)
- **Préservant tous les assets** (règle d'or)
- **Optimisé SEO/GEO 2026** (PAA, featured snippets)
- **Adapté au ton du blog** (persona cohérent)

---

## Mise à Jour des Statistiques

**Années dans les titres** : mettre à jour ("Guide 2024" → "Guide 2026").
**Ne pas modifier** : URLs (`/guide-2024/`), citations académiques ("Smith, 2023"), comparaisons historiques ("entre 2020 et 2024").

**Si données 2026 disponibles** :
```html
<p>En 2026, le taux de réussite atteint 92,3% selon
<a href="...">le Ministère de l'Éducation</a>.</p>
```

**Si données 2026 indisponibles** :
```html
<p>En 2025, le taux atteignait 91,5% (dernières données disponibles).</p>
```

---

## Correction Duplication (contenu dupliqué)

Si un paragraphe est identique à un passage d'un autre article du site, trois options :

1. **Différenciation par angle** : réécrire en changeant l'angle selon le contexte propre à l'article
2. **Résumé contextuel** : résumer en 1-2 phrases + lien vers l'article source
3. **Suppression avec lien** : si le paragraphe n'apporte rien de supplémentaire au contexte actuel

**Contrainte** : préserver le sens, respecter le ton, maintenir la longueur (±20%). Ne jamais modifier les liens ou images associés.

---

*Stratégie FULL_REFRESH - v2.0 - Février 2026*
