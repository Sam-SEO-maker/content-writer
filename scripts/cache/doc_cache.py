"""
Document Cache Module

Cache singleton pour la documentation SEO et les prompts.
Évite de recharger les fichiers à chaque requête.
"""

import json
from pathlib import Path
from threading import Lock
from typing import Optional


class DocumentCache:
    """
    Cache singleton pour les documents.

    Charge une seule fois:
    - CLAUDE.md (orientation)
    - Prompts templates
    - Configurations de blogs

    Thread-safe via Lock.
    """

    _instance: Optional["DocumentCache"] = None
    _lock = Lock()

    def __new__(cls, base_path: Optional[Path] = None):
        """Implémentation du pattern Singleton."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialise le cache.

        Args:
            base_path: Chemin racine du projet
        """
        if self._initialized:
            return

        self.base_path = base_path or Path(__file__).parent.parent.parent
        self._cache: dict[str, str] = {}
        self._blog_configs: dict[str, dict] = {}
        self._prompts_dispatch: dict = {}
        self._decision_rules: dict = {}

        self._load_all()
        self._initialized = True

    def _load_all(self):
        """Charge tous les documents en cache."""
        self._load_claude_guide()
        self._load_blog_configs()
        self._load_prompts_dispatch()
        self._load_decision_rules()

    def _load_file(self, relative_path: str) -> str:
        """Charge un fichier texte."""
        full_path = self.base_path / relative_path
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Fichier non trouvé: {full_path}")
            return ""
        except Exception as e:
            print(f"Erreur lecture {full_path}: {e}")
            return ""

    def _load_json(self, relative_path: str) -> dict:
        """Charge un fichier JSON."""
        full_path = self.base_path / relative_path
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Fichier non trouvé: {full_path}")
            return {}
        except Exception as e:
            print(f"Erreur lecture {full_path}: {e}")
            return {}

    def _load_claude_guide(self):
        """Charge CLAUDE.md - Guide opérationnel complet."""
        self._cache["claude_guide"] = self._load_file("CLAUDE.md")

    def _load_blog_configs(self):
        """Charge toutes les configurations de blogs."""
        from _shared.core.tenant_paths import TenantPaths
        for blog_id, config_file in TenantPaths(base_path=self.base_path).blog_config_files():
            self._blog_configs[blog_id] = self._load_json(
                str(config_file.relative_to(self.base_path))
            )

    def _load_prompts_dispatch(self):
        """Charge la configuration de dispatch des prompts."""
        self._prompts_dispatch = self._load_json("_shared/config/prompts_dispatch.json")

    def _load_decision_rules(self):
        """Charge les règles de décision."""
        self._decision_rules = self._load_json("_shared/config/decision_rules.json")

    # =========================================================================
    # Public API
    # =========================================================================

    def get_claude_guide(self) -> str:
        """
        Retourne le guide opérationnel complet CLAUDE.md.

        Returns:
            Contenu de CLAUDE.md (architecture multi-tenant, règles éditoriales, cocons, etc.)
        """
        return self._cache.get("claude_guide", "")

    def get_prompt(self, prompt_path: str) -> str:
        """
        Retourne un prompt template.

        Args:
            prompt_path: Chemin relatif sous `_shared/` (ex: "strategies/full_refresh.md")

        Returns:
            Contenu du prompt
        """
        cache_key = f"prompt_{prompt_path}"

        if cache_key not in self._cache:
            full_path = f"_shared/{prompt_path}"
            self._cache[cache_key] = self._load_file(full_path)

        return self._cache.get(cache_key, "")

    def get_blog_config(self, blog_id: str) -> dict:
        """
        Retourne la configuration d'un blog.

        Args:
            blog_id: Identifiant du blog (ex: "enseigna")

        Returns:
            Configuration du blog
        """
        return self._blog_configs.get(blog_id, {})

    def get_all_blog_ids(self) -> list[str]:
        """
        Retourne la liste de tous les blog IDs.

        Returns:
            Liste des identifiants de blogs
        """
        return list(self._blog_configs.keys())

    def get_prompts_dispatch(self) -> dict:
        """
        Retourne la configuration de dispatch des prompts.

        Returns:
            Configuration prompts_dispatch.json
        """
        return self._prompts_dispatch

    def get_decision_rules(self) -> dict:
        """
        Retourne les règles de décision.

        Returns:
            Configuration decision_rules.json
        """
        return self._decision_rules

    def get_combined_guidelines(self, include_geo: bool = True, include_eeat: bool = True, include_claude: bool = True) -> str:
        """
        Retourne l'orientation issue de CLAUDE.md (Règle d'Or + architecture).

        Depuis 2026-07, les guidelines SEO/GEO/E-E-A-T ne vivent plus dans
        `_shared/docs/` mais dans la skill `edito-refresh` (chargée par le
        subagent de génération). Ne restent ici que les sections clés de
        CLAUDE.md. Les paramètres include_* sont conservés pour compatibilité
        d'appel mais n'ont plus d'effet.
        """
        parts = []
        if include_claude:
            claude = self.get_claude_guide()
            if claude:
                parts.append("# CLAUDE.md - Orientation\n\n")
                parts.append(self._extract_key_sections(
                    claude,
                    ["Règle d'Or", "Architecture multi-tenant"]
                ))
        return "".join(parts)

    def _extract_key_sections(self, content: str, section_keywords: list[str]) -> str:
        """Extrait les sections clés d'un document."""
        import re

        extracted = []
        lines = content.split('\n')

        capture = False
        current_section = []

        for line in lines:
            # Détecter les en-têtes
            if line.startswith('#'):
                # Vérifier si c'est une section à capturer
                if any(kw.lower() in line.lower() for kw in section_keywords):
                    capture = True
                    if current_section:
                        extracted.append('\n'.join(current_section))
                    current_section = [line]
                elif capture and line.startswith('## '):
                    # Nouvelle section de même niveau, arrêter la capture
                    if current_section:
                        extracted.append('\n'.join(current_section))
                    current_section = []
                    capture = False
            elif capture:
                current_section.append(line)

        if current_section:
            extracted.append('\n'.join(current_section))

        return '\n\n'.join(extracted)

    def reload(self):
        """Force le rechargement de tous les documents."""
        self._cache.clear()
        self._blog_configs.clear()
        self._prompts_dispatch.clear()
        self._decision_rules.clear()
        self._load_all()

    @classmethod
    def reset_instance(cls):
        """Réinitialise l'instance singleton (utile pour les tests)."""
        with cls._lock:
            cls._instance = None
