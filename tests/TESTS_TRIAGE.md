# Triage des tests en échec (JOURNAL HISTORIQUE — clos)

> **État final 2026-07-23 : suite VERTE — 250 tests, 0 échec** (`python3 -m pytest -q`,
> `pytest.ini` restreint la collecte à `tests/`). Les 49 échecs listés plus bas ont été
> résolus depuis (réécriture vers l'API actuelle ou suppression avec leur feature) :
> `test_scheduler` et son "vrai doute" de dédup sont partis avec le module scheduler
> (purge single-sheet du 2026-07-23, commit 48de374) ; `test_workflow.py` (harnais manuel
> sur l'onglet retiré URLs_Input, 0 test collecté) supprimé le même jour.
> Ce fichier est conservé comme journal de la remise au vert — état 2026-07-15 ci-dessous.

## (Historique) Triage initial — état 2026-07-15

Contexte : suite historiquement rouge (échecs PRÉEXISTANTS à la refonte Phase 0→6).
Objectif = vert franc **sans masquer de vraie régression**.

## Fait

- **Erreurs de collection : 23 → 0.** Imports renommés corrigés
  (`AssetValidation`→`AssetValidationResult` ; `scripts.cocon`→`scripts.audit.
  cannibalization` + `scripts.linking.similarity_engine`). Fixtures HTMLAnalyzer
  (`domain` requis, `analyze(html, url)`).
- **4 fichiers obsolètes supprimés** (testaient le module `WebScraper` SUPPRIMÉ) :
  `test_web_scraper`, `test_cannibalization`, `test_cannibalization_mocked`,
  `test_post_refresh_validation` (ces 3 derniers = harnesses manuels, 0 assert).

## Progrès (verdi depuis)

- `test_gutenberg_formatter` : **vert** (nbsp entité OU char).
- `test_output_manager` : **vert** (4/4). Le "bug domain-vs-id" était DÉJÀ résolu
  par le monorepo (`get_site_output_dir` mappe domaine→id, vérifié) — c'étaient des
  assertions périmées (`.name` "enseigna"→"outputs", sous-dossier "json"→"metadata").
- `test_html_analyzer` : **11/18 vert** (dict→dataclass + `extract_assets_dict`).
- `year_updater` (source) : **bug corrigé** — `YEARS_TO_REPLACE` statique → fenêtre
  dynamique.

État global : **64 → 49 échecs** (0 erreur de collection).

## Reste : 49 échecs d'assertion — classés

| Fichier | N | Nature | Action |
|---|---|---|---|
| `test_html_analyzer` | 2 | `malformed_html` + classification internal-links selon domaine | Comportement de parsing à tracer (fixture). |
| `test_decision_engine` | 13 | stratégies réduites (Phase 2 : plus de `TITLE_OPTIMIZATION`…) | Mettre à jour vers les 2 stratégies. **Décision produit** : low-CTR → NO_ACTION est-il voulu ? |
| `test_asset_manager` | 10 | modèle redesigné (`has_blacklisted`/`missing_images` → `blacklist_violations`/`*_valid`) | Réécrire vers les champs actuels (mapping sémantique). |
| `test_year_updater` | 7 | logique d'exclusion citations académiques | Vérifier l'intention (préserver années de citations = voulu, cf. E-E-A-T). |
| `test_ghostwriter` | 5 | fixtures `rewrite_context` incomplètes vs signature actuelle | Compléter les fixtures. |
| `test_content_extractor` | 3 | sortie d'extraction changée | Vérifier le contrat actuel. |
| `test_scheduler` | 1 | dedup file : ⚠️ **VRAI DOUTE** — `add_task` dédup contre `_processed`, PAS la file. `size()`=2 pour 2 ajouts identiques non-traités. Bug ou voulu ? | Décision produit sur la sémantique de dédup. |

**Résolus par suppression de features** (décisions produit 2026-07) :
- `test_editorial_auditor` (2) + `test_parent_h2_whitelist` (1) : supprimés — les
  features EditorialAuditor/FactChecker (quality gate bloquant) et le maillage en
  silo (parent-H2 whitelist, cocons) ont été retirées du repo (véracité déléguée à
  `source-research` ; décision de refresh data-driven).

## Garde-fous (VRAIS problèmes — ne PAS green-washer)

- **`test_scheduler`** : la dédup ne couvre pas la file d'attente (seulement le
  déjà-traité). Le faire passer sans décision masquerait une éventuelle régression.
- **`test_parent_h2_whitelist`** : révèle une méthode **documentée mais absente du
  code**. Ne pas supprimer le test sans décider du sort de la feature.
- Les autres = dette de test pure (contrat obsolète), sûrs à réécrire vers l'API
  actuelle après vérification fichier par fichier.
