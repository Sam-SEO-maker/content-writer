# Refresh générique (fallback)

Prompt de repli utilisé quand aucune stratégie spécifique ne s'applique
(`strategy_selector` → fallback).

## Scope
Refresh complet et générique de l'article : actualiser le contenu, la structure et
l'E-E-A-T, adapter le format au dominant de la SERP, préserver tous les assets.

## Règles (toutes héritées des skills : ne rien redéfinir ici)
- **Fond** (E-E-A-T, sources, densité, réponse directe, FAQ, fraîcheur, SEO/GEO) →
  skill `edito-refresh`.
- **Forme** (préservation des assets / Règle d'Or, HTML clean, listes, tableaux,
  métadonnées, callouts colorés interdits) → skill `format-wordpress`.
- **Structure d'ensemble et ton** → skill du tenant.

En pratique, ce fallback équivaut à `full_refresh` sans le delta propre
(anti-paraphrase de l'intro, correction des duplications).
