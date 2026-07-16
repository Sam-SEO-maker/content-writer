# CLAUDE.md — Guide d'orientation (Content Writer)

**Refresh SEO multi-tenant.** Ce fichier est un **index d'orientation**, pas un manuel :
il dit *qui tu es*, *quels tenants existent*, *quelle est la chaîne*, et *quelle skill /
commande invoquer*. Le « comment rédiger » vit dans les skills (`.claude/skills/` transverses +
`tenants/{id}/.claude/skills/` par tenant), chargées à la demande.

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
├── .claude/skills/        skills de rédaction scopées au tenant (discovery native)
├── prompts/
│   ├── site.md            ton, blacklist, format WP (source maîtresse chargée)
│   ├── vs_concurrent.md   override articles « versus » (enseigna)
│   ├── reference.md       exemple HTML à imiter (superprof-ressources)
│   └── blocks/ | guides/  annexes chargées à la demande
├── config/tenant.json     generation_skill/qc_skill, language, auth_mode, ytg…
├── linking_maps/          cartes de maillage
└── outputs/               html/ csv/ acf/ metadata/ audit/ …
```

> Les fichiers `prompts/` varient selon le tenant : seul `site.md` est garanti.

- **Catalogue ≠ registre** (distinction clé) :
  - **Catalogue** `_shared/config/superprof_blogs_catalog.json` (6 ressources + 90 blogs) =
    le *menu* des marchés onboardables, généré depuis GSC via `build_superprof_catalog.py`.
  - **Registre** `_shared/config/sites.json` = seuls les tenants **réellement matérialisés**
    (2 aujourd'hui), seul lu au runtime. **Gitignoré** (local/généré) ; versionné =
    `sites.example.json` + catalogue + sync Notion. Alimenté par `notion sync-sites`
    (Notion « config pays » → sites.json, unidirectionnel ; le moteur ne lit jamais Notion au runtime).
- **Résolution des chemins** : `_shared/core/tenant_paths.py` (point unique). `tenants/` ne
  contient QUE les tenants travaillés, il grossit à la demande — jamais 90 dossiers.
- **Onboarder un tenant** : `cw tenant init <id>` (l'id doit exister au catalogue) crée le
  squelette `tenants/{id}/` pré-rempli + l'entrée `sites.json` (merge additif). L'éditorial
  (`site.md`, skill de génération) reste à écrire. `cw tenant list [--type]` liste le catalogue.
- **Nommage** : Superprof pays = `lang-country-type` (`es-es-ressources`, `en-uk-ressources`) ;
  client autonome = slug de marque (`enseigna`). `superprof-ressources` = dérogation historique.
- **Skills par tenant** : les skills de rédaction propres à un tenant vivent sous
  `tenants/{id}/.claude/skills/` (discovery scopée native, **déjà en place**) ;
  `edito-refresh`, `format-wordpress`, `recherche-sources` sont transverses à la racine.
  Le mapping tenant→skill n'est **pas hardcodé** : le subagent lit `generation_skill` /
  `qc_skill` dans `tenant.json`.

**Règle d'override** : `Site > Strategy`. Composition du prompt (`PromptComposer`) =
**stratégie (`_shared/strategies/`) + site.md** (+ `vs_concurrent.md` pour les articles versus) ;
les autres niveaux (base, catégorie, template) sont inactifs.

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
| `/audit serp <url>` | Audit SERP ciblé (PAA, secondary keywords) |
| `/decide --blog <id>` | Moteur de décision data-driven (Sheet) |
| `/market-status --site <id>` | État des lieux SEO GSC d'un tenant (→ Sheet) |
| `/blog --market <id>` | Perfs SEO d'un blog via MCP GSC : totaux + top KW (résumé chat) |
| `/page <url>` | Perfs SEO d'une URL précise via MCP GSC (tenant déduit de l'URL) |

CLI réel (les commandes wrappent) : `python3 content_writer.py <groupe> <cmd>`.
Liste des groupes/commandes à jour : `python3 content_writer.py --help` (et
`… <groupe> --help`), auto-générée par Click — source de vérité.

## Index — Skills (`.claude/skills/`)

| Skill | Portée | Quand l'invoquer |
|---|---|---|
| `refresh` (orchestrateur) | racine | séquence audit → génération → QC → maillage (via `/refresh`) |
| `edito-refresh` | racine (transverse) | règles SEO/GEO/E-E-A-T de ranking, appliquées à chaque article |
| `format-wordpress` | racine (transverse) | règles HTML/WP transverses (accents, tiret, ancres, listes) |
| `recherche-sources <sujet\|url>` | racine (transverse) | documenter un sujet avec des sources vérifiées (brief E-E-A-T) |
| `generate-enseigna-avis` | `tenants/enseigna/` | rédiger un article avis Enseigna (ACF JSON, verdict en fin) |
| `sp-ressources-gutenberg` | `tenants/superprof-ressources/` | rédiger un article Superprof Ressources (Gutenberg maison, 5 blocs) |
| `qc-sp-ressources` | `tenants/superprof-ressources/` | checklist QC post-génération Superprof Ressources |

> Les skills métier sont **scopées par tenant** (`tenants/{id}/.claude/skills/`) et
> résolues via `generation_skill`/`qc_skill` de la config. Transverses à la racine :
> `edito-refresh`, `format-wordpress`, `recherche-sources` (+ l'orchestrateur `refresh`).

**Subagent** : `content-generator` (`.claude/agents/`) exécute la génération sous abonnement Max,
lit `generation_prompt.txt`, écrit les fichiers, ne renvoie pas de HTML dans le chat.

## Où trouver le « comment »

- **Rédaction / format / interdits** → skill `format-wordpress`.
- **SEO / GEO / E-E-A-T** (ranking, transverse) → skill `edito-refresh`
  (`SKILL.md` + `references/{geo-strategies,eeat-framework,semantic-density}.md`).
- **Formats & métadonnées, template refresh** → skill `format-wordpress`,
  `_shared/prompts/refresh_article.md`.
- **Règles site-spécifiques** → `tenants/{id}/prompts/site.md`.
- **Stratégies de rédaction** → `_shared/strategies/` (full_refresh, semantic_reorientation,
  format_adaptation, title_optimization ; dispatch via `_shared/config/prompts_dispatch.json`).
  Ne portent que le *delta* de la stratégie ; les règles éditoriales transverses vivent
  dans la skill `edito-refresh`.

## 3 Piliers

1. **Préservation** : jamais réduire les assets (Règle d'Or).
2. **Data-driven** : décisions GSC + DataForSEO, pas d'intuition.
3. **Multi-tenant** : respecter l'identité éditoriale de chaque tenant, registre plat.
