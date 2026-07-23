"""
Prompt Composer Module

Compose le prompt de génération en combinant les niveaux ACTIFS :
- Stratégie (`_shared/strategies/{strategy}.md`) — delta conditionnel du moteur
  de décision (alias : partial_refresh → full_refresh.md) ;
- Site override (`sites/{id}/prompts/site.md`) — règles éditoriales du site ;
- Versus (`sites/{id}/prompts/vs_concurrent.md`, niveau 4bis) — seulement si
  `article_type == "versus"`.

Les niveaux base / catégorie / template de l'ancien composeur 5 niveaux sont
inactifs (stubs conservés comme points d'extension). Les règles SEO/E-E-A-T
transverses vivent dans les skills (edito-refresh, format-wordpress).
"""

from pathlib import Path
from typing import Optional


class PromptComposer:
    """
    Compose le prompt : stratégie + site.md (+ vs_concurrent.md si versus).

    Override rule: Site > Strategy.

    Usage:
        composer = PromptComposer()
        prompt = composer.compose(
            strategy="semantic_reorientation",
            site_id="enseigna.fr",
            article_type="versus",   # optionnel — ajoute vs_concurrent.md
        )
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialise le composer.

        Args:
            project_root: Racine du projet (par défaut: auto-détectée). Les stratégies
                vivent désormais sous `_shared/strategies/` ; les overrides de site sont
                résolus via SitePaths depuis la racine.
        """
        if project_root is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent

        self.project_root = project_root
        self.strategies_path = project_root / "_shared" / "strategies"

    def compose(
        self,
        strategy: str,
        subject: Optional[str] = None,
        site_id: Optional[str] = None,
        content_type: Optional[str] = None,
        article_type: Optional[str] = None
    ) -> str:
        """
        Compose le prompt final (niveaux actifs : stratégie + site + versus).

        Args:
            strategy: Stratégie de refresh (ex: "full_refresh", "semantic_reorientation")
            subject: Sujet optionnel (ex: "education_reviews", "music_lessons")
            site_id: ID du site (ex: "enseigna.fr") pour prompts site-specific
            content_type: Type de contenu optionnel (ex: "review", "guide") pour template
            article_type: sous-type d'article du site (ex. enseigna : "avis" |
                "versus"). "versus" ajoute le prompt vs_concurrent.md (niveau 4bis).
                Distinct de content_type (qui pilote le template, niveau 5).

        Returns:
            Prompt complet prêt à envoyer au LLM
        """
        parts = []

        # Niveau 1: Prompts de base (UNIFORMES - toujours inclus)
        base_prompts = self._load_base_prompts()
        parts.extend(base_prompts)

        # Niveau 2: Prompt de catégorie (NOUVEAU - stats, experts, PAA)
        if subject:
            category_prompt = self._load_category_prompt_with_fallback(subject, site_id)
            if category_prompt:
                parts.append(f"# Catégorie: {subject}\n\n{category_prompt}")

        # Niveau 3: Prompt de stratégie
        strategy_prompt = self._load_strategy_prompt(strategy)
        if strategy_prompt:
            parts.append(f"# Stratégie: {strategy}\n\n{strategy_prompt}")

        # Niveau 4: Site Override (NOUVEAU - blacklist, règles spéciales)
        if site_id:
            site_override = self._load_site_override(site_id)
            if site_override:
                parts.append(f"# Site Override: {site_id}\n\n{site_override}")

            # Niveau 4bis: prompt de sous-type versus (comparatif A vs B).
            # Complète site.md, ne le remplace pas. Déclenché par article_type
            # (distinct de content_type, qui pilote le template niveau 5).
            if article_type == "versus":
                vs_prompt = self._load_vs_concurrent(site_id)
                if vs_prompt:
                    parts.append(f"# Type versus: {site_id}\n\n{vs_prompt}")

        # Niveau 5: Template (NOUVEAU, optionnel)
        if content_type:
            template = self._load_template(content_type)
            if template:
                parts.append(f"# Template: {content_type}\n\n{template}")

        return "\n\n---\n\n".join(parts)

    def _load_base_prompts(self) -> list[str]:
        """
        Charge les prompts de base toujours inclus (Niveau 1).

        Plus aucun prompt de base sur disque : les templates de callouts colorés
        sont interdits (cf. skills). Conservé comme point d'extension.

        Returns:
            Liste vide
        """
        return []

    def _load_strategy_prompt(self, strategy: str) -> Optional[str]:
        """
        Charge le prompt de stratégie (Niveau 3).

        Args:
            strategy: Nom de la stratégie

        Returns:
            Contenu du prompt ou None
        """
        # Alias : stratégies sans fichier .md propre (cf. prompts_dispatch.json,
        # non lu ici — garder les deux synchronisés).
        strategy = {
            "partial_refresh": "full_refresh",
            "eeat_rewrite": "semantic_reorientation",
        }.get(strategy, strategy)
        # Essayer .md d'abord, puis .txt
        return (
            self._load_prompt(self.strategies_path / f"{strategy}.md") or
            self._load_prompt(self.strategies_path / f"{strategy}.txt")
        )

    def _load_category_prompt_with_fallback(
        self,
        subject: str,
        site_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Niveau 2 (catégorie) : plus aucun prompt de catégorie sur disque.

        Les répertoires `categories/` et `subjects/` legacy ont été retirés ; la
        structure/le ton spécifiques vivent désormais dans les skills du site.
        Conservé comme point d'extension (retourne toujours None).
        """
        return None

    def _load_site_override(self, site_id: str) -> Optional[str]:
        """
        Charge le prompt site override depuis sites/{site_id}.md (Niveau 4).

        Args:
            site_id: ID du site (ex: "enseigna.fr", "moments-yoga")

        Returns:
            Contenu du prompt ou None
        """
        # Résolution via le point unique SitePaths (base = racine du projet).
        from _shared.core.site_paths import SitePaths
        return self._load_prompt(SitePaths(base_path=self.project_root).site_prompt(site_id))

    def _load_vs_concurrent(self, site_id: str) -> Optional[str]:
        """Charge le prompt du sous-type versus depuis sites/{id}/prompts/vs_concurrent.md.

        Returns None si le site n'a pas de prompt versus (cas normal pour la
        plupart des sites).
        """
        from _shared.core.site_paths import SitePaths
        return self._load_prompt(SitePaths(base_path=self.project_root).vs_concurrent_prompt(site_id))

    def _load_template(self, content_type: str) -> Optional[str]:
        """
        Niveau 5 (template) : plus aucun template sur disque (répertoire
        `templates/` legacy retiré). Conservé comme point d'extension.
        """
        return None

    def _load_prompt(self, path: Path) -> Optional[str]:
        """Charge un fichier prompt."""
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"Erreur chargement prompt {path}: {e}")
            return None

