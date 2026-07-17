"""
Strategy Selector Module

Sélectionne et configure la stratégie de refresh optimale.
"""

import json
from pathlib import Path
from typing import Optional

from _shared.core.models import RefreshStrategy, StrategyConfig


class StrategySelector:
    """
    Sélecteur de stratégie de refresh.

    Combine la décision du moteur avec:
    - Les overrides par blog
    - Les guidelines spécifiques

    Le prompt de site n'est PAS résolu ici : la composition
    strategy + tenants/{id}/prompts/site.md est faite par PromptComposer.
    """

    def __init__(
        self,
        prompts_dispatch_path: Optional[Path] = None,
        blog_config: Optional[dict] = None
    ):
        """
        Initialise le sélecteur.

        Args:
            prompts_dispatch_path: Chemin vers prompts_dispatch.json
            blog_config: Configuration du blog actuel
        """
        self.prompts_dispatch = {}
        self.blog_config = blog_config or {}

        if prompts_dispatch_path and prompts_dispatch_path.exists():
            self._load_prompts_dispatch(prompts_dispatch_path)

    def _load_prompts_dispatch(self, path: Path):
        """Charge la configuration de dispatch des prompts."""
        with open(path, "r", encoding="utf-8") as f:
            self.prompts_dispatch = json.load(f)

    def select_strategy(
        self,
        primary_action: str,
        audit_data: dict,
        decision_result: dict
    ) -> StrategyConfig:
        """
        Sélectionne et configure la stratégie complète.

        Args:
            primary_action: Action principale du DecisionEngine
            audit_data: Données d'audit
            decision_result: Résultat du DecisionEngine

        Returns:
            StrategyConfig complète
        """
        # Mapper l'action vers la stratégie
        try:
            strategy = RefreshStrategy(primary_action)
        except ValueError:
            strategy = RefreshStrategy.NO_ACTION

        # Récupérer le scope de réécriture
        rewrite_scope = decision_result.get("rewrite_scope", "none")

        # Déterminer le prompt de base
        prompt_template = self._get_prompt_template(strategy)

        # Récupérer les overrides du blog
        blog_overrides = self.blog_config.get("prompt_overrides", {})

        # Déterminer si enrichissement E-E-A-T nécessaire
        requires_eeat = strategy in [
            RefreshStrategy.SEMANTIC_REORIENTATION,
            RefreshStrategy.EEAT_REWRITE,
            RefreshStrategy.FULL_REFRESH,
        ]

        # Calculer les tokens estimés
        estimated_tokens = self._estimate_tokens(strategy, audit_data)

        # Récupérer les guidelines
        guidelines = self._get_guidelines(strategy)

        return StrategyConfig(
            strategy=strategy,
            rewrite_scope=rewrite_scope,
            estimated_tokens=estimated_tokens,
            prompt_template=prompt_template,
            subject_prompt=None,
            blog_overrides=blog_overrides,
            preserve_assets=True,  # Toujours préserver
            requires_eeat_enrichment=requires_eeat,
            guidelines=guidelines,
        )

    def _get_prompt_template(self, strategy: RefreshStrategy) -> str:
        """Retourne le chemin du template de prompt pour une stratégie."""
        strategy_prompts = self.prompts_dispatch.get("strategy_prompts", {})

        mapping = {
            RefreshStrategy.TITLE_OPTIMIZATION: "title_optimization",
            RefreshStrategy.PARTIAL_REFRESH: "partial_refresh",
            RefreshStrategy.SEMANTIC_REORIENTATION: "semantic_reorientation",
            RefreshStrategy.FORMAT_ADAPTATION: "format_adaptation",
            RefreshStrategy.FULL_REFRESH: "partial_refresh",  # Utilise le même mais scope différent
            RefreshStrategy.EEAT_REWRITE: "semantic_reorientation",
        }

        key = mapping.get(strategy)
        if key and key in strategy_prompts:
            return strategy_prompts[key].get("file", "")

        return "_shared/strategies/full_refresh.md"  # Fallback

    def _estimate_tokens(self, strategy: RefreshStrategy, audit_data: dict) -> int:
        """Estime le nombre de tokens nécessaires."""
        base_tokens = {
            RefreshStrategy.NO_ACTION: 0,
            RefreshStrategy.TITLE_OPTIMIZATION: 500,
            RefreshStrategy.PARTIAL_REFRESH: 1500,
            RefreshStrategy.FULL_REFRESH: 4000,
            RefreshStrategy.SEMANTIC_REORIENTATION: 4000,
            RefreshStrategy.FORMAT_ADAPTATION: 3000,
            RefreshStrategy.EEAT_REWRITE: 5000,
            RefreshStrategy.REDIRECT_301: 0,
            RefreshStrategy.LONG_TAIL_SPECIALIZATION: 2000,
        }

        tokens = base_tokens.get(strategy, 2000)

        # Ajuster selon la taille du contenu
        word_count = audit_data.get("content", {}).get("word_count", 1500)
        if word_count > 2000:
            tokens = int(tokens * 1.2)
        elif word_count < 1000:
            tokens = int(tokens * 0.8)

        return tokens

    def _get_guidelines(self, strategy: RefreshStrategy) -> list[str]:
        """Retourne les guidelines pour une stratégie."""
        guidelines_map = {
            RefreshStrategy.TITLE_OPTIMIZATION: [
                "Analyser les titres des 3 premiers résultats SERP",
                "Ajouter l'année si pertinent",
                "Utiliser des power words pour améliorer le CTR",
                "Garder sous 60 caractères",
                "Inclure le mot-clé principal",
            ],
            RefreshStrategy.PARTIAL_REFRESH: [
                "Mettre à jour uniquement les données obsolètes",
                "Conserver la structure et le style original",
                "Ajouter des sources récentes (2025-2026)",
                "Actualiser la section FAQ avec les PAA actuels",
                "Vérifier et corriger les liens cassés",
            ],
            RefreshStrategy.FULL_REFRESH: [
                "Réécrire le contenu en préservant les assets",
                "Renforcer les signaux E-E-A-T",
                "Ajouter statistiques sourcées récentes",
                "Inclure au moins une citation d'expert",
                "Optimiser pour GEO 2026",
            ],
            RefreshStrategy.SEMANTIC_REORIENTATION: [
                "Identifier les variantes de mots-clés en progression",
                "Restructurer autour de ces variantes",
                "Renforcer massivement les signaux E-E-A-T",
                "Ajouter section 'Notre expérience'",
                "Citer des sources institutionnelles",
            ],
            RefreshStrategy.FORMAT_ADAPTATION: [
                "Identifier le format dominant sur la SERP",
                "Restructurer sans perdre le contenu de valeur",
                "Adapter les éléments visuels (listes, tableaux)",
                "Conserver tous les assets",
                "Maintenir le maillage interne",
            ],
            RefreshStrategy.EEAT_REWRITE: [
                "Réécriture complète avec focus E-E-A-T maximal",
                "Ajouter bio d'auteur avec credentials",
                "Inclure méthodologie si applicable",
                "Citer 3+ sources institutionnelles",
                "Section 'Notre expérience' obligatoire",
            ],
            RefreshStrategy.LONG_TAIL_SPECIALIZATION: [
                "Identifier une variante longue traîne unique",
                "Recentrer le contenu sur cette variante",
                "Différencier clairement de l'URL concurrente",
                "Ajuster le maillage interne",
                "Mettre à jour le titre et la meta",
            ],
        }

        return guidelines_map.get(strategy, [])

    def compose_prompt_context(
        self,
        strategy_config: StrategyConfig,
        audit_data: dict,
        assets: dict,
        seo_guidelines: str
    ) -> dict:
        """
        Compose le contexte complet pour le prompt de réécriture.

        Args:
            strategy_config: Configuration de la stratégie
            audit_data: Données d'audit
            assets: Assets à préserver
            seo_guidelines: Guidelines SEO (depuis le cache)

        Returns:
            Dictionnaire de contexte pour le LLM
        """
        return {
            "strategy": strategy_config.strategy.value,
            "rewrite_scope": strategy_config.rewrite_scope,
            "guidelines": strategy_config.guidelines,
            "blog_overrides": strategy_config.blog_overrides,
            "requires_eeat": strategy_config.requires_eeat_enrichment,

            "audit": {
                "url": audit_data.get("url", ""),
                "title": audit_data.get("content", {}).get("title", ""),
                "meta_description": audit_data.get("content", {}).get("meta_description", ""),
                "word_count": audit_data.get("content", {}).get("word_count", 0),
                "main_keyword": audit_data.get("performance", {}).get("main_keyword", ""),
                "ctr": audit_data.get("performance", {}).get("ctr_30d", 0),
                "position": audit_data.get("performance", {}).get("avg_position", 0),
                "alerts": audit_data.get("alerts", []),
                "recommendations": audit_data.get("recommendations", []),
            },

            "assets_to_preserve": {
                "images_count": assets.get("counts", {}).get("images", 0),
                "internal_links_count": assets.get("counts", {}).get("internal_links", 0),
                "external_links_count": assets.get("counts", {}).get("external_links", 0),
                "superprof_required": True,
                "images": assets.get("images", []),
                "internal_links": assets.get("internal_links", []),
            },

            "seo_guidelines": seo_guidelines,

            "output_format": {
                "type": "diff" if strategy_config.rewrite_scope == "diff_based" else "full",
                "sections_format": "AVANT / APRÈS / JUSTIFICATION" if strategy_config.rewrite_scope == "diff_based" else "complete",
            }
        }
