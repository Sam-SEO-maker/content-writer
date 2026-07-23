"""
Refresh Orchestrator Module

Orchestrateur principal qui coordonne le workflow complet de refresh.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
import logging
import requests
import time
import json
import re
from urllib.parse import urlparse
import subprocess
import sys

# Force UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from _shared.core.models import RefreshWorkflowResult
from _shared.core.utils.timing import OperationTimer, timed

# Imports des modules internes
from ..audit import AuditEngine, GSCAnalyzer, SERPAnalyzer, HTMLAnalyzer
from ..decision import DecisionEngine, StrategySelector
from ..ghostwriter import Ghostwriter, TitleOptimizer
from ..assets import AssetManager
from ..sheets import SheetsClient, WorkflowTracker
from ..cache import DocumentCache
from ..scraping import ContentExtractor, WordPressAPIClient
from ..scraping.content_extractor import _convert_wp_shortcodes
from ..audit.semantic_checker import SemanticChecker  # NEW: Post-generation semantic density check
from ..audit.ytg_analyzer import YTGAnalyzer, YTGGuideResult  # YTG semantic guides
from ..notion import NotionClient  # Notion anti-cannibalization

# Imports pour action_formatter
from ..utils.action_formatter import generate_to_do_action, generate_recommended_actions, map_action_to_blogpost
from ..utils.output_manager import dated_batch_folder_name


class RefreshOrchestrator:
    """
    Orchestrateur principal du workflow de refresh SEO.

    Coordonne les 7 étapes:
    0. Selection - Identifier les articles à rafraîchir
    1. Ingest - Récupérer le HTML et les données
    2. Audit - Analyser la performance et le contenu
    3. Decision - Déterminer la stratégie
    4. Writing - Réécrire le contenu
    5. Linking - Valider et restaurer les assets
    6. Sync - Mettre à jour le Sheets
    """

    # Mapping site_slug (or domain) → semantic category for SemanticChecker
    BLOG_CATEGORY_MAP = {
        "enseigna": "education",
        "enseigna.fr": "education",
        "superprof.fr-ressources": "education",
        "superprof.fr-ressources.fr": "education",
    }

    def __init__(
        self,
        base_path: Optional[Path] = None,
        spreadsheet_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialise l'orchestrateur.

        Args:
            base_path: Chemin racine du projet
            spreadsheet_id: ID du Google Sheet de pilotage
        """
        self.base_path = base_path or Path(__file__).parent.parent.parent

        # Résolveur de chemins par site (point unique — Phase 4)
        from _shared.core.site_paths import SitePaths
        self._site_paths = SitePaths(base_path=self.base_path)

        # Initialiser le cache
        self.doc_cache = DocumentCache(self.base_path)

        # Initialiser les composants
        self.asset_manager = AssetManager()
        self.ghostwriter = Ghostwriter()
        self.title_optimizer = TitleOptimizer()

        # Output manager pour gestion centralisée des sorties
        from ..utils.output_manager import OutputManager
        self.output_mgr = OutputManager(self.base_path)

        # Content extractor for HTML parsing (asset baseline extraction)
        self.content_extractor = ContentExtractor(base_path=self.base_path)

        # (Quality gate EditorialAuditor retiré 2026-07 : plus de blocage éditorial ;
        # décision data-driven + véracité via source-research en amont.)

        # Semantic checker pour validation post-génération (anti-suroptimisation)
        self.semantic_checker = SemanticChecker(
            self.base_path / "_shared" / "prompts" / "categories"
        )

        # YTG analyzer pour guides sémantiques (STEP 2.5 — lazy init)
        self.ytg_analyzer: Optional[YTGAnalyzer] = None

        # Notion client pour anti-cannibalisation par titre (STEP 3.5a — lazy init)
        self.notion_client: Optional[NotionClient] = None


        # Decision engine avec rules
        rules_path = self.base_path / "_shared" / "config" / "decision_rules.json"
        self.decision_engine = DecisionEngine(rules_path)

        # Sheets client (optionnel mais recommandé)
        # NOTE: SheetsClient utilise l'API directe Google, pas MCP
        self.sheets_client = None
        self.workflow_tracker = None
        if spreadsheet_id:
            self.sheets_client = SheetsClient(spreadsheet_id)
            self.workflow_tracker = WorkflowTracker(self.sheets_client)
        else:
            import logging
            logging.getLogger("RefreshOrchestrator").warning(
                "No spreadsheet_id provided — all Sheets updates will be SKIPPED. "
                "Set SPREADSHEET_ID in .env or pass --spreadsheet-id to enable."
            )

        # Cache des configurations de blogs
        self._blog_engines: dict[str, AuditEngine] = {}
        self._gsc_analyzers: dict[str, GSCAnalyzer] = {}
        self._serp_analyzers: dict[str, SERPAnalyzer] = {}
        self._wp_api_clients: dict[str, Optional[WordPressAPIClient]] = {}

        # Load sites.json for site_slug mapping (domain → id)
        self._sites_config = self._load_sites_config()

    def _load_sites_config(self) -> dict:
        """
        Charge sites.json et crée un mapping domain → id pour les noms de fichiers.

        Returns:
            Mapping {domain: id} pour résoudre les noms de fichiers
        """
        import json
        sites_json_path = self.base_path / "_shared" / "config" / "sites.json"
        mapping = {}

        try:
            with open(sites_json_path, "r", encoding="utf-8") as f:
                sites_config = json.load(f)
                for site in sites_config.get("sites", []):
                    domain = site.get("domain", "")
                    site_id = site.get("id", "")
                    if domain and site_id:
                        mapping[domain] = site_id
                        # Also map id → id for direct access
                        mapping[site_id] = site_id
        except Exception as e:
            import logging
            logging.getLogger("RefreshOrchestrator").warning(f"Failed to load sites.json: {e}")

        return mapping

    def _normalize_site_slug(self, site_slug: str) -> str:
        """
        Normalise un site_slug pour obtenir le nom correct du fichier de configuration.

        Exemple: "enseigna.fr" → "enseigna"

        Args:
            site_slug: ID du blog (peut être domain ou id)

        Returns:
            ID normalisé pour les noms de fichiers
        """
        # Si le site_slug est un domain, le mapper vers l'id
        if site_slug in self._sites_config:
            return self._sites_config[site_slug]
        # Sinon, retourner tel quel
        return site_slug

    def _get_audit_engine(self, site_slug: str) -> AuditEngine:
        """Récupère ou crée un AuditEngine pour un blog."""
        if site_slug not in self._blog_engines:
            # Normalize site_slug to get correct config
            normalized_site_slug = self._normalize_site_slug(site_slug)
            site_config = self.doc_cache.get_blog_config(normalized_site_slug)
            self._blog_engines[site_slug] = AuditEngine(site_config)
        return self._blog_engines[site_slug]

    def _get_gsc_analyzer(self, site_slug: str) -> GSCAnalyzer:
        """Récupère ou crée un GSCAnalyzer pour un blog."""
        if site_slug not in self._gsc_analyzers:
            # Normalize site_slug to get correct config
            normalized_site_slug = self._normalize_site_slug(site_slug)
            site_config = self.doc_cache.get_blog_config(normalized_site_slug)
            gsc_property = site_config.get("gsc_property", "")
            self._gsc_analyzers[site_slug] = GSCAnalyzer(gsc_property)
        return self._gsc_analyzers[site_slug]

    def _get_serp_analyzer(self, site_slug: str) -> SERPAnalyzer:
        """Récupère ou crée un SERPAnalyzer pour un blog.

        `serp_location` et `language` sont optionnels dans site.json : un site
        qui ne les déclare pas cible France/fr (marchés historiques).
        """
        if site_slug not in self._serp_analyzers:
            # Normalize site_slug to get correct config
            normalized_site_slug = self._normalize_site_slug(site_slug)
            site_config = self.doc_cache.get_blog_config(normalized_site_slug)
            # `or` et non .get(défaut) : le scaffold écrit "" quand le pays n'est
            # pas résolu, et une locale vide ferait échouer l'appel DataForSEO.
            self._serp_analyzers[site_slug] = SERPAnalyzer(
                location=site_config.get("serp_location") or "France",
                language=site_config.get("language") or "fr",
            )
        return self._serp_analyzers[site_slug]

    def _get_wp_api_client(self, site_slug: str) -> Optional[WordPressAPIClient]:
        """
        Retourne un WordPressAPIClient pour ce blog, ou None si non configuré.

        Lit wp_api_config dans _shared/config/blogs/{site_slug}.json.
        Le client est instancié une seule fois par site_slug (cache).
        """
        if site_slug in self._wp_api_clients:
            return self._wp_api_clients[site_slug]

        config_path = self._site_paths.site_config(site_slug)
        client = None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                site_config = json.load(f)

            wp_cfg = site_config.get("wp_api_config")
            if wp_cfg:
                client = WordPressAPIClient(
                    api_base_url=wp_cfg["api_base_url"],
                    user_env_var=wp_cfg["user_env_var"],
                    password_env_var=wp_cfg["password_env_var"],
                    timeout=wp_cfg.get("timeout", 30),
                )
        except FileNotFoundError:
            pass
        except (KeyError, ValueError) as e:
            logging.getLogger("RefreshOrchestrator").warning(
                f"wp_api_config invalid for {site_slug}: {e}"
            )

        self._wp_api_clients[site_slug] = client
        return client

    def _fetch_html(self, url: str, site_slug: str = "") -> dict:
        """
        Récupère le contenu HTML d'une URL.

        Priorité :
        1. WordPress REST API (si wp_api_config présent dans la config du blog)
        2. Fallback : HTTP direct + ContentExtractor (scraping page publique)

        Args:
            url: URL de l'article
            site_slug: ID du blog pour sélection client WP API et temp cache

        Returns:
            {
                "full_html": str,              # HTML du contenu (rendu ou page complète)
                "clean_body": str,             # Corps d'article extrait
                "extraction_metadata": dict,   # Méthode utilisée, stats, wp_post_id si API
                "assets_baseline": dict        # Counts pour Rule of Gold
            }
        """
        logger = logging.getLogger("RefreshOrchestrator")

        # Resolve site_slug to domain for OutputManager (expects "enseigna.fr" not "enseigna")
        output_site_id = site_slug
        if site_slug and "." not in site_slug:
            for domain, sid in self._sites_config.items():
                if sid == site_slug and "." in domain:
                    output_site_id = domain
                    break

        def _save_temp_cache(html: str) -> None:
            if not output_site_id:
                return
            try:
                url_slug = self.output_mgr._url_to_slug(url)
                self.output_mgr.save_temp_html(output_site_id, url_slug, html)
            except ValueError as e:
                logger.debug(f"Skipping temp cache: {e}")

        # --- Stratégie 1 : WordPress REST API ---
        wp_client = self._get_wp_api_client(site_slug)
        if wp_client:
            try:
                post_data = wp_client.get_post_by_url(url)
                if post_data:
                    rendered = post_data["rendered"]
                    assets_baseline = self.content_extractor._extract_assets_baseline(rendered)
                    word_count = len(rendered.split())
                    _save_temp_cache(rendered)
                    logger.info(
                        f"Content via wp_api (post_id={post_data['id']}): "
                        f"{word_count} words, {assets_baseline['counts']['images']} images"
                    )
                    return {
                        "full_html": rendered,
                        "clean_body": rendered,
                        "extraction_metadata": {
                            "method_used": "wp_api",
                            "word_count": word_count,
                            "wp_post_id": post_data["id"],
                            "wp_slug": post_data["slug"],
                            "wp_raw": post_data["raw"],
                        },
                        "assets_baseline": assets_baseline,
                    }
            except Exception as e:
                logger.warning(f"WP API failed for {url}, falling back to scraping: {e}")

        # --- Stratégie 2 : HTTP direct + ContentExtractor ---
        try:
            resp = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ContentWriter/1.0)"},
                allow_redirects=True,
            )
            resp.raise_for_status()
            full_html = resp.text

            clean_body, extraction_meta = self.content_extractor.extract_article_body(
                full_html, output_site_id or site_slug, url=url
            )
            assets_baseline = self.content_extractor._extract_assets_baseline(clean_body)
            word_count = len(clean_body.split())
            _save_temp_cache(clean_body)

            logger.info(
                f"Content via direct_http ({extraction_meta.get('method_used')}): "
                f"{word_count} words, {assets_baseline['counts']['images']} images"
            )

            return {
                "full_html": full_html,
                "clean_body": clean_body,
                "extraction_metadata": {
                    "method_used": f"direct_http_{extraction_meta.get('method_used', 'unknown')}",
                    "word_count": word_count,
                },
                "assets_baseline": assets_baseline,
            }

        except Exception as e:
            logger.error(f"Failed to fetch/extract HTML from {url}: {str(e)}")
            return {
                "full_html": "",
                "clean_body": "",
                "extraction_metadata": {"method_used": "error", "error": str(e)[:200]},
                "assets_baseline": {"counts": {"images": 0, "tables": 0, "videos": 0, "internal_links": 0}},
            }

    def _get_notion_refresh_tracker_db_id(self) -> str:
        """Read the Notion refresh tracker database ID from sites.json."""
        try:
            config_path = Path(__file__).parent.parent.parent / "_shared" / "config" / "sites.json"
            with open(config_path) as f:
                return json.load(f).get("notion_refresh_tracker_db_id", "")
        except Exception:
            return ""

    def _extract_content_metrics(self, html_or_extraction: any, url: str, site_slug: str) -> dict:
        """
        Extrait les métriques de contenu (word count, images, liens internes).

        Compatible avec:
        - Ancien format: html (str) - extrait métriques via HTMLAnalyzer
        - Nouveau format: extraction result (dict) - utilise assets_baseline

        Args:
            html_or_extraction: Contenu HTML (str) OU résultat d'extraction (dict)
            url: URL de l'article
            site_slug: ID du blog

        Returns:
            Dictionnaire avec word_count_before, images_count, internal_links_count, tables_count
        """
        import logging
        logger = logging.getLogger("RefreshOrchestrator")

        try:
            # Nouveau format: dict avec assets_baseline
            if isinstance(html_or_extraction, dict) and "assets_baseline" in html_or_extraction:
                extraction_result = html_or_extraction
                assets = extraction_result["assets_baseline"]["counts"]
                metadata = extraction_result["extraction_metadata"]

                return {
                    "word_count_before": metadata.get("word_count", 0),
                    "images_count": assets.get("images", 0),
                    "tables_count": assets.get("tables", 0),
                    "videos_count": assets.get("videos", 0),
                    "internal_links_count": assets.get("internal_links", 0),
                }

            # Ancien format: string HTML (fallback pour compatibilité)
            html = html_or_extraction if isinstance(html_or_extraction, str) else ""
            if not html:
                logger.warning("No HTML content to extract metrics from")
                return self._get_empty_metrics()

            site_config = self.doc_cache.get_blog_config(site_slug)
            domain = site_config.get("domain", "")

            analyzer = HTMLAnalyzer(domain)
            html_result = analyzer.analyze(html, url)

            # Extraire les métriques
            word_count = len(html_result.text_content.split()) if html_result.text_content else 0

            # Compter les images
            images_count = len(html_result.images) if html_result.images else 0

            # Compter les liens internes
            internal_links_count = 0
            if html_result.internal_links:
                internal_links_count = len(html_result.internal_links)

            return {
                "word_count_before": word_count,
                "images_count": images_count,
                "internal_links_count": internal_links_count,
            }

        except Exception as e:
            logger.warning(f"Failed to extract content metrics: {str(e)[:100]}")
            return self._get_empty_metrics()

    def _get_empty_metrics(self) -> dict:
        """Retourne des métriques vides."""
        return {
            "word_count_before": 0,
            "images_count": 0,
            "tables_count": 0,
            "videos_count": 0,
            "internal_links_count": 0,
        }

    def process_url(
        self,
        url: str,
        site_slug: str,
        html_content: str,
        force_action: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        provided_keyword: Optional[str] = None,
        timer: Optional[OperationTimer] = None,
    ) -> RefreshWorkflowResult:
        """
        Traite une URL complète à travers le workflow.

        Args:
            url: URL de l'article
            site_slug: Identifiant du blog
            html_content: Contenu HTML de la page
            force_action: Action forcée (bypass decision engine)
            custom_prompt: Prompt personnalisé (4 niveaux) remplace les guidelines du cache
            provided_keyword: Mot-clé fourni (optionnel, force analyse SERP)
            timer: OperationTimer optionnel pour chronométrer gsc_fetch / sheets_write / context_prep

        Returns:
            RefreshWorkflowResult avec les détails
        """
        start_time = datetime.now()
        errors = []
        logger = logging.getLogger("RefreshOrchestrator")

        try:
            # Démarrer le tracking
            if self.workflow_tracker:
                self.workflow_tracker.start_workflow(url)

            # =========================================================
            # STEP 1: INGEST - Déjà fait (html_content fourni)
            # =========================================================
            if self.workflow_tracker:
                self.workflow_tracker.advance_step(url, "ingest")

            # =========================================================
            # STEP 1.5 (RETIRÉ 2026-07) : le quality gate EditorialAuditor bloquait
            # le refresh des pages jugées de mauvaise qualité. Supprimé : dans le
            # modèle actuel, la décision de refresh vient des signaux data (GSC :
            # baisse trafic → FULL_REFRESH) et la véracité factuelle est garantie en
            # amont de la génération par la skill `source-research` (sources
            # réelles vérifiées) + le prompt site. Plus de blocage éditorial.

            # =========================================================
            # STEP 2: AUDIT
            # =========================================================

            audit_engine = self._get_audit_engine(site_slug)
            with timed(timer, "gsc_fetch"):
                audit_report = audit_engine.full_audit(url, html_content, provided_keyword=provided_keyword)
            audit_dict = audit_engine.to_dict(audit_report)
            # Inject semantic category for ghostwriter semantic field loading
            audit_dict["category"] = self.BLOG_CATEGORY_MAP.get(site_slug, "")

            if self.workflow_tracker:
                self.workflow_tracker.advance_step(url, "audit")
                # Créer la ligne d'audit (sera loggée après décision pour ajouter les actions)
                audit_row = self.workflow_tracker.audit_report_to_row(audit_dict)

            # =========================================================
            # STEP 2.5: YTG SEMANTIC GUIDE (enrichissement optionnel)
            # =========================================================
            # Non-bloquant : si YTG non configuré ou timeout, le workflow
            # continue avec les termes statiques de la catégorie.
            try:
                main_kw = audit_dict.get("performance", {}).get("main_keyword", "")
                # Fallback multi-source si l'audit GSC n'a pas fourni de mot-clé.
                if not main_kw:
                    try:
                        from scripts.audit.keyword_resolver import KeywordResolver
                        main_kw, _kw_src = KeywordResolver().resolve(site_slug, url=url)
                        if main_kw:
                            logger.info(f"[STEP 2.5] main_keyword résolu '{main_kw}' (source={_kw_src})")
                    except Exception as _kw_e:
                        logger.warning(f"[STEP 2.5] résolution KW échouée: {_kw_e}")
                ytg_result = self._fetch_ytg_guide(main_kw, audit_dict)
                if ytg_result:
                    audit_dict["ytg_guide_id"] = ytg_result.guide_id
                    audit_dict["semantic_field_override"] = ytg_result.semantic_terms
                    audit_dict["ytg_competitor_targets"] = {
                        "top3_soseo": ytg_result.top3_soseo,
                        "top3_dseo": ytg_result.top3_dseo,
                        "top10_soseo": ytg_result.top10_soseo,
                        "top10_dseo": ytg_result.top10_dseo,
                    }
                    audit_dict["ytg_term_colors"] = ytg_result.term_colors
                    logger.info(
                        f"[STEP 2.5] YTG: {len(ytg_result.semantic_terms)} termes, "
                        f"TOP3 SOSEO={ytg_result.top3_soseo}% DSEO={ytg_result.top3_dseo}%"
                    )
                else:
                    logger.info("[STEP 2.5] YTG non configuré — termes statiques utilisés")
            except Exception as e:
                logger.warning(f"[STEP 2.5] YTG non-bloquant, erreur ignorée: {e}")

            # =========================================================
            # STEP 3: DECISION
            # =========================================================

            if force_action:
                primary_action = force_action
                decision_result = {
                    "primary_action": force_action,
                    "rewrite_scope": "full_content" if "FULL" in force_action else "diff_based",
                    "rules_triggered": [],
                }
            else:
                decision = self.decision_engine.evaluate(audit_dict)
                primary_action = decision.primary_action
                decision_result = {
                    "primary_action": decision.primary_action,
                    "rewrite_scope": decision.rewrite_scope,
                    "rules_triggered": [r.rule_id for r in decision.rules_triggered],
                    "estimated_tokens": decision.estimated_tokens,
                    "prompt_template": decision.prompt_template,
                }

            if self.workflow_tracker:
                self.workflow_tracker.advance_step(url, "decision")

                # Enrichir l'audit_row avec les actions recommandées
                if 'audit_row' in locals():
                    # Récupérer les changements d'années effectués par le diff_engine
                    year_changes = []
                    if hasattr(self, 'ghostwriter') and hasattr(self.ghostwriter, 'diff_engine'):
                        year_changes = getattr(self.ghostwriter.diff_engine, '_year_changes', [])

                    # Générer To Do (action claire pour l'utilisateur)
                    to_do_action = generate_to_do_action(decision_result)

                    # Générer Recommended Actions (détails techniques)
                    recommended_actions = generate_recommended_actions(
                        year_changes=year_changes,
                        decision_result=decision_result,
                        audit_data=audit_dict
                    )

                    # Mettre à jour l'audit_row
                    audit_row.to_do = to_do_action
                    audit_row.recommended_actions = recommended_actions


            # Si NO_ACTION ou DATA_COLLECTION_REQUIRED, terminer ici
            if primary_action in ("NO_ACTION", "DATA_COLLECTION_REQUIRED"):
                if self.workflow_tracker:
                    self.workflow_tracker.complete_workflow(url, success=True)

                return RefreshWorkflowResult(
                    url=url,
                    site_slug=site_slug,
                    success=True,
                    action_taken="NO_ACTION",
                    audit_score=audit_report.overall_score,
                    rewrite_type=None,
                    new_title=None,
                    new_meta=None,
                    assets_valid=True,
                    errors=[],
                    execution_time_seconds=(datetime.now() - start_time).total_seconds(),
                )

            # Si REDIRECT_301, signaler et terminer (la suggestion est portée par
            # le résultat action_taken=REDIRECT_301_SUGGESTED ; l'écriture Sheet
            # legacy visait la colonne action_requise de l'onglet retiré).
            if primary_action == "REDIRECT_301":
                if self.workflow_tracker:
                    self.workflow_tracker.complete_workflow(url, success=True)

                return RefreshWorkflowResult(
                    url=url,
                    site_slug=site_slug,
                    success=True,
                    action_taken="REDIRECT_301_SUGGESTED",
                    audit_score=audit_report.overall_score,
                    rewrite_type=None,
                    new_title=None,
                    new_meta=None,
                    assets_valid=True,
                    errors=[],
                    execution_time_seconds=(datetime.now() - start_time).total_seconds(),
                )

            # =========================================================
            # STEP 3.5a: NOTION TITLE ANTI-CANNIBALIZATION
            # =========================================================
            # Vérifie si un article avec un titre similaire existe déjà
            # dans la base Notion. Non-bloquant.
            try:
                notion_db_id = self._get_notion_commandes_db_id(site_slug)
                if notion_db_id:
                    if not self.notion_client:
                        self.notion_client = NotionClient()
                    if self.notion_client.is_configured:
                        commandes = self.notion_client.get_commandes(
                            database_id=notion_db_id,
                            site_slug=site_slug,
                        )
                        current_title = audit_dict.get("title", "")
                        notion_match = self.notion_client.find_title_match(
                            commandes, current_title
                        )
                        audit_dict["notion_title_match"] = {
                            "matched": bool(notion_match),
                            "existing_title": notion_match.title if notion_match else "",
                            "existing_url": notion_match.url if notion_match else "",
                            "existing_status": notion_match.status if notion_match else "",
                        }
                        if notion_match:
                            logger.warning(
                                f"[STEP 3.5a] Notion: titre similaire trouvé → "
                                f"'{notion_match.title}' ({notion_match.url})"
                            )
                        else:
                            logger.info("[STEP 3.5a] Notion: aucune cannibalisation de titre détectée")
                    else:
                        audit_dict["notion_title_match"] = {"matched": False}
                else:
                    audit_dict["notion_title_match"] = {"matched": False}
            except Exception as e:
                logger.warning(f"[STEP 3.5a] Notion non-bloquant, erreur ignorée: {e}")
                audit_dict["notion_title_match"] = {"matched": False}

            # =========================================================
            # STEP 4: WRITING (Préparation du contexte)
            # =========================================================

            # Configurer la stratégie
            prompts_path = self.base_path / "_shared" / "config" / "prompts_dispatch.json"
            site_config = self.doc_cache.get_blog_config(site_slug)
            strategy_selector = StrategySelector(prompts_path, site_config)

            strategy_config = strategy_selector.select_strategy(
                primary_action,
                audit_dict,
                decision_result
            )

            # Préparer le contexte de réécriture
            with timed(timer, "context_prep"):
                rewrite_context = self.ghostwriter.prepare_rewrite_context(
                    original_html=html_content,
                    strategy_config={
                        "strategy": strategy_config.strategy.value,
                        "rewrite_scope": strategy_config.rewrite_scope,
                        "guidelines": strategy_config.guidelines,
                        "blog_overrides": strategy_config.blog_overrides,
                    },
                    audit_data=audit_dict,
                    assets=audit_report.assets,
                    seo_guidelines=custom_prompt or self.doc_cache.get_combined_guidelines(),
                )

            if self.workflow_tracker:
                self.workflow_tracker.advance_step(url, "writing")

            # NOTE: La réécriture effective par LLM est à faire par l'appelant
            # Ici on retourne le contexte préparé

            # =========================================================
            # STEP 5: LINKING (Validation assets)
            # =========================================================
            # La validation sera faite après réception du contenu réécrit
            if self.workflow_tracker:
                self.workflow_tracker.advance_step(url, "linking")

            # =========================================================
            # STEP 6: SYNC
            # =========================================================
            if self.workflow_tracker:
                self.workflow_tracker.advance_step(url, "sync")
                self.workflow_tracker.complete_workflow(url, success=True)

            return RefreshWorkflowResult(
                url=url,
                site_slug=site_slug,
                success=True,
                action_taken=primary_action,
                audit_score=audit_report.overall_score,
                rewrite_type=strategy_config.rewrite_scope,
                new_title=None,  # À remplir après réécriture LLM
                new_meta=None,
                assets_valid=True,
                errors=errors,
                execution_time_seconds=(datetime.now() - start_time).total_seconds(),
                main_keyword=audit_dict.get("main_keyword", ""),
                people_also_ask=audit_dict.get("people_also_ask", ""),
                secondary_keywords=audit_dict.get("secondary_keywords", ""),
                # STEP 2.5 : guide YTG calculé ci-dessus, propagé au CLI refresh.
                ytg_guide_id=audit_dict.get("ytg_guide_id", ""),
                ytg_semantic_field=audit_dict.get("semantic_field_override", []),
                ytg_competitor_targets=audit_dict.get("ytg_competitor_targets", {}),
                ytg_term_colors=audit_dict.get("ytg_term_colors", {}),
            )

        except Exception as e:
            import traceback
            error_msg = str(e)
            errors.append(error_msg)
            logger.error(f"FULL EXCEPTION TRACEBACK:\n{traceback.format_exc()}")

            if self.workflow_tracker:
                self.workflow_tracker.record_error(url, error_msg)
                self.workflow_tracker.complete_workflow(url, success=False)

            if timer is not None:
                timer.success = False
                timer.errors.append(str(error_msg)[:200])

            return RefreshWorkflowResult(
                url=url,
                site_slug=site_slug,
                success=False,
                action_taken="ERROR",
                audit_score=0,
                rewrite_type=None,
                new_title=None,
                new_meta=None,
                assets_valid=False,
                errors=errors,
                execution_time_seconds=(datetime.now() - start_time).total_seconds(),
            )

    # =========================================================================
    # YTG & Notion helpers
    # =========================================================================

    def _fetch_ytg_guide(
        self,
        keyword: str,
        audit_dict: dict,
    ) -> Optional[YTGGuideResult]:
        """
        Récupère ou crée un guide YTG pour le mot-clé donné.

        Stratégie de cache : si audit_dict["ytg_guide_id"] est présent, on
        tente de réutiliser le guide existant (pas de recréation → économie de crédits).
        Si absent ou non-prêt, on crée un nouveau guide et on attend.

        Returns:
            YTGGuideResult ou None si YTG non configuré / erreur.
        """
        if not keyword:
            return None

        # Lazy init
        if self.ytg_analyzer is None:
            self.ytg_analyzer = YTGAnalyzer()

        if not self.ytg_analyzer.is_configured:
            return None

        # get_or_create_guide : 1 seul GET si guide_id en cache, sinon création
        # Pas de download de tous les guides (déduplication gérée par batch-prefetch)
        cached_guide_id = audit_dict.get("ytg_guide_id", "")
        return self.ytg_analyzer.get_or_create_guide(
            guide_id=cached_guide_id,
            keyword=keyword,
        )

    def _ytg_gate_enabled(self, site_slug: str) -> bool:
        """Lit ytg.gate depuis _shared/config/blogs/{site_slug}.json (défaut: False)."""
        try:
            cfg_path = self._site_paths.site_config(site_slug)
            if not cfg_path.exists():
                return False
            with open(cfg_path, encoding="utf-8") as f:
                return bool(json.load(f).get("ytg", {}).get("gate", False))
        except Exception:
            return False

    def _get_notion_commandes_db_id(self, site_slug: str) -> Optional[str]:
        """Lit notion_commandes_db_id depuis sites.json pour ce blog."""
        sites = []
        try:
            sites_path = self.base_path / "_shared" / "config" / "sites.json"
            if sites_path.exists():
                with open(sites_path) as f:
                    data = json.load(f)
                    sites = data.get("sites", [])
        except Exception:
            return None

        for site in sites:
            if (site.get("site_slug") or site.get("id")) == site_slug:
                return site.get("notion_commandes_db_id") or None
        return None

    # =========================================================================
    # NEW: v2.0 Single-Sheet Architecture Batch Operations
    # =========================================================================

    def _keyword_from_slug(url: str) -> Optional[str]:
        """
        Extrait un keyword seed nettoyé depuis le slug de l'URL.

        Nettoyage : suppression stop words, restauration accents,
        limite à 4 mots-clés essentiels.

        Ex: "les-avantages-de-la-cuisson-a-la-vapeur-pour-perdre-du-poids"
            → "avantages cuisson vapeur perte poids" (5 mots max)
        """
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        if not path:
            return None
        slug = path.split("/")[-1]
        words = slug.replace("-", " ").replace("_", " ").strip().split()

        if not words:
            return None

        # Restaurer les accents
        words = [RefreshOrchestrator._ACCENT_FIXES.get(w, w) for w in words]

        # Retirer les stop words
        core_words = [w for w in words if w.lower() not in RefreshOrchestrator._FR_STOP_WORDS]

        # Si tout a été filtré, garder les mots originaux sans stop words numériques
        if not core_words:
            core_words = [w for w in words if len(w) > 2]

        if not core_words:
            return None

        # Limiter à 5 mots max pour un seed efficace
        keyword = " ".join(core_words[:5])

        if len(keyword) < 3:
            return None

        return keyword

    def _archive_previous_context(context_dir: Path) -> Optional[Path]:
        """Archive le contenu d'une passe précédente dans _archive/{timestamp}/.

        Relancer `cw refresh` sur une URL déjà traitée ne doit jamais détruire le
        contexte précédent (audit, prompt, plan, brief de sources) : tout ce qui
        n'est pas déjà dans `_archive/` est déplacé vers un sous-dossier horodaté.
        Retourne le dossier d'archive créé, ou None si le contexte était vierge.
        """
        import shutil

        entries = [p for p in context_dir.iterdir() if p.name != "_archive"] \
            if context_dir.exists() else []
        if not entries:
            return None

        archive_dir = context_dir / "_archive" / datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            shutil.move(str(entry), str(archive_dir / entry.name))
        print(f"[CONTEXT] Previous pass archived → {archive_dir}")
        return archive_dir

    def _prepare_context_for_claude_code(self, original_html: str, action: str, row, extraction_result: dict = None, ytg_data: dict = None) -> Path:
        """
        Prépare les fichiers de contexte pour Claude Code.

        Args:
            original_html: HTML original de l'article
            action: Type d'action (FULL_REFRESH, REFRESH_TITLES, etc.)
            row: RefreshAuditRow contenant les métadonnées
            extraction_result: Résultat d'extraction avec assets_baseline (optionnel)
            ytg_data: Données YTG pré-génération (termes, guide_id, targets)

        Returns:
            Path: Chemin du dossier de contexte créé
        """
        # Log auto-process detection
        if action == "FULL_REFRESH" or action == "FULL REFRESH":
            print(f"[AUTO-PROCESS] FULL_REFRESH action detected for: {row.blogpost_url}")
            print(f"[AUTO-PROCESS] Preparing the context for automatic generation...")

        # Create a slug from URL (used for the context bundle directory name)
        url_slug = re.sub(r'[^a-z0-9]+', '_', row.blogpost_url.lower()).strip('_')

        # Output slug: last URL path segment only (article slug), without domain/categories.
        # Used to name delivered files (e.g. "distance-zero-soustraction.html", not the full
        # domain+category-encoded url_slug) so the html/ folder stays readable at a glance.
        output_slug = row.blogpost_url.rstrip('/').rsplit('/', 1)[-1]
        if output_slug.endswith('.html'):
            output_slug = output_slug[:-len('.html')]

        # Create context directory
        context_dir = Path("_shared/context") / url_slug
        context_dir.mkdir(parents=True, exist_ok=True)

        # Un refresh précédent a laissé un contexte ? L'archiver AVANT d'écrire
        # (une relance sur la même URL ne doit jamais écraser la passe d'avant).
        # Les fichiers courants gardent leurs noms canoniques (audit_data.json,
        # generation_prompt.txt…), lus en dur par finalize/ytg_qc/plan.
        self._archive_previous_context(context_dir)

        # Save original HTML
        html_file = context_dir / "original.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(original_html)

        # Load guidelines
        seo_guidelines = self.doc_cache.get_combined_guidelines() or ""
        site_prompt = ""
        try:
            # Normalize site_slug to get correct file name (e.g., "enseigna.fr" → "enseigna")
            normalized_site_slug = self._normalize_site_slug(row.site_slug)
            site_prompt = self.doc_cache.get_prompt(f"sites/{normalized_site_slug}.md") or ""
        except:
            pass

        # Prepare audit data
        audit_data = {
            "site_slug": row.site_slug,
            "url": row.blogpost_url,
            "title": row.title,
            "main_keyword": row.main_keyword,
            "action": action,
            "post_type": str(row.post_type) if row.post_type else "",
            "impressions_30d": row.impressions_30d,
            "clicks_30d": row.clicks_30d,
            "ctr_30d": float(row.ctr_30d) if row.ctr_30d else 0.0,
            "people_also_ask": row.people_also_ask[:500] if row.people_also_ask else "",
            "secondary_keywords": row.secondary_keywords[:500] if row.secondary_keywords else "",
            "url_slug": url_slug,
            "output_dir": f"sites/{row.site_slug}/outputs",
            # Semantic field: category for SemanticChecker._load_semantic_field()
            "category": self.BLOG_CATEGORY_MAP.get(row.site_slug, ""),
        }

        # Inject full asset tags from extraction_result for ghostwriter
        if extraction_result and "assets_baseline" in extraction_result:
            baseline = extraction_result["assets_baseline"]
            audit_data["original_image_tags"] = baseline.get("image_tags", [])
            audit_data["original_internal_link_tags"] = baseline.get("internal_link_tags", [])
            audit_data["assets_counts"] = baseline.get("counts", {})

        # Inject YTG semantic terms for ghostwriter (STEP 2.5 pre-generation)
        if ytg_data:
            audit_data["ytg_guide_id"] = ytg_data.get("ytg_guide_id", "")
            audit_data["semantic_field_override"] = ytg_data.get("semantic_field_override", [])
            audit_data["ytg_competitor_targets"] = ytg_data.get("ytg_competitor_targets", {})
            audit_data["ytg_term_colors"] = ytg_data.get("ytg_term_colors", {})

        audit_file = context_dir / "audit_data.json"
        with open(audit_file, 'w', encoding='utf-8') as f:
            json.dump(audit_data, f, indent=2, ensure_ascii=False)

        # Save guidelines
        guidelines_file = context_dir / "guidelines.txt"
        with open(guidelines_file, 'w', encoding='utf-8') as f:
            f.write(f"GUIDELINES SYSTÈME:\n{seo_guidelines[:3000]}\n\n")
            f.write(f"GUIDELINES SITE {row.site_slug}:\n{site_prompt[:1500]}\n")

        batch_folder = dated_batch_folder_name()
        html_subdir = f"html/{batch_folder}"

        # Build task instructions
        instructions = [
            "Lis le fichier original.html complet",
            "Lis les données d'audit dans audit_data.json",
            "Lis les guidelines dans guidelines.txt",
            "Génère le HTML optimisé en respectant la RÈGLE D'OR",
            f"Sauvegarde le résultat dans sites/{row.site_slug}/outputs/{html_subdir}/{output_slug}_refreshed.html",
            f"Sauvegarde les métadonnées dans sites/{row.site_slug}/outputs/metadata/{output_slug}_metadata.json",
        ]
        if row.site_slug == "superprof.fr-ressources":
            refreshed_html_path = f"sites/{row.site_slug}/outputs/{html_subdir}/{output_slug}_refreshed.html"
            instructions.append(
                f"Exécute en Bash depuis la racine du projet (extraction CSV des tableaux, "
                f"OBLIGATOIRE avant l'étape suivante, même si le rapport de génération dit "
                f"que les tableaux ont été traités) : "
                f".venv/bin/python content_writer.py batch extract-tables "
                f"--site-id {row.site_slug} --file {refreshed_html_path}"
            )
            instructions.append(
                f"Exécute en Bash depuis la racine du projet : "
                f".venv/bin/python content_writer.py ngl-status '{row.blogpost_url}' 'Rédigé'"
            )

        # Create task bundle
        task_data = {
            "task_type": "content_refresh",
            "status": "READY",
            "created_at": datetime.now().isoformat(),
            "url_slug": url_slug,
            "output_slug": output_slug,
            "files": {
                "input": {
                    "original_html": str(html_file.absolute()),
                    "audit_data": str(audit_file.absolute()),
                    "guidelines": str(guidelines_file.absolute())
                },
                "output": {
                    "refreshed_html": f"sites/{row.site_slug}/outputs/{html_subdir}/{output_slug}_refreshed.html",
                    "metadata": f"sites/{row.site_slug}/outputs/metadata/{output_slug}_metadata.json"
                }
            },
            "instructions": instructions,
        }

        task_file = context_dir / "task.json"
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, indent=2, ensure_ascii=False)

        print(f"[INFO] [OK] Context prepared in: {context_dir}")
        print(f"[INFO]   Files created:")
        print(f"[INFO]   - {html_file.name}")
        print(f"[INFO]   - {audit_file.name}")
        print(f"[INFO]   - {guidelines_file.name}")
        print(f"[INFO]   - {task_file.name}")

        return context_dir

    def _generate_refreshed_content(self, original_html: str, action: str, row, extraction_result: dict = None, ytg_data: dict = None) -> tuple:
        """
        Génère le contenu rafraîchi via Claude Code (abonnement Max).

        Cette méthode:
        1. Prépare les fichiers de contexte (avec image_tags si extraction_result fourni)
        2. Indique à Claude Code de traiter la tâche
        3. Vérifie et retourne les résultats

        Args:
            original_html: HTML original de l'article
            action: Type d'action (FULL_REFRESH, REFRESH_TITLES, etc.)
            row: RefreshAuditRow contenant les métadonnées
            extraction_result: Résultat d'extraction avec assets_baseline (optionnel)
            ytg_data: Données YTG pré-génération (termes, guide_id, targets)

        Returns:
            tuple: (refreshed_html, optimized_title)
        """
        try:
            # STEP 1: Prepare context files (pass extraction_result for image_tags)
            context_dir = self._prepare_context_for_claude_code(original_html, action, row, extraction_result, ytg_data=ytg_data)

            url_slug = re.sub(r'[^a-z0-9]+', '_', row.blogpost_url.lower()).strip('_')
            output_slug = row.blogpost_url.rstrip('/').rsplit('/', 1)[-1]
            if output_slug.endswith('.html'):
                output_slug = output_slug[:-len('.html')]

            # STEP 2: Check if Claude Code should be invoked
            # Define expected output paths using OutputManager (title-based naming)
            outputs = self.output_mgr.get_output_files(row.site_slug, output_slug, title=row.title)
            refreshed_file = outputs["refreshed_html"]
            metadata_file = outputs["metadata"]

            print(f"\n{'='*70}")
            print(f"[CLAUDE CODE] TASK READY FOR PROCESSING")
            print(f"{'='*70}")
            print(f"Context: {context_dir.absolute()}")
            print(f"\nClaude Code must now:")
            print(f"  1. Read the context files")
            print(f"  2. Generate the optimized content")
            print(f"  3. Save to:")
            print(f"     - {refreshed_file}")
            print(f"     - {metadata_file}")
            print(f"{'='*70}\n")

            # STEP 3: Check if output already exists (for retry/resume scenarios)
            if refreshed_file.exists() and metadata_file.exists():
                print(f"[INFO] [OK] Output files found, reading the results...")

                # Read refreshed HTML
                with open(refreshed_file, 'r', encoding='utf-8') as f:
                    refreshed_html = f.read()

                # Read metadata
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    output_metadata = json.load(f)

                optimized_title = output_metadata.get("title_optimized", row.title)

                print(f"[INFO] [OK] Content retrieved from outputs/:")
                print(f"      HTML: {refreshed_file}")
                print(f"      Metadata: {metadata_file}")

                return refreshed_html, optimized_title

            else:
                # Files don't exist yet - Claude Code needs to process
                # Check if we're in auto-process mode (FULL_REFRESH detected)
                if action == "FULL_REFRESH" or action == "FULL REFRESH":
                    print(f"[AUTO-PROCESS] Full Refresh detected, context prepared")
                    print(f"[AUTO-PROCESS] Task ready in: {context_dir}")
                    print(f"[AUTO-PROCESS] The files will be generated by Claude Code")
                    print(f"[AUTO-PROCESS] Workflow continues, generation pending...")

                    # Return original HTML for now - content will be generated later by Claude Code
                    # This allows the batch workflow to continue without blocking
                    return original_html, row.title
                else:
                    # Non-FULL_REFRESH actions: raise exception to signal manual processing needed
                    print(f"[WAITING] Output files not found.")
                    print(f"[WAITING] Claude Code must process the task in: {context_dir}")
                    print(f"[WAITING] Once done, re-run the script to continue.")
                    raise Exception(f"Claude Code processing required. Context prepared in: {context_dir}")

        except Exception as e:
            print(f"[ERROR] Content generation error: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            # Fallback: return original HTML
            return original_html, row.title

    def _enseigna_rows_for_refresh(self, action: str) -> list:
        """
        Adapte les EnseignaAvisRow (onglets Avis/Versus réels) à l'interface
        attendue par la boucle de `batch_refresh` (row.site_slug, row.title, etc.),
        sans dupliquer la logique de génération/validation qui suit.
        """
        @dataclass
        class _EnseignaRefreshRow:
            site_slug: str = "enseigna"
            blogpost_url: str = ""
            main_keyword: str = ""
            title: str = ""
            post_type: str = ""
            impressions_30d: int = 0
            clicks_30d: int = 0
            ctr_30d: float = 0.0
            index_diagnostic: str = ""
            _source: object = field(default=None, repr=False)

        avis_rows = self.sheets_client.read_pending_for_refresh_enseigna(action)
        return [
            _EnseignaRefreshRow(
                blogpost_url=r.url,
                main_keyword=r.top_keyword,
                title="",  # pas de colonne title sur Avis/Versus — le ghostwriter part du H1 scrapé
                post_type="review",
                impressions_30d=r.impressions_30d,
                clicks_30d=r.clicks_30d,
                ctr_30d=r.ctr,
                _source=r,
            )
            for r in avis_rows
        ]

    def batch_refresh(self, action: str, site_slug: Optional[str] = None, post_type: Optional[str] = None, limit: Optional[int] = None) -> dict:
        """
        Batch refresh pour lignes where action_blogpost = action.

        Supports:
        - PARTIAL_REFRESH: Update stats/dates
        - REFRESH_TITLES: Optimize H1/H2
        - FULL_REFRESH: Complete rewrite

        Updates:
        - Column H: status (TODO → AUDITING → DONE) [REFONTE Feb 2026]
        - Columns P-Q: new_h1_title, new_h2_titles

        Args:
            action: Refresh action type
            site_slug: Filter by site_slug (optional)
            post_type: Filter by post_type - "CHILD", "PARENT", "STANDALONE" (optional)

        Returns:
            {
                "processed": int,
                "success": int,
                "failed": int,
                "assets_restored": int,
                "errors": list
            }
        """
        import logging
        logger = logging.getLogger("RefreshOrchestrator")

        if not self.sheets_client:
            return {"processed": 0, "success": 0, "failed": 0, "assets_restored": 0, "errors": []}

        # Router vers les onglets réels du site. Seul enseigna.fr a un flux batch
        # piloté par Sheet (Avis/Versus). L'ancien fallback lisait l'onglet retiré
        # Refreshs_Audit et renvoyait silencieusement 0 ligne — remplacé par une
        # erreur explicite (le batch superprof passe par prepare_weekly_batch).
        from _shared.core.constants import canonical_site_slug
        site_canonical = canonical_site_slug(site_slug) if site_slug else None
        if site_canonical == "enseigna.fr":
            rows = self._enseigna_rows_for_refresh(action)
        else:
            msg = (f"batch_refresh: no sheet-driven batch flow wired for site "
                   f"'{site_canonical}' (only enseigna.fr Avis/Versus). "
                   f"Superprof batches run via scripts/agent/prepare_weekly_batch.")
            logger.error(msg)
            return {"processed": 0, "success": 0, "failed": 0,
                    "assets_restored": 0, "errors": [msg]}

        # Filter by post_type if specified
        if post_type:
            rows = [r for r in rows if r.post_type == post_type]

        # Limit number of rows to process
        if limit and limit > 0:
            rows = rows[:limit]

        results = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "assets_restored": 0,
            "errors": []
        }

        for row in rows:
            results["processed"] += 1

            try:
                # STEP 1: Fetch original HTML (NEW: autonomous scraping with extraction)
                extraction_result = self._fetch_html(row.blogpost_url, row.site_slug)
                if not extraction_result.get("clean_body"):
                    raise ValueError(f"Failed to fetch HTML for {row.blogpost_url}")

                # STEP 2: Extract original assets (BASELINE FOR RULE OF GOLD)
                original_metrics = self._extract_content_metrics(extraction_result, row.blogpost_url, row.site_slug)
                original_images = original_metrics.get("images_count", 0)
                original_links = original_metrics.get("internal_links_count", 0)

                # STEP 2.5: YTG GUIDE — fetch semantic terms BEFORE generation
                ytg_pre_data = {}
                try:
                    if self.ytg_analyzer is None:
                        self.ytg_analyzer = YTGAnalyzer()

                    if self.ytg_analyzer.is_configured and row.main_keyword:
                        ytg_result = self._fetch_ytg_guide(row.main_keyword, {})
                        if ytg_result:
                            ytg_pre_data = {
                                "ytg_guide_id": ytg_result.guide_id,
                                "semantic_field_override": ytg_result.semantic_terms,
                                "ytg_competitor_targets": {
                                    "top3_soseo": ytg_result.top3_soseo,
                                    "top3_dseo": ytg_result.top3_dseo,
                                    "top10_soseo": ytg_result.top10_soseo,
                                    "top10_dseo": ytg_result.top10_dseo,
                                },
                                "ytg_term_colors": ytg_result.term_colors,
                            }
                            logger.info(
                                f"[STEP 2.5] YTG PRE-GEN: {len(ytg_result.semantic_terms)} termes, "
                                f"TOP3 SOSEO={ytg_result.top3_soseo}% DSEO={ytg_result.top3_dseo}%"
                            )
                except Exception as ytg_pre_err:
                    logger.warning(f"[STEP 2.5] YTG pre-gen non-blocking error: {ytg_pre_err}")

                # STEP 3: Generate refreshed content
                if action in ["FULL_REFRESH", "FULL REFRESH"]:
                    # Full content generation with Claude Opus 4.6
                    # Use CLEAN BODY for ghostwriter (article content only)
                    # Pass extraction_result so image_tags reach the context/prompt
                    refreshed_html, optimized_title = self._generate_refreshed_content(
                        original_html=extraction_result["clean_body"],
                        action=action,
                        row=row,
                        extraction_result=extraction_result,
                        ytg_data=ytg_pre_data,
                    )
                else:
                    # Title-only optimization for REFRESH_TITLES
                    # Keep original clean body unchanged
                    refreshed_html = extraction_result["clean_body"]
                    optimized_title = self.title_optimizer.optimize_title(
                        original_title=row.title,
                        main_keyword=row.main_keyword,
                        site_slug=row.site_slug,
                        post_type=row.post_type,
                        gsc_metrics={
                            "impressions": row.impressions_30d,
                            "clicks": row.clicks_30d,
                            "ctr": row.ctr_30d,
                            "position": getattr(row, 'avg_position', None),
                        } if row.impressions_30d else None,
                        serp_metrics=None  # Will be populated from SERP audit when available
                    )

                # STEP 3.5: Extract H2 titles from refreshed content
                import re
                from bs4 import BeautifulSoup

                try:
                    soup = BeautifulSoup(refreshed_html, 'html.parser')
                    h2_titles = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]
                    h2_titles_json = json.dumps(h2_titles[:10], ensure_ascii=False)  # Limiter à 10 H2
                except Exception:
                    h2_titles_json = "[]"

                refreshed_titles = {
                    "new_h1_title": optimized_title,
                    "new_h2_titles": h2_titles_json,
                }

                # STEP 4: Extract metrics from refreshed content
                refreshed_metrics = self._extract_content_metrics(refreshed_html, row.blogpost_url, row.site_slug)
                refreshed_images = refreshed_metrics.get("images_count", 0)
                refreshed_links = refreshed_metrics.get("internal_links_count", 0)

                # STEP 5: VALIDATE ASSETS (RULE OF GOLD)
                assets_restored = 0
                if refreshed_images < original_images or refreshed_links < original_links:
                    # Use AssetManager to restore missing assets
                    # Use FULL HTML for asset validation (contains all images, tables, videos)
                    try:
                        # Extract assets from original
                        original_assets = self.asset_manager.extract_assets(extraction_result["full_html"])

                        # Validate using correct API
                        validation = self.asset_manager.validate(
                            original_assets=original_assets,
                            new_content=refreshed_html,
                            original_content=extraction_result["full_html"],
                        )

                        if not validation.is_valid:
                            # Restore missing assets using correct API
                            refreshed_html = self.asset_manager.restore_missing_assets(
                                content=refreshed_html,
                                original_assets=original_assets,
                                validation_result=validation
                            )
                            assets_restored = 1
                            # Re-extract metrics after restoration
                            refreshed_metrics = self._extract_content_metrics(refreshed_html, row.blogpost_url, row.site_slug)
                    except Exception as asset_err:
                        # If asset validation fails, log but continue
                        self.logger = __import__("logging").getLogger("RefreshOrchestrator")
                        self.logger.warning(f"Asset validation error: {str(asset_err)[:50]}")

                # STEP 5.6: YTG POST-VALIDATION (SEMANTIC DENSITY CHECK)
                ytg_post_scores = {}
                ytg_gate_block = False
                try:
                    # Lazy init YTG analyzer
                    if self.ytg_analyzer is None:
                        self.ytg_analyzer = YTGAnalyzer()

                    if self.ytg_analyzer.is_configured:
                        # Retrieve ytg_guide_id from context audit_data.json (written by batch-prefetch)
                        ytg_guide_id = ""
                        url_slug_ytg = re.sub(r'[^a-z0-9]+', '_', row.blogpost_url.lower()).strip('_')
                        audit_data_path = Path("_shared/context") / url_slug_ytg / "audit_data.json"
                        ytg_targets = {}
                        if audit_data_path.exists():
                            try:
                                with open(audit_data_path, encoding="utf-8") as f:
                                    cached_audit = json.load(f)
                                ytg_guide_id = cached_audit.get("ytg_guide_id", "")
                                ytg_targets = cached_audit.get("ytg_competitor_targets", {})
                            except Exception:
                                pass

                        # Fallback: fetch/create guide from keyword.
                        # Le main_keyword du row peut être vide (blogs sans col
                        # keyword remplie) → résolution multi-source (Notion/Sheet/GSC/slug).
                        if not ytg_guide_id:
                            resolved_kw = row.main_keyword
                            if not resolved_kw:
                                try:
                                    from scripts.audit.keyword_resolver import KeywordResolver
                                    resolved_kw, kw_src = KeywordResolver().resolve(
                                        row.site_slug, url=row.blogpost_url
                                    )
                                    if resolved_kw:
                                        logger.info(
                                            f"[STEP 5.6] main_keyword résolu '{resolved_kw}' "
                                            f"(source={kw_src})"
                                        )
                                except Exception as _kw_err:
                                    logger.warning(f"[STEP 5.6] résolution KW échouée: {_kw_err}")
                            ytg_result = self._fetch_ytg_guide(resolved_kw, {})
                            if ytg_result:
                                ytg_guide_id = ytg_result.guide_id
                                ytg_targets = {
                                    "top3_soseo": ytg_result.top3_soseo,
                                    "top3_dseo": ytg_result.top3_dseo,
                                    "top10_soseo": ytg_result.top10_soseo,
                                    "top10_dseo": ytg_result.top10_dseo,
                                }

                        if ytg_guide_id:
                            # Extract text from HTML for YTG analysis
                            from bs4 import BeautifulSoup
                            soup_ytg = BeautifulSoup(refreshed_html, "html.parser")
                            text_content = soup_ytg.get_text(separator=" ", strip=True)

                            # Analyze content against YTG guide
                            analysis = self.ytg_analyzer.analyze_content(ytg_guide_id, text_content)
                            if analysis:
                                our_soseo = analysis.get("our_soseo", 0)
                                our_dseo = analysis.get("our_dseo", 0)
                                top3_soseo = ytg_targets.get("top3_soseo", 0)
                                top3_dseo = ytg_targets.get("top3_dseo", 0)

                                ytg_post_scores = {
                                    "our_soseo": our_soseo,
                                    "our_dseo": our_dseo,
                                    "top3_soseo": top3_soseo,
                                    "top3_dseo": top3_dseo,
                                    "ytg_guide_id": ytg_guide_id,
                                }

                                # Log results + verdict structuré (OPTIMAL / NEEDS_FIX)
                                soseo_ok = our_soseo >= top3_soseo if top3_soseo else True
                                dseo_ok = our_dseo <= top3_dseo if top3_dseo else True

                                if soseo_ok and dseo_ok:
                                    ytg_verdict = "OPTIMAL"
                                    logger.info(
                                        f"[STEP 5.6] YTG OPTIMAL — SOSEO: {our_soseo:.0f}% "
                                        f"(cible TOP3: {top3_soseo:.0f}%) | "
                                        f"DSEO: {our_dseo:.0f}% (cible TOP3: {top3_dseo:.0f}%)"
                                    )
                                else:
                                    ytg_verdict = "NEEDS_FIX"
                                    warnings = []
                                    if not soseo_ok:
                                        warnings.append(
                                            f"SOSEO {our_soseo:.0f}% < TOP3 {top3_soseo:.0f}%"
                                        )
                                    if not dseo_ok:
                                        warnings.append(
                                            f"DSEO {our_dseo:.0f}% > TOP3 {top3_dseo:.0f}%"
                                        )
                                    logger.warning(
                                        f"[STEP 5.6] YTG WARNING — {' | '.join(warnings)} "
                                        f"— {row.blogpost_url[:60]}"
                                    )

                                ytg_post_scores["verdict"] = ytg_verdict
                                ytg_post_scores["soseo_ok"] = soseo_ok
                                ytg_post_scores["dseo_ok"] = dseo_ok

                                # Gate optionnel (config blog ytg.gate) : si le contenu
                                # n'est pas OPTIMAL, ne pas marquer DONE → à revoir avant WP.
                                if ytg_verdict != "OPTIMAL" and self._ytg_gate_enabled(site_slug):
                                    ytg_gate_block = True
                                    logger.warning(
                                        f"[STEP 5.6] YTG GATE actif ({site_slug}) — "
                                        f"{row.blogpost_url[:60]} passe en révision (pas DONE)"
                                    )

                                # Persist scores in context audit_data.json for traceability
                                if audit_data_path.exists():
                                    try:
                                        with open(audit_data_path, encoding="utf-8") as f:
                                            persist_data = json.load(f)
                                        persist_data["ytg_post_validation"] = ytg_post_scores
                                        with open(audit_data_path, "w", encoding="utf-8") as f:
                                            json.dump(persist_data, f, ensure_ascii=False, indent=2)
                                    except Exception:
                                        pass
                        else:
                            logger.debug(f"[STEP 5.6] YTG skipped: no guide for '{row.main_keyword[:40]}'")
                except Exception as ytg_err:
                    logger.warning(f"[STEP 5.6] YTG post-validation non-blocking error: {ytg_err}")

                # STEP 7: Mark as done (REFONTE Feb 2026: unified status)
                # Gate YTG : si actif et contenu sous-optimisé → révision, pas DONE.
                new_status = "NEEDS_REVIEW" if ytg_gate_block else "DONE"

                # STEP 8: Update sheet (refresh_date Avis/Versus — seul flux batch câblé)
                update_ok = self.sheets_client.update_refresh_status_enseigna(
                    url=row.blogpost_url,
                    refresh_date=datetime.now().strftime("%Y-%m-%d"),
                )
                if not update_ok:
                    logger.error(f"[STEP 8] ÉCHEC écriture Avis/Versus (refresh_date) pour {row.blogpost_url[:60]}")
                else:
                    logger.info(f"[STEP 8] ✓ Avis/Versus mis à jour: refresh_date écrit pour {row.blogpost_url[:60]}")

                # STEP 9: Log to Notion refresh tracker (non-blocking)
                try:
                    notion_db_id = self._get_notion_refresh_tracker_db_id()
                    if notion_db_id:
                        if not self.notion_client:
                            from scripts.notion.notion_client import NotionClient
                            self.notion_client = NotionClient()
                        if self.notion_client.is_configured:
                            # Déterminer le statut d'indexation depuis le diagnostic GSC
                            _indexed = "NO"
                            if row.index_diagnostic:
                                try:
                                    import json as _json
                                    _diag = _json.loads(row.index_diagnostic) if isinstance(row.index_diagnostic, str) else row.index_diagnostic
                                    if _diag.get("scenario") == "INDEXED" or _diag.get("verdict") == "PASS":
                                        _indexed = "YES"
                                except Exception:
                                    pass

                            notion_result = self.notion_client.log_refresh(
                                database_id=notion_db_id,
                                title=refreshed_titles.get("new_h1_title") or row.title or "Sans titre",
                                url=row.blogpost_url,
                                strategy=action,
                                site_slug=row.site_slug,
                                impressions=row.impressions_30d,
                                clicks=row.clicks_30d,
                                indexed=_indexed,
                            )
                            if notion_result:
                                logger.info(f"[STEP 9] ✓ Notion refresh tracker updated for {row.blogpost_url[:60]}")
                            else:
                                logger.warning(f"[STEP 9] Notion create_page returned None for {row.blogpost_url[:60]}")
                except Exception as notion_err:
                    logger.warning(f"[STEP 9] Notion logging failed (non-blocking): {notion_err}")

                results["success"] += 1
                if assets_restored > 0:
                    results["assets_restored"] += assets_restored

            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)[:100]
                results["errors"].append(error_msg)
                logger.error(f"[batch_refresh] Exception pour {row.blogpost_url[:60]}: {error_msg}")
                # Pas de refresh_date écrit en cas d'échec : la ligne Avis/Versus
                # reste éligible au prochain run.
                logger.info(f"[batch_refresh] pas de refresh_date écrit (échec) pour {row.blogpost_url[:60]}")

        return results

