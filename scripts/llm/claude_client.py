"""
Claude Client Module

Client pour corrections automatiques via Claude Code sub-agents.
Utilise le plan Max de Claude AI sans API key externe.
"""

from typing import Optional
from pathlib import Path


class ClaudeClient:
    """
    Client pour corrections via Claude Code sub-agents.

    Fonctionnalités:
    - Correction répétitions/duplications
    - Ajout sources E-E-A-T
    - Correction tone (tutoiement/vouvoiement)
    - Mise à jour statistiques

    Note: Utilise Claude Code sub-agents (plan Max) plutôt qu'API Anthropic
    """

    def __init__(self, prompts_path: Optional[Path] = None):
        """
        Initialise le client Claude.

        Args:
            prompts_path: Chemin vers _shared/prompts/corrections/
        """
        if prompts_path is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            prompts_path = project_root / "_shared" / "prompts" / "corrections"

        self.prompts_path = prompts_path
        self.simulation_mode = True  # True = retourne prompts, False = exécute sub-agents

    def correct_duplication(
        self,
        html_content: str,
        duplicate_paragraph: str,
        context: str,
        blog_id: str
    ) -> dict:
        """
        Génère un prompt de correction de duplication.

        Args:
            html_content: Contenu HTML complet de l'article
            duplicate_paragraph: Paragraphe dupliqué à corriger
            context: Contexte de l'article (H1, H2 parent)
            blog_id: ID du blog (pour respecter tone)

        Returns:
            Dict avec {
                "action": "correct_duplication",
                "prompt": str (prompt pour Claude),
                "html_corrected": str (si simulation_mode=False)
            }
        """
        prompt = self._compose_duplication_prompt(
            duplicate_paragraph, context, blog_id
        )

        if self.simulation_mode:
            return {
                "action": "correct_duplication",
                "prompt": prompt,
                "html_corrected": None,  # Nécessite sub-agent pour correction réelle
                "status": "prompt_ready"
            }

        # TODO: Lancer sub-agent Claude Code via Task tool
        # Pour l'instant, retourner prompt uniquement
        return {
            "action": "correct_duplication",
            "prompt": prompt,
            "html_corrected": None,
            "status": "requires_subagent"
        }

    def add_eeat_sources(
        self,
        html_content: str,
        article_h1: str,
        blog_id: str,
        required_sources_count: int = 2
    ) -> dict:
        """
        Génère un prompt pour ajouter des sources E-E-A-T.

        Args:
            html_content: Contenu HTML complet
            article_h1: Titre de l'article (pour contexte)
            blog_id: ID du blog (pour sources appropriées)
            required_sources_count: Nombre de sources à ajouter

        Returns:
            Dict avec action, prompt, html_corrected
        """
        prompt = self._compose_eeat_prompt(
            article_h1, blog_id, required_sources_count
        )

        if self.simulation_mode:
            return {
                "action": "add_eeat_sources",
                "prompt": prompt,
                "html_corrected": None,
                "status": "prompt_ready"
            }

        return {
            "action": "add_eeat_sources",
            "prompt": prompt,
            "html_corrected": None,
            "status": "requires_subagent"
        }

    def correct_tone(
        self,
        html_content: str,
        target_tone: str,  # "vouvoiement" ou "tutoiement"
        blog_id: str
    ) -> dict:
        """
        Génère un prompt pour corriger le ton.

        Args:
            html_content: Contenu HTML complet
            target_tone: Ton cible ("vouvoiement" ou "tutoiement")
            blog_id: ID du blog

        Returns:
            Dict avec action, prompt, html_corrected
        """
        prompt = self._compose_tone_prompt(target_tone, blog_id)

        if self.simulation_mode:
            return {
                "action": "correct_tone",
                "prompt": prompt,
                "html_corrected": None,
                "status": "prompt_ready"
            }

        return {
            "action": "correct_tone",
            "prompt": prompt,
            "html_corrected": None,
            "status": "requires_subagent"
        }

    def update_statistics(
        self,
        html_content: str,
        old_years: list[str],
        current_year: int,
        blog_id: str
    ) -> dict:
        """
        Génère un prompt pour mettre à jour les statistiques.

        Args:
            html_content: Contenu HTML complet
            old_years: Liste des années obsolètes détectées
            current_year: Année actuelle
            blog_id: ID du blog

        Returns:
            Dict avec action, prompt, html_corrected
        """
        prompt = self._compose_statistics_prompt(old_years, current_year, blog_id)

        if self.simulation_mode:
            return {
                "action": "update_statistics",
                "prompt": prompt,
                "html_corrected": None,
                "status": "prompt_ready"
            }

        return {
            "action": "update_statistics",
            "prompt": prompt,
            "html_corrected": None,
            "status": "requires_subagent"
        }

    def _compose_duplication_prompt(
        self,
        duplicate_paragraph: str,
        context: str,
        blog_id: str
    ) -> str:
        """
        Compose le prompt pour correction de duplication.

        Args:
            duplicate_paragraph: Paragraphe dupliqué
            context: Contexte (H1, H2)
            blog_id: ID du blog

        Returns:
            Prompt composé
        """
        base_prompt = self._load_prompt("duplication.md")

        return f"""
{base_prompt}

**Blog**: {blog_id}
**Contexte**: {context}

**Paragraphe dupliqué à différencier**:
{duplicate_paragraph}

**Tâche**: Réécrire ce paragraphe pour le différencier du contenu dupliqué.
Utiliser un angle différent ou résumer l'information.

**Contraintes**:
- Préserver le sens original
- Adapter au contexte de cet article spécifique
- Respecter le ton du blog
"""

    def _compose_eeat_prompt(
        self,
        article_h1: str,
        blog_id: str,
        required_sources_count: int
    ) -> str:
        """
        Compose le prompt pour ajout sources E-E-A-T.

        Args:
            article_h1: Titre de l'article
            blog_id: ID du blog
            required_sources_count: Nombre de sources à ajouter

        Returns:
            Prompt composé
        """
        base_prompt = self._load_prompt("eeat_sources.md")

        # Mapper blog_id vers domaines autoritaires recommandés
        authoritative_domains = {
            "enseigna": ["education.gouv.fr", "eduscol.fr", "onisep.fr"],
            "superprof-ressources": ["education.gouv.fr", "eduscol.fr", "onisep.fr"],
        }

        recommended_domains = authoritative_domains.get(blog_id, ["education.gouv.fr"])

        return f"""
{base_prompt}

**Blog**: {blog_id}
**Article**: {article_h1}
**Sources requises**: {required_sources_count}

**Domaines autoritaires recommandés**:
{', '.join(recommended_domains)}

**Tâche**: Ajouter {required_sources_count} sources autoritaires à l'article.

**Contraintes**:
- Utiliser les domaines recommandés ci-dessus
- Intégrer naturellement dans le contenu (pas en section "Sources")
- Format: <a href="URL">Texte ancre descriptif</a>
- Privilégier données récentes (2024-2026)
"""

    def _compose_tone_prompt(self, target_tone: str, blog_id: str) -> str:
        """
        Compose le prompt pour correction de ton.

        Args:
            target_tone: "vouvoiement" ou "tutoiement"
            blog_id: ID du blog

        Returns:
            Prompt composé
        """
        base_prompt = self._load_prompt("tone_correction.md")

        return f"""
{base_prompt}

**Blog**: {blog_id}
**Ton cible**: {target_tone}

**Tâche**: Convertir tout le contenu vers {target_tone}.

**Exemples**:
- Tutoiement → Vouvoiement: "Tu dois" → "Vous devez"
- Vouvoiement → Tutoiement: "Vous pouvez" → "Tu peux"

**Contraintes**:
- Conversion exhaustive (tous les pronoms, verbes, possessifs)
- Préserver le style et la fluidité
- Ne PAS modifier les citations, URLs, ou balises HTML
"""

    def _compose_statistics_prompt(
        self,
        old_years: list[str],
        current_year: int,
        blog_id: str
    ) -> str:
        """
        Compose le prompt pour mise à jour statistiques.

        Args:
            old_years: Années obsolètes
            current_year: Année actuelle
            blog_id: ID du blog

        Returns:
            Prompt composé
        """
        base_prompt = self._load_prompt("statistics_update.md")

        return f"""
{base_prompt}

**Blog**: {blog_id}
**Années obsolètes détectées**: {', '.join(old_years)}
**Année cible**: {current_year}

**Tâche**: Mettre à jour toutes les statistiques et références temporelles.

**Règles**:
- Remplacer années obsolètes par {current_year} dans les titres et contenu
- NE PAS modifier les URLs (ex: /guide-2025 reste inchangé)
- NE PAS modifier les citations académiques (ex: "Selon Smith (2025)")
- Mettre à jour les statistiques avec données {current_year} si disponibles

**Contraintes**:
- Vérifier cohérence des données
- Ajouter disclaimer si données {current_year} non disponibles
- Préserver les comparaisons historiques
"""

    def _load_prompt(self, filename: str) -> str:
        """
        Charge un prompt de correction depuis _shared/prompts/corrections/.

        Args:
            filename: Nom du fichier prompt

        Returns:
            Contenu du prompt ou prompt par défaut
        """
        prompt_file = self.prompts_path / filename

        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception as e:
                print(f"Erreur chargement prompt {filename}: {e}")

        # Prompt par défaut si fichier non trouvé
        return f"# Correction automatique\n\nPrompt de base pour {filename}"
