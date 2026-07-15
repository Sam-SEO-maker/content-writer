# Triage des tests en échec (état 2026-07-15)

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

## Reste : 64 échecs d'assertion (API drift) — classés

Ces échecs viennent de refactors **volontaires** (Phase 2→5) : les tests encodent
l'ancien contrat. À traiter au cas par cas, car certains **révèlent un vrai bug**
(à NE PAS green-washer).

| Fichier | N | Nature | Action recommandée |
|---|---|---|---|
| `test_html_analyzer` | 18 | dict → dataclass `HTMLAnalysisResult` (`result["h1"]`→attributs) | Réécrire les assertions en accès attribut (mapping title/headings/…). Mécanique mais par-assertion. |
| `test_decision_engine` | 13 | stratégies réduites (Phase 2 : plus de `TITLE_OPTIMIZATION`…) | Mettre à jour les attentes vers les 2 stratégies actuelles. **Vérifier l'intention produit** (low-CTR → NO_ACTION est-il voulu ?). |
| `test_asset_manager` | 10 | modèle redesigné (`has_blacklisted`/`missing_images`/`superprof_error` → `blacklist_violations`/`*_valid`) | Réécrire vers les champs actuels (mapping sémantique, pas 1:1). |
| `test_year_updater` | 6 | logique d'exclusion citations académiques changée + `YEARS_TO_REPLACE` statique | Rendre year-relatif ; **NB `YEARS_TO_REPLACE=[2024,2025]` est HARDCODÉ dans la source** → vrai risque (2027 manquera 2026). |
| `test_ghostwriter` | 5 | signatures `_build_generation_prompt` / rewrite_context enrichis | Compléter les fixtures aux champs requis actuels. |
| `test_output_manager` | 4 | `output_dir.name == "enseigna"` mais code écrit sous le domaine | ⚠️ **VRAI BUG** (mémoire `project_output_dir_domain_vs_id_inconsistency`). Le test est CORRECT — corriger le CODE, pas le test. |
| `test_content_extractor` | 3 | sortie d'extraction changée | Vérifier le contrat actuel avant d'ajuster. |
| `test_editorial_auditor` | 2 | FactChecker : détection date-mismatch topic/année | Vérifier l'intention (2025 dans topic 2026 doit-il alerter ?). |
| `test_scheduler` | 1 | `size()` = 2 au lieu de 1 (état partagé ?) | Investiguer fuite d'état. |
| `test_parent_h2_whitelist` | 1 | `Ghostwriter.validate_parent_h2_structure` supprimé/renommé | Retrouver le remplaçant ou retirer le test. |
| `test_gutenberg_formatter` | 1 | sortie nbsp : `\xa0` (char) au lieu de `&nbsp;` (entité) | Aligner l'assertion sur la sortie actuelle. |

## Garde-fous

- **`test_output_manager`** et **`test_year_updater` (source hardcodée)** pointent
  de VRAIS problèmes : ne pas modifier ces tests pour les faire passer sans
  corriger d'abord le code (ce serait masquer la régression que le vert doit
  révéler). Traiter le code dans un lot dédié.
- Les autres sont de la dette de test pure (contrat obsolète), sûrs à réécrire
  vers l'API actuelle une fois celle-ci vérifiée fichier par fichier.
