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
from _shared.core.models.audit_models import EditorialAuditResult
from _shared.core.utils.timing import OperationTimer, timed

# Imports des modules internes
from ..audit import AuditEngine, GSCAnalyzer, SERPAnalyzer, HTMLAnalyzer, EditorialAuditor
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

    # Mapping blog_id (or domain) → semantic category for SemanticChecker
    BLOG_CATEGORY_MAP = {
        "enseigna": "education",
        "enseigna.fr": "education",
        "superprof-ressources": "education",
        "superprof-ressources.fr": "education",
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

        # Résolveur de chemins par tenant (point unique — Phase 4)
        from _shared.core.tenant_paths import TenantPaths
        self._tenant_paths = TenantPaths(base_path=self.base_path)

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

        # Editorial auditor pour quality gate (étape 1.5)
        editorial_rules_path = self.base_path / "_shared" / "config" / "editorial_rules.json"
        self.editorial_auditor = EditorialAuditor(editorial_rules_path)

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

        # Load sites.json for blog_id mapping (domain → id)
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

    def _normalize_blog_id(self, blog_id: str) -> str:
        """
        Normalise un blog_id pour obtenir le nom correct du fichier de configuration.

        Exemple: "enseigna.fr" → "enseigna"

        Args:
            blog_id: ID du blog (peut être domain ou id)

        Returns:
            ID normalisé pour les noms de fichiers
        """
        # Si le blog_id est un domain, le mapper vers l'id
        if blog_id in self._sites_config:
            return self._sites_config[blog_id]
        # Sinon, retourner tel quel
        return blog_id

    def _get_audit_engine(self, blog_id: str) -> AuditEngine:
        """Récupère ou crée un AuditEngine pour un blog."""
        if blog_id not in self._blog_engines:
            # Normalize blog_id to get correct config
            normalized_blog_id = self._normalize_blog_id(blog_id)
            blog_config = self.doc_cache.get_blog_config(normalized_blog_id)
            self._blog_engines[blog_id] = AuditEngine(blog_config)
        return self._blog_engines[blog_id]

    def _get_gsc_analyzer(self, blog_id: str) -> GSCAnalyzer:
        """Récupère ou crée un GSCAnalyzer pour un blog."""
        if blog_id not in self._gsc_analyzers:
            # Normalize blog_id to get correct config
            normalized_blog_id = self._normalize_blog_id(blog_id)
            blog_config = self.doc_cache.get_blog_config(normalized_blog_id)
            gsc_property = blog_config.get("gsc_property", "")
            self._gsc_analyzers[blog_id] = GSCAnalyzer(gsc_property)
        return self._gsc_analyzers[blog_id]

    def _get_serp_analyzer(self, blog_id: str) -> SERPAnalyzer:
        """Récupère ou crée un SERPAnalyzer pour un blog."""
        if blog_id not in self._serp_analyzers:
            # SERPAnalyzer est agnostic au blog, on crée juste une instance
            self._serp_analyzers[blog_id] = SERPAnalyzer()
        return self._serp_analyzers[blog_id]

    def _get_wp_api_client(self, blog_id: str) -> Optional[WordPressAPIClient]:
        """
        Retourne un WordPressAPIClient pour ce blog, ou None si non configuré.

        Lit wp_api_config dans _shared/config/blogs/{blog_id}.json.
        Le client est instancié une seule fois par blog_id (cache).
        """
        if blog_id in self._wp_api_clients:
            return self._wp_api_clients[blog_id]

        config_path = self._tenant_paths.blog_config(blog_id)
        client = None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                blog_config = json.load(f)

            wp_cfg = blog_config.get("wp_api_config")
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
                f"wp_api_config invalid for {blog_id}: {e}"
            )

        self._wp_api_clients[blog_id] = client
        return client

    def _fetch_html(self, url: str, blog_id: str = "") -> dict:
        """
        Récupère le contenu HTML d'une URL.

        Priorité :
        1. WordPress REST API (si wp_api_config présent dans la config du blog)
        2. Fallback : HTTP direct + ContentExtractor (scraping page publique)

        Args:
            url: URL de l'article
            blog_id: ID du blog pour sélection client WP API et temp cache

        Returns:
            {
                "full_html": str,              # HTML du contenu (rendu ou page complète)
                "clean_body": str,             # Corps d'article extrait
                "extraction_metadata": dict,   # Méthode utilisée, stats, wp_post_id si API
                "assets_baseline": dict        # Counts pour Rule of Gold
            }
        """
        logger = logging.getLogger("RefreshOrchestrator")

        # Resolve blog_id to domain for OutputManager (expects "enseigna.fr" not "enseigna")
        output_site_id = blog_id
        if blog_id and "." not in blog_id:
            for domain, sid in self._sites_config.items():
                if sid == blog_id and "." in domain:
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
        wp_client = self._get_wp_api_client(blog_id)
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
                full_html, output_site_id or blog_id, url=url
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

    def _extract_content_metrics(self, html_or_extraction: any, url: str, blog_id: str) -> dict:
        """
        Extrait les métriques de contenu (word count, images, liens internes).

        Compatible avec:
        - Ancien format: html (str) - extrait métriques via HTMLAnalyzer
        - Nouveau format: extraction result (dict) - utilise assets_baseline

        Args:
            html_or_extraction: Contenu HTML (str) OU résultat d'extraction (dict)
            url: URL de l'article
            blog_id: ID du blog

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

            blog_config = self.doc_cache.get_blog_config(blog_id)
            domain = blog_config.get("domain", "")

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
        blog_id: str,
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
            blog_id: Identifiant du blog
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
            # STEP 1.5: EDITORIAL AUDIT (Quality Gate)
            # =========================================================
            # Update status in spreadsheet
            if self.sheets_client:
                with timed(timer, "sheets_write"):
                    self.sheets_client.update_refresh_status(url, "AUDITING")

            editorial_result = self._run_editorial_audit(url, html_content, blog_id)

            # Si l'audit éditorial bloque, terminer ici
            if editorial_result and not editorial_result.should_proceed:
                if self.workflow_tracker:
                    self.workflow_tracker.complete_workflow(url, success=False)

                # Générer l'URL du rapport (path relatif pour Sheets)
                url_slug = re.sub(r'[^a-z0-9]+', '_', url.lower()).strip('_')
                report_relative_url = f"tenants/{blog_id}/outputs/editorial_audits/{url_slug}_editorial_audit.md"

                # Log dans Sheets si disponible
                if self.sheets_client:
                    with timed(timer, "sheets_write"):
                        self.sheets_client.log_editorial_audit(
                            url=url,
                            score=editorial_result.overall_score,
                            verdict="BLOCKED",
                            blocking_issues_count=len(editorial_result.blocking_issues),
                            blocking_issues="; ".join(editorial_result.blocking_issues[:3]),
                            report_url=report_relative_url
                        )

                if timer is not None:
                    timer.success = False
                    timer.errors.append("BLOCKED_QUALITY_ISSUES")
                return RefreshWorkflowResult(
                    url=url,
                    blog_id=blog_id,
                    success=False,
                    action_taken="BLOCKED_QUALITY_ISSUES",
                    audit_score=0,
                    rewrite_type=None,
                    new_title=None,
                    new_meta=None,
                    assets_valid=False,
                    errors=[f"Editorial audit blocked: {', '.join(editorial_result.blocking_issues[:2])}"],
                    execution_time_seconds=(datetime.now() - start_time).total_seconds(),
                )

            # Si l'audit passe, continuer avec STEP 2
            if editorial_result and self.sheets_client:
                verdict = "PASSED" if editorial_result.overall_score >= 7.0 else "REVIEW_REQUIRED"
                url_slug = re.sub(r'[^a-z0-9]+', '_', url.lower()).strip('_')
                report_relative_url = f"tenants/{blog_id}/outputs/editorial_audits/{url_slug}_editorial_audit.md"

                with timed(timer, "sheets_write"):
                    self.sheets_client.log_editorial_audit(
                        url=url,
                        score=editorial_result.overall_score,
                        verdict=verdict,
                        blocking_issues_count=len(editorial_result.blocking_issues),
                        blocking_issues="",
                        report_url=report_relative_url
                    )

            # =========================================================
            # STEP 2: AUDIT
            # =========================================================
            # Update status in spreadsheet
            if self.sheets_client:
                with timed(timer, "sheets_write"):
                    self.sheets_client.update_refresh_status(url, "AUDITING")

            audit_engine = self._get_audit_engine(blog_id)
            with timed(timer, "gsc_fetch"):
                audit_report = audit_engine.full_audit(url, html_content, provided_keyword=provided_keyword)
            audit_dict = audit_engine.to_dict(audit_report)
            # Inject semantic category for ghostwriter semantic field loading
            audit_dict["category"] = self.BLOG_CATEGORY_MAP.get(blog_id, "")

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
                        main_kw, _kw_src = KeywordResolver().resolve(blog_id, url=url)
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
            # Update status in spreadsheet
            if self.sheets_client:
                with timed(timer, "sheets_write"):
                    self.sheets_client.update_refresh_status(url, "AUDITING")

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
                # Log la décision
                with timed(timer, "sheets_write"):
                    self.sheets_client.log_decision(
                        url=url,
                        rules_triggered=decision_result.get("rules_triggered", []),
                        primary_action=primary_action,
                        rewrite_scope=decision_result.get("rewrite_scope", ""),
                        estimated_tokens=decision_result.get("estimated_tokens", 0),
                        prompt_template=decision_result.get("prompt_template", ""),
                    )

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

                    # Loger l'audit dans Sheets
                    with timed(timer, "sheets_write"):
                        self.sheets_client.log_audit(audit_row)

            # Update colonne G (action_blogpost) in spreadsheet
            if self.sheets_client:
                action_blogpost = map_action_to_blogpost(primary_action)
                assets = audit_dict.get("assets", {})
                images = assets.get("images", [])
                internal_links = assets.get("internal_links", [])
                content_metrics = {
                    "word_count_before": audit_dict.get("word_count", 0),
                    "images_count": len(images) if isinstance(images, list) else images,
                    "internal_links_count": len(internal_links) if isinstance(internal_links, list) else internal_links,
                }
                cannibalization_data = {
                    "flag": False,
                    "urls": "",
                }
                with timed(timer, "sheets_write"):
                    self.sheets_client.update_decision(
                        url=url,
                        action_blogpost=action_blogpost,
                        content_metrics=content_metrics,
                        cannibalization=cannibalization_data,
                    )

            # Si NO_ACTION ou DATA_COLLECTION_REQUIRED, terminer ici
            if primary_action in ("NO_ACTION", "DATA_COLLECTION_REQUIRED"):
                if self.workflow_tracker:
                    self.workflow_tracker.complete_workflow(url, success=True)

                return RefreshWorkflowResult(
                    url=url,
                    blog_id=blog_id,
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

            # Si REDIRECT_301, signaler et terminer
            if primary_action == "REDIRECT_301":
                if self.sheets_client:
                    with timed(timer, "sheets_write"):
                        self.sheets_client.set_action_required(
                            url,
                            audit_report.cannibalization.suggested_action
                        )

                if self.workflow_tracker:
                    self.workflow_tracker.complete_workflow(url, success=True)

                return RefreshWorkflowResult(
                    url=url,
                    blog_id=blog_id,
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
                notion_db_id = self._get_notion_commandes_db_id(blog_id)
                if notion_db_id:
                    if not self.notion_client:
                        self.notion_client = NotionClient()
                    if self.notion_client.is_configured:
                        commandes = self.notion_client.get_commandes(
                            database_id=notion_db_id,
                            blog_id=blog_id,
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
            # Update status in spreadsheet
            if self.sheets_client:
                with timed(timer, "sheets_write"):
                    self.sheets_client.update_refresh_status(url, "AUDITING")

            # Configurer la stratégie
            prompts_path = self.base_path / "_shared" / "config" / "prompts_dispatch.json"
            blog_config = self.doc_cache.get_blog_config(blog_id)
            strategy_selector = StrategySelector(prompts_path, blog_config)

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

            # Update status to TODO (not DONE yet - text not generated)
            # DONE will be set by batch_refresh() after LLM call
            if self.sheets_client:
                with timed(timer, "sheets_write"):
                    self.sheets_client.update_refresh_status(url, "TODO")

            return RefreshWorkflowResult(
                url=url,
                blog_id=blog_id,
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
            )

        except Exception as e:
            import traceback
            error_msg = str(e)
            errors.append(error_msg)
            logger.error(f"FULL EXCEPTION TRACEBACK:\n{traceback.format_exc()}")

            if self.workflow_tracker:
                self.workflow_tracker.record_error(url, error_msg)
                self.workflow_tracker.complete_workflow(url, success=False)

            # Update status to FAILED in spreadsheet
            if self.sheets_client:
                with timed(timer, "sheets_write"):
                    self.sheets_client.update_refresh_status(url, "BLOCKED")

            if timer is not None:
                timer.success = False
                timer.errors.append(str(error_msg)[:200])

            return RefreshWorkflowResult(
                url=url,
                blog_id=blog_id,
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

    def _ytg_gate_enabled(self, blog_id: str) -> bool:
        """Lit ytg.gate depuis _shared/config/blogs/{blog_id}.json (défaut: False)."""
        try:
            cfg_path = self._tenant_paths.blog_config(blog_id)
            if not cfg_path.exists():
                return False
            with open(cfg_path, encoding="utf-8") as f:
                return bool(json.load(f).get("ytg", {}).get("gate", False))
        except Exception:
            return False

    def _get_notion_commandes_db_id(self, blog_id: str) -> Optional[str]:
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
            if site.get("id") == blog_id:
                return site.get("notion_commandes_db_id") or None
        return None

    # =========================================================================
    # NEW: v2.0 Single-Sheet Architecture Batch Operations
    # =========================================================================

    def batch_editorial_audit(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> dict:
        """
        Batch editorial audit pour lignes où editorial_verdict est vide.

        Updates:
        - Columns Y-AC: Editorial audit results
        - Column H: status (if BLOCKED)
        - Column W: error_message (if BLOCKED)

        Args:
            blog_id: Filter by blog_id (optional)
            post_type: Filter by post_type - "CHILD", "PARENT", "STANDALONE" (optional)

        Returns:
            {
                "processed": int,
                "passed": int,
                "blocked": int,
                "review_required": int,
                "failed": int,
                "errors": list[str]
            }
        """
        if not self.sheets_client:
            return {"processed": 0, "passed": 0, "blocked": 0, "review_required": 0, "failed": 0, "errors": ["No sheets client"]}

        # Read rows where editorial audit not done yet
        rows = self.sheets_client.read_pending_for_editorial_audit(blog_id)

        # Filter by post_type if specified
        if post_type:
            rows = [r for r in rows if r.post_type == post_type]

        results = {
            "processed": 0,
            "passed": 0,
            "blocked": 0,
            "review_required": 0,
            "failed": 0,
            "errors": []
        }

        for idx, row in enumerate(rows):
            results["processed"] += 1

            try:
                # STEP 1: Fetch HTML content (autonomous scraping)
                extraction_result = self._fetch_html(row.blogpost_url, row.blog_id)
                if not extraction_result.get("clean_body"):
                    raise ValueError(f"Failed to fetch HTML for {row.blogpost_url}")

                # STEP 2: Run editorial audit
                editorial_result = self.editorial_auditor.audit(
                    url=row.blogpost_url,
                    html_content=extraction_result["clean_body"],
                    blog_id=row.blog_id,
                    use_llm_verification=False  # Tier 2 LLM not implemented yet
                )

                # STEP 3: Generate markdown report
                report_md = self.editorial_auditor.generate_markdown_report(editorial_result)

                # STEP 4: Save report
                url_slug = re.sub(r'[^a-z0-9]+', '_', row.blogpost_url.lower()).strip('_')
                self.output_mgr.save_editorial_audit(row.blog_id, url_slug, report_md)

                # STEP 5: Determine verdict
                if not editorial_result.should_proceed:
                    verdict = "BLOCKED"
                    results["blocked"] += 1
                elif editorial_result.overall_score >= 7.0:
                    verdict = "PASSED"
                    results["passed"] += 1
                else:
                    verdict = "REVIEW_REQUIRED"
                    results["review_required"] += 1

                # STEP 6: Log to spreadsheet (columns X-AB)
                report_relative_url = f"tenants/{row.blog_id}/outputs/editorial_audits/{url_slug}_editorial_audit.md"

                self.sheets_client.log_editorial_audit(
                    url=row.blogpost_url,
                    score=editorial_result.overall_score,
                    verdict=verdict,
                    blocking_issues_count=len(editorial_result.blocking_issues),
                    blocking_issues="; ".join(editorial_result.blocking_issues[:3]),
                    report_url=report_relative_url
                )

                print(f"[EDITORIAL] {row.blogpost_url[:50]} → {verdict} ({editorial_result.overall_score:.1f}/10)")

            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)[:50]
                results["errors"].append(error_msg)
                print(f"[ERROR] Editorial audit failed for {row.blogpost_url[:50]}: {error_msg}")

            # Rate limiting: pause between processing
            if idx < len(rows) - 1:
                time.sleep(0.5)  # 0.5 seconds pause

        return results

    def batch_keyword_discovery(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> dict:
        """
        STEP 0: Keyword Discovery — Remplit main_keyword (col D) pour les URLs où il est vide.

        Cascade de sources:
        1. DataForSEO ranked_keywords (top keyword par volume de recherche)
        2. GSC (top keyword par impressions)
        3. Extraction heuristique du slug URL (dernier recours)

        Args:
            blog_id: Filter by blog_id (optional)
            post_type: Filter by post_type (optional)

        Returns:
            {"processed": int, "dataforseo": int, "gsc": int, "slug": int, "failed": int, "errors": list}
        """
        if not self.sheets_client:
            return {"processed": 0, "dataforseo": 0, "gsc": 0, "slug": 0, "failed": 0, "errors": ["No sheets client"]}

        rows = self.sheets_client.read_rows_missing_keyword(blog_id)

        logger = logging.getLogger("RefreshOrchestrator")

        if post_type:
            rows = [r for r in rows if r.post_type == post_type]

        results = {
            "processed": 0,
            "dataforseo": 0,
            "gsc": 0,
            "slug": 0,
            "failed": 0,
            "errors": []
        }

        for idx, row in enumerate(rows):
            results["processed"] += 1
            keyword = None
            source = None

            try:
                # === SOURCE 1: DataForSEO ranked_keywords ===
                serp_analyzer = self._get_serp_analyzer(row.blog_id)
                dfs_result = serp_analyzer.discover_main_keyword(row.blogpost_url)
                if dfs_result and dfs_result.get("keyword"):
                    keyword = dfs_result["keyword"]
                    source = "dataforseo"
                    vol = dfs_result.get("search_volume", 0)
                    pos = dfs_result.get("position", 0)
                    logger.info(f"[STEP 0] DataForSEO: '{keyword}' (vol={vol}, pos={pos}) for {row.blogpost_url[:60]}")

                # === SOURCE 2: GSC top keyword par impressions ===
                # Use lightweight _fetch_performance_direct instead of full analyze()
                if not keyword:
                    try:
                        gsc_analyzer = self._get_gsc_analyzer(row.blog_id)
                        perf = gsc_analyzer._fetch_performance_direct(row.blogpost_url)
                        if perf and perf.main_keyword:
                            keyword = perf.main_keyword
                            source = "gsc"
                            logger.info(f"[STEP 0] GSC: '{keyword}' for {row.blogpost_url[:60]}")
                    except Exception as gsc_err:
                        logger.warning(f"[STEP 0] GSC fallback failed for {row.blogpost_url[:60]}: {gsc_err}")

                # === SOURCE 3: DataForSEO keyword_suggestions (slug as seed) ===
                slug_seed = self._keyword_from_slug(row.blogpost_url)
                if not keyword and slug_seed:
                    try:
                        suggest_result = serp_analyzer.suggest_keyword_from_seed(slug_seed)
                        if suggest_result and suggest_result.get("keyword"):
                            keyword = suggest_result["keyword"]
                            source = "dataforseo"
                            vol = suggest_result.get("search_volume", 0)
                            logger.info(f"[STEP 0] KW Suggestions: '{keyword}' (vol={vol}) from seed '{slug_seed}' for {row.blogpost_url[:60]}")
                    except Exception as suggest_err:
                        logger.warning(f"[STEP 0] KW Suggestions failed for seed '{slug_seed}': {suggest_err}")

                # === SOURCE 3.5: DataForSEO related_keywords (termes connexes plus larges) ===
                if not keyword and slug_seed:
                    try:
                        broader_result = serp_analyzer.find_broader_keyword(slug_seed)
                        if broader_result and broader_result.get("keyword"):
                            keyword = broader_result["keyword"]
                            source = "dataforseo"
                            vol = broader_result.get("search_volume", 0)
                            logger.info(f"[STEP 0] Related KW: '{keyword}' (vol={vol}) from seed '{slug_seed}' for {row.blogpost_url[:60]}")
                    except Exception as broader_err:
                        logger.warning(f"[STEP 0] Related KW failed for seed '{slug_seed}': {broader_err}")

                # === SOURCE 4: Slug brut (dernier recours) ===
                if not keyword:
                    keyword = self._keyword_from_slug(row.blogpost_url)
                    if keyword:
                        source = "slug"
                        logger.info(f"[STEP 0] Slug (fallback): '{keyword}' for {row.blogpost_url[:60]}")

                # === Écriture en spreadsheet ===
                if keyword and source:
                    self.sheets_client.update_main_keyword(
                        url=row.blogpost_url,
                        keyword=keyword,
                        source=source
                    )
                    results[source] += 1

                    # Si le status était BLOCKED à cause du keyword manquant, le remettre à vide
                    if row.status == "BLOCKED" and row.error_message and "main_keyword is required" in row.error_message:
                        self.sheets_client._update_cell(
                            self.sheets_client.SHEET_REFRESHS_AUDIT,
                            f"H{row.row_index}", ""
                        )
                        self.sheets_client._update_cell(
                            self.sheets_client.SHEET_REFRESHS_AUDIT,
                            f"W{row.row_index}", ""
                        )
                        logger.info(f"[STEP 0] Reset BLOCKED status for {row.blogpost_url[:60]}")
                else:
                    results["failed"] += 1
                    results["errors"].append(f"No keyword found: {row.blogpost_url[:60]}")

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{row.blogpost_url[:50]}: {str(e)[:50]}")

            # Rate limiting
            if idx < len(rows) - 1:
                time.sleep(1.0)

        logger.info(
            f"[STEP 0] Keyword Discovery: {results['processed']} processed, "
            f"{results['dataforseo']} DataForSEO, {results['gsc']} GSC, "
            f"{results['slug']} slug, {results['failed']} failed"
        )
        return results

    def batch_keyword_re_discovery(
        self,
        min_volume: int = 10,
        blog_id: Optional[str] = None,
        post_type: Optional[str] = None,
    ) -> dict:
        """
        Re-vérifie le volume des keywords existants et les remplace si volume < min_volume.

        Pour chaque ligne avec un main_keyword déjà rempli :
        1. Vérifie le volume actuel via DataForSEO keyword_overview
        2. Si volume < min_volume, relance la cascade de découverte complète
        3. Met à jour le spreadsheet si un meilleur keyword est trouvé

        Args:
            min_volume: Seuil minimum de volume (défaut 50)
            blog_id: Filtrer par blog_id (optionnel)
            post_type: Filtrer par post_type (optionnel)

        Returns:
            {"processed": int, "low_volume": int, "updated": int, "unchanged": int, "errors": list}
        """
        if not self.sheets_client:
            return {"processed": 0, "low_volume": 0, "updated": 0, "unchanged": 0, "errors": ["No sheets client"]}

        rows = self.sheets_client.read_rows_with_keyword(blog_id)

        logger = logging.getLogger("RefreshOrchestrator")

        if post_type:
            rows = [r for r in rows if r.post_type == post_type]

        results = {
            "processed": 0,
            "low_volume": 0,
            "updated": 0,
            "unchanged": 0,
            "errors": [],
        }

        for idx, row in enumerate(rows):
            results["processed"] += 1
            current_kw = row.main_keyword.strip()

            try:
                serp_analyzer = self._get_serp_analyzer(row.blog_id)

                # Étape 1 : vérifier le volume du keyword existant
                current_volume = serp_analyzer.check_keyword_volume(current_kw)
                logger.info(f"[KW Refresh] '{current_kw}' vol={current_volume} for {row.blogpost_url[:60]}")

                if current_volume >= min_volume:
                    results["unchanged"] += 1
                    continue

                # Étape 2 : keyword sous le seuil → relancer la cascade
                results["low_volume"] += 1
                logger.info(f"[KW Refresh] Low volume ({current_volume} < {min_volume}), re-discovering for {row.blogpost_url[:60]}")

                new_keyword = None
                source = None

                # SOURCE 1 : ranked_keywords (filtre volume >= 50 intégré)
                dfs_result = serp_analyzer.discover_main_keyword(row.blogpost_url)
                if dfs_result and dfs_result.get("keyword") and dfs_result["keyword"] != current_kw:
                    new_keyword = dfs_result["keyword"]
                    source = "dataforseo"
                    logger.info(f"[KW Refresh] ranked_keywords: '{new_keyword}' (vol={dfs_result.get('search_volume', 0)})")

                # SOURCE 2 : GSC
                if not new_keyword:
                    try:
                        gsc_analyzer = self._get_gsc_analyzer(row.blog_id)
                        perf = gsc_analyzer._fetch_performance_direct(row.blogpost_url)
                        if perf and perf.main_keyword and perf.main_keyword != current_kw:
                            new_keyword = perf.main_keyword
                            source = "gsc"
                            logger.info(f"[KW Refresh] GSC: '{new_keyword}'")
                    except Exception:
                        pass

                # SOURCE 3 : keyword_suggestions depuis slug
                slug_seed = self._keyword_from_slug(row.blogpost_url)
                if not new_keyword and slug_seed:
                    suggest = serp_analyzer.suggest_keyword_from_seed(slug_seed)
                    if suggest and suggest.get("keyword") and suggest["keyword"] != current_kw:
                        new_keyword = suggest["keyword"]
                        source = "dataforseo"
                        logger.info(f"[KW Refresh] Suggestions: '{new_keyword}' (vol={suggest.get('search_volume', 0)})")

                # SOURCE 3.5 : related_keywords (termes connexes)
                if not new_keyword and slug_seed:
                    broader = serp_analyzer.find_broader_keyword(slug_seed, min_volume=min_volume)
                    if broader and broader.get("keyword") and broader["keyword"] != current_kw:
                        new_keyword = broader["keyword"]
                        source = "dataforseo"
                        logger.info(f"[KW Refresh] Related KW: '{new_keyword}' (vol={broader.get('search_volume', 0)})")

                if new_keyword and source:
                    self.sheets_client.update_main_keyword(
                        url=row.blogpost_url,
                        keyword=new_keyword,
                        source=source,
                    )
                    results["updated"] += 1
                    logger.info(f"[KW Refresh] Updated: '{current_kw}' → '{new_keyword}' for {row.blogpost_url[:60]}")
                else:
                    results["unchanged"] += 1
                    logger.info(f"[KW Refresh] No better keyword found, keeping '{current_kw}'")

            except Exception as e:
                results["errors"].append(f"{row.blogpost_url[:50]}: {str(e)[:50]}")

            if idx < len(rows) - 1:
                time.sleep(1.0)

        logger.info(
            f"[KW Refresh] Done: {results['processed']} processed, "
            f"{results['low_volume']} low-volume, {results['updated']} updated, "
            f"{results['unchanged']} unchanged"
        )
        return results

    # Stop words français à retirer des slugs pour créer des seeds pertinents
    _FR_STOP_WORDS = {
        "le", "la", "les", "l", "un", "une", "des", "du", "de", "d",
        "a", "au", "aux", "en", "et", "ou", "sur", "pour", "par", "avec",
        "dans", "est", "ce", "se", "son", "sa", "ses", "qui", "que", "qu",
        "ne", "pas", "plus", "tout", "tous", "mon", "ma", "mes", "nos", "votre",
        "quel", "quelle", "quels", "quelles", "quest", "comment", "pourquoi",
    }

    # Corrections d'accents fréquentes dans les slugs français
    _ACCENT_FIXES = {
        "debutant": "débutant", "debutants": "débutants", "debuter": "débuter",
        "ameliorer": "améliorer", "systeme": "système", "epaules": "épaules",
        "etirement": "étirement", "etirements": "étirements", "equilibre": "équilibre",
        "energie": "énergie", "regulier": "régulier", "seance": "séance",
        "securite": "sécurité", "methode": "méthode", "benefice": "bénéfice",
        "benefices": "bénéfices", "specifique": "spécifique", "premiere": "première",
        "americaine": "américaine", "americain": "américain",
        "velo": "vélo", "elliptique": "elliptique",
        "mathematiques": "mathématiques", "francais": "français",
        "scolaire": "scolaire", "scolaires": "scolaires",
        "difficulte": "difficulté", "qualite": "qualité",
        "materiel": "matériel", "ionien": "ionien",
        "therapie": "thérapie", "cereales": "céréales",
        "exercice": "exercice", "exercices": "exercices",
        "entrainement": "entraînement", "recuperation": "récupération",
        "lhistoire": "histoire", "langlais": "anglais",
    }

    @staticmethod
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

    def batch_audit_gsc(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> dict:
        """
        Batch audit GSC pour lignes where audit_gsc = AUDITING.

        Updates:
        - Column I: audit_gsc (AUDITING → DONE/FAILED)
        - Columns K-M: GSC metrics (impressions_30d, clicks_30d, ctr_30d)
        - Column W: error_message (if FAILED)

        Args:
            blog_id: Filter by blog_id (optional)
            post_type: Filter by post_type - "CHILD", "PARENT", "STANDALONE" (optional)

        Returns:
            {
                "processed": int,
                "success": int,
                "failed": int,
                "errors": list[str]
            }
        """
        if not self.sheets_client:
            return {"processed": 0, "success": 0, "failed": 0, "errors": ["No sheets client"]}

        # Ensure column W exists
        self.sheets_client.ensure_column_w_header()

        _gsc_logger = logging.getLogger("RefreshOrchestrator")

        # Read rows where audit_gsc = AUDITING
        rows = self.sheets_client.read_pending_for_gsc_audit(blog_id)

        # Filter by post_type if specified
        if post_type:
            rows = [r for r in rows if r.post_type == post_type]

        results = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "url_not_on_google": 0,
            "indexing_issues": 0,
            "discovered_not_indexed": 0,
            "errors": []
        }

        for idx, row in enumerate(rows):
            results["processed"] += 1

            try:
                gsc_analyzer = self._get_gsc_analyzer(row.blog_id)

                # Run GSC audit
                gsc_result = gsc_analyzer.analyze(row.blogpost_url)

                # Extract metrics from GSCAnalysisResult
                metrics = {}
                if gsc_result and gsc_result.performance:
                    perf = gsc_result.performance
                    metrics = {
                        "impressions_30d": int(perf.impressions_30d or 0),
                        "clicks_30d": int(perf.clicks_30d or 0),
                        "ctr_30d": float(perf.ctr_30d or 0.0),
                    }

                # NEW: Diagnostic d'indexation détaillé
                index_diagnostic = gsc_analyzer._check_indexation_detailed(
                    row.blogpost_url
                )

                # Incrémenter les compteurs par scénario
                scenario = index_diagnostic.get("scenario", "UNKNOWN")
                if scenario == "URL_NOT_ON_GOOGLE":
                    results["url_not_on_google"] += 1
                elif scenario == "INDEXING_ISSUE":
                    results["indexing_issues"] += 1
                elif scenario == "DISCOVERED_NOT_INDEXED":
                    results["discovered_not_indexed"] += 1

                # Sérialiser en JSON pour stockage
                import json
                index_diagnostic_json = json.dumps(index_diagnostic, ensure_ascii=False)

                # Update sheet
                self.sheets_client.update_audit_gsc(
                    url=row.blogpost_url,
                    status="DONE",
                    metrics=metrics,
                    index_diagnostic=index_diagnostic_json
                )
                results["success"] += 1

            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)[:50]  # Truncate error message
                results["errors"].append(error_msg)
                # Update sheet with error
                self.sheets_client.update_audit_gsc(
                    url=row.blogpost_url,
                    status="FAILED",
                    error_message=error_msg
                )

            # Rate limiting: pause between API calls to respect quotas
            if idx < len(rows) - 1:
                time.sleep(2.0)  # 2 seconds pause (URL Inspection API quota protection)

        # Afficher les statistiques de diagnostic
        print(f"\n[DIAGNOSTIC] Index statistics:")
        print(f"  - URLs not in Google index: {results['url_not_on_google']}")
        print(f"  - URLs with indexing errors: {results['indexing_issues']}")
        print(f"  - Discovered but not indexed: {results['discovered_not_indexed']}")

        return results

    def batch_audit_serp(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> dict:
        """
        Batch audit SERP pour lignes where audit_serp = AUDITING.

        Updates:
        - Column J: audit_serp (AUDITING → DONE/FAILED)
        - Columns N-O: SERP data (people_also_ask, secondary_keywords)
        - Column W: error_message (if FAILED)

        Args:
            blog_id: Filter by blog_id (optional)
            post_type: Filter by post_type - "CHILD", "PARENT", "STANDALONE" (optional)

        Returns:
            {"processed": int, "success": int, "failed": int, "errors": list}
        """
        if not self.sheets_client:
            return {"processed": 0, "success": 0, "failed": 0, "errors": ["No sheets client"]}

        rows = self.sheets_client.read_pending_for_serp_audit(blog_id)

        # Filter by post_type if specified
        if post_type:
            rows = [r for r in rows if r.post_type == post_type]

        results = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }

        for idx, row in enumerate(rows):
            results["processed"] += 1

            try:
                serp_analyzer = self._get_serp_analyzer(row.blog_id)
                keyword = row.main_keyword.strip() if row.main_keyword else ""

                if not keyword:
                    raise ValueError(f"main_keyword is required for SERP analysis (URL: {row.blogpost_url[:50]})")

                # Run SERP audit
                serp_result = serp_analyzer.analyze(keyword, row.blog_id)

                # Extract data from SERPAnalysisResult
                paa_questions = []
                secondary_keywords = []

                # Vérifier que le résultat contient des données réelles
                has_data = (
                    serp_result
                    and (serp_result.paa_questions or serp_result.organic_results)
                )

                if has_data:
                    # Extract PAA questions
                    paa_questions = serp_result.paa_questions or []
                    # Extract secondary keywords from organic results
                    if serp_result.organic_results:
                        keywords_set = set()
                        for result in serp_result.organic_results[:10]:
                            if result.keywords:
                                keywords_set.update(result.keywords[:3])
                        secondary_keywords = list(keywords_set)[:10]
                else:
                    print(f"[SERP] ⚠ Résultat vide pour '{keyword}' — PAA et keywords seront vides")

                # Update sheet
                paa_str = ", ".join(paa_questions[:5])
                kw_str = ", ".join(secondary_keywords[:10])
                update_ok = self.sheets_client.update_audit_serp(
                    url=row.blogpost_url,
                    status="DONE",
                    serp_data={
                        "people_also_ask": paa_str,
                        "secondary_keywords": kw_str,
                    }
                )
                if not update_ok:
                    print(f"[SERP] ✗ ÉCHEC écriture spreadsheet N/O pour {row.blogpost_url[:60]}")
                elif paa_str:
                    print(f"[SERP] ✓ PAA écrites: {paa_str[:80]}")
                results["success"] += 1

            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)[:50]
                results["errors"].append(error_msg)
                self.sheets_client.update_audit_serp(
                    url=row.blogpost_url,
                    status="FAILED",
                    error_message=error_msg
                )

            # Rate limiting: pause between API calls to respect quotas
            if idx < len(rows) - 1:
                time.sleep(1.0)  # 1 second pause between DataforSEO API calls

        return results

    def batch_decision(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> dict:
        """
        Batch decision pour lignes where audit_gsc=DONE AND audit_serp=DONE.

        Updates:
        - Column G: action_blogpost (NO ACTION, PARTIAL REFRESH, REFRESH TITLES, FULL REFRESH)
        - Columns R-V: Content metrics + cannibalization

        Args:
            blog_id: Filter by blog_id (optional)
            post_type: Filter by post_type - "CHILD", "PARENT", "STANDALONE" (optional)

        Returns:
            {
                "processed": int,
                "no_action": int,
                "partial_refresh": int,
                "refresh_titles": int,
                "full_refresh": int,
                "errors": list
            }
        """
        if not self.sheets_client:
            return {"processed": 0, "no_action": 0, "partial_refresh": 0, "refresh_titles": 0, "full_refresh": 0, "errors": []}

        rows = self.sheets_client.read_pending_for_decision(blog_id)

        # Filter by post_type if specified
        if post_type:
            rows = [r for r in rows if r.post_type == post_type]

        results = {
            "processed": 0,
            "no_action": 0,
            "partial_refresh": 0,
            "refresh_titles": 0,
            "full_refresh": 0,
            "errors": []
        }

        for row in rows:
            results["processed"] += 1

            try:
                # SCRAPING OBLIGATOIRE: Fetch actual HTML content (NEW: autonomous scraping)
                extraction_result = self._fetch_html(row.blogpost_url, row.blog_id)
                if not extraction_result.get("clean_body"):
                    raise ValueError(f"Failed to fetch HTML for {row.blogpost_url}")

                # Extract real content metrics from scraped HTML (NEW: uses assets_baseline)
                content_metrics = self._extract_content_metrics(extraction_result, row.blogpost_url, row.blog_id)

                # Extract title from HTML (h1 tag)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(extraction_result.get("full_html", ""), 'html.parser')
                title_tag = soup.find('h1')
                extracted_title = title_tag.get_text(strip=True) if title_tag else ""

                # Run decision engine with all audit data + title for freshness check
                decision = self.decision_engine.evaluate({
                    "url": row.blogpost_url,
                    "title": extracted_title or row.title,  # Use extracted title or fallback to row title
                    "main_keyword": row.main_keyword,
                    "performance": {
                        "ctr_30d": row.ctr_30d,
                        "impressions_30d": row.impressions_30d,
                        "clicks_30d": row.clicks_30d,  # FIX: Ajouté clicks_30d manquant
                    },
                    "index_diagnostic": row.index_diagnostic,  # Pour règles d'indexation
                })

                # Map to action_blogpost
                action_blogpost = map_action_to_blogpost(decision.primary_action)

                # Update sheet (including title in column D)
                self.sheets_client.update_decision(
                    url=row.blogpost_url,
                    action_blogpost=action_blogpost,
                    content_metrics=content_metrics,
                    cannibalization={
                        "flag": row.cannibalization_flag,
                        "urls": row.cannibalization_urls,
                    },
                    title=extracted_title  # NEW: Write title to column D
                )

                # Count action type
                if action_blogpost == "NO ACTION":
                    results["no_action"] += 1
                elif action_blogpost == "PARTIAL REFRESH":
                    results["partial_refresh"] += 1
                elif action_blogpost == "REFRESH TITLES":
                    results["refresh_titles"] += 1
                elif action_blogpost == "FULL REFRESH":
                    results["full_refresh"] += 1

            except Exception as e:
                results["errors"].append(str(e)[:50])

        return results

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
            print(f"[AUTO-PROCESS] Action FULL_REFRESH détectée pour: {row.blogpost_url}")
            print(f"[AUTO-PROCESS] Préparation du contexte pour génération automatique...")

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

        # Save original HTML
        html_file = context_dir / "original.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(original_html)

        # Load guidelines
        seo_guidelines = self.doc_cache.get_combined_guidelines() or ""
        site_prompt = ""
        try:
            # Normalize blog_id to get correct file name (e.g., "enseigna.fr" → "enseigna")
            normalized_blog_id = self._normalize_blog_id(row.blog_id)
            site_prompt = self.doc_cache.get_prompt(f"sites/{normalized_blog_id}.md") or ""
        except:
            pass

        # Prepare audit data
        audit_data = {
            "blog_id": row.blog_id,
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
            "output_dir": f"tenants/{row.blog_id}/outputs",
            # Semantic field: category for SemanticChecker._load_semantic_field()
            "category": self.BLOG_CATEGORY_MAP.get(row.blog_id, ""),
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
            f.write(f"GUIDELINES SITE {row.blog_id}:\n{site_prompt[:1500]}\n")

        batch_folder = dated_batch_folder_name()
        html_subdir = f"html/{batch_folder}"

        # Build task instructions
        instructions = [
            "Lis le fichier original.html complet",
            "Lis les données d'audit dans audit_data.json",
            "Lis les guidelines dans guidelines.txt",
            "Génère le HTML optimisé en respectant la RÈGLE D'OR",
            f"Sauvegarde le résultat dans tenants/{row.blog_id}/outputs/{html_subdir}/{output_slug}_refreshed.html",
            f"Sauvegarde les métadonnées dans tenants/{row.blog_id}/outputs/metadata/{output_slug}_metadata.json",
        ]
        if row.blog_id == "superprof-ressources":
            refreshed_html_path = f"tenants/{row.blog_id}/outputs/{html_subdir}/{output_slug}_refreshed.html"
            instructions.append(
                f"Exécute en Bash depuis la racine du projet (extraction CSV des tableaux, "
                f"OBLIGATOIRE avant l'étape suivante, même si le rapport de génération dit "
                f"que les tableaux ont été traités) : "
                f".venv/bin/python content_writer.py batch extract-tables "
                f"--site-id {row.blog_id} --file {refreshed_html_path}"
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
                    "refreshed_html": f"tenants/{row.blog_id}/outputs/{html_subdir}/{output_slug}_refreshed.html",
                    "metadata": f"tenants/{row.blog_id}/outputs/metadata/{output_slug}_metadata.json"
                }
            },
            "instructions": instructions,
        }

        task_file = context_dir / "task.json"
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, indent=2, ensure_ascii=False)

        print(f"[INFO] [OK] Contexte préparé dans: {context_dir}")
        print(f"[INFO]   Fichiers créés:")
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
            outputs = self.output_mgr.get_output_files(row.blog_id, output_slug, title=row.title)
            refreshed_file = outputs["refreshed_html"]
            metadata_file = outputs["metadata"]

            print(f"\n{'='*70}")
            print(f"[CLAUDE CODE] TÂCHE PRÊTE POUR TRAITEMENT")
            print(f"{'='*70}")
            print(f"Contexte: {context_dir.absolute()}")
            print(f"\nClaude Code doit maintenant:")
            print(f"  1. Lire les fichiers du contexte")
            print(f"  2. Générer le contenu optimisé")
            print(f"  3. Sauvegarder dans:")
            print(f"     - {refreshed_file}")
            print(f"     - {metadata_file}")
            print(f"{'='*70}\n")

            # STEP 3: Check if output already exists (for retry/resume scenarios)
            if refreshed_file.exists() and metadata_file.exists():
                print(f"[INFO] [OK] Fichiers de sortie trouvés, lecture des résultats...")

                # Read refreshed HTML
                with open(refreshed_file, 'r', encoding='utf-8') as f:
                    refreshed_html = f.read()

                # Read metadata
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    output_metadata = json.load(f)

                optimized_title = output_metadata.get("title_optimized", row.title)

                print(f"[INFO] [OK] Contenu récupéré depuis outputs/:")
                print(f"      HTML: {refreshed_file}")
                print(f"      Metadata: {metadata_file}")

                return refreshed_html, optimized_title

            else:
                # Files don't exist yet - Claude Code needs to process
                # Check if we're in auto-process mode (FULL_REFRESH detected)
                if action == "FULL_REFRESH" or action == "FULL REFRESH":
                    print(f"[AUTO-PROCESS] Full Refresh détecté, contexte préparé")
                    print(f"[AUTO-PROCESS] Tâche prête dans: {context_dir}")
                    print(f"[AUTO-PROCESS] Les fichiers seront générés par Claude Code")
                    print(f"[AUTO-PROCESS] Workflow continue, génération en attente...")

                    # Return original HTML for now - content will be generated later by Claude Code
                    # This allows the batch workflow to continue without blocking
                    return original_html, row.title
                else:
                    # Non-FULL_REFRESH actions: raise exception to signal manual processing needed
                    print(f"[ATTENTE] Fichiers de sortie non trouvés.")
                    print(f"[ATTENTE] Claude Code doit traiter la tâche dans: {context_dir}")
                    print(f"[ATTENTE] Une fois terminé, relancer le script pour continuer.")
                    raise Exception(f"Claude Code processing required. Context prepared in: {context_dir}")

        except Exception as e:
            print(f"[ERROR] Erreur génération contenu: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            # Fallback: return original HTML
            return original_html, row.title

    def batch_title_optimization(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> dict:
        """
        Batch title optimization: génère new_h1_title (col P) et extrait H2s actuels (col Q).

        S'exécute APRÈS Decision et AVANT Refresh.
        Traite les URLs avec action_blogpost remplie ET new_h1_title (col P) vide.

        Args:
            blog_id: Filter by blog_id (optional)
            post_type: Filter by post_type (optional, for backwards compat)

        Returns:
            {"processed": int, "success": int, "failed": int, "errors": list}
        """
        import logging
        logger = logging.getLogger("RefreshOrchestrator")

        if not self.sheets_client:
            return {"processed": 0, "success": 0, "failed": 0, "errors": ["No sheets client"]}

        # Read all rows from spreadsheet
        data = self.sheets_client._read_sheet(self.sheets_client.SHEET_REFRESHS_AUDIT)

        from _shared.core.models import RefreshAuditRow

        results = {"processed": 0, "success": 0, "failed": 0, "errors": []}

        for i, row in enumerate(data[1:], start=2):
            if len(row) < 7:
                continue

            row_blog_id = row[0] if len(row) > 0 else ""
            row_post_type = row[5] if len(row) > 5 else ""
            action = row[6] if len(row) > 6 else ""
            current_h1 = row[15] if len(row) > 15 else ""

            # Filter: blog_id
            if blog_id and row_blog_id != blog_id:
                continue

            # Filter: post_type
            if post_type and row_post_type != post_type:
                continue

            # Filter: must have a decision AND col P must be empty
            if not action or action == "NO ACTION":
                continue
            if current_h1.strip():
                continue  # Already has new_h1_title

            url = row[2] if len(row) > 2 else ""
            keyword = row[3] if len(row) > 3 else ""
            title = row[4] if len(row) > 4 else ""

            results["processed"] += 1

            try:
                # STEP 1: Scrape HTML to extract current H2 structure
                extraction_result = self._fetch_html(url, row_blog_id)
                h2_titles_json = "[]"

                if extraction_result.get("clean_body"):
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(extraction_result["clean_body"], 'html.parser')
                    h2_list = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]
                    h2_titles_json = json.dumps(h2_list[:10], ensure_ascii=False)

                    # Use scraped H1 if title column is empty
                    if not title:
                        h1_tag = soup.find('h1')
                        if h1_tag:
                            title = h1_tag.get_text(strip=True)

                # STEP 2: Optimize H1 title
                gsc_metrics = None
                impressions = row[10] if len(row) > 10 else ""
                clicks = row[11] if len(row) > 11 else ""
                ctr = row[12] if len(row) > 12 else ""

                if impressions or clicks or ctr:
                    def safe_float(val):
                        if not val:
                            return 0.0
                        try:
                            return float(str(val).replace(",", "."))
                        except (ValueError, TypeError):
                            return 0.0

                    gsc_metrics = {
                        "impressions": safe_float(impressions),
                        "clicks": safe_float(clicks),
                        "ctr": safe_float(ctr),
                    }

                optimized_title = self.title_optimizer.optimize_title(
                    original_title=title,
                    main_keyword=keyword,
                    blog_id=row_blog_id,
                    post_type=row_post_type,
                    gsc_metrics=gsc_metrics,
                )

                # STEP 3: Write to spreadsheet (O = new_h1_title, P = H2 structure)
                self.sheets_client.update_refresh_status(
                    url=url,
                    status=row[7] if len(row) > 7 else "TODO",  # Keep current status
                    new_titles={
                        "new_h1_title": optimized_title,
                        "new_h2_titles": h2_titles_json,
                    }
                )

                results["success"] += 1
                logger.info(f"[TITLE] {url[:50]} → \"{optimized_title[:60]}\"")

            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)[:80]
                results["errors"].append(error_msg)
                logger.error(f"[TITLE] Error for {url[:50]}: {error_msg}")

            # Rate limiting
            if results["processed"] < 100:
                time.sleep(0.3)

        return results

    def _enseigna_rows_for_refresh(self, action: str) -> list:
        """
        Adapte les EnseignaAvisRow (onglets Avis/Versus réels) à l'interface
        attendue par la boucle de `batch_refresh` (row.blog_id, row.title, etc.),
        sans dupliquer la logique de génération/validation qui suit.
        """
        @dataclass
        class _EnseignaRefreshRow:
            blog_id: str = "enseigna"
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

    def batch_refresh(self, action: str, blog_id: Optional[str] = None, post_type: Optional[str] = None, limit: Optional[int] = None) -> dict:
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
            blog_id: Filter by blog_id (optional)
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

        # Enseigna n'a pas d'onglet Refreshs_Audit (architecture V2) — router vers
        # les onglets réels Avis/Versus via l'adaptateur dédié.
        if blog_id == "enseigna":
            rows = self._enseigna_rows_for_refresh(action)
        else:
            rows = self.sheets_client.read_pending_for_refresh(action, blog_id)

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
                extraction_result = self._fetch_html(row.blogpost_url, row.blog_id)
                if not extraction_result.get("clean_body"):
                    raise ValueError(f"Failed to fetch HTML for {row.blogpost_url}")

                # STEP 2: Extract original assets (BASELINE FOR RULE OF GOLD)
                original_metrics = self._extract_content_metrics(extraction_result, row.blogpost_url, row.blog_id)
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
                        blog_id=row.blog_id,
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
                refreshed_metrics = self._extract_content_metrics(refreshed_html, row.blogpost_url, row.blog_id)
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
                            new_content=refreshed_html
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
                            refreshed_metrics = self._extract_content_metrics(refreshed_html, row.blogpost_url, row.blog_id)
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
                                        row.blog_id, url=row.blogpost_url
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

                                # Log results + verdict structuré (OPTIMAL / A_CORRIGER)
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
                                    ytg_verdict = "A_CORRIGER"
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
                                if ytg_verdict != "OPTIMAL" and self._ytg_gate_enabled(blog_id):
                                    ytg_gate_block = True
                                    logger.warning(
                                        f"[STEP 5.6] YTG GATE actif ({blog_id}) — "
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

                # STEP 8: Update sheet with new titles
                if blog_id == "enseigna":
                    update_ok = self.sheets_client.update_refresh_status_enseigna(
                        url=row.blogpost_url,
                        refresh_date=datetime.now().strftime("%Y-%m-%d"),
                    )
                    if not update_ok:
                        logger.error(f"[STEP 8] ÉCHEC écriture Avis/Versus (refresh_date) pour {row.blogpost_url[:60]}")
                    else:
                        logger.info(f"[STEP 8] ✓ Avis/Versus mis à jour: refresh_date écrit pour {row.blogpost_url[:60]}")
                else:
                    update_ok = self.sheets_client.update_refresh_status(
                        url=row.blogpost_url,
                        status=new_status,
                        new_titles=refreshed_titles
                    )
                    if not update_ok:
                        logger.error(f"[STEP 8] ÉCHEC écriture spreadsheet H/P/Q pour {row.blogpost_url[:60]}")
                    else:
                        logger.info(f"[STEP 8] ✓ Spreadsheet mis à jour: H=DONE, P={refreshed_titles.get('new_h1_title', '')[:40]}, Q=H2s")

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
                                blog_id=row.blog_id,
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
                # Écriture partielle: marquer BLOCKED avec l'erreur dans la spreadsheet
                if blog_id == "enseigna":
                    # Avis/Versus n'ont pas de colonne status/BLOCKED — ne pas écrire
                    # refresh_date laisse la ligne éligible au prochain run.
                    logger.info(f"[batch_refresh] Enseigna: pas de refresh_date écrit (échec) pour {row.blogpost_url[:60]}")
                else:
                    try:
                        self.sheets_client.update_refresh_status(
                            url=row.blogpost_url,
                            status="BLOCKED"
                        )
                        logger.info(f"[batch_refresh] Status BLOCKED écrit pour {row.blogpost_url[:60]}")
                    except Exception:
                        pass  # Si même ça échoue, on ne peut rien faire

        return results

    def _prepare_workflow_statuses(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> int:
        """
        Prépare les URLs pour le workflow automatisé en initialisant les statuts intermédiaires.

        FIX: Pour les URLs avec audit_gsc=DONE mais audit_serp vide/incomplet,
        met audit_serp à "AUDITING" pour que l'étape 3 puisse les traiter.

        Returns:
            Nombre d'URLs préparées
        """
        if not self.sheets_client:
            return 0

        try:
            data = self.sheets_client._read_sheet(self.sheets_client.SHEET_REFRESHS_AUDIT)

            # OPTIMIZED: Accumulate all updates for batch processing
            updates = []

            for i, row in enumerate(data[1:], start=2):
                if len(row) > 8:
                    # Filter by blog_id if specified
                    if blog_id and (len(row) < 1 or row[0] != blog_id):
                        continue

                    # Filter by post_type if specified (column F, index 5)
                    if post_type:
                        row_post_type = row[5] if len(row) > 5 else ""
                        if row_post_type != post_type:
                            continue

                    audit_gsc = row[8] if len(row) > 8 else ""  # Column I
                    audit_serp = row[9] if len(row) > 9 else ""  # Column J

                    # Si GSC est DONE mais SERP n'est pas initialisé ou est en cours incomplet
                    if audit_gsc == "DONE" and audit_serp not in ["AUDITING", "DONE", "FAILED"]:
                        # Ajouter à la liste des updates
                        updates.append({"cell": f"J{i}", "value": "AUDITING"})

            # Batch update all cells in one API call
            if updates:
                self.sheets_client._batch_update_cells(updates)

            return len(updates)

        except Exception as e:
            print(f"[WARNING] Erreur lors de la préparation des statuts: {e}")
            return 0

    def batch_workflow_auto(self, blog_id: Optional[str] = None, auto_refresh: bool = True, post_type: Optional[str] = None) -> dict:
        """
        Workflow automatisé complet en 5 étapes séquentielles.

        Exécute sans intervention :
        1. batch_editorial_audit → Colonnes Y-AC (Quality Gate)
        2. batch_audit_gsc → Colonnes I, K-M, X
        3. batch_audit_serp → Colonnes J, N-O
        4. batch_decision → Colonnes G, R-V
        5. batch_refresh (auto) → Colonnes H, P-Q (si auto_refresh=True)

        Args:
            blog_id: Filter by blog_id (optional)
            auto_refresh: Si True, exécute automatiquement batch_refresh selon les actions (défaut: True)
            post_type: Filter by post_type - "CHILD", "PARENT", "STANDALONE" (optional)

        Returns:
            {
                "step1_editorial_audit": {...},
                "step2_audit_gsc": {...},
                "step3_audit_serp": {...},
                "step4_decision": {...},
                "step5_title_optimization": {...},
                "step6_refresh": {...} | None,
                "total_duration_seconds": float,
                "success": bool,
                "errors": list
            }
        """
        import time
        start_time = time.time()

        workflow_result = {
            "step1_editorial_audit": None,
            "step2_audit_gsc": None,
            "step3_audit_serp": None,
            "step4_decision": None,
            "step5_title_optimization": None,
            "step6_refresh": {},
            "total_duration_seconds": 0,
            "success": False,
            "errors": []
        }

        try:
            print(f"\n{'='*70}")
            print(f"🚀 WORKFLOW AUTOMATISÉ - Démarrage")
            print(f"{'='*70}")
            if blog_id:
                print(f"📌 Blog filter: {blog_id}")
            if post_type:
                print(f"📌 Post type filter: {post_type}")
            print()

            # ================================================================
            # STEP 0: Préparation - Réinitialiser et initialiser les statuts
            # ================================================================
            if self.sheets_client:
                print(f"[STEP 0/6] 🔧 Préparation workflow (reset + initialisation statuts)...")

                # 0.1: Reset des anciens statuts (REFONTE Feb 2026)
                reset_stats = self.sheets_client._reset_and_prepare_statuses(blog_id, post_type=post_type)
                if reset_stats["status_reset"] > 0:
                    print(f"  ✓ {reset_stats['status_reset']} statut(s) réinitialisé(s) à TODO")

                # 0.2: Préparation transitions de workflow
                # Pour les URLs avec audit_gsc=DONE mais audit_serp vide/incomplet,
                # initialiser audit_serp à "AUDITING" pour que l'étape 3 les traite
                prepared_count = self._prepare_workflow_statuses(blog_id, post_type=post_type)
                if prepared_count > 0:
                    print(f"  ✓ {prepared_count} URL(s) préparée(s) pour audit SERP")
                print()

            # ================================================================
            # STEP 1: Editorial Audit (X-AB) - Quality Gate
            # ================================================================
            print(f"[STEP 1/6] 📝 Editorial Audit (colonnes X-AB)...")
            step1_result = self.batch_editorial_audit(blog_id, post_type=post_type)
            workflow_result["step1_editorial_audit"] = step1_result

            if step1_result["failed"] > 0:
                workflow_result["errors"].append(f"Step 1: {step1_result['failed']} échecs Editorial Audit")

            print(f"  ✅ Editorial: {step1_result['passed']} passed, "
                  f"{step1_result['review_required']} review required, "
                  f"{step1_result['blocked']} blocked, "
                  f"{step1_result['failed']} failed")
            print()

            # ================================================================
            # STEP 2: Audit GSC (H, J-L, W)
            # ================================================================
            print(f"[STEP 2/6] 📊 Audit GSC (colonnes H, J-L, W)...")
            step2_result = self.batch_audit_gsc(blog_id, post_type=post_type)
            workflow_result["step2_audit_gsc"] = step2_result

            if step2_result["failed"] > 0:
                workflow_result["errors"].append(f"Step 2: {step2_result['failed']} échecs GSC")

            print(f"  ✅ GSC: {step2_result['success']} succès, {step2_result['failed']} échecs")
            print(f"  📈 Diagnostics: URL_NOT_ON_GOOGLE={step2_result.get('url_not_on_google', 0)}, "
                  f"INDEXING_ISSUES={step2_result.get('indexing_issues', 0)}, "
                  f"DISCOVERED_NOT_INDEXED={step2_result.get('discovered_not_indexed', 0)}")
            print()

            # ================================================================
            # STEP 3: Audit SERP (I, M-N)
            # ================================================================
            print(f"[STEP 3/6] 🔍 Audit SERP (colonnes I, M-N)...")
            step3_result = self.batch_audit_serp(blog_id, post_type=post_type)
            workflow_result["step3_audit_serp"] = step3_result

            if step3_result["failed"] > 0:
                workflow_result["errors"].append(f"Step 3: {step3_result['failed']} échecs SERP")

            print(f"  ✅ SERP: {step3_result['success']} succès, {step3_result['failed']} échecs")
            print()

            # ================================================================
            # STEP 4: Decision Engine (F, Q-U)
            # ================================================================
            print(f"[STEP 4/6] 🎯 Decision Engine (colonnes F, Q-U)...")
            step4_result = self.batch_decision(blog_id, post_type=post_type)
            workflow_result["step4_decision"] = step4_result

            if step4_result.get("errors"):
                workflow_result["errors"].append(f"Step 4: {len(step4_result['errors'])} erreurs")

            print(f"  ✅ Décisions prises:")
            print(f"     - NO ACTION: {step4_result['no_action']}")
            print(f"     - PARTIAL REFRESH: {step4_result['partial_refresh']}")
            print(f"     - REFRESH TITLES: {step4_result['refresh_titles']}")
            print(f"     - FULL REFRESH: {step4_result['full_refresh']}")
            print()

            # ================================================================
            # STEP 5: Title Optimization (O-P) - Nouveaux H1 + H2 structure
            # ================================================================
            print(f"[STEP 5/6] 🏷️ Title Optimization (colonnes O-P)...")
            step5_result = self.batch_title_optimization(blog_id, post_type=post_type)
            workflow_result["step5_title_optimization"] = step5_result

            if step5_result["failed"] > 0:
                workflow_result["errors"].append(f"Step 5: {step5_result['failed']} échecs Title Optimization")

            print(f"  ✅ Titres: {step5_result['success']} optimisés, {step5_result['failed']} échecs")
            print()

            # ================================================================
            # STEP 6: Auto Refresh (G) - Optionnel
            # ================================================================
            if auto_refresh:
                print(f"[STEP 6/6] ✍️ Batch Refresh (colonne G)...")

                # Execute refresh for each action type if count > 0
                refresh_actions = [
                    ("PARTIAL REFRESH", step4_result['partial_refresh']),
                    ("REFRESH TITLES", step4_result['refresh_titles']),
                    ("FULL REFRESH", step4_result['full_refresh']),
                ]

                for action_name, count in refresh_actions:
                    if count > 0:
                        print(f"  🔄 Refresh: {action_name} ({count} articles)...")
                        refresh_result = self.batch_refresh(action=action_name, blog_id=blog_id, post_type=post_type)
                        workflow_result["step6_refresh"][action_name] = refresh_result

                        print(f"     ✅ {refresh_result['success']} succès, "
                              f"{refresh_result['failed']} échecs, "
                              f"{refresh_result.get('assets_restored', 0)} assets restaurés")

                        if refresh_result.get('errors'):
                            workflow_result["errors"].extend(refresh_result['errors'][:3])  # Limiter les erreurs loggées
            else:
                print(f"[STEP 6/6] ⏭️ Auto-refresh désactivé (utilisez --auto-refresh pour activer)")

            # ================================================================
            # Final Report
            # ================================================================
            workflow_result["total_duration_seconds"] = time.time() - start_time
            workflow_result["success"] = len(workflow_result["errors"]) == 0

            print()
            print(f"{'='*70}")
            print(f"✅ WORKFLOW TERMINÉ")
            print(f"{'='*70}")
            print(f"⏱️  Durée totale: {workflow_result['total_duration_seconds']:.1f}s")
            print(f"{'🟢 SUCCÈS' if workflow_result['success'] else '🔴 ERREURS DÉTECTÉES'}")
            if workflow_result["errors"]:
                print(f"⚠️  Erreurs ({len(workflow_result['errors'])}):")
                for error in workflow_result["errors"][:5]:
                    print(f"   - {error}")
            print(f"{'='*70}\n")

            return workflow_result

        except Exception as e:
            workflow_result["errors"].append(f"Workflow interrupted: {str(e)[:100]}")
            workflow_result["total_duration_seconds"] = time.time() - start_time
            workflow_result["success"] = False

            print(f"\n{'='*70}")
            print(f"🔴 WORKFLOW INTERROMPU")
            print(f"{'='*70}")
            print(f"❌ Erreur: {str(e)[:200]}")
            print(f"⏱️  Durée avant interruption: {workflow_result['total_duration_seconds']:.1f}s")
            print(f"{'='*70}\n")

            import traceback
            traceback.print_exc()

            return workflow_result

    def _run_editorial_audit(
        self,
        url: str,
        html_content: str,
        blog_id: str
    ) -> Optional[EditorialAuditResult]:
        """
        Exécute l'audit éditorial (Quality Gate - Step 1.5).

        Args:
            url: URL de l'article
            html_content: Contenu HTML à auditer
            blog_id: Identifiant du blog

        Returns:
            EditorialAuditResult si audit réussi, None si erreur
        """
        import logging
        import os
        logger = logging.getLogger("RefreshOrchestrator")

        # Check if editorial audit is enabled
        if os.getenv("EDITORIAL_AUDIT_ENABLED", "true").lower() == "false":
            logger.info(f"[STEP 1.5] Editorial Audit DISABLED (skipped)")
            # Return a dummy result that allows workflow to continue
            from _shared.core.models.audit_models import EditorialAuditResult
            return EditorialAuditResult(
                url=url,
                topic="N/A",
                ymyl_level="low",
                truth_score=100,
                eeat_score=100,
                freshness_score=100,
                genericness_score=100,
                overall_score=10.0,
                fact_checks=[],
                factual_errors_count=0,
                critical_errors_count=0,
                eeat_diagnosis=None,
                recommendations=[],
                blocking_issues=[],
                should_proceed=True,
                execution_time_ms=0
            )

        try:
            logger.info(f"[STEP 1.5] Editorial Audit for {url[:50]}")

            # Exécuter l'audit éditorial
            editorial_result = self.editorial_auditor.audit(
                url=url,
                html_content=html_content,
                blog_id=blog_id,
                use_llm_verification=False  # Tier 2 LLM not implemented yet
            )

            # Générer le rapport markdown
            report_md = self.editorial_auditor.generate_markdown_report(editorial_result)

            # Sauvegarder le rapport
            url_slug = re.sub(r'[^a-z0-9]+', '_', url.lower()).strip('_')
            report_path = self.output_mgr.save_editorial_audit(blog_id, url_slug, report_md)

            logger.info(
                f"Editorial audit completed: score={editorial_result.overall_score:.1f}/10, "
                f"should_proceed={editorial_result.should_proceed}, "
                f"blocking_issues={len(editorial_result.blocking_issues)}"
            )

            if not editorial_result.should_proceed:
                logger.warning(
                    f"🚫 BLOCKED by editorial audit (score < 4.0): {url[:50]}\n"
                    f"   Issues: {', '.join(editorial_result.blocking_issues[:3])}"
                )
                logger.info(f"   Report saved: {report_path}")

            return editorial_result

        except Exception as e:
            logger.error(f"Editorial audit failed: {str(e)[:200]}")
            return None

    # =========================================================================
