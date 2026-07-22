# CLAUDE.md — Orientation guide (Content Writer)

**Multi-site SEO refresh.** This file is an **orientation index**, not a manual:
it says *who you are*, *which sites exist*, *what the chain is*, and *which skill /
command to invoke*. The "how to write" lives in the skills (`.claude/skills/` cross-cutting +
`sites/<site-slug>/.claude/skills/` per site), loaded on demand.

**Version**: 4.0 (monorepo overhaul) · **Project**: Content Writer

---

## Role & Mission

You are **Claude**, the project's SEO refresh agent. You optimise **existing content**
from data signals (GSC + DataForSEO), preserving each site's editorial identity.
**Data-driven** decisions, never from intuition.

**Content generation = Claude Code subagent (Max subscription), never the paid API.**

## Golden Rule (absolute invariant)

**Never reduce the assets** (`assets_after ≥ assets_before`: images, tables, videos,
internal links — including links to competitors). Details + validation JSON: `refresh` skill.

## Multi-site architecture

Each site (any client: a Superprof country blog, `enseigna.fr`, a future client)
is grouped under **`sites/<site-slug>/`**:

```
sites/<site-slug>/
├── .claude/skills/        writing skills scoped to the site (native discovery)
├── prompts/
│   ├── site.md            tone, blacklist, WP format (master source, loaded)
│   ├── vs_concurrent.md   override for "versus" articles (enseigna.fr)
│   ├── reference.md       HTML example to imitate (superprof.fr-ressources)
│   └── blocks/ | guides/  annexes loaded on demand
├── config/site.json       generation_skill/qc_skill, language, auth_mode, ytg…
├── linking_maps/          internal linking maps
└── outputs/               html/ csv/ acf/ metadata/ audit/ …
```

> The `prompts/` files vary by site: only `site.md` is guaranteed.

- **Catalog ≠ registry** (key distinction):
  - **Catalog** `_shared/config/superprof_sites_catalog.json` (6 ressources + 90 blogs) =
    the *menu* of onboardable sites, generated from GSC via `build_superprof_catalog.py`.
  - **Registry** `_shared/config/sites.json` = only the sites **actually materialised**
    (2 today), the only one read at runtime. **Gitignored** (local/generated); versioned =
    `sites.example.json` + catalog + Notion sync. Fed by `notion sync-sites`
    (Notion "config pays" → sites.json, one-way; the engine never reads Notion at runtime).
- **Path resolution**: `_shared/core/site_paths.py` (single point). `sites/` holds
  ONLY the sites being worked on; it grows on demand — never 90 folders.
- **Isolation per SEO Manager**: each country lead clones via **git sparse-checkout**
  (shared engine + their single `sites/<site-slug>/`); the other sites stay on GitHub, absent
  from disk. Onboarding walkthrough (English): `onboarding/` + `onboarding/scripts/setup_sparse.sh`.
- **Onboard a site**: `python3 content_writer.py site init <site-slug>` — scaffolds
  `sites/<site-slug>/` (config pre-filled from the catalog + prompts + outputs), adds
  the `sites.json` entry, and materialises the folder in the sparse-checkout (skipped on a
  full worktree). The editorial part (`site.md`, generation skill) is still to be written. `site list`
  browses the catalog.
- **Naming**: the site slug is **the domain as you type it** (`superprof.de`,
  `superprof.mx`, `enseigna.fr`). When one domain hosts two sites (blog + ressources,
  6 markets), the ressources site appends its real URL segment: `superprof.fr-ressources`,
  `superprof.es-apuntes`, `superprof.de-lernplattform`. Legacy slugs (`enseigna`,
  `superprof-ressources`, `es-es-ressources`…) are still accepted on input
  (`canonical_site_slug`, `_shared/core/constants.py`).
- **Per-site skills**: a site's own writing skills live under
  `sites/<site-slug>/.claude/skills/` (native scoped discovery, **already in place**);
  `edito-refresh`, `format-wordpress`, `source-research` are cross-cutting at the root.
  The site→skill mapping is **not hardcoded**: the subagent reads `generation_skill` /
  `qc_skill` from `site.json`.

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
| `/refresh <url> --site <site-slug> --main-keyword ""` | Full refresh: audit → decision → source research → generation → `cw finalize` |
| `/batch --action X --site <site-slug>` | Batch refresh from Google Sheets |
| `/audit serp <url> --main-keyword ""` | Targeted SERP audit (PAA, SERP features, top 10). Always pass `--main-keyword`: without it the keyword is derived from the URL slug, so any typo or shorthand in the slug is queried verbatim and the SERP answers a keyword nobody searches |
| `/plan-check <url> --site <site-slug>` | Validate the editorial outline (`content_plan.md`) against the SEO invariants — heading hierarchy, PAA coverage, proof placement. Deterministic (no generation). Verdict OK / NEEDS_FIX before writing. Scaffold it first with `plan init` (CLI lays the file + injects signals; the agent fills the outline via the `seo-outline` skill) |
| `/decide --site <site-slug>` | Data-driven decision engine (Sheet) |
| `/site-status --site <site-slug>` | GSC SEO status of a site (→ Sheet) |
| `/blog --site <site-slug>` | SEO performance of a blog via GSC MCP: totals + top KW (chat summary) |
| `/page <url>` | SEO performance of a specific URL via GSC MCP (site inferred from the URL) |

Actual CLI (the commands wrap it): `python3 content_writer.py <group> <cmd>`.
Up-to-date list of groups/commands: `python3 content_writer.py --help` (and
`… <group> --help`), auto-generated by Click — source of truth.

> Onboarding (no slash, CLI only): `site list` (catalog) and
> `site init <site-slug>` (scaffold site + sites.json + sparse-checkout). See `onboarding/`.

## Index — Skills (`.claude/skills/`)

| Skill | Scope | When to invoke |
|---|---|---|
| `edito-refresh` | root (cross-cutting) | SEO/GEO/E-E-A-T ranking rules, applied to every article |
| `seo-outline` | root (cross-cutting) | build the SEO/GEO editorial outline (content_plan.md) before writing — /refresh step 2bis |
| `format-wordpress` | root (cross-cutting) | cross-cutting HTML/WP rules (accents, dash, anchors, lists) |
| `source-research <topic\|url>` | root (cross-cutting) | document a topic with verified sources (E-E-A-T brief) |
| `generate-enseigna-avis` | `sites/enseigna.fr/` | write an Enseigna review article (ACF JSON, verdict at the end) |
| `sp-ressources-gutenberg` | `sites/superprof.fr-ressources/` | write a Superprof Ressources article (in-house Gutenberg, 5 blocks) |
| `qc-sp-ressources` | `sites/superprof.fr-ressources/` | post-generation QC checklist for Superprof Ressources |

> The business skills are **scoped per site** (`sites/<site-slug>/.claude/skills/`) and
> resolved via `generation_skill`/`qc_skill` from the config. Cross-cutting at the root:
> `edito-refresh`, `format-wordpress`, `source-research`. The `refresh` orchestrator is a
> **slash command** (`.claude/commands/refresh.md`), not a skill — see the table above.

**Subagent**: `content-generator` (`.claude/agents/`) runs generation under the Max subscription,
reads `generation_prompt.txt`, writes the files, never returns HTML in the chat.

## Where to find the "how"

- **Writing / format / forbidden things** → `format-wordpress` skill.
- **SEO / GEO / E-E-A-T** (ranking, cross-cutting) → `edito-refresh` skill
  (`SKILL.md` + `references/{geo-strategies,eeat-framework,semantic-density}.md`).
- **Building the outline before writing** (PAA→sections, proof placement, heading
  hierarchy invariants) → `seo-outline` skill (`/refresh` step 2bis → `content_plan.md`).
- **Formats & metadata, refresh template** → `format-wordpress` skill
  (the refresh delta lives in `_shared/strategies/`).
- **Site-specific rules** → `sites/<site-slug>/prompts/site.md`.
- **Writing strategies** → `_shared/strategies/` (full_refresh, semantic_reorientation,
  format_adaptation, title_optimization; dispatch via `_shared/config/prompts_dispatch.json`).
  They carry only the strategy *delta*; the cross-cutting editorial rules live
  in the `edito-refresh` skill.

## 3 Pillars

1. **Preservation**: never reduce the assets (Golden Rule).
2. **Data-driven**: GSC + DataForSEO decisions, no intuition.
3. **Multi-site**: respect each site's editorial identity, flat registry.
