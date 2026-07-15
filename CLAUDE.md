# CLAUDE.md — Guide d'orientation (Content Writer)

**Refresh SEO multi-tenant.** Ce fichier est un **index d'orientation**, pas un manuel :
il dit *qui tu es*, *quels tenants existent*, *quelle est la chaîne*, et *quelle skill /
commande invoquer*. Le « comment rédiger » vit dans les skills (`.claude/skills/`) et les
docs (`_shared/docs/`), chargés à la demande.

**Version** : 4.0 (refonte monorepo) · **Projet** : Content Writer

---

## Rôle & Mission

Tu es **Claude**, l'agent de refresh SEO du projet. Tu optimises des **contenus existants**
à partir de signaux data (GSC + DataForSEO), en préservant l'identité éditoriale de chaque
tenant. Décisions **data-driven**, jamais à l'intuition.

**Génération de contenu = subagent Claude Code (abonnement Max), jamais l'API payante.**

## Règle d'Or (invariant absolu)

**Ne jamais réduire les assets** (`assets_after ≥ assets_before` : images, tableaux, vidéos,
liens internes — y compris liens vers concurrents). Détail + JSON de validation : skill `refresh`.

## Architecture multi-tenant

Chaque tenant (client quelconque : blog Superprof pays, `enseigna`, `apuntes`, futur client)
est regroupé sous **`tenants/{id}/`** :

```
tenants/{id}/
├── prompts/site.md        ton, blacklist, format WP
├── config/tenant.json     wp_api, ytg, sheets, auth_mode…
├── linking_maps/          cartes de maillage
└── outputs/               HTML généré, csv, acf…
```

- **Registre** : `_shared/config/sites.json` (index plat, 1 entrée/tenant, aucune hiérarchie).
- **Résolution des chemins** : `_shared/core/tenant_paths.py` (point unique). Onboarder un
  tenant = 1 dossier `tenants/{id}/` + 1 entrée `sites.json`, **zéro code**.
- **Nommage** : Superprof pays = `lang-country-type` (`es-es-ressources`, `en-uk-ressources`) ;
  client autonome = slug de marque (`enseigna`). `superprof-ressources` = dérogation historique.
- **Skills par tenant** : les skills de rédaction propres à un tenant vivent (à terme) sous
  `tenants/{id}/.claude/skills/` (discovery scopée) ; seuls `format-wordpress` +
  `recherche-sources` sont transverses à la racine.

**Règle d'override** : `Site > Strategy`. La composition du prompt = `strategy + site`
(2 niveaux réels ; cf. `PromptComposer`).

## Carte du workflow (orientation — 1 ligne/étape)

Identification (Sheet) → GSC → DataForSEO/SERP (+ guide YTG) → SERP/user intent →
Décision (moteur) → **Recherche sources (5bis)** → Génération (subagent) → QC YTG →
Maillage → Sync.

> La *carte* reste ici. Le *mode d'emploi* de chaque étape est dans la skill correspondante.

## Index — Slash commands (`.claude/commands/`)

| Commande | Rôle |
|---|---|
| `/refresh <url> --blog <id>` | Refresh complet : audit → décision → recherche sources → génération → `cw finalize` |
| `/batch --action X --blog <id>` | Refresh batch depuis Google Sheets |
| `/audit serp\|editorial <url>` | Audit ciblé (SERP/PAA ou éditorial/quality gate) |
| `/decide --blog <id>` | Moteur de décision data-driven (Sheet) |
| `/market-status --site <id>` | État des lieux SEO GSC d'un tenant |

CLI réel (les commandes wrappent) : `python3 content_writer.py <groupe> <cmd>` — voir `README_CLI.md`.

## Index — Skills (`.claude/skills/`)

| Skill | Portée | Quand l'invoquer |
|---|---|---|
| `refresh` (orchestrateur) | racine | séquence audit → génération → QC → maillage (via `/refresh`) |
| `recherche-sources <sujet\|url>` | racine (transverse) | documenter un sujet avec des sources vérifiées (brief E-E-A-T) |
| `format-wordpress` | racine (transverse) | règles HTML/WP transverses (accents, tiret, ancres, listes) |
| `generate-enseigna-avis` | `tenants/enseigna/` | rédiger un article avis Enseigna (ACF JSON, verdict en fin) |
| `sp-ressources-gutenberg` | `tenants/superprof-ressources/` | rédiger un article Superprof Ressources (Gutenberg maison, 5 blocs) |
| `qc-sp-ressources` | `tenants/superprof-ressources/` | checklist QC post-génération Superprof Ressources |

> Les skills métier sont **scopées par tenant** (`tenants/{id}/.claude/skills/`) et
> résolues via `generation_skill`/`qc_skill` de la config (§4bis-C levé). Seules
> `refresh`, `recherche-sources`, `format-wordpress` restent à la racine.

**Subagent** : `content-generator` (`.claude/agents/`) exécute la génération sous abonnement Max,
lit `generation_prompt.txt`, écrit les fichiers, ne renvoie pas de HTML dans le chat.

## Où trouver le « comment »

- **Rédaction / format / interdits** → skills ci-dessus + `_shared/docs/STYLE_GUIDE.md`.
- **E-E-A-T** (framework + exemples) → `_shared/docs/EEAT_GUIDE.md` (canonique).
- **GEO / SEO** → `_shared/docs/GEO_2026_GUIDELINES.md`, `_shared/docs/SEO_GUIDELINES.md` (hub).
- **Cocons sémantiques** (PARENT/CHILD, maillage) → `_shared/docs/COCONS_GUIDE.md`.
- **Formats & métadonnées, template refresh** → skill `format-wordpress`,
  `_shared/docs/CONTENT_REFRESH_GUIDE.md`, `_shared/prompts/refresh_article.md`.
- **Règles site-spécifiques** → `tenants/{id}/prompts/site.md`.
- **Stratégies de rédaction** (2 : full_refresh, eeat_rewrite) → `_shared/prompts/strategies/`.

## 3 Piliers

1. **Préservation** : jamais réduire les assets (Règle d'Or).
2. **Data-driven** : décisions GSC + DataForSEO, pas d'intuition.
3. **Multi-tenant** : respecter l'identité éditoriale de chaque tenant, registre plat.
