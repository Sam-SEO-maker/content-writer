---
name: recherche-sources
description: >-
  Documente un sujet ou une URL avec des sources vérifiées pour nourrir le brief
  E-E-A-T avant génération. Recherche en cascade : bibliothèque curée par matière
  d'abord, puis complément web (deep-research / WebSearch / WebFetch) qui enrichit
  la bibliothèque. Sources réelles et vérifiées, jamais inventées. Invocable seule
  ou appelée par l'orchestrateur refresh. Lecture + écriture biblio.
disable-model-invocation: false
---

# Recherche de sources — brief E-E-A-T

Constitue un socle de **sources vérifiées** pour un sujet/URL, en amont de la
génération. Objectif : nourrir le E-E-A-T avec des références réelles (académiques,
institutionnelles, données chiffrées récentes), **jamais fabriquées**.

> **Statut : chantier à construire** (plan, étape 5bis). Deux livrables : (a) le
> socle bibliothèque par matière (constitution semi-auto : l'agent propose →
> l'humain valide) ; (b) le câblage recherche + injection au brief. Tant que la
> bibliothèque n'existe pas, la skill fonctionne en mode « web seul » (tier 2-3)
> et amorce la bibliothèque au passage.

## Recherche en cascade (3 tiers)

### Tier 1 — Bibliothèque curée par matière (prioritaire)
Piocher d'abord dans `tenants/{tenant}/sources/{matière}.md` : sources déjà
validées par un humain, réutilisables d'un article à l'autre.

> ⚠️ Le dossier `tenants/{tenant}/` **n'existe pas encore** (créé en Phase 4,
> monorepo). D'ici là, la bibliothèque n'est pas disponible : passer directement
> au tier 2. Ne pas inventer de chemin ni de contenu.

### Tier 2 — Complément web ciblé (lacunes du tier 1)
Pour les lacunes, lancer une recherche documentaire :
- **`deep-research`** (skill) pour un sujet large nécessitant vérification
  multi-source et rapport cité.
- **`WebSearch` / `WebFetch`** pour des vérifications ponctuelles (une stat, une
  date, une source primaire précise).

### Tier 3 — Enrichissement de la bibliothèque
Les sources vérifiées trouvées au tier 2 sont **proposées** pour ajout à
`tenants/{tenant}/sources/{matière}.md` (validation humaine avant intégration
définitive). C'est ce qui fait grossir le tier 1 au fil des articles.

## Critères de qualité d'une source

- **Primaire de préférence** : INSERM, INSEE, ministères, revues à comité de
  lecture, organismes officiels, plutôt que blogs/agrégateurs.
- **Récente** quand la donnée est datée (stats, réglementations).
- **Vérifiable** : URL résolvable, auteur/organisme identifiable.
- **Pertinente** au niveau E-E-A-T du blog (voir la skill du site).

## Sortie : brief de sources

Fournir une liste structurée, prête à injecter dans le brief de génération :

```json
{
  "sujet": "…",
  "sources": [
    {"source": "INSERM", "url": "https://…", "year": 2026, "claim": "donnée précise appuyée"}
  ],
  "lacunes": ["points non couverts, à traiter avec prudence ou sans chiffre"]
}
```

Chaque source est reliée à la **claim** qu'elle appuie, pour que la génération ne
cite pas une source hors de son propos.

## Interdits

- ❌ **Inventer une source ou un chiffre.** Une anecdote/statistique sans source
  vérifiable ne s'écrit pas (cf. Preuves d'Expérience E-E-A-T : ne pas fabriquer
  d'anecdotes chiffrées).
- ❌ « Consulté le [date] » dans les références restituées — [[feedback-no-consulte-le]].
- ❌ Tiret cadratin `—` — [[feedback-no-em-dash]].

## Articulation

- **Invocable seule** : « documente-moi ce sujet » → renvoie le brief de sources.
- **Appelée par l'orchestrateur** `refresh` **avant** la génération (étape
  « Recherche sources » du workflow), en amont des skills de rédaction
  ([[generate-enseigna-avis]], [[sp-ressources-gutenberg]]) qui consomment le brief.

## Dépendances à construire (backlog, ne pas bloquer dessus)

1. Socle bibliothèque `tenants/{tenant}/sources/{matière}.md` (dépend du monorepo,
   Phase 4).
2. Script de constitution semi-auto (agent propose → humain valide).
3. Câblage injection brief → générateur.
