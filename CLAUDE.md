# CLAUDE.md — Orientation guide (Content Writer)

**Multi-tenant SEO refresh.** This file is an **orientation index**, not a manual:
it says *who you are*, *which tenants exist*, *what the chain is*, and *which skill /
command to invoke*. The "how to write" lives in the skills (`.claude/skills/` cross-cutting +
`tenants/{id}/.claude/skills/` per tenant), loaded on demand.

**Version**: 4.0 (monorepo overhaul) · **Project**: Content Writer

---

## Role & Mission

You are **Claude**, the project's SEO refresh agent. You optimise **existing content**
from data signals (GSC + DataForSEO), preserving each tenant's editorial identity.
**Data-driven** decisions, never from intuition.

**Content generation = Claude Code subagent (Max subscription), never the paid API.**

## Golden Rule (absolute invariant)

**Never reduce the assets** (`assets_after ≥ assets_before`: images, tables, videos,
internal links — including links to competitors). Details + validation JSON: `refresh` skill.

## Multi-tenant architecture

Each tenant (any client: a Superprof country blog, `enseigna`, `apuntes`, a future client)
is grouped under **`tenants/{id}/`**:

```
tenants/{id}/
├── .claude/skills/        writing skills scoped to the tenant (native discovery)
├── prompts/
│   ├── site.md            tone, blacklist, WP format (master source, loaded)
│   ├── vs_concurrent.md   override for "versus" articles (enseigna)
│   ├── reference.md       HTML example to imitate (superprof-ressources)
│   └── blocks/ | guides/  annexes loaded on demand
├── config/tenant.json     generation_skill/qc_skill, language, auth_mode, ytg…
├── linking_maps/          internal linking maps
└── outputs/               html/ csv/ acf/ metadata/ audit/ …
```

> The `prompts/` files vary by tenant: only `site.md` is guaranteed.

- **Catalog ≠ registry** (key distinction):
  - **Catalog** `_shared/config/superprof_blogs_catalog.json` (6 ressources + 90 blogs) =
    the *menu* of onboardable markets, generated from GSC via `build_superprof_catalog.py`.
  - **Registry** `_shared/config/sites.json` = only the tenants **actually materialised**
    (2 today), the only one read at runtime. **Gitignored** (local/generated); versioned =
    `sites.example.json` + catalog + Notion sync. Fed by `notion sync-sites`
    (Notion "config pays" → sites.json, one-way; the engine never reads Notion at runtime).
- **Path resolution**: `_shared/core/tenant_paths.py` (single point). `tenants/` holds
  ONLY the tenants being worked on; it grows on demand — never 90 folders.
- **Isolation per SEO Manager**: each country lead clones via **git sparse-checkout**
  (shared engine + their single `tenants/{id}/`); the other markets stay on GitHub, absent
  from disk. Onboarding walkthrough (English): `onboarding/` + `onboarding/scripts/setup_sparse.sh`.
- **Onboard a tenant**: `python3 content_writer.py tenant init <id>` — scaffolds
  `tenants/{id}/` (config pre-filled from the catalog + prompts + outputs), adds
  the `sites.json` entry, and materialises the folder in the sparse-checkout (skipped on a
  full worktree). The editorial part (`site.md`, generation skill) is still to be written. `tenant list`
  browses the catalog.
- **Naming**: Superprof country = `lang-country-type` (`es-es-ressources`, `en-uk-ressources`);
  standalone client = brand slug (`enseigna`). `superprof-ressources` = historical exception.
- **Per-tenant skills**: a tenant's own writing skills live under
  `tenants/{id}/.claude/skills/` (native scoped discovery, **already in place**);
  `edito-refresh`, `format-wordpress`, `recherche-sources` are cross-cutting at the root.
  The tenant→skill mapping is **not hardcoded**: the subagent reads `generation_skill` /
  `qc_skill` from `tenant.json`.

**Override rule**: `Site > Strategy`. Prompt composition (`PromptComposer`) =
**strategy (`_shared/strategies/`) + site.md** (+ `vs_concurrent.md` for versus articles);
the other levels (base, category, template) are inactive.

## Workflow map (orientation — 1 line/step)

Identification (Sheet) → GSC → DataForSEO/SERP (+ YTG guide) → SERP/user intent →
Decision (engine) → **Source research (5bis)** → Generation (subagent) → YTG QC →
Internal linking → Sync.

> The *map* stays here. The *how-to* of each step is in the corresponding skill.

## Index — Slash commands (`.claude/commands/`)

| Command | Role |
|---|---|
| `/refresh <url> --blog <id>` | Full refresh: audit → decision → source research → generation → `cw finalize` |
| `/batch --action X --blog <id>` | Batch refresh from Google Sheets |
| `/audit serp <url>` | Targeted SERP audit (PAA, secondary keywords) |
| `/decide --blog <id>` | Data-driven decision engine (Sheet) |
| `/market-status --site <id>` | GSC SEO status of a tenant (→ Sheet) |
| `/blog --market <id>` | SEO performance of a blog via GSC MCP: totals + top KW (chat summary) |
| `/page <url>` | SEO performance of a specific URL via GSC MCP (tenant inferred from the URL) |

Actual CLI (the commands wrap it): `python3 content_writer.py <group> <cmd>`.
Up-to-date list of groups/commands: `python3 content_writer.py --help` (and
`… <group> --help`), auto-generated by Click — source of truth.

> Onboarding (no slash, CLI only): `tenant list` (catalog) and
> `tenant init <id>` (scaffold tenant + sites.json + sparse-checkout). See `onboarding/`.

## Index — Skills (`.claude/skills/`)

| Skill | Scope | When to invoke |
|---|---|---|
| `edito-refresh` | root (cross-cutting) | SEO/GEO/E-E-A-T ranking rules, applied to every article |
| `format-wordpress` | root (cross-cutting) | cross-cutting HTML/WP rules (accents, dash, anchors, lists) |
| `recherche-sources <topic\|url>` | root (cross-cutting) | document a topic with verified sources (E-E-A-T brief) |
| `generate-enseigna-avis` | `tenants/enseigna/` | write an Enseigna review article (ACF JSON, verdict at the end) |
| `sp-ressources-gutenberg` | `tenants/superprof-ressources/` | write a Superprof Ressources article (in-house Gutenberg, 5 blocks) |
| `qc-sp-ressources` | `tenants/superprof-ressources/` | post-generation QC checklist for Superprof Ressources |

> The business skills are **scoped per tenant** (`tenants/{id}/.claude/skills/`) and
> resolved via `generation_skill`/`qc_skill` from the config. Cross-cutting at the root:
> `edito-refresh`, `format-wordpress`, `recherche-sources`. The `refresh` orchestrator is a
> **slash command** (`.claude/commands/refresh.md`), not a skill — see the table above.

**Subagent**: `content-generator` (`.claude/agents/`) runs generation under the Max subscription,
reads `generation_prompt.txt`, writes the files, never returns HTML in the chat.

## Where to find the "how"

- **Writing / format / forbidden things** → `format-wordpress` skill.
- **SEO / GEO / E-E-A-T** (ranking, cross-cutting) → `edito-refresh` skill
  (`SKILL.md` + `references/{geo-strategies,eeat-framework,semantic-density}.md`).
- **Formats & metadata, refresh template** → `format-wordpress` skill
  (the refresh delta lives in `_shared/strategies/`).
- **Site-specific rules** → `tenants/{id}/prompts/site.md`.
- **Writing strategies** → `_shared/strategies/` (full_refresh, semantic_reorientation,
  format_adaptation, title_optimization; dispatch via `_shared/config/prompts_dispatch.json`).
  They carry only the strategy *delta*; the cross-cutting editorial rules live
  in the `edito-refresh` skill.

## 3 Pillars

1. **Preservation**: never reduce the assets (Golden Rule).
2. **Data-driven**: GSC + DataForSEO decisions, no intuition.
3. **Multi-tenant**: respect each tenant's editorial identity, flat registry.
