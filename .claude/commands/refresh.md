---
description: Refresh SEO complet d'une URL (fetch WP REST/scrape → GSC/SERP/PAA/intent → décision → recherche sources → génération via subagent).
argument-hint: <url> --blog <enseigna|superprof-ressources> [--strategy X] [--keyword K]
allowed-tools: Bash(python3 content_writer.py refresh:*), Bash(python3 content_writer.py finalize:*), Task, Read, Write, WebSearch, WebFetch, Skill
---

Lance le refresh de l'URL fournie en séquençant la chaîne du workflow :
récupération contenu → GSC → SERP/PAA → user intent → décision →
**recherche sources** → génération → (QC YTG / maillage en Phase 3bis).

## Étape 1 — Récupération + audit + décision déterministes (CLI `cw`)

Exécute :

```bash
python3 content_writer.py refresh $ARGUMENTS
```

⚠️ **Cette commande couvre déjà les étapes 1 à 6 du workflow** (via `_fetch_html`
+ `AuditEngine.full_audit` + `process_url`) ; ne PAS les refaire à la main :

- **Récupération du `post_content`** en 2 stratégies automatiques (`_fetch_html`) :
  1. **WordPress REST API** (`WordPressAPIClient`, si `wp_api_config` présent pour
     le blog),
  2. **Fallback scraping** page publique (`ContentExtractor`) quand la REST est
     bloquée.
- **Perfs SEO GSC** (clics/impressions/CTR/position, `GSCAnalyzer`, fallback
  mot-clé 12 mois),
- **Résolution du mot-clé principal** (GSC → multi-source `KeywordResolver`),
- **Analyse SERP** : PAA, features, TOP concurrents (`SERPAnalyzer`),
- **User intent** + format dominant (`IntentDetector`),
- **Décision stratégie** (moteur data-driven) + **composition du prompt**.

Sortie dans le `context_dir` affiché :

- `generation_prompt.txt` (prompt composé : stratégie + site, signaux
  GSC/SERP/PAA/intent déjà intégrés),
- chemins `Output HTML` / `Output JSON`, `Strategy`, `Assets avant`.

Si l'action est `NO_ACTION`, `BLOCKED_QUALITY_ISSUES`, `ERROR` ou
`REDIRECT_301_SUGGESTED` : **s'arrêter** et rapporter, rien à générer.

## Étape 2 — Recherche de sources (brief E-E-A-T) — la brique manquante

`cw refresh` ne va **pas** chercher de sources : sans cette étape, `eeat_sources`
serait inventé par le LLM. Avant de générer, invoquer la skill **recherche-sources**
sur le sujet/URL (cascade : bibliothèque curée par matière si dispo → complément
web `WebSearch`/`WebFetch` / `deep-research`). Produire un brief structuré
(source → claim → url → année), sans jamais fabriquer de chiffre.

> Tant que `tenants/{tenant}/sources/` n'existe pas (Phase 4), la skill opère en
> mode web seul.

## Étape 3 — Génération (subagent `content-generator`)

Déléguer la rédaction au subagent **content-generator** (abonnement Max, jamais
l'API payante) via l'outil Task. Lui transmettre :

- le chemin `generation_prompt.txt` (contient déjà PAA, intent, SERP, mot-clé),
- **le brief de sources vérifiées de l'étape 2** (à injecter dans le contenu et
  dans `eeat_sources`, pas d'invention),
- le `blog_id` (pour charger la bonne skill de rédaction),
- les chemins `Output HTML` / `Output JSON`,
- la `Strategy` et les `Assets avant` (Règle d'Or : assets après ≥ avant).

Le subagent écrit directement le HTML brut + métadonnées dans les fichiers de
sortie ; il **ne renvoie pas** de HTML dans le chat. Note le chemin du HTML brut
écrit (`Output HTML`), il est requis à l'étape 4.

## Étape 4 — Finalisation déterministe (`cw finalize`)

Une fois le HTML brut écrit, chaîner save → assets → QC YTG → maillage :

```bash
python3 content_writer.py finalize <url> --blog <id> --html-file <Output HTML>
```

Cette commande (déterministe) :

- **sauvegarde** le HTML nu + `.gutenberg.html` + CSV des tableaux,
- **valide les assets** (Règle d'Or ; restaure les manquants),
- lance le **QC sémantique YTG** → verdict :
  - `OPTIMAL` → poursuit le maillage,
  - `A_CORRIGER` → renvoie les termes sous/sur-optimisés : **relancer le subagent
    content-generator** pour recorriger le HTML (boucle, cap 2-3 itérations), puis
    relancer `finalize`,
  - `BLOQUE` → **arrêt + alerte humaine** (sur-optimisation grave, pas de maillage,
    pas de re-génération auto),
- applique le **maillage** (`EnseignaAvisLinker` pour enseigna ; pour superprof les
  liens de landing sont injectés en amont par `SuperprofRotator`). Ajouter
  `--apply-linking` pour écrire les liens (sinon dry-run).

## Étape 5 — Rapport

Rapporter : stratégie appliquée, sources retenues, chemins de sortie
(`_shared/outputs/{tenant}/`), verdict YTG, verdict assets (avant/après), et
liens ajoutés. Objectif : URL → contenu + verdict + liens, sans reprise manuelle.