"""
GSC Analyzer Module

Analyse des performances via Google Search Console API directe.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from _shared.core.models import (
    KeywordPerformance,
    URLPerformance,
    QuickWin,
    GSCAnalysisResult,
)
from _shared.core.constants import (
    CTR_LOW_THRESHOLD,
    CTR_GOOD_THRESHOLD,
    IMPRESSIONS_SIGNIFICANT,
    POSITION_DECLINE_ALERT,
    TRAFFIC_DECLINE_MODERATE,
    TRAFFIC_DECLINE_SEVERE,
)

# Google API (optionnel, pour mode direct)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# Chemin du service account (via .env ou fallback)
import os
SERVICE_ACCOUNT_PATH = Path(os.environ.get("GOOGLE_SA_PATH", "~/.credentials/google/google-service-account.json")).expanduser()


# --- Routage source GSC (Phase 6c, cf. GSC_MCP_POC_FINDINGS.md) -------------
# Le MCP `gsc-remote` (serveur superprof.cloud) n'expose QUE des propriétés
# `superprof.*` — enseigna.fr en est absent. On route donc PAR PROPRIÉTÉ :
#   - propriété couverte par le MCP  → source "mcp"  (superprof.*)
#   - sinon                          → source "service_account"  (enseigna, …)
# Garantie dure : toute propriété non couverte tombe sur le SA (jamais le MCP).
SOURCE_MCP = "mcp"
SOURCE_SERVICE_ACCOUNT = "service_account"

# Substrings de domaine couverts par le MCP gsc-remote (dérivé du list_properties
# live 2026-07-15 : uniquement des variantes superprof). Élargir cette liste au
# fur et à mesure que d'autres tenants sont ajoutés au serveur MCP.
MCP_COVERED_DOMAIN_HINTS = ("superprof.", "super-prof.")


def gsc_source_for_property(gsc_property: str) -> str:
    """Retourne la source GSC à utiliser pour une propriété : MCP ou SA.

    Décision purement basée sur le domaine (cf. contrainte enseigna). Toute
    propriété non reconnue comme couverte par le MCP tombe sur le service account.
    """
    prop = (gsc_property or "").lower()
    if any(hint in prop for hint in MCP_COVERED_DOMAIN_HINTS):
        return SOURCE_MCP
    return SOURCE_SERVICE_ACCOUNT


class GSCAnalyzer:
    """
    Analyseur de performances Google Search Console.

    Utilise l'API directe GSC via service account.
    """

    def __init__(self, gsc_property: str, auth_mode: str = "service_account"):
        """
        Initialise l'analyseur GSC.

        Args:
            gsc_property: Propriete GSC (ex: 'https://enseigna.fr/')
            auth_mode: 'service_account' (défaut) ou 'oauth_user' (Phase 4bis-B).
        """
        self.gsc_property = gsc_property
        self.auth_mode = auth_mode
        self._gsc_service = None

        # Routage source (Phase 6c) : MCP pour superprof.*, SA sinon (enseigna…).
        # NB: aujourd'hui le FETCH passe encore par le SA dans tous les cas (le MCP
        # n'est pas appelable depuis ce process Python — il l'est côté Claude Code).
        # `data_source` fige la DÉCISION de routage, testable et prête pour la
        # bascule méthode par méthode. Garantie : enseigna → toujours SA.
        self.data_source = gsc_source_for_property(gsc_property)

        # Initialiser l'API directe si disponible
        if GOOGLE_API_AVAILABLE:
            self._init_direct_api()

    @property
    def uses_mcp(self) -> bool:
        """True si cette propriété est routée vers le MCP gsc-remote (superprof.*)."""
        return self.data_source == SOURCE_MCP

    def _init_direct_api(self):
        """Initialise la connexion directe a l'API GSC (auth selon auth_mode)."""
        try:
            from _shared.core.google_auth import get_credentials
            credentials = get_credentials(
                scopes=['https://www.googleapis.com/auth/webmasters.readonly'],
                auth_mode=self.auth_mode,
            )
            if credentials is None:
                self._gsc_service = None
                return
            self._gsc_service = build('searchconsole', 'v1', credentials=credentials)
        except Exception as e:
            print(f"Erreur init API GSC directe: {e}")
            self._gsc_service = None

    def analyze(self, url: str) -> GSCAnalysisResult:
        """
        Analyse complete des performances d'une URL.

        Args:
            url: URL a analyser

        Returns:
            GSCAnalysisResult avec toutes les donnees
        """
        # Si pas d'API directe, retourner des donnees vides
        if self._gsc_service is None:
            return self._empty_result(url)

        # Recuperer les donnees de performance
        performance = self._fetch_performance_direct(url)

        # Detecter les quick wins
        quick_wins = self._detect_quick_wins_direct(url)

        # Verifier l'indexation
        indexation_status = self._check_indexation(url)

        # Analyser les tendances et generer les alertes
        is_declining, severity, alerts = self._analyze_trends(performance)

        return GSCAnalysisResult(
            url=url,
            performance=performance,
            quick_wins=quick_wins,
            indexation_status=indexation_status,
            is_declining=is_declining,
            decline_severity=severity,
            alert_messages=alerts,
        )

    def _fetch_performance_direct(self, url: str) -> URLPerformance:
        """Récupère les perfs 30j d'une URL.

        Routage (Phase 6c) : la **période courante par requête** passe par le MCP
        gsc-remote pour superprof.* (fallback SA sur erreur), par le SA pour
        enseigna/tenants hors MCP. Le **calcul de tendances** (baseline période
        N-1) reste sur le SA dans TOUS les cas — voir `_calculate_trends_direct` :
        il repose sur un total *par page* de la période précédente, non couvert de
        façon fiable par les tools MCP (compare_search_periods tronque au top-N et
        risque de manquer les pages à faible trafic). On ne bascule donc PAS le
        cœur de la détection de déclin tant que cette parité n'est pas validée à
        l'échelle. Bascule méthode par méthode, jamais big-bang.
        """
        today = datetime.now()
        prev_end = (today - timedelta(days=31)).strftime("%Y-%m-%d")
        prev_start = (today - timedelta(days=61)).strftime("%Y-%m-%d")

        # 1. Période courante par requête : MCP si superprof.*, sinon/fallback SA.
        rows = self._fetch_current_period_rows(url)
        if rows is None:
            return URLPerformance(url=url, clicks_30d=0, impressions_30d=0,
                                  ctr_30d=0, avg_position_30d=0)

        keywords = []
        total_clicks = 0
        total_impressions = 0
        position_sum = 0
        for r in rows:
            keywords.append(KeywordPerformance(
                query=r["query"], clicks=r["clicks"], impressions=r["impressions"],
                ctr=r["ctr"], position=r["position"],
            ))
            total_clicks += r["clicks"]
            total_impressions += r["impressions"]
            if r["impressions"] > 0:
                position_sum += r["position"] * r["impressions"]

        avg_position = position_sum / total_impressions if total_impressions > 0 else 0
        ctr_30d = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        main_keyword = max(keywords, key=lambda k: k.impressions).query if keywords else None

        # 2. Tendances : SA uniquement (cœur décision, cf. docstring).
        clicks_trend, impressions_trend, position_trend = self._calculate_trends_direct(
            url, prev_start, prev_end, total_clicks, total_impressions, avg_position
        )

        return URLPerformance(
            url=url,
            clicks_30d=total_clicks,
            impressions_30d=total_impressions,
            ctr_30d=ctr_30d,
            avg_position_30d=avg_position,
            clicks_trend=clicks_trend,
            impressions_trend=impressions_trend,
            position_trend=position_trend,
            keywords=keywords,
            main_keyword=main_keyword,
        )

    def _fetch_current_period_rows(self, url: str) -> "Optional[list[dict]]":
        """Lignes période courante 30j par requête {query,clicks,impressions,ctr,position}.

        ⚠️ NON basculé vers le MCP (reste sur SA). Raison : `clicks_30d`/
        `impressions_30d` sont des **sommes sur TOUTES les requêtes** de l'URL et
        alimentent directement le moteur de décision + le calcul de tendance. Or le
        tool MCP `get_search_by_page_query` **plafonne à ~20 requêtes** → sous-compte
        les URLs à longue traîne (constaté : 2394 vs 2567 clics, tendance faussée).
        Tant que le MCP ne pagine pas au-delà de 20, on ne bascule PAS cette somme.
        La structure (helper isolé) est prête : dès que le row-limit MCP est levé,
        router ici comme pour `fetch_top_keywords_12m`. Voir GSC_MCP_POC_FINDINGS.md.

        (Le fallback SA reste la seule voie ici ; enseigna → SA de toute façon.)
        """
        return self._fetch_current_period_rows_via_sa(url)

    def _fetch_current_period_rows_via_sa(self, url: str) -> "Optional[list[dict]]":
        """Ancienne lecture SA période courante (conservée, fallback)."""
        if not self._gsc_service:
            return None
        today = datetime.now()
        end_date = today.strftime("%Y-%m-%d")
        start_date_30d = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        request_body = {
            "startDate": start_date_30d,
            "endDate": end_date,
            "dimensions": ["query"],
            "dimensionFilterGroups": [{
                "filters": [{"dimension": "page", "expression": url}]
            }],
            "rowLimit": 50,
        }
        try:
            response = self._gsc_service.searchanalytics().query(
                siteUrl=self.gsc_property, body=request_body
            ).execute()
        except Exception as e:
            print(f"Erreur GSC API directe pour {url}: {e}")
            return []
        # Valeurs brutes préservées (parité stricte avec l'ancien SA : pas
        # d'arrondi de position, clicks/impressions tels quels).
        return [
            {
                "query": r["keys"][0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": r.get("ctr", 0) * 100,
                "position": r.get("position", 0),
            }
            for r in response.get("rows", [])
        ]

    def fetch_main_keyword(self, url: str) -> "Optional[str]":
        """Mot-clé principal 30j (max impressions) d'une URL — usage batch discovery.

        Routage MCP/SA (superprof.* → MCP, fallback SA ; enseigna → SA). Sûr même
        avec le plafond ~20 du MCP : le max-impressions est TOUJOURS en tête, donc
        présent dans les 20 premières lignes. Parité vérifiée 5/5 URLs.
        Contrairement aux SOMMES (clicks_30d/impressions_30d), non affecté par la
        troncature — d'où une méthode dédiée plutôt que `_fetch_performance_direct`.
        """
        rows = self._fetch_current_period_rows_for_main_kw(url)
        if not rows:
            return None
        return max(rows, key=lambda r: r["impressions"])["query"]

    def _fetch_current_period_rows_for_main_kw(self, url: str) -> list[dict]:
        """Lignes 30j par requête pour le main_keyword : MCP (fallback SA) / SA."""
        if self.uses_mcp:
            try:
                from scripts.audit.gsc_mcp_client import GSCMCPClient
                return GSCMCPClient().search_by_page_query(self.gsc_property, url, days=30)
            except Exception as e:
                print(f"[GSC] MCP main_kw indisponible ({str(e)[:80]}) — fallback service account.")
        return self._fetch_current_period_rows_via_sa(url) or []

    def _fetch_top_keywords_12m_via_mcp(self, url: str, limit: int) -> list[dict]:
        """Lecture 12m par requête via le MCP gsc-remote. Lève GSCMCPError si KO."""
        from scripts.audit.gsc_mcp_client import GSCMCPClient
        client = GSCMCPClient()
        rows = client.search_by_page_query(self.gsc_property, url, days=365)
        keywords = [
            {"query": r["query"], "clicks": r["clicks"], "impressions": r["impressions"]}
            for r in rows
        ]
        keywords.sort(key=lambda k: (-k["clicks"], -k["impressions"]))
        return keywords[:limit]

    def fetch_top_keyword_12m(self, url: str) -> "Optional[str]":
        """Retourne le mot-clé cible sur 12 mois : max clicks, sinon max impressions.

        Dérivé de `fetch_top_keywords_12m` (routage MCP/SA identique).
        """
        top = self.fetch_top_keywords_12m(url, limit=50)
        return top[0]["query"] if top else None

    def _fetch_top_keyword_12m_via_sa(self, url: str) -> "Optional[str]":
        """Ancienne implémentation directe SA (conservée, fallback)."""
        if not self._gsc_service:
            return None
        today = datetime.now()
        start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "dimensionFilterGroups": [{"filters": [{"dimension": "page", "expression": url}]}],
            "rowLimit": 50,
        }
        try:
            response = self._gsc_service.searchanalytics().query(
                siteUrl=self.gsc_property, body=request_body
            ).execute()
        except Exception as e:
            print(f"Erreur GSC 12m pour {url}: {e}")
            return None

        rows = response.get("rows", [])
        if not rows:
            return None

        best_by_clicks = max(rows, key=lambda r: r.get("clicks", 0))
        if best_by_clicks.get("clicks", 0) > 0:
            return best_by_clicks["keys"][0]

        best_by_impressions = max(rows, key=lambda r: r.get("impressions", 0))
        return best_by_impressions["keys"][0] if best_by_impressions.get("impressions", 0) > 0 else None

    def fetch_top_keywords_12m(self, url: str, limit: int = 20) -> list[dict]:
        """
        Retourne les N meilleures requêtes GSC sur 12 mois, triées clicks DESC puis
        impressions DESC. Chaque élément : {"query", "clicks", "impressions"}.

        Routage (Phase 6c) : MCP gsc-remote pour superprof.* (fallback SA sur
        erreur MCP), service account pour enseigna et tout tenant hors MCP.
        NB row-limit : le MCP plafonne à ~20 lignes. Pour limit>20 on retombe
        sur le SA (qui pagine jusqu'à 50) afin de ne pas tronquer silencieusement.
        """
        if self.uses_mcp and limit <= 20:
            try:
                return self._fetch_top_keywords_12m_via_mcp(url, limit)
            except Exception as e:  # GSCMCPError ou réseau → fallback SA
                print(f"[GSC] MCP indisponible ({str(e)[:80]}) — fallback service account.")
        return self._fetch_top_keywords_12m_via_sa(url, limit)

    def _fetch_top_keywords_12m_via_sa(self, url: str, limit: int = 20) -> list[dict]:
        """Ancienne implémentation directe SA (conservée, fallback)."""
        if not self._gsc_service:
            return []
        today = datetime.now()
        start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "dimensionFilterGroups": [{"filters": [{"dimension": "page", "expression": url}]}],
            "rowLimit": max(limit, 50),
        }
        try:
            response = self._gsc_service.searchanalytics().query(
                siteUrl=self.gsc_property, body=request_body
            ).execute()
        except Exception as e:
            print(f"Erreur GSC fetch_top_keywords_12m pour {url}: {e}")
            return []

        rows = response.get("rows", [])
        keywords = [
            {
                "query": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
            }
            for r in rows
        ]
        keywords.sort(key=lambda k: (-k["clicks"], -k["impressions"]))
        return keywords[:limit]

    def _calculate_trends_direct(
        self,
        url: str,
        prev_start: str,
        prev_end: str,
        current_clicks: int,
        current_impressions: int,
        current_position: float,
    ) -> tuple[float, float, float]:
        """Calcule les tendances via API directe."""
        try:
            request_body = {
                "startDate": prev_start,
                "endDate": prev_end,
                "dimensions": ["page"],
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "page",
                        "expression": url
                    }]
                }]
            }

            response = self._gsc_service.searchanalytics().query(
                siteUrl=self.gsc_property,
                body=request_body
            ).execute()

            if response.get("rows"):
                row = response["rows"][0]
                prev_clicks = row.get("clicks", 0)
                prev_impressions = row.get("impressions", 0)
                prev_position = row.get("position", 0)

                clicks_trend = ((current_clicks - prev_clicks) / prev_clicks * 100) if prev_clicks > 0 else 0
                impressions_trend = ((current_impressions - prev_impressions) / prev_impressions * 100) if prev_impressions > 0 else 0
                position_trend = prev_position - current_position

                return clicks_trend, impressions_trend, position_trend

        except Exception as e:
            print(f"Erreur calcul tendances: {e}")

        return 0.0, 0.0, 0.0

    def _detect_quick_wins_direct(self, url: str) -> list[QuickWin]:
        """Détecte les quick wins via API directe GSC."""
        quick_wins = []

        try:
            today = datetime.now()
            end_date = today.strftime("%Y-%m-%d")
            start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")

            request_body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["query"],
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "page",
                        "expression": url
                    }]
                }],
                "rowLimit": 50
            }

            response = self._gsc_service.searchanalytics().query(
                siteUrl=self.gsc_property,
                body=request_body
            ).execute()

            # Identifier les quick wins : impressions élevées + CTR faible
            for row in response.get("rows", []):
                impressions = row.get("impressions", 0)
                ctr = row.get("ctr", 0) * 100  # Convert to %

                # Quick win criteria
                if impressions >= 100 and ctr < CTR_LOW_THRESHOLD:
                    potential = "high" if impressions > 500 else "medium"

                    item = {
                        "query": row["keys"][0],
                        "impressions": impressions,
                        "ctr": ctr / 100,  # _generate_recommendation expects 0-1 range
                        "position": row.get("position", 0)
                    }

                    quick_wins.append(QuickWin(
                        url=url,
                        query=item["query"],
                        impressions=impressions,
                        ctr=ctr,
                        position=item["position"],
                        potential=potential,
                        recommendation=self._generate_recommendation(item),
                    ))

        except Exception as e:
            print(f"Erreur détection quick wins (API directe): {e}")

        return quick_wins

    def _generate_recommendation(self, item: dict) -> str:
        """Génère une recommandation basée sur les données."""
        ctr = item.get("ctr", 0) * 100
        position = item.get("position", 0)
        impressions = item.get("impressions", 0)

        if position <= 5 and ctr < 2:
            return "Position excellente mais CTR faible - Optimiser le titre et la meta description"
        elif position <= 10 and ctr < 2:
            return "Top 10 avec CTR faible - Revoir le titre pour améliorer l'attractivité"
        elif position > 10 and impressions > 300:
            return "Bonnes impressions en page 2 - Améliorer le contenu pour atteindre le top 10"
        else:
            return "Optimiser le contenu et les signaux E-E-A-T"

    def _check_indexation(self, url: str) -> str:
        """Vérifie le statut d'indexation de l'URL via API directe."""
        try:
            if not self._gsc_service:
                return "UNKNOWN"

            inspection = self._gsc_service.urlInspection().index().inspect(
                body={
                    "inspectionUrl": url,
                    "siteUrl": self.gsc_property
                }
            ).execute()

            verdict = inspection.get("inspectionResult", {}).get("indexStatusResult", {}).get("verdict", "UNKNOWN")

            if verdict == "PASS":
                return "INDEXED"
            elif verdict == "FAIL":
                return "NOT_INDEXED"
            else:
                return "UNKNOWN"

        except Exception:
            return "UNKNOWN"

    def _check_indexation_detailed(self, url: str) -> dict:
        """
        Diagnostic détaillé d'indexation via URL Inspection API.

        Returns:
            dict avec structure:
            {
                "verdict": "PASS|FAIL|NEUTRAL|UNKNOWN",
                "coverage_state": "Indexed|Crawled - currently not indexed|...",
                "scenario": "INDEXED|URL_NOT_ON_GOOGLE|INDEXING_ISSUE|DISCOVERED_NOT_INDEXED",
                "indexing_state": "INDEXING_ALLOWED|INDEXING_DISALLOWED",
                "page_fetch_state": "SUCCESSFUL|FAILED",
                "mobile_usability_issues": [...],
                "last_crawl_time": "ISO datetime",
                "recommended_action": "FULL_REFRESH|PARTIAL_REFRESH|..."
            }
        """
        try:
            if not self._gsc_service:
                raise ValueError("No GSC API available")

            # API directe : URL Inspection
            inspection = self._gsc_service.urlInspection().index().inspect(
                body={
                    "inspectionUrl": url,
                    "siteUrl": self.gsc_property
                }
            ).execute()
            data = inspection

            # Extraire les champs détaillés
            inspection_result = data.get("inspectionResult", {})
            index_status = inspection_result.get("indexStatusResult", {})
            mobile_usability = inspection_result.get("mobileUsabilityResult", {})

            verdict = index_status.get("verdict", "UNKNOWN")
            coverage_state = index_status.get("coverageState", "UNKNOWN")
            indexing_state = index_status.get("indexingState", "UNKNOWN")
            page_fetch_state = index_status.get("pageFetchState", "UNKNOWN")
            crawled_as = index_status.get("crawledAs", "UNKNOWN")
            last_crawl_time = index_status.get("lastCrawlTime", "")

            # Détecter 404 (page not found)
            if page_fetch_state == "FAILED" or "404" in coverage_state or "not found" in coverage_state.lower():
                return {
                    "verdict": "FAIL",
                    "coverage_state": coverage_state or "Page not found (404)",
                    "scenario": "URL_404",
                    "indexing_state": indexing_state,
                    "page_fetch_state": page_fetch_state,
                    "crawled_as": crawled_as,
                    "mobile_usability_issues": [],
                    "last_crawl_time": last_crawl_time,
                    "recommended_action": "DELETE_OR_REDIRECT",
                    "error": "URL returns 404 - page not found"
                }

            # Détecter redirections
            if "redirect" in coverage_state.lower() or "301" in coverage_state or "302" in coverage_state:
                return {
                    "verdict": "FAIL",
                    "coverage_state": coverage_state,
                    "scenario": "URL_REDIRECTED",
                    "indexing_state": indexing_state,
                    "page_fetch_state": page_fetch_state,
                    "crawled_as": crawled_as,
                    "mobile_usability_issues": [],
                    "last_crawl_time": last_crawl_time,
                    "recommended_action": "UPDATE_REDIRECT_TARGET",
                    "error": "URL is redirected - update to target URL"
                }

            # Extraire les problèmes
            mobile_issues = [
                issue.get("issue", "")
                for issue in mobile_usability.get("issues", [])
            ]

            # Classifier le scénario
            scenario = self._classify_indexation_scenario(
                verdict=verdict,
                coverage_state=coverage_state,
                indexing_state=indexing_state,
                mobile_issues=mobile_issues,
                page_fetch_state=page_fetch_state
            )

            # Déterminer l'action recommandée
            recommended_action = self._recommend_action_from_scenario(scenario)

            return {
                "verdict": verdict,
                "coverage_state": coverage_state,
                "scenario": scenario,
                "indexing_state": indexing_state,
                "page_fetch_state": page_fetch_state,
                "crawled_as": crawled_as,
                "mobile_usability_issues": mobile_issues,
                "last_crawl_time": last_crawl_time,
                "recommended_action": recommended_action
            }

        except Exception as e:
            # Gestion robuste des erreurs - ne fait pas planter le pipeline
            error_msg = str(e)
            return {
                "verdict": "UNKNOWN",
                "coverage_state": "API Error",
                "scenario": "API_ERROR",
                "indexing_state": "UNKNOWN",
                "page_fetch_state": "UNKNOWN",
                "crawled_as": "UNKNOWN",
                "mobile_usability_issues": [],
                "last_crawl_time": "",
                "recommended_action": "NO_ACTION",
                "error": error_msg[:200]  # Truncate long error messages
            }

    def _classify_indexation_scenario(
        self,
        verdict: str,
        coverage_state: str,
        indexing_state: str,
        mobile_issues: list,
        page_fetch_state: str = "UNKNOWN"
    ) -> str:
        """
        Classifie le statut d'indexation en 6 scénarios.

        Scénarios:
        - INDEXED: Page indexée normalement
        - URL_NOT_ON_GOOGLE: Connue mais absente de l'index (crawled not indexed)
        - INDEXING_ISSUE: Indexée mais avec erreurs (mobile, structured data)
        - DISCOVERED_NOT_INDEXED: Connue mais jamais crawlée
        - URL_404: Page non trouvée (404 error)
        - URL_REDIRECTED: Page redirigée (301/302)
        """
        # URL_404: Page non trouvée
        if page_fetch_state == "FAILED" or "404" in coverage_state or "not found" in coverage_state.lower():
            return "URL_404"

        # URL_REDIRECTED: Page redirigée
        if "redirect" in coverage_state.lower() or "301" in coverage_state or "302" in coverage_state:
            return "URL_REDIRECTED"

        # INDEXED: Verdict PASS et pas d'erreurs critiques
        if verdict == "PASS" and not mobile_issues:
            return "INDEXED"

        # INDEXING_ISSUE: Indexée mais erreurs présentes
        if verdict == "PASS" and mobile_issues:
            return "INDEXING_ISSUE"

        # URL_NOT_ON_GOOGLE: Crawlée mais non indexée
        if verdict == "FAIL" and "crawled" in coverage_state.lower():
            return "URL_NOT_ON_GOOGLE"

        # DISCOVERED_NOT_INDEXED: Découverte mais pas crawlée
        if verdict == "NEUTRAL" or indexing_state == "INDEXING_DISALLOWED":
            return "DISCOVERED_NOT_INDEXED"

        # Fallback
        return "UNKNOWN"

    def _recommend_action_from_scenario(self, scenario: str) -> str:
        """Map scenario → action recommandée."""
        mapping = {
            "INDEXED": "NO_ACTION",
            "URL_NOT_ON_GOOGLE": "FULL_REFRESH",
            "INDEXING_ISSUE": "PARTIAL_REFRESH",
            "DISCOVERED_NOT_INDEXED": "CONTENT_QUALITY_CHECK",
            "URL_404": "DELETE_OR_REDIRECT",
            "URL_REDIRECTED": "UPDATE_REDIRECT_TARGET",
            "API_ERROR": "NO_ACTION",
            "UNKNOWN": "NO_ACTION"
        }
        return mapping.get(scenario, "NO_ACTION")

    def _analyze_trends(self, performance: URLPerformance) -> tuple[bool, str, list[str]]:
        """Analyse les tendances et génère les alertes."""
        is_declining = False
        severity = "none"
        alerts = []

        # Vérifier la baisse de clics
        if performance.clicks_trend < TRAFFIC_DECLINE_SEVERE:
            is_declining = True
            severity = "severe"
            alerts.append(f"Chute de trafic sévère: {performance.clicks_trend:.1f}% sur 30 jours")
        elif performance.clicks_trend < TRAFFIC_DECLINE_MODERATE:
            is_declining = True
            severity = "moderate"
            alerts.append(f"Baisse de trafic modérée: {performance.clicks_trend:.1f}% sur 30 jours")

        # Vérifier la baisse d'impressions (règle produit : impressions OU clics
        # en baisse → page en déclin → FULL_REFRESH côté audit_engine).
        if performance.impressions_trend < TRAFFIC_DECLINE_SEVERE:
            is_declining = True
            severity = "severe"
            alerts.append(f"Chute d'impressions sévère: {performance.impressions_trend:.1f}% sur 30 jours")
        elif performance.impressions_trend < TRAFFIC_DECLINE_MODERATE:
            is_declining = True
            if severity != "severe":
                severity = "moderate"
            alerts.append(f"Baisse d'impressions modérée: {performance.impressions_trend:.1f}% sur 30 jours")

        # Vérifier la perte de positions
        if performance.position_trend < -POSITION_DECLINE_ALERT:
            is_declining = True
            if severity != "severe":
                severity = "moderate"
            alerts.append(f"Perte de {abs(performance.position_trend):.1f} positions")

        # Vérifier le CTR faible avec bonnes impressions
        if performance.ctr_30d < CTR_LOW_THRESHOLD and performance.impressions_30d > IMPRESSIONS_SIGNIFICANT:
            alerts.append(f"CTR faible ({performance.ctr_30d:.1f}%) malgré {performance.impressions_30d} impressions - Optimiser titre/meta")

        return is_declining, severity, alerts

    def _empty_result(self, url: str) -> GSCAnalysisResult:
        """Retourne un résultat vide pour les tests."""
        return GSCAnalysisResult(
            url=url,
            performance=URLPerformance(
                url=url,
                clicks_30d=0,
                impressions_30d=0,
                ctr_30d=0,
                avg_position_30d=0,
            ),
            quick_wins=[],
            indexation_status="UNKNOWN",
        )

    def to_dict(self, result: GSCAnalysisResult) -> dict:
        """Convertit le résultat en dictionnaire pour export."""
        return {
            "url": result.url,
            "indexation_status": result.indexation_status,
            "is_declining": result.is_declining,
            "decline_severity": result.decline_severity,
            "alerts": result.alert_messages,
            "performance": {
                "clicks_30d": result.performance.clicks_30d,
                "impressions_30d": result.performance.impressions_30d,
                "ctr_30d": result.performance.ctr_30d,
                "avg_position_30d": result.performance.avg_position_30d,
                "clicks_trend": result.performance.clicks_trend,
                "impressions_trend": result.performance.impressions_trend,
                "position_trend": result.performance.position_trend,
                "main_keyword": result.performance.main_keyword,
            },
            "keywords": [
                {
                    "query": kw.query,
                    "clicks": kw.clicks,
                    "impressions": kw.impressions,
                    "ctr": kw.ctr,
                    "position": kw.position,
                }
                for kw in result.performance.keywords
            ],
            "quick_wins": [
                {
                    "query": qw.query,
                    "impressions": qw.impressions,
                    "ctr": qw.ctr,
                    "position": qw.position,
                    "potential": qw.potential,
                    "recommendation": qw.recommendation,
                }
                for qw in result.quick_wins
            ],
        }
