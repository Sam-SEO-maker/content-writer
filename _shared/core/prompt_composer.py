"""
Prompt Composer Module

Compose automatiquement les prompts en combinant :
1. Prompt de catégorie (stats, experts, PAA) - selon le subject_category
2. Prompt de stratégie (FULL/DIFF/TITLE) - selon la stratégie
3. Prompt site override (blacklist, règles spéciales) - selon le site_id
4. Template (optionnel) - selon le content_type

Note: Les règles SEO/E-E-A-T de base sont dans CLAUDE.md (accessible à Claude Code).
"""

from pathlib import Path
from typing import Optional


class PromptComposer:
    """
    Compose les prompts en 4 niveaux automatiquement.

    Hiérarchie: Category → Strategy → Site → Template (optionnel)
    Override rule: Site > Strategy > Category

    Les règles SEO/E-E-A-T de base sont désormais dans CLAUDE.md.

    Usage:
        composer = PromptComposer()

        # Composer un prompt complet avec nouvelle structure
        prompt = composer.compose(
            strategy="semantic_reorientation",
            subject="education_reviews",
            site_id="enseigna",
            content_type="review"
        )

        # Lister les sujets disponibles
        subjects = composer.list_available_subjects()
    """

    def __init__(self, prompts_path: Optional[Path] = None):
        """
        Initialise le composer.

        Args:
            prompts_path: Chemin vers _shared/prompts/ (par défaut: auto-détecté)
        """
        if prompts_path is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            prompts_path = project_root / "_shared" / "prompts"

        self.prompts_path = prompts_path
        self.strategies_path = self.prompts_path / "strategies"
        self.subjects_path = self.prompts_path / "subjects"  # Legacy fallback
        self.categories_path = self.prompts_path / "categories"  # NEW
        self.sites_path = self.prompts_path / "sites"  # NEW
        self.templates_path = self.prompts_path / "templates"  # NEW

    def compose(
        self,
        strategy: str,
        subject: Optional[str] = None,
        site_id: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> str:
        """
        Compose le prompt final en combinant les 5 niveaux.

        Args:
            strategy: Stratégie de refresh (ex: "refresh_full", "refresh_diff")
            subject: Sujet optionnel (ex: "education_reviews", "music_lessons")
            site_id: ID du site (ex: "enseigna") pour prompts site-specific
            content_type: Type de contenu optionnel (ex: "review", "guide") pour template

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
            # Complète site.md, ne le remplace pas. Déclenché par content_type.
            if content_type == "versus":
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

        callouts.md est chargé systématiquement car ses templates HTML
        (callouts, CTA, disclaimers) s'appliquent à tous les articles.

        Returns:
            Liste avec le prompt callouts
        """
        callouts = self._load_prompt(self.templates_path / "callouts.md")
        if callouts:
            return [f"# Templates Callouts\n\n{callouts}"]
        return []

    def _load_strategy_prompt(self, strategy: str) -> Optional[str]:
        """
        Charge le prompt de stratégie (Niveau 3).

        Args:
            strategy: Nom de la stratégie

        Returns:
            Contenu du prompt ou None
        """
        # Essayer .md d'abord, puis .txt
        return (
            self._load_prompt(self.strategies_path / f"{strategy}.md") or
            self._load_prompt(self.strategies_path / f"{strategy}.txt")
        )

    def _load_category_prompt(self, subject: str) -> Optional[str]:
        """
        Charge le prompt de catégorie depuis categories/{group}/{subject}.md (Niveau 2).

        Args:
            subject: Nom du subject (ex: "education_reviews", "music_lessons")

        Returns:
            Contenu du prompt ou None
        """
        # Mapping subject → category path
        category_mapping = {
            "education_reviews": "education/education_reviews.md",
            "education_general": "education/education_general.md",
            "math_sciences": "education/math_sciences.md",
            "music_lessons": "music/music_lessons.md",
            "yoga_wellness": "wellness/yoga_wellness.md",
            "sports_coaching": "sports/sports_coaching.md",
        }

        category_path = category_mapping.get(subject)
        if not category_path:
            return None

        full_path = self.categories_path / category_path
        return self._load_prompt(full_path)

    def _load_category_prompt_with_fallback(
        self,
        subject: str,
        site_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Charge le prompt de catégorie avec fallback vers ancienne structure.

        Essaie d'abord la nouvelle structure categories/, puis fallback sur subjects/
        pour rétrocompatibilité pendant la migration.

        Args:
            subject: Nom du subject
            site_id: ID du site (pour fallback legacy)

        Returns:
            Contenu du prompt ou None
        """
        # Essayer nouvelle structure categories/
        new_prompt = self._load_category_prompt(subject)
        if new_prompt:
            return new_prompt

        # Fallback sur ancienne structure subjects/ (legacy)
        return self._load_subject_prompt(subject, site_id)

    def _load_site_override(self, site_id: str) -> Optional[str]:
        """
        Charge le prompt site override depuis sites/{site_id}.md (Niveau 4).

        Args:
            site_id: ID du site (ex: "enseigna", "moments-yoga")

        Returns:
            Contenu du prompt ou None
        """
        # Résolution via le point unique TenantPaths (base = parent de _shared/prompts).
        from _shared.core.tenant_paths import TenantPaths
        base_path = self.prompts_path.parent.parent
        return self._load_prompt(TenantPaths(base_path=base_path).site_prompt(site_id))

    def _load_vs_concurrent(self, site_id: str) -> Optional[str]:
        """Charge le prompt du sous-type versus depuis tenants/{id}/prompts/vs_concurrent.md.

        Returns None si le tenant n'a pas de prompt versus (cas normal pour la
        plupart des tenants).
        """
        from _shared.core.tenant_paths import TenantPaths
        base_path = self.prompts_path.parent.parent
        return self._load_prompt(TenantPaths(base_path=base_path).vs_concurrent_prompt(site_id))

    def _load_template(self, content_type: str) -> Optional[str]:
        """
        Charge le template depuis templates/{content_type}_template.md (Niveau 5).

        Args:
            content_type: Type de contenu (ex: "review", "guide")

        Returns:
            Contenu du template ou None
        """
        return self._load_prompt(self.templates_path / f"{content_type}_template.md")

    def _load_subject_prompt(
        self,
        subject: str,
        site_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Charge le prompt de sujet avec fallback :
        1. Essaie {site_id}_{subject}.txt (ex: enseigna_cours_maths.txt)
        2. Sinon essaie {subject}.txt (ex: cours_maths.txt)
        3. Sinon retourne None

        Args:
            subject: Nom du sujet
            site_id: ID du site pour prompts site-specific

        Returns:
            Contenu du prompt ou None
        """
        # Essayer avec préfixe site (site-specific)
        if site_id:
            site_specific = self.subjects_path / f"{site_id}_{subject}.txt"
            if site_specific.exists():
                return self._load_prompt(site_specific)

        # Fallback sur prompt générique
        generic = self.subjects_path / f"{subject}.txt"
        if generic.exists():
            return self._load_prompt(generic)

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

    def list_available_subjects(self) -> list[str]:
        """
        Liste tous les prompts de sujets disponibles.

        Returns:
            Liste des noms de sujets (sans extension .txt)
        """
        if not self.subjects_path.exists():
            return []

        return [p.stem for p in self.subjects_path.glob("*.txt")]

    def list_available_strategies(self) -> list[str]:
        """
        Liste toutes les stratégies disponibles.

        Returns:
            Liste des noms de stratégies (sans extension .txt)
        """
        if not self.strategies_path.exists():
            return []

        return [p.stem for p in self.strategies_path.glob("*.txt")]
