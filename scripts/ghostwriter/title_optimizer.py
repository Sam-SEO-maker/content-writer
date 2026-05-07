"""
Title Optimizer Module

Génère des titres optimisés SEO en utilisant Claude (Max).
Intègre les métriques GSC/SERP pour des recommandations data-driven.
Configuration scalable : lit les guidelines depuis _shared/prompts/sites/{blog_id}.md
"""

from datetime import datetime
from typing import Optional
import re
import json
from pathlib import Path


class TitleOptimizer:
    """
    Optimisateur de titres SEO.

    Génère des titres optimisés basés sur :
    - Métriques GSC (impressions, clicks, CTR, position)
    - Analyse SERP (TOP 3 format, structure)
    - Caractéristiques de l'article (keyword, post_type, blog_id)
    - Guidelines éditoriales du blog
    """

    # Default blog guidelines (can be overridden by _load_blog_config)
    DEFAULT_GUIDELINES = {
        "tone": "informatif, pratique",
        "style": "guide complet",
        "audience": "Lecteurs généraux",
        "max_length": 65,
        "title_suffix": "Guide Complet",  # Default suffix for enhancement
    }

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialise l'optimiseur de titres.

        Args:
            base_path: Chemin racine du projet (pour charger les configs)
        """
        self.current_year = datetime.now().year
        self.base_path = base_path or Path(__file__).parent.parent.parent
        self._blog_config_cache = {}  # Cache des configurations de blogs

    def optimize_title(
        self,
        original_title: str,
        main_keyword: str,
        blog_id: str,
        post_type: str = "",  # kept for backwards compat, unused
        gsc_metrics: Optional[dict] = None,
        serp_metrics: Optional[dict] = None,
    ) -> str:
        """
        Génère un titre optimisé SEO.

        Args:
            original_title: Titre original
            main_keyword: Mot-clé principal
            blog_id: ID du blog (pour guidelines)
            gsc_metrics: Métriques GSC (impressions, clicks, ctr, position)
            serp_metrics: Métriques SERP (format TOP 3, length, structure)

        Returns:
            Titre optimisé avec date mise à jour
        """
        # Guard: None-safety
        original_title = original_title or ""
        main_keyword = main_keyword or ""

        if not original_title.strip():
            print(f"[TITLE] ⚠ original_title est vide, retour du keyword comme fallback")
            return main_keyword or "Sans titre"

        # Step 1: Extract current year from original title
        year_pattern = r'\b(20\d{2})\b'
        original_year_match = re.search(year_pattern, original_title)
        original_year = int(original_year_match.group(1)) if original_year_match else None

        # Step 2: Update year if outdated (>1 year old)
        title = original_title
        if original_year and (self.current_year - original_year) >= 1:
            title = re.sub(year_pattern, str(self.current_year), title)

        # Step 3: Analyze title structure and optimize
        guidelines = self._load_blog_config(blog_id)

        # Step 4: Apply intelligent optimizations based on blog and keywords
        title = self._enhance_for_blog(title, blog_id, main_keyword)

        # Step 5: Apply optimizations based on metrics
        if gsc_metrics:
            title = self._optimize_for_gsc(title, gsc_metrics, main_keyword)

        if serp_metrics:
            title = self._optimize_for_serp(title, serp_metrics, main_keyword)

        # Step 6: Format title according to blog guidelines
        title = self._format_title(title, blog_id)

        # Step 7: Ensure length is optimal
        title = self._enforce_length(title, guidelines["max_length"])

        return title

    def _load_blog_config(self, blog_id: str) -> dict:
        """
        Charge la configuration du blog depuis _shared/config/sites.json ou defaults.

        Structure: sites.json contient {"sites": [{id, name, domain, ...}]}

        Returns:
            Configuration du blog (tone, style, audience, title_suffix, etc.)
        """
        # Vérifier le cache
        if blog_id in self._blog_config_cache:
            return self._blog_config_cache[blog_id]

        # Charger depuis sites.json si disponible
        sites_config_path = self.base_path / "_shared" / "config" / "sites.json"
        if sites_config_path.exists():
            try:
                with open(sites_config_path, 'r', encoding='utf-8') as f:
                    sites_data = json.load(f)
                    # Chercher le blog dans le array "sites"
                    for site in sites_data.get("sites", []):
                        if site.get("id") == blog_id:
                            # Merger avec defaults
                            merged_config = {**self.DEFAULT_GUIDELINES}
                            # Utiliser content_type pour déterminer le suffix
                            content_type = site.get("content_type", "guide")
                            merged_config["content_type"] = content_type
                            merged_config["registre"] = site.get("registre", "vouvoiement")
                            merged_config["tone"] = site.get("tone", "informatif")

                            # Déterminer title_suffix en fonction du type
                            title_suffix = self._determine_title_suffix(content_type, site.get("registre"))
                            merged_config["title_suffix"] = title_suffix

                            self._blog_config_cache[blog_id] = merged_config
                            return merged_config
            except Exception:
                pass

        # Retourner defaults
        config = dict(self.DEFAULT_GUIDELINES)
        self._blog_config_cache[blog_id] = config
        return config

    def _determine_title_suffix(self, content_type: str, registre: str) -> str:
        """
        Détermine le suffixe de titre en fonction du type de contenu.

        Args:
            content_type: Type de contenu (review, guide, etc.)
            registre: Registre de langue (vouvoiement, tutoiement)

        Returns:
            Suffixe approprié pour le titre
        """
        if content_type == "review":
            return "Avis Complet"
        elif content_type == "guide":
            if registre == "tutoiement":
                return "Guide Pratique"
            else:
                return "Guide Complet pour Parents"
        else:
            return "Guide Complet"

    def _enhance_for_blog(
        self, title: str, blog_id: str, main_keyword: str
    ) -> str:
        """
        Améliore intelligemment le titre en fonction de la configuration du blog.

        Stratégie : ajouter un suffix SEULEMENT si ça tient dans le max_length.
        Sinon, garder le titre tel quel (sera formaté après).
        """
        config = self._load_blog_config(blog_id)

        # Remove trailing punctuation for manipulation
        title = title.rstrip("?!.")

        # Vérifier si un suffixe peut être ajouté sans dépasser max_length
        title_suffix = config.get("title_suffix", "")
        max_length = config.get("max_length", 65)

        if ":" not in title and title_suffix:
            proposed_title = f"{title} : {title_suffix}"
            # Ajouter le suffix SEULEMENT si ça rentre dans max_length
            if len(proposed_title) <= max_length:
                title = proposed_title
            # Sinon, garder le titre sans suffixe

        return title

    def _optimize_for_gsc(
        self, title: str, gsc_metrics: dict, main_keyword: str
    ) -> str:
        """
        Optimise le titre basé sur les métriques GSC.

        Stratégies:
        - CTR faible + impressions élevées → Rendre plus attrayant
        - Position dégradée → Intégrer keyword plus tôt
        - Clicks élevés → Préserver structure actuelle
        """
        ctr = float(gsc_metrics.get("ctr", 0))
        impressions = float(gsc_metrics.get("impressions", 0))
        position = float(gsc_metrics.get("position", 1))

        # CTR < 2% with high impressions → Low title appeal
        if ctr < 2.0 and impressions > 1000:
            # Add urgency or value prop
            if "?" not in title:
                title = f"{title} : Guide Complet"
            # Ensure keyword is early
            if main_keyword.lower() not in title[:30].lower():
                title = f"{main_keyword} : {title}"

        # Position degraded (> position 10) → Front-load keyword
        if position > 10 and main_keyword.lower() not in title[:20].lower():
            # Move keyword to beginning
            title_parts = title.split(":")
            if len(title_parts) > 1:
                title = f"{main_keyword} : {title_parts[1].strip()}"

        return title

    def _optimize_for_serp(
        self, title: str, serp_metrics: dict, main_keyword: str
    ) -> str:
        """
        Optimise le titre basé sur l'analyse SERP.

        Stratégies:
        - Format dominant dans TOP 3 (liste, guide, FAQ) → adapter structure
        - Longueur TOP 3 → ajuster longueur
        - Features SERP (PAA, carrousel) → adapter
        """
        dominant_format = serp_metrics.get("format", "guide")
        top_3_avg_length = serp_metrics.get("avg_length", 60)

        # Adapt title based on TOP 3 format
        if dominant_format == "listicle" and not re.search(r'\d+\s+', title):
            # Add number if listicle dominant
            title = f"7 {title}" if "7" not in title else title

        elif dominant_format == "guide" and "guide" not in title.lower():
            if ":" not in title:
                title = f"{title} : Guide Complet"

        elif dominant_format == "comparison" and "vs" not in title.lower():
            pass  # Keep as is

        return title

    def _format_title(self, title: str, blog_id: str) -> str:
        """
        Formate le titre selon les guidelines du blog.

        Règle: Une seule majuscule à la première lettre, reste en minuscules.
        - Ponctuation: ? pour interrogatif, ! pour exclamatif, . sinon
        """
        # Guard: None-safety
        if not title or not title.strip():
            return title or ""

        # Strip leading/trailing whitespace and punctuation
        title = title.strip().rstrip('?!.')

        # Apply rule: Capitalize first letter, lowercase everything else
        if title:
            title = title[0].upper() + title[1:].lower()

        # Determine if it's interrogative (contains verbs like "comment", "que", "quoi", "pourquoi")
        interrogative_words = {'comment', 'que', 'quoi', 'pourquoi', 'où', 'quand', 'quel', 'quelle', 'quels', 'quelles'}
        words = title.split()
        first_word = words[0].lower().strip('?!.') if words else ""

        if first_word in interrogative_words:
            title = f"{title}?"
        else:
            title = f"{title}?"  # Default to ? for SEO-friendly H1s

        return title

    def _enforce_length(self, title: str, max_length: int) -> str:
        """
        Applique la limite de longueur.

        SEO optimal: 50-65 characters for SERP display.
        """
        if len(title) <= max_length:
            return title

        # Remove trailing content intelligently
        if " : " in title:
            # Truncate after colon if too long
            parts = title.split(" : ")
            return f"{parts[0]}"

        # Truncate with ellipsis
        return f"{title[:max_length-3].rsplit(' ', 1)[0]}..."

    def generate_prompt_for_claude(
        self,
        original_title: str,
        main_keyword: str,
        blog_id: str,
        current_content_sample: str,
        post_type: str = "",  # kept for backwards compat, unused
        gsc_metrics: Optional[dict] = None,
    ) -> str:
        """
        Génère un prompt pour Claude (Max) pour optimisation manuelle si besoin.
        """
        guidelines = self._load_blog_config(blog_id)

        prompt = f"""
## Optimiser un Titre SEO

**Blog**: {blog_id}
**Ton**: {guidelines['tone']}
**Audience**: {guidelines['audience']}

**Titre actuel**: "{original_title}"
**Keyword principal**: "{main_keyword}"

**Contraintes**:
- Longueur optimale: {guidelines['max_length']} caractères max
- Inclure le keyword principal naturellement
- Adapter au ton du blog
- Mettre à jour l'année à {self.current_year}
- Être attrayant pour la SERP

**Métriques GSC actuelles**:
{self._format_metrics(gsc_metrics) if gsc_metrics else "Non disponibles"}

**Tâche**: Génère 3 variantes de titres optimisés SEO, du plus simple au plus créatif.

Format:
1. **Variante simple**: [titre]
   - Raison: [pourquoi c'est mieux]

2. **Variante équilibrée**: [titre]
   - Raison: [pourquoi c'est mieux]

3. **Variante créative**: [titre]
   - Raison: [pourquoi c'est mieux]
"""
        return prompt.strip()

    def _format_metrics(self, metrics: dict) -> str:
        """Formate les métriques pour affichage."""
        if not metrics:
            return "Non disponibles"

        lines = []
        for key, value in metrics.items():
            if value:
                lines.append(f"- {key}: {value}")

        return "\n".join(lines) if lines else "Non disponibles"
