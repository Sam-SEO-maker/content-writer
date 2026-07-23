"""
Utils Package

Modules utilitaires réellement consommés, importés en direct par leurs
appelants (pas de ré-export hub) :
- `timing` — OperationTimer/timed (orchestrateur, benchmark runner)
- `year_updater` — YearUpdater (diff engine, asset manager)

(html_utils/text_utils/scoring_utils supprimés le 2026-07-23 : 13 fonctions
exportées, zéro consommateur — doublons jamais câblés des méthodes privées de
html_analyzer/asset_manager.)
"""
