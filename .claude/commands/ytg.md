---
description: QC sémantique YTG d'un article (URL) — crée/résout le guide sur le mot-clé principal et analyse le contenu.
argument-hint: <url> ["<mot-clé principal>"] [--fix] [--json-out]
allowed-tools: Bash(python3 content_writer.py ytg qc:*), Read
---

Lance le **QC sémantique YourTextGuru** sur **un article précis**, désigné par son URL.
Le contenu analysé est le **HTML généré localement** (`*.gutenberg.html`) — c'est un QC
**avant publication WP**, pas un scrape de la page en ligne (le WAF Superprof bloque le live).

`$ARGUMENTS` = **`<url>` obligatoire**, suivi d'un **mot-clé principal optionnel** (entre
guillemets s'il contient des espaces). Le mot-clé pilote la **création/résolution du guide
YTG** : le fournir garantit le bon guide. **Fournis-le dès que tu le connais** — sans lui,
le résolveur retombe souvent sur le slug (titre de l'article ≠ vrai mot-clé SEO → guide faux).

À partir de l'URL, déduis :

1. **`--blog`** depuis le domaine / chemin de l'URL :
   - `superprof.fr/ressources/...` → `superprof-ressources`
   - `enseigna.fr/...` → `enseigna`
   - (autres tenants : voir `_shared/config/sites.json`)
2. **`--slug`** = dernier segment de path, sans extension ni slash final
   (ex: `.../francais-terminale/long-bec-fable.html` → `long-bec-fable`).
3. **`--keyword`** = le mot-clé principal si fourni dans `$ARGUMENTS` (override le résolveur).

Puis exécute :

```bash
python3 content_writer.py ytg qc --blog <blog_id> --slug <slug> [--keyword "<mot-clé>"]
```

Ajoute `--fix` (signaler les A_CORRIGER au correcteur) ou `--json-out`
(rapport `_shared/outputs/{blog}/ytg_qc_report.json`) si présents dans `$ARGUMENTS`.
`--keyword` exige `--slug` (un seul article) — le CLI refuse sinon.

Le moteur résout le mot-clé principal (Notion/Sheet/GSC/slug), résout ou crée le guide YTG,
analyse le HTML → SOSEO/DSEO vs cibles TOP3, et rend un verdict
**OPTIMAL / A_CORRIGER / BLOQUE / SKIP**.

Si aucun `*.gutenberg.html` local ne correspond au slug → le rapporter (rien à analyser :
l'article n'a pas encore été généré localement). Pour le QC de **tous** les articles d'un
blog, utiliser `python3 content_writer.py ytg qc --blog <id>` sans `--slug`.

Rapporter un résumé compact : verdict, SOSEO/DSEO vs cible, et les termes sous/sur-optimisés.
