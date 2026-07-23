"""
Ghostwriter Module

Moteur principal de réécriture intelligente.
"""

from datetime import datetime
from typing import Optional
from pathlib import Path
import json
import logging

from _shared.core.models import ContentDiff, RewriteResult
from _shared.core.prompt_composer import PromptComposer
from scripts.audit.semantic_checker import SemanticChecker
from scripts.cta.superprof_rotator import SuperprofRotator
from scripts.utils.output_manager import title_to_slug, dated_batch_folder_name
from .diff_engine import DiffEngine

logger = logging.getLogger(__name__)


# Codes langue (ISO 639-1) → nom lisible, pour l'instruction de rédaction
# multi-marché du prompt de génération (cf. catalogue Superprof, Phase 6d).
_LANGUAGE_NAMES = {
    "fr": "français", "es": "espagnol", "en": "anglais", "de": "allemand",
    "it": "italien", "pt": "portugais", "nl": "néerlandais", "pl": "polonais",
    "sv": "suédois", "no": "norvégien", "da": "danois", "fi": "finnois",
    "is": "islandais", "cs": "tchèque", "sk": "slovaque", "hu": "hongrois",
    "el": "grec", "et": "estonien", "lv": "letton", "lt": "lituanien",
    "sl": "slovène", "hr": "croate", "bg": "bulgare", "sr": "serbe",
    "bs": "bosnien", "sq": "albanais", "ro": "roumain", "uk": "ukrainien",
    "tr": "turc", "he": "hébreu", "id": "indonésien", "vi": "vietnamien",
    "ko": "coréen", "ja": "japonais", "zh": "chinois", "ar": "arabe",
}


def language_directive(lang_code: str) -> list[str]:
    """Bloc de prompt imposant la langue de rédaction du marché (multi-site).

    Retourne des lignes prêtes à étendre `prompt_parts`, ou [] si la langue est
    absente/inconnue (le comportement historique implicite reste alors le repli).
    """
    lang_name = _LANGUAGE_NAMES.get(lang_code, "")
    if not lang_name:
        return []
    return [
        f"## LANGUE DE RÉDACTION : {lang_name}",
        "",
        f"Rédige INTÉGRALEMENT l'article en **{lang_name}** "
        f"(titres, corps, FAQ, métadonnées). Conserve les noms propres et "
        f"citations dans leur langue d'origine. N'ajoute aucune traduction.",
        "",
    ]


class Ghostwriter:
    """
    Moteur de réécriture intelligent.

    Fonctionnalités:
    - Réécriture partielle (diff-based) pour économiser les tokens
    - Réécriture complète avec préservation des assets
    - Préservation du style original
    - Intégration des guidelines GEO 2026
    """

    # Fallback mapping site_slug → semantic category (mirrors RefreshOrchestrator)
    BLOG_CATEGORY_MAP = {
        "enseigna": "education",
        "enseigna.fr": "education",
        "superprof.fr-ressources": "education",
        "superprof.fr": "education",
    }

    def __init__(self):
        """Initialise le Ghostwriter."""
        self.diff_engine = DiffEngine()
        self.prompt_composer = PromptComposer()
        self.semantic_checker = SemanticChecker()
        self.superprof_rotator = SuperprofRotator()

    def prepare_rewrite_context(
        self,
        original_html: str,
        strategy_config: dict,
        audit_data: dict,
        assets: dict,
        seo_guidelines: str
    ) -> dict:
        """
        Prépare le contexte complet pour la réécriture.

        Args:
            original_html: HTML original de l'article
            strategy_config: Configuration de la stratégie
            audit_data: Données d'audit
            assets: Assets à préserver
            seo_guidelines: Guidelines SEO

        Returns:
            Contexte formaté pour le LLM
        """
        # Ensure assets is never None
        if assets is None:
            assets = {}

        rewrite_scope = strategy_config.get("rewrite_scope", "full_content")

        # Extraire les sections
        sections = self.diff_engine.extract_sections(original_html)

        # Identifier les sections à modifier si partial
        sections_to_modify = []
        if rewrite_scope == "diff_based":
            sections_to_modify = self.diff_engine.identify_sections_to_modify(
                sections,
                audit_data.get("recommendations", [])
            )

        context = {
            "instruction": self._generate_instruction(strategy_config, rewrite_scope),
            "original_content": {
                "title": sections.get("h1", ""),
                "sections": [
                    {
                        "id": k,
                        "title": v.get("title", "") if isinstance(v, dict) else "",
                        "content": v.get("content", "") if isinstance(v, dict) else v,
                        "requires_modification": k in sections_to_modify if sections_to_modify else True,
                    }
                    for k, v in sections.items()
                    if k != "h1"
                ],
            },
            "audit_insights": {
                "main_keyword": audit_data.get("performance", {}).get("main_keyword", ""),
                "current_position": audit_data.get("performance", {}).get("avg_position", 0),
                "ctr": audit_data.get("performance", {}).get("ctr_30d", 0),
                "alerts": audit_data.get("alerts", []),
                "recommendations": audit_data.get("recommendations", []),
                "gsc_queries": self._format_gsc_queries(audit_data.get("performance", {}).get("keywords", [])),
            },

            "maillage_rules": self._get_maillage_rules(),

            "assets_to_preserve": {
                "rule": "NE JAMAIS supprimer d'images contextuelles ou de liens. Seulement maintenir ou enrichir.",
                "featured_image_note": "L'image à la Une est gérée par WordPress - NE PAS l'inclure dans le HTML",
                "placement_rule": (
                    "PLACEMENT CONTEXTUEL OBLIGATOIRE : "
                    "Chaque image doit être placée sous la première phrase de transition "
                    "du premier titre H2 et du dernier titre H2 du texte qu'elle illustre. "
                    "JAMAIS grouper les images en fin d'article."
                ),
                "images": [
                    self._build_image_html(img)
                    for img in assets.get("images", [])
                ],
                "internal_links": [
                    link.get("html", f"<a href='{link.get('href', '')}'>{link.get('anchor', '')}</a>")
                    for link in assets.get("internal_links", [])
                ],
                "superprof_link": (assets.get("superprof_link") or {}).get("html", ""),
                "cta_blocks": assets.get("cta_blocks") or [],
                "counts": assets.get("counts") or {},
            },
            "guidelines": strategy_config.get("guidelines", []),
            "blog_specific": strategy_config.get("blog_overrides", {}),
            "seo_guidelines_summary": self._extract_key_guidelines(seo_guidelines),
            "output_format": self._get_output_format(rewrite_scope),

            # Règles de densité de contenu (NOUVEAU)
            "content_density_rules": {
                "min_words_per_h2": 300,
                "min_words_per_h3": 150,
                "min_sentences_per_paragraph": 3,
            },
        }

        # NEW: Load semantic field terms for injection into generation prompt
        semantic_field_terms = audit_data.get("semantic_field_override", [])
        if not semantic_field_terms:
            # Resolve category from audit_data or site_slug fallback
            category = audit_data.get("category", "")
            if not category:
                # Fallback: derive category from site_slug
                # "blog_id" = clé legacy des audit_data.json générés avant le renommage
                site_slug = audit_data.get("site_slug", "") or audit_data.get("blog_id", "")
                category = self.BLOG_CATEGORY_MAP.get(site_slug, "")
            subject = audit_data.get("subject", "")
            if category:
                semantic_field_terms = self.semantic_checker._load_semantic_field(
                    category, subject
                )
        context["semantic_field_terms"] = semantic_field_terms

        # YTG term colors (bleu/rouge/orange) pour guidage par terme
        context["ytg_term_colors"] = audit_data.get("ytg_term_colors", {})

        return context

    def _format_gsc_queries(self, keywords: list[dict]) -> dict:
        """
        Format GSC queries intelligemment pour optimisation sémantique.

        Stratégie:
        - Quick wins: Impressions élevées + CTR faible (opportunités faciles)
        - Long tail: Faibles volumes mais bonne position (à enrichir)
        - Core keywords: Requêtes principales (à renforcer)

        Args:
            keywords: Liste de dicts avec query, clicks, impressions, ctr, position

        Returns:
            Dict structuré avec segments de requêtes et recommandations
        """
        if not keywords:
            return {
                "available": False,
                "message": "Aucune donnée GSC disponible (nouveau contenu ou pas de trafic)"
            }

        # Catégoriser les requêtes
        quick_wins = []  # Impressions > 100, CTR < 2%, Position < 20
        long_tail = []   # Impressions < 50, Position < 15
        core_keywords = []  # Impressions > 100, Position < 10

        for kw in keywords:
            query = kw.get("query", "")
            impressions = kw.get("impressions", 0)
            ctr = kw.get("ctr", 0)
            position = kw.get("position", 100)

            # Quick wins: beaucoup d'impressions mais faible CTR
            if impressions > 100 and ctr < 2.0 and position < 20:
                quick_wins.append({
                    "query": query,
                    "impressions": impressions,
                    "ctr": round(ctr, 2),
                    "position": round(position, 1),
                    "opportunity": "Optimiser titre/H2/intro pour améliorer CTR"
                })

            # Long tail: faible volume mais bien positionné
            elif impressions < 50 and position < 15:
                long_tail.append({
                    "query": query,
                    "position": round(position, 1),
                    "opportunity": "Enrichir contenu pour capter plus de trafic"
                })

            # Core keywords: requêtes principales
            elif impressions > 100 and position < 10:
                core_keywords.append({
                    "query": query,
                    "impressions": impressions,
                    "position": round(position, 1),
                    "opportunity": "Renforcer expertise et E-E-A-T"
                })

        # Formater le résumé pour le prompt
        summary = []
        if quick_wins:
            top_qw = quick_wins[:3]
            summary.append(f"**Quick Wins ({len(quick_wins)} opportunités)** : " +
                          ", ".join([f'"{q["query"]}" ({q["impressions"]} imp., CTR {q["ctr"]}%)'
                                   for q in top_qw]))

        if long_tail:
            top_lt = long_tail[:5]
            summary.append(f"**Long Tail ({len(long_tail)} requêtes)** : " +
                          ", ".join([f'"{q["query"]}" (pos {q["position"]})' for q in top_lt]))

        if core_keywords:
            top_core = core_keywords[:3]
            summary.append(f"**Core Keywords ({len(core_keywords)})** : " +
                          ", ".join([f'"{q["query"]}" (pos {q["position"]})' for q in top_core]))

        return {
            "available": True,
            "total_queries": len(keywords),
            "quick_wins": quick_wins[:5],  # Top 5 quick wins
            "long_tail": long_tail[:10],   # Top 10 long tail
            "core_keywords": core_keywords[:5],  # Top 5 core
            "summary_for_prompt": "\n".join(summary),
            "recommendations": [
                f"Intégrer naturellement les requêtes quick wins dans les H2/H3",
                f"Enrichir le contenu pour couvrir les {len(long_tail)} requêtes long tail",
                f"Renforcer l'expertise sur les {len(core_keywords)} requêtes principales"
            ] if (quick_wins or long_tail or core_keywords) else []
        }

    def _build_image_html(self, img: dict) -> str:
        """Build image HTML preserving figure/figcaption when caption exists."""
        if img.get("html"):
            return img["html"]
        src = img.get("src", "")
        alt = img.get("alt", "")
        caption = img.get("caption", "")
        if caption:
            return f'<figure><img src="{src}" alt="{alt}"><figcaption>{caption}</figcaption></figure>'
        return f'<img src="{src}" alt="{alt}">'

    def _get_maillage_rules(self) -> dict:
        """Retourne les règles de maillage interne."""
        return {
            "forbidden": [
                "NE JAMAIS créer de section 'Articles connexes' ou 'Pour aller plus loin'",
                "NE JAMAIS lister les liens internes sous forme de liste à puces",
                "NE JAMAIS empiler les images en fin d'article",
                "NE JAMAIS regrouper les liens dans une seule section",
            ],
            "required": [
                "Intégrer chaque lien interne NATURELLEMENT dans une phrase du contenu",
                "Espacer les liens internes de 150-200 mots minimum",
                "Placer les images EN CONTEXTE, près du texte qu'elles illustrent",
            ],
            "spacing_words": 150,
        }

    def _generate_instruction(self, strategy_config: dict, rewrite_scope: str) -> str:
        """Retourne le nom de la stratégie et son périmètre d'action."""
        strategy = strategy_config.get("strategy", "PARTIAL_REFRESH")

        scopes = {
            "TITLE_OPTIMIZATION": "Optimiser uniquement le titre H1 et la meta description.",
            "PARTIAL_REFRESH": "Rafraîchir les sections obsolètes, mettre à jour statistiques et données dépassées.",
            "FULL_REFRESH": "Réécriture complète avec enrichissement E-E-A-T, en préservant tous les assets.",
            "SEMANTIC_REORIENTATION": "Réorienter vers les variantes de mots-clés identifiées, restructuration sémantique.",
            "FORMAT_ADAPTATION": "Adapter le format au format dominant de la SERP en conservant tous les assets.",
            "EEAT_REWRITE": "Réécriture complète avec focus E-E-A-T maximal, sources institutionnelles obligatoires.",
        }

        return scopes.get(strategy, scopes["PARTIAL_REFRESH"])

    def _get_output_format(self, rewrite_scope: str) -> dict:
        """Retourne le format de sortie attendu."""
        if rewrite_scope in ["diff_based", "targeted_sections"]:
            return {
                "type": "diff",
                "format": """
Pour chaque section modifiée:

## [Titre de la section]

### AVANT:
[Contenu original]

### APRÈS:
[Nouveau contenu]

### JUSTIFICATION:
[Raison de la modification]
""",
            }
        else:
            return {
                "type": "full",
                "format": """
Retourne l'article complet réécrit en HTML:
- Titre H1
- Meta description (en commentaire)
- Contenu complet avec H2, paragraphes, listes
- Tous les assets préservés
""",
            }

    def _extract_key_guidelines(self, seo_guidelines: str) -> str:
        """Extrait les points clés des guidelines SEO."""
        # Extraire les éléments essentiels
        key_points = """
## Points Clés SEO/GEO 2026

### Structure
- Minimum 1500 mots total
- 1 H1, minimum 3 H2
- Section FAQ obligatoire
- Tableau récapitulatif recommandé

### Densité de Contenu (OBLIGATOIRE)
- Minimum 300 mots par section H2
- Minimum 150 mots par sous-section H3
- Minimum 3 phrases par paragraphe
- Paragraphes construits avec arguments développés

### E-E-A-T
- Statistiques sourcées (2025-2026)
- Citation d'expert avec credentials
- Sources institutionnelles (annuaire du site : sites/{id}/sources/authority-map.md)

### GEO
- Réponse directe en début de chaque H2
- Listes à puces pour informations clés
- Format Q&A dans la FAQ

### Maillage Interne (CRITIQUE)
- ❌ INTERDIT: Section "Articles connexes" en fin d'article
- ❌ INTERDIT: Liste de liens à puces
- ❌ INTERDIT: Images empilées en fin d'article
- ✅ OBLIGATOIRE: Liens intégrés naturellement dans les phrases
- ✅ OBLIGATOIRE: Espacement de 150-200 mots entre liens
- ✅ OBLIGATOIRE: Images près du texte qu'elles illustrent

### Liens
- 1 seul lien Superprof (ancre variée, naturelle)
- 1-2 liens externes vers sources d'autorité
- Liens internes vers articles connexes

### Image à la Une
- NE PAS inclure dans le HTML (gérée par WordPress)
- Inclure uniquement les images contextuelles
"""
        return key_points

    @staticmethod
    def _title_to_slug(title: str) -> str:
        return title_to_slug(title)

    @staticmethod
    def _clean_anchor_strong(html: str) -> str:
        """
        Supprime les balises <strong> à l'intérieur des ancres <a>.

        Anti-pattern SEO : <a href="..."><strong>texte</strong></a>
        Corrigé en : <a href="...">texte</a>
        """
        import re
        return re.sub(
            r'(<a\s[^>]*>)\s*<strong>(.*?)</strong>\s*(</a>)',
            r'\1\2\3',
            html,
            flags=re.DOTALL
        )

    @staticmethod
    def _clean_links_in_headings(html: str) -> str:
        """
        Supprime les liens <a> à l'intérieur des balises <h2> et <h3>.

        Red flag SEO : <h2>Texte <a href="...">ancre</a> suite</h2>
        Corrigé en : <h2>Texte ancre suite</h2>
        """
        import re
        def strip_links(match):
            heading_content = match.group(2)
            cleaned = re.sub(r'<a\s[^>]*>(.*?)</a>', r'\1', heading_content, flags=re.DOTALL)
            return f'<{match.group(1)}>{cleaned}</{match.group(1)}>'
        return re.sub(
            r'<(h[23][^>]*)>(.*?)</\1>',
            strip_links,
            html,
            flags=re.DOTALL
        )

    @staticmethod
    def _validate_superprof_urls(html: str, valid_slugs: set[str]) -> str:
        """
        Valide les URLs Superprof dans le HTML généré.
        Remplace les URLs hors config par la première URL valide du set.

        Anti-hallucination : le LLM peut inventer des URLs Superprof
        (ex: /cours/coach-sportif/amiens/, /cours/full-contact/lyon/).
        """
        import re
        if not valid_slugs:
            return html

        fallback_slug = sorted(valid_slugs)[0]
        fallback_url = f"https://www.superprof.fr{fallback_slug}"

        def check_url(match):
            full_url = match.group(1)
            # Extraire le slug (tout après superprof.fr)
            slug_match = re.search(r'superprof\.fr(/cours/[^"\'\s]+)', full_url)
            if not slug_match:
                return match.group(0)
            slug = slug_match.group(1)
            # Normaliser (assurer trailing slash)
            if not slug.endswith("/"):
                slug += "/"
            if slug in valid_slugs:
                return match.group(0)  # URL valide, on garde
            # URL invalide : remplacer
            print(f"[Ghostwriter] URL Superprof invalide remplacée : {slug} → {fallback_slug}")
            return match.group(0).replace(full_url, fallback_url)

        return re.sub(
            r'href="(https?://(?:www\.)?superprof\.fr/cours/[^"]*)"',
            check_url,
            html,
        )

    def process_rewrite_response(
        self,
        llm_response: str,
        original_html: str,
        rewrite_type: str,
        url: str,
        site_slug: str = "",
    ) -> RewriteResult:
        """
        Traite la réponse du LLM et produit le résultat.

        Args:
            llm_response: Réponse brute du LLM
            original_html: HTML original
            rewrite_type: Type de réécriture effectuée
            url: URL de l'article
            site_slug: ID du blog (pour validation URLs Superprof)

        Returns:
            RewriteResult avec le contenu traité
        """
        # Post-processing : nettoyer les anti-patterns SEO
        llm_response = self._clean_anchor_strong(llm_response)
        llm_response = self._clean_links_in_headings(llm_response)

        # Valider les URLs Superprof contre la config (anti-hallucination)
        if site_slug:
            site_id = SuperprofRotator.normalize_site_id(site_slug)
            valid_slugs = self.superprof_rotator.get_valid_slugs(site_id)
            if valid_slugs:
                llm_response = self._validate_superprof_urls(llm_response, valid_slugs)

        # Extraire le nouveau titre
        new_title = self._extract_new_title(llm_response)

        # Extraire la nouvelle meta
        new_meta = self._extract_new_meta(llm_response)

        # Calculer le diff si applicable
        diff = None
        if rewrite_type in ["partial", "diff_based"]:
            diff = self.diff_engine.compare_content(original_html, llm_response)

        # Compter les sections modifiées
        sections_modified = diff.modified_sections if diff else 0

        return RewriteResult(
            url=url,
            rewrite_type=rewrite_type,
            original_html=original_html,
            new_content=llm_response,
            diff=diff,
            new_title=new_title,
            new_meta_description=new_meta,
            sections_modified=sections_modified,
            tokens_used=0,  # À remplir par l'appelant
            assets_preserved=True,  # À valider par asset_manager
            validation_errors=[],
        )

    def _extract_new_title(self, content: str) -> str:
        """Extrait le nouveau titre H1."""
        import re
        match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.I | re.S)
        if match:
            return re.sub(r'<[^>]+>', '', match.group(1)).strip()
        return ""

    def _extract_new_meta(self, content: str) -> str:
        """Extrait la nouvelle meta description."""
        import re
        # Chercher dans un commentaire ou une balise meta
        match = re.search(r'meta[^>]*description[^>]*content=["\']([^"\']+)["\']', content, re.I)
        if match:
            return match.group(1)

        # Chercher dans un commentaire
        match = re.search(r'<!--\s*meta[:\s]+([^-]+)-->', content, re.I)
        if match:
            return match.group(1).strip()

        return ""

    def generate_from_context(
        self,
        context_dir: Path,
        output_dir: Path,
        site_slug: str
    ) -> dict:
        """
        Génère le contenu optimisé à partir d'un contexte préparé.

        Cette méthode lit les fichiers de contexte, compose le prompt complet
        avec CLAUDE.md + catégories, et génère le HTML optimisé.

        Args:
            context_dir: Répertoire contenant les fichiers de contexte
                        (original.html, audit_data.json, guidelines.txt, task.json)
            output_dir: Répertoire de sortie pour le HTML généré
            site_slug: ID du blog (ex: "enseigna.fr")

        Returns:
            Dict avec status, output_files, metadata
        """
        # 1. Lire les fichiers de contexte
        original_html_path = context_dir / "original.html"
        audit_data_path = context_dir / "audit_data.json"
        guidelines_path = context_dir / "guidelines.txt"
        task_path = context_dir / "task.json"

        if not all([
            original_html_path.exists(),
            audit_data_path.exists(),
            guidelines_path.exists(),
            task_path.exists()
        ]):
            return {
                "status": "error",
                "error": "Fichiers de contexte incomplets",
                "missing_files": [
                    str(f) for f in [original_html_path, audit_data_path, guidelines_path, task_path]
                    if not f.exists()
                ]
            }

        # Lire les fichiers
        with open(original_html_path, 'r', encoding='utf-8') as f:
            original_html = f.read()

        with open(audit_data_path, 'r', encoding='utf-8') as f:
            audit_data = json.load(f)

        with open(guidelines_path, 'r', encoding='utf-8') as f:
            guidelines = f.read()

        with open(task_path, 'r', encoding='utf-8') as f:
            task_info = json.load(f)

        # 2. Extraire les informations pour composer le prompt.
        # La décision porte la clé "primary_action" (écrite par l'orchestrateur
        # depuis DecisionResult.primary_action), PAS "strategy". Lire la mauvaise
        # clé faisait retomber TOUTE décision sur FULL_REFRESH (bug historique).
        decision = audit_data.get("decision", {})
        strategy = decision.get("primary_action") or decision.get("strategy")
        if not strategy:
            logger.warning(
                "Aucune stratégie dans la décision (ni primary_action ni strategy) ; "
                "fallback FULL_REFRESH. audit_data.decision=%r",
                decision,
            )
            strategy = "FULL_REFRESH"
        # Normaliser l'action vers une stratégie ayant un prompt .md : les actions
        # du moteur sans membre RefreshStrategy homonyme (CONTENT_GAP_ANALYSIS,
        # DEEP_AUDIT_AND_REWRITE...) passaient telles quelles au composer, qui ne
        # trouvait aucun fichier → prompt de stratégie silencieusement absent.
        # Source unique de conversion : StrategySelector.ACTION_TO_STRATEGY.
        from _shared.core.models import RefreshStrategy
        from scripts.decision.strategy_selector import StrategySelector
        try:
            strategy = RefreshStrategy(strategy).value
        except ValueError:
            mapped = StrategySelector.ACTION_TO_STRATEGY.get(strategy)
            if mapped is None:
                logger.warning(
                    "Action '%s' sans stratégie mappée ; fallback FULL_REFRESH.", strategy)
            strategy = (mapped or RefreshStrategy.FULL_REFRESH).value
        subject_category = audit_data.get("site_config", {}).get("subject_category", "education_general")

        # Sous-type d'article (avis/versus) déduit de l'URL — point unique.
        # "versus" ajoute vs_concurrent.md au prompt et route la sortie html/versus/.
        from _shared.core.article_type import classify_article_type
        article_url = audit_data.get("url", "") or task_info.get("url_slug", "")
        article_type = classify_article_type(article_url, site_slug=site_slug)

        # 3. Composer le prompt complet (CLAUDE.md + catégorie + stratégie + site)
        # Note: CLAUDE.md est déjà accessible à Claude Code via le système
        composed_prompt = self.prompt_composer.compose(
            strategy=strategy.lower(),
            subject=subject_category,
            site_id=site_slug,
            content_type=audit_data.get("site_config", {}).get("content_type"),
            article_type=article_type
        )

        # 4. Préparer le contexte de réécriture
        strategy_config = audit_data.get("decision", {}).get("strategy_config", {})
        assets = audit_data.get("assets", {})

        # Enrich assets with original image/link tags from extraction (if available)
        if "original_image_tags" in audit_data and audit_data["original_image_tags"]:
            assets["images"] = audit_data["original_image_tags"]
        if "original_internal_link_tags" in audit_data and audit_data["original_internal_link_tags"]:
            assets["internal_links"] = audit_data["original_internal_link_tags"]
        if "assets_counts" in audit_data:
            assets["counts"] = audit_data["assets_counts"]

        rewrite_context = self.prepare_rewrite_context(
            original_html=original_html,
            strategy_config=strategy_config,
            audit_data=audit_data,
            assets=assets,
            seo_guidelines=guidelines
        )

        # 5. Construire le prompt final pour génération
        generation_prompt = self._build_generation_prompt(
            composed_prompt=composed_prompt,
            rewrite_context=rewrite_context,
            original_html=original_html,
            audit_data=audit_data,
            guidelines=guidelines,
            site_slug=site_slug,
            context_dir=context_dir,
        )

        # 5b. Sauvegarder la sélection CTA Superprof dans audit_data (anti-répétition)
        site_id = SuperprofRotator.normalize_site_id(site_slug)
        if site_id not in ("enseigna",):
            try:
                article_url = task_info.get("url_slug", "")
                article_subject = audit_data.get("article_subject", "")
                recently = self.superprof_rotator.get_recently_used(context_dir)
                cta_selection = self.superprof_rotator.select_landing(
                    site_id=site_id,
                    article_subject=article_subject,
                    article_url=article_url,
                    recently_used_slugs=recently["slugs"],
                    recently_used_anchors=recently["anchors"],
                )
                audit_data["superprof_landing_used"] = cta_selection["slug"]
                audit_data["superprof_anchor_used"] = cta_selection["anchor"]
                audit_data["superprof_selection_reason"] = cta_selection["reason"]
                # Persister dans audit_data.json
                with open(context_dir / "audit_data.json", "w", encoding="utf-8") as f:
                    json.dump(audit_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # 6. Retourner les informations pour génération
        # Note: La génération réelle sera faite par Claude Code (moi-même)
        # quand l'utilisateur invoque cette méthode
        return {
            "status": "ready_for_generation",
            "context_dir": str(context_dir),
            "output_dir": str(output_dir),
            "generation_prompt": generation_prompt,
            "metadata": {
                "url": task_info.get("url_slug", ""),
                "site_slug": site_slug,
                "strategy": strategy,
                "subject_category": subject_category,
                "article_type": article_type,
                "original_word_count": len(original_html.split()),
                "assets_before": assets.get("counts") or {},
            },
            "output_files": {
                "html": str(output_dir / "html" / dated_batch_folder_name() / f"{self._title_to_slug(audit_data.get('title', '')) or context_dir.name}_refreshed.html"),
                "metadata": str(output_dir / "json" / dated_batch_folder_name() / f"{context_dir.name}_metadata.json")
            }
        }

    def _strip_wordpress_wrappers(self, html: str) -> str:
        """
        Extrait le contenu éditorial en supprimant les wrappers WordPress.

        Retire: <article>, <div class="content-wrap">, <header>, <div class="entry-header">,
                <div class="post-thumbnail">, <div class="entry-content">, etc.
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            # Priorité 1 : extraire le contenu du div entry-content
            entry_content = soup.find('div', class_='entry-content')
            if entry_content:
                return entry_content.decode_contents().strip()
            # Priorité 2 : l'article WordPress contient le contenu après les metas
            article = soup.find('article')
            if article:
                for selector in ['header', 'div.post-thumbnail', 'div.article-meta',
                                  'div.outer-content-wrap', 'div.content-wrap']:
                    el = article.select_one(selector)
                    if el:
                        el.decompose()
                return article.decode_contents().strip()
        except Exception:
            pass
        return html

    def _build_generation_prompt(
        self,
        composed_prompt: str,
        rewrite_context: dict,
        original_html: str,
        audit_data: dict,
        guidelines: str,
        site_slug: str = "",
        context_dir: Optional[Path] = None,
    ) -> str:
        """
        Construit le prompt final pour la génération.

        Structure : contraintes data-driven → instructions éditoriales (.md) → contexte → HTML original

        Les règles éditoriales (ton, E-E-A-T, storytelling, format HTML, ponctuation)
        sont dans CLAUDE.md (contexte système), les skills et les fichiers _shared/strategies/.
        Ce prompt n'injecte que des données spécifiques à l'article.
        """
        current_year = datetime.now().year

        prompt_parts = [
            "# TÂCHE: Refresh SEO Article",
            "",
        ]

        # Langue de sortie EXPLICITE (multi-marché). Rend le workflow transposable :
        # le contenu est produit dans la langue du marché (site_config.language),
        # sans dépendre de la langue de la source scrapée. Voir catalogue Superprof.
        prompt_parts.extend(
            language_directive((audit_data.get("site_config", {}) or {}).get("language", ""))
        )

        # Données chiffrées de l'article (compteurs, année)
        prompt_parts.extend([
            "## DONNÉES ARTICLE",
            "",
            "### Assets à préserver (compteurs exacts)",
            f"- Images : {rewrite_context['assets_to_preserve']['counts'].get('images', 0)}",
            f"- Liens internes : {rewrite_context['assets_to_preserve']['counts'].get('internal_links', 0)}",
            f"- Lien Superprof : 1",
            "",
            f"### Année actuelle : {current_year}",
            f"Mettre à jour les années obsolètes dans les titres et statistiques.",
            f"Ne pas modifier les URLs ni les citations académiques.",
            "",
        ])

        # Instructions éditoriales (catégorie + stratégie + site depuis les .md)
        prompt_parts.extend([
            "## INSTRUCTIONS ÉDITORIALES",
            "",
            composed_prompt,
            "",
            "---",
            "",
        ])

        # Champ sémantique cible (termes à couvrir dans l'article)
        semantic_terms = rewrite_context.get("semantic_field_terms", [])
        if semantic_terms:
            main_kw = rewrite_context['audit_insights'].get('main_keyword', '')
            ytg_term_colors = rewrite_context.get("ytg_term_colors", {})
            prompt_parts.extend(self._format_semantic_field_prompt(
                semantic_terms, main_kw,
                term_colors=ytg_term_colors or None,
            ))

        # Contexte de performance de l'article
        prompt_parts.extend([
            "## CONTEXTE ARTICLE",
            "",
            f"**Stratégie** : {rewrite_context['instruction']}",
            "",
            "### Titre actuel",
            f"```\n{rewrite_context['original_content']['title']}\n```",
            "",
            "### Performance GSC",
            f"- Mot-clé principal : {rewrite_context['audit_insights']['main_keyword']}",
            f"- Position actuelle : {rewrite_context['audit_insights']['current_position']}",
            f"- CTR 30j : {rewrite_context['audit_insights']['ctr']}%",
            "",
        ])

        # Requêtes GSC (données sémantiques)
        gsc_queries = rewrite_context['audit_insights'].get('gsc_queries', {})
        if gsc_queries.get('available', False):
            prompt_parts.extend([
                "### Requêtes GSC (Opportunités Sémantiques)",
                f"**{gsc_queries['total_queries']} requêtes** génèrent du trafic vers cette page :",
                "",
            ])
            if gsc_queries.get('summary_for_prompt'):
                prompt_parts.extend([gsc_queries['summary_for_prompt'], ""])
            if gsc_queries.get('recommendations'):
                for rec in gsc_queries['recommendations']:
                    prompt_parts.append(f"- {rec}")
                prompt_parts.append("")

        # People Also Ask (questions SERP réelles) → à couvrir en FAQ.
        # Source : SERP DataForSEO (audit_engine.to_dict). Sans cette section,
        # la FAQ générée n'est pas alignée sur les questions réellement posées.
        paa_raw = audit_data.get("people_also_ask", "")
        paa_questions = [q.strip() for q in paa_raw.split(",") if q.strip()] if isinstance(paa_raw, str) else list(paa_raw or [])
        if paa_questions:
            prompt_parts.append("### People Also Ask (questions SERP à couvrir en FAQ)")
            prompt_parts.append(
                "Traiter ces questions réellement posées sur Google (FAQ ou corps), "
                "chacune avec une réponse directe :"
            )
            for q in paa_questions[:5]:
                prompt_parts.append(f"- {q}")
            prompt_parts.append("")

        # Secondary keywords (SERP / related searches) à couvrir naturellement.
        sk_raw = audit_data.get("secondary_keywords", "")
        secondary_keywords = [k.strip() for k in sk_raw.split(",") if k.strip()] if isinstance(sk_raw, str) else list(sk_raw or [])
        if secondary_keywords:
            prompt_parts.append("### Mots-clés secondaires (SERP) à couvrir")
            prompt_parts.append(", ".join(secondary_keywords[:10]))
            prompt_parts.append("")

        # Recommandations audit
        recommendations = rewrite_context['audit_insights']['recommendations']
        if recommendations:
            prompt_parts.append("### Recommandations audit")
            for rec in recommendations:
                prompt_parts.append(f"- {rec}")
            prompt_parts.append("")

        # Assets listés (balises HTML exactes à réintégrer)
        images_list = rewrite_context['assets_to_preserve']['images']
        links_list = rewrite_context['assets_to_preserve']['internal_links']
        prompt_parts.extend([
            "### IMAGES À RÉINTÉGRER (OBLIGATOIRE)",
            "",
            f"**{len(images_list)} images** à placer dans le HTML généré :",
            "",
            "**Règle de placement** : Chaque image doit être placée sous la première phrase",
            "de transition du premier titre H2 et du dernier titre H2 du texte qu'elle illustre.",
            "JAMAIS grouper les images en fin d'article. JAMAIS omettre une image.",
            "",
            "**Captions** : Si une image est fournie avec un bloc `<figure>` contenant un",
            "`<figcaption>`, CONSERVER la structure complète `<figure><img .../><figcaption>...</figcaption></figure>`.",
            "Ne JAMAIS supprimer les captions existantes. Reproduire le HTML exact fourni.",
            "",
        ])
        for i, img in enumerate(images_list, 1):
            prompt_parts.append(f"  Image {i}: {img}")
        prompt_parts.extend([
            "",
            f"### Liens internes à conserver ({len(links_list)})",
            "",
        ])
        for link in links_list:
            prompt_parts.append(f"  {link}")
        prompt_parts.append("")

        # CTA Superprof — landing + ancre rotative (données DataForSEO)
        if site_slug and site_slug not in ("enseigna", "enseigna.fr"):
            try:
                article_url = audit_data.get("url", "") or audit_data.get("url_slug", "")
                article_subject = audit_data.get("article_subject", "")
                # Normaliser site_slug (retirer .fr/.com)
                site_id = SuperprofRotator.normalize_site_id(site_slug)
                # Récupérer slugs ET ancres récents pour anti-répétition
                recently = self.superprof_rotator.get_recently_used(
                    context_dir
                ) if context_dir else {"slugs": [], "anchors": []}
                cta_directive = self.superprof_rotator.get_prompt_directive(
                    site_id=site_id,
                    article_subject=article_subject,
                    article_url=article_url,
                    recently_used_slugs=recently["slugs"],
                    recently_used_anchors=recently["anchors"],
                )
                prompt_parts.extend(["", cta_directive, ""])
            except Exception as e:
                prompt_parts.extend([
                    "",
                    "### CTA Superprof",
                    f"- 1 lien Superprof obligatoire (erreur rotator: {e})",
                    "",
                ])

        # Contenu original
        prompt_parts.extend([
            "---",
            "",
            "## CONTENU ORIGINAL",
            "",
            "```html",
            self._strip_wordpress_wrappers(original_html),
            "```",
            "",
            "---",
            "",
            "**GÉNÈRE LE HTML OPTIMISÉ.**",
        ])

        return "\n".join(prompt_parts)

    def _format_semantic_field_prompt(
        self,
        semantic_terms: list[str],
        main_keyword: str = "",
        term_colors: Optional[dict] = None,
    ) -> list[str]:
        """
        Format semantic field terms for injection into the generation prompt.

        Produces a structured section listing terms the LLM should cover,
        with frequency targets calibrated to achieve SOSEO 55-75% / DSEO < 20%.

        Args:
            semantic_terms: List of semantic field terms from category or YTG/DataForSEO
            main_keyword: Primary keyword (components get highest frequency target)
            term_colors: Optional dict {term: color} from YTG guide.
                "blue"   = sous-optimisé → enrichir
                "red"    = surdose → réduire
                "orange" = forte optimisation → maintenir avec attention
                "green"  = couverture normale → maintenir

        Returns:
            List of prompt lines to extend prompt_parts
        """
        if not semantic_terms:
            return []

        # Split main keyword into topic words
        topic_words = set()
        if main_keyword:
            for w in main_keyword.lower().split():
                if len(w) > 2:
                    topic_words.add(w)

        # Classify terms into tiers
        tier1 = []  # Topic words (from main KW) — 3-5x
        tier2 = []  # Important terms (first 10 non-topic) — 2-4x
        tier3 = []  # Supporting terms (rest) — 1-2x

        for term in semantic_terms:
            term_lower = term.lower()
            if term_lower in topic_words:
                tier1.append(term_lower)
            elif len(tier2) < 10:
                tier2.append(term_lower)
            else:
                tier3.append(term_lower)

        # Add topic words not already in the list
        for tw in topic_words:
            if tw not in tier1:
                tier1.append(tw)

        lines = [
            "## CHAMP SÉMANTIQUE CIBLE (OBLIGATOIRE)",
            "",
            "Pour atteindre la zone TOP 3 (SOSEO 55-75%, DSEO < 20%), l'article DOIT",
            "couvrir les termes suivants. Pour chaque terme utilisé 3+ fois, alterner",
            "avec un synonyme ou une périphrase (règle de synonymie obligatoire).",
            "",
        ]

        if tier1:
            lines.append(f"**Termes du mot-clé** (3-5 occurrences chacun, distribués) :")
            lines.append(", ".join(tier1))
            lines.append("")

        if tier2:
            lines.append(f"**Termes importants** (2-4 occurrences chacun) :")
            lines.append(", ".join(tier2))
            lines.append("")

        if tier3:
            lines.append(f"**Termes secondaires** (1-2 occurrences chacun) :")
            lines.append(", ".join(tier3[:20]))  # Cap at 20 to avoid prompt bloat
            lines.append("")

        lines.extend([
            "**Règles** :",
            f"- Couvrir au minimum {min(len(semantic_terms), 25)} termes sur {len(semantic_terms)}",
            "- Distribuer uniformément dans TOUTES les sections (pas de concentration)",
            "- Jamais 3+ termes sémantiques dans la même phrase",
            "- Synonymes obligatoires au-delà de 3 occurrences d'un même terme",
            "",
        ])

        # Section guidance YTG par couleur (si fournie)
        if term_colors:
            all_terms_set = set(t.lower() for t in semantic_terms)
            blue_terms = [
                t for t, c in term_colors.items()
                if c == "blue" and t.lower() in all_terms_set
            ][:12]
            red_terms = [
                t for t, c in term_colors.items()
                if c == "red" and t.lower() in all_terms_set
            ][:8]
            orange_terms = [
                t for t, c in term_colors.items()
                if c == "orange" and t.lower() in all_terms_set
            ][:8]

            if blue_terms or red_terms or orange_terms:
                lines.extend([
                    "**Guidance YourTextGuru (données SERP réelles — PRIORITÉ)** :",
                ])
                if blue_terms:
                    lines.append(
                        f"- SOUS-OPTIMISÉS (enrichir — actuellement absents ou trop rares) : "
                        f"{', '.join(blue_terms)}"
                    )
                if orange_terms:
                    lines.append(
                        f"- FORTE OPTIMISATION (maintenir, synonymes recommandés) : "
                        f"{', '.join(orange_terms)}"
                    )
                if red_terms:
                    lines.append(
                        f"- EN SURDOSE (réduire ou remplacer par synonymes) : "
                        f"{', '.join(red_terms)}"
                    )
                lines.append("")

        lines.extend([
            "---",
            "",
        ])

        return lines

    def generate_diff_prompt(
        self,
        sections_to_modify: list[dict],
        audit_recommendations: list[str],
        assets: dict
    ) -> str:
        """
        Génère un prompt optimisé pour la réécriture partielle.

        Ne transmet que les sections à modifier pour économiser des tokens.

        Args:
            sections_to_modify: Sections nécessitant une modification
            audit_recommendations: Recommandations de l'audit
            assets: Assets à préserver

        Returns:
            Prompt optimisé
        """
        prompt_parts = [
            "# Réécriture Partielle (Mode Ghostwriter)\n",
            "Tu dois modifier UNIQUEMENT les sections suivantes.\n",
            "Format de sortie: AVANT / APRÈS / JUSTIFICATION\n\n",
            "## Recommandations de l'audit:\n",
        ]

        for rec in audit_recommendations:
            prompt_parts.append(f"- {rec}\n")

        prompt_parts.append("\n## Sections à modifier:\n\n")

        for section in sections_to_modify:
            prompt_parts.append(f"### {section.get('title', 'Section')}\n")
            prompt_parts.append(f"```\n{section.get('content', '')[:1000]}\n```\n\n")

        prompt_parts.append("## Assets à préserver (NE PAS SUPPRIMER):\n")
        prompt_parts.append(f"- {(assets.get('counts') or {}).get('images', 0)} images\n")
        prompt_parts.append(f"- {(assets.get('counts') or {}).get('internal_links', 0)} liens internes\n")
        prompt_parts.append(f"- 1 lien Superprof obligatoire\n")

        return "".join(prompt_parts)

