# Brief de lancement — Refonte orchestrateur (à coller en session fraîche)

## Contexte (état au 2026-07-15)

Repo : `/Users/samuel/Desktop/Claude Code/Content Writer` (git, remote GitHub `origin`).

Branches :
- `main` — stable, à jour, **référence — ne pas coder dessus**.
- `refonte/orchestrateur` — **branche de travail de la refonte** (créée depuis `main` réconcilié, poussée sur `origin`). C'est ici qu'on code.
- `docs/plans-refonte` — déjà fusionnée dans `main`, ignorer.

Deux plans, à la racine, servent de source de vérité :
- `MULTI_MARKET_ORCHESTRATOR_PLAN.md` — plan d'architecture + **séquencement global** (le tableau des phases, section « Séquencement global recommandé »).
- `BRIEF_SIMPLIFICATION_PLAN.md` — détail de l'Étape 0 (nettoyage) et des briefs A→F.

## Règles d'or (non négociables)

1. **Une phase à la fois.** Arrêt + vérification après chacune (chaque phase a son point d'arrêt/vérif dans le tableau). Ne jamais enchaîner « tout d'un coup ».
2. **Phase 0 = PR séparée**, aucun changement de comportement (nettoyage ≠ refonte).
3. **`CLAUDE.md` réécrit UNE seule fois** (phase 5), jamais avant que skills + commandes existent.
4. **Génération de contenu = subagents Claude Code (abonnement Max), jamais l'API payante.**
5. Travailler sur `refonte/orchestrateur`. `main` reste le filet (`git checkout main` = état qui marche).
6. Commit/push seulement sur demande explicite.

## Séquencement des phases

| Phase | Contenu | Point d'arrêt / vérif |
|---|---|---|
| **0. Nettoyage** (PR séparée) | Supprimer/archiver niveaux morts du composer (dossiers fantômes `categories/`, `templates/`, `subjects/`, `prompts/formats/*`) ; archiver les 3 stratégies non utilisées ; ajouter `.claudeignore` (`_shared/context/`, `_shared/outputs/`, `_shared/temp/`, `_local/`, `Images/`, `__pycache__/`, `.venv/`, `_archive/`) ; isoler `_local/`. | Grep ne fouille plus les données générées ; tests toujours verts. |
| **1. Skills** | Skill témoin `qc-sp-ressources` → valider via `/context` → 4 autres skills. Skill refresh `edito-refresh` + `references/{full_refresh,eeat_rewrite,seo_geo_eeat}.md`. | `/qc-sp-ressources` charge à la demande ; QC identique à l'ancien. |
| **2. Réduction stratégies + bug** | `strategy_prompts` → 2 fichiers ; corriger bug fallback `ghostwriter.py:594` ; simplifier `PromptComposer`/`compose()` à 2 niveaux (strategy + site). | Forcer TITLE_OPTIMIZATION → le ghostwriter ne compose plus full_refresh. |
| **3. Slash commands + subagent** | Permissions `.claude/settings.json`, wrappers `.claude/commands/` (→ `cw`), subagent `content-generator` référençant les skills phase 1. | `/refresh` bout en bout sans invite ; génération via subagent. |
| **3bis. Bout-en-bout** | Chaîne complète : subagent lit `generation_prompt.txt` → `save_refreshed_html()` → `YTGQualityCheck.check_html()` → boucle correction (`A_CORRIGER` recorrige / `BLOQUE` stop) → maillage (`SuperprofRotator` / `EnseignaAvisLinker`) ; refondre le tail `process_url`. | `/refresh <url>` : URL → contenu dans `_shared/outputs/{tenant}/` + verdict YTG + liens, sans reprise manuelle. |
| **4. Monorepo `tenants/{tenant}/`** | `git mv` des 4 arbres `{id}` → `tenants/{id}/` ; racines de chemins ; dé-hardcode superprof-only (`superprof_rotator`, `push_to_wp`, `build_superprof_landings`) ; externaliser onglet/colonnes/sheet_id Sheet par tenant ; `auth_mode` service_account\|oauth_user (flow Chrome) ; `sites.json` → index mince ; `CODEOWNERS`. | Refresh enseigna OK depuis `tenants/enseigna/` ; tenant factice non-Superprof chargé sans modif code. |
| **5. `CLAUDE.md` (UNE fois) + consolidation `_shared/docs/`** | Allègement CLAUDE.md → index skills + slash commands. Consolider docs : fusion E-E-A-T sur `EEAT_GUIDE.md` + repointer `doc_cache.py:108` ; supprimer `ADD_COLUMNS_GUIDE.md` ; archiver `YEAR_UPDATE_IMPLEMENTATION.md` ; décider `SITEMAP_DISCOVERY.md` ; vérif fraîcheur `OUTPUT_ARCHITECTURE`/`PARENT_H2_WHITELIST`. | `/context` « Memory files » chute (~150-200 l. vs 668) ; un seul doc E-E-A-T, même nom via CLAUDE.md ET doc_cache.py. |
| **6. Multi-tenant runtime + Notion** | Alias `--market`, `--publish`, GSC via MCP `gsc-remote` ; config pays Notion → sync `sites.json` (unidirectionnel) ; recensement blogs Superprof pays. | `markets.json`/`sites.json` cohérent ; le moteur ne lit pas Notion au run. |

Ordre des dépendances : 0 → 1-2 (sans toucher CLAUDE.md) → 3/3bis → 4 → 5 (seule réécriture CLAUDE.md) → 6.

## Première action en session fraîche

Vérifier qu'on est bien sur `refonte/orchestrateur` (`git branch --show-current`), lire les deux plans, puis attaquer **la phase 0 uniquement** : présenter d'abord le périmètre exact (liste des fichiers/dossiers à supprimer/archiver) AVANT de toucher quoi que ce soit, et faire la phase 0 dans une PR séparée.
