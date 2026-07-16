"""
Audit Engine Module

Orchestrateur principal qui coordonne tous les composants d'audit.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from _shared.core.models import (
    HTMLAnalysisResult,
    GSCAnalysisResult,
    SERPAnalysisResult,
    CannibalizationResult,
    IntentAnalysisResult,
    ContentFormat,
    AuditReport,
)
from .html_analyzer import HTMLAnalyzer
from .gsc_analyzer import GSCAnalyzer
from .serp_analyzer import SERPAnalyzer
from .cannibalization import CannibalizationDetector
from .intent_detector import IntentDetector


class AuditEngine:
    """
    Moteur d'audit principal.

    Coordonne l'analyse HTML, GSC, SERP, cannibalisation et intention
    pour produire un rapport d'audit complet.
    """

    def __init__(self, blog_config: dict):
        self.logger = logging.getLogger(f"AuditEngine[{blog_config.get('blog_id', 'unknown')}]")
        """
        Initialise le moteur d'audit.

        Args:
            blog_config: Configuration du blog (depuis config/blogs/{blog_id}.json)
        """
        self.blog_config = blog_config

        self.domain = blog_config.get("domain", "")
        self.gsc_property = blog_config.get("gsc_property", f"https://{self.domain}/")

        # Initialiser les analyseurs
        self.html_analyzer = HTMLAnalyzer(self.domain)
        self.gsc_analyzer = GSCAnalyzer(self.gsc_property)
        self.serp_analyzer = SERPAnalyzer()
        self.cannibalization_detector = CannibalizationDetector(self.domain)
        self.intent_detector = IntentDetector()

        # Cache du sitemap
        self._sitemap_cache: list[str] = []

    def full_audit(self, url: str, html_content: str, provided_keyword: str = None) -> AuditReport:
        """
        Exécute un audit complet sur une URL.

        Args:
            url: URL de l'article à auditer
            html_content: Contenu HTML de la page
            provided_keyword: Mot-clé fourni (facultatif, force analyse SERP)

        Returns:
            AuditReport complet
        """
        self.logger.debug(f"[full_audit] START: url={url}, provided_keyword='{provided_keyword}'")
        audit_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Analyse HTML
        html_analysis = self.html_analyzer.analyze(html_content, url)

        # 2. Extraction des assets
        assets = self.html_analyzer.extract_assets_dict(html_analysis)

        # 3. Analyse GSC
        gsc_analysis = self.gsc_analyzer.analyze(url)

        # 4. Analyse SERP (si mot-clé principal trouvé OR fourni)
        main_keyword = provided_keyword or gsc_analysis.performance.main_keyword
        # Fallback 12m : si le 30j GSC ne retourne pas de keyword (trafic insuffisant sur 30j)
        if not main_keyword:
            main_keyword = self.gsc_analyzer.fetch_top_keyword_12m(url)
            if main_keyword:
                self.logger.info(f"[full_audit] Keyword 30j vide → fallback GSC 12m: '{main_keyword}'")
                # Propager dans gsc_analysis.performance pour que to_dict le reprenne
                if gsc_analysis and gsc_analysis.performance:
                    gsc_analysis.performance.main_keyword = main_keyword
        self.logger.debug(f"[full_audit] main_keyword resolved: provided='{provided_keyword}' → final='{main_keyword}'")
        serp_analysis = None
        intent_analysis = None
        if main_keyword:
            serp_analysis = self.serp_analyzer.analyze(
                main_keyword,
                self.domain,
            )

            # 5. Analyse d'intention
            current_format = self._detect_current_format(html_analysis)
            intent_analysis = self.intent_detector.analyze(
                keyword=main_keyword,
                current_content_format=current_format,
                gsc_keywords=[self._kw_to_dict(k) for k in gsc_analysis.performance.keywords],
                serp_results=[self._serp_to_dict(r) for r in (serp_analysis.organic_results if serp_analysis else [])],
                serp_features=[self._feature_to_dict(f) for f in (serp_analysis.features if serp_analysis else [])],
            )

        # 6. Détection de cannibalisation
        cannibalization = self.cannibalization_detector.detect(
            target_url=url,
            keywords_data=[self._kw_to_dict(k) for k in gsc_analysis.performance.keywords],
            sitemap_urls=self._sitemap_cache,
        )

        # 7. Calcul des scores
        overall_score = self._calculate_overall_score(html_analysis, gsc_analysis)
        eeat_score = self._calculate_eeat_score(html_analysis)
        freshness_score = self._calculate_freshness_score(html_analysis, gsc_analysis)

        # 8. Génération des alertes et recommandations
        alerts = self._generate_alerts(gsc_analysis, cannibalization, intent_analysis)
        recommendations = self._generate_recommendations(
            html_analysis, gsc_analysis, serp_analysis, intent_analysis
        )

        # 9. Suggestion d'action
        suggested_action, action_priority = self._suggest_action(
            gsc_analysis, cannibalization, intent_analysis, freshness_score
        )

        return AuditReport(
            url=url,
            blog_id=self.blog_config.get("blog_id", ""),
            audit_date=audit_date,
            html_analysis=html_analysis,
            gsc_analysis=gsc_analysis,
            serp_analysis=serp_analysis,
            cannibalization=cannibalization,
            intent_analysis=intent_analysis,
            overall_score=overall_score,
            eeat_score=eeat_score,
            freshness_score=freshness_score,
            alerts=alerts,
            recommendations=recommendations,
            suggested_action=suggested_action,
            action_priority=action_priority,
            assets=assets,
            provided_keyword=provided_keyword or "",
        )

    def quick_audit(self, url: str, html_content: str) -> dict:
        """
        Audit rapide pour le traitement en batch.

        Retourne un résumé simplifié sans analyse SERP complète.
        """
        html_analysis = self.html_analyzer.analyze(html_content, url)
        gsc_analysis = self.gsc_analyzer.analyze(url)

        overall_score = self._calculate_overall_score(html_analysis, gsc_analysis)
        freshness_score = self._calculate_freshness_score(html_analysis, gsc_analysis)

        return {
            "url": url,
            "word_count": html_analysis.word_count,
            "images": len(html_analysis.images),
            "internal_links": len(html_analysis.internal_links),
            "clicks_30d": gsc_analysis.performance.clicks_30d,
            "impressions_30d": gsc_analysis.performance.impressions_30d,
            "ctr_30d": gsc_analysis.performance.ctr_30d,
            "avg_position": gsc_analysis.performance.avg_position_30d,
            "is_declining": gsc_analysis.is_declining,
            "overall_score": overall_score,
            "freshness_score": freshness_score,
            "needs_refresh": freshness_score < 60 or gsc_analysis.is_declining,
        }

    def set_sitemap_cache(self, urls: list[str]):
        """Définit le cache du sitemap pour la détection de cannibalisation."""
        self._sitemap_cache = urls

    def _detect_current_format(self, html_analysis: HTMLAnalysisResult) -> ContentFormat:
        """Détecte le format actuel du contenu."""
        title = html_analysis.title.lower()
        h2_text = " ".join(html_analysis.headings.h2_list).lower()

        if html_analysis.has_faq_section:
            return ContentFormat.FAQ
        if "vs" in title or "comparatif" in title or "avis" in title:
            return ContentFormat.COMPARISON
        if any(char.isdigit() for char in title.split()[0:2]):
            return ContentFormat.LISTICLE
        if "comment" in title or "tutoriel" in title:
            return ContentFormat.TUTORIAL
        if "guide" in title:
            return ContentFormat.GUIDE

        return ContentFormat.OTHER

    def _calculate_overall_score(
        self,
        html: HTMLAnalysisResult,
        gsc: GSCAnalysisResult
    ) -> int:
        """Calcule le score global de l'article (0-100)."""
        score = 50  # Base

        # Contenu
        if html.word_count >= 1500:
            score += 10
        if len(html.headings.h2_list) >= 3:
            score += 5
        if html.has_faq_section:
            score += 5
        if html.has_table:
            score += 3
        if len(html.images) >= 2:
            score += 5

        # Performance
        if gsc.performance.ctr_30d >= 3.0:
            score += 10
        elif gsc.performance.ctr_30d >= 2.0:
            score += 5

        if gsc.performance.avg_position_30d <= 5:
            score += 10
        elif gsc.performance.avg_position_30d <= 10:
            score += 5

        # Pénalités
        if gsc.is_declining:
            score -= 15
        if gsc.indexation_status == "NOT_INDEXED":
            score -= 30

        return max(0, min(100, score))

    def _calculate_eeat_score(self, html: HTMLAnalysisResult) -> int:
        """Calcule le score E-E-A-T estimé (0-100)."""
        score = 25  # Base

        # Experience
        if "expérience" in html.text_content.lower() or "testé" in html.text_content.lower():
            score += 15

        # Expertise
        if html.word_count >= 1800:
            score += 10
        if len(html.headings.h2_list) >= 4:
            score += 5

        # Authoritativeness
        external_authority_links = sum(
            1 for link in html.external_links
            if any(auth in link.href for auth in ["gouv.fr", ".edu", "inserm", "has-sante"])
        )
        score += min(15, external_authority_links * 5)

        # Trustworthiness
        if html.has_faq_section:
            score += 5
        if html.has_table:
            score += 5
        if len(html.internal_links) >= 3:
            score += 5

        return max(0, min(100, score))

    def _calculate_freshness_score(
        self,
        html: HTMLAnalysisResult,
        gsc: GSCAnalysisResult
    ) -> int:
        """Calcule le score de fraîcheur du contenu (0-100)."""
        score = 70  # Base (on ne peut pas toujours détecter la date)

        # Tendances GSC
        if gsc.performance.clicks_trend > 10:
            score += 15
        elif gsc.performance.clicks_trend < -30:
            score -= 25
        elif gsc.performance.clicks_trend < -10:
            score -= 10

        # Perte de positions
        if gsc.performance.position_trend < -5:
            score -= 15

        # Indicateurs de contenu obsolète dans le texte
        text_lower = html.text_content.lower()
        old_years = ["2020", "2021", "2022", "2023"]
        for year in old_years:
            if year in text_lower:
                score -= 5

        return max(0, min(100, score))

    def _generate_alerts(
        self,
        gsc: GSCAnalysisResult,
        cannibalization: CannibalizationResult,
        intent: Optional[IntentAnalysisResult]
    ) -> list[str]:
        """Génère les alertes basées sur l'audit."""
        alerts = []

        # Alertes GSC
        alerts.extend(gsc.alert_messages)

        # Alerte indexation
        if gsc.indexation_status == "NOT_INDEXED":
            alerts.append("CRITIQUE: Page désindexée - Vérifier robots.txt et balises noindex")

        # Alerte cannibalisation
        if cannibalization.requires_action:
            alerts.append(f"CANNIBALISATION: {cannibalization.suggested_action}")

        # Alerte intention
        if intent and intent.intent_shift_detected:
            shift = intent.shifts[0] if intent.shifts else None
            if shift:
                alerts.append(
                    f"SHIFT D'INTENTION: {shift.from_intent.value} → {shift.to_intent.value} "
                    f"(confiance: {shift.confidence:.0f}%)"
                )

        return alerts

    def _generate_recommendations(
        self,
        html: HTMLAnalysisResult,
        gsc: GSCAnalysisResult,
        serp: Optional[SERPAnalysisResult],
        intent: Optional[IntentAnalysisResult]
    ) -> list[str]:
        """Génère les recommandations basées sur l'audit."""
        recommendations = []

        # Recommandations contenu
        if html.word_count < 1500:
            recommendations.append(
                f"Enrichir le contenu: {html.word_count} mots actuels, minimum recommandé: 1500"
            )

        if not html.has_faq_section:
            recommendations.append("Ajouter une section FAQ avec les questions PAA")

        if not html.has_table:
            recommendations.append("Ajouter un tableau récapitulatif pour améliorer la lisibilité")

        if len(html.images) < 2:
            recommendations.append(
                f"Ajouter des images: {len(html.images)} actuelles, minimum recommandé: 3"
            )

        # Recommandations CTR
        if gsc.performance.ctr_30d < 2.0 and gsc.performance.impressions_30d > 500:
            recommendations.append(
                "CTR faible - Optimiser le titre H1 et la meta description pour plus d'attractivité"
            )

        # Recommandations SERP
        if serp and serp.paa_questions:
            paa_sample = serp.paa_questions[:3]
            recommendations.append(
                f"Intégrer les PAA dans la FAQ: {', '.join(paa_sample[:2])}..."
            )

        # Recommandations intention
        if intent:
            recommendations.extend(intent.recommendations)

        return recommendations

    def _suggest_action(
        self,
        gsc: GSCAnalysisResult,
        cannibalization: CannibalizationResult,
        intent: Optional[IntentAnalysisResult],
        freshness_score: int
    ) -> tuple[str, int]:
        """Suggère l'action à prendre et sa priorité."""

        # Priorité 1: Page désindexée
        if gsc.indexation_status == "NOT_INDEXED":
            return "EEAT_REWRITE", 1

        # Priorité 1: Cannibalisation sévère
        if cannibalization.requires_action:
            if "Redirect 301" in cannibalization.suggested_action:
                return "REDIRECT_301", 1
            return "LONG_TAIL_SPECIALIZATION", 2

        # Priorité 1: Baisse d'impressions/clics → FULL_REFRESH (règle produit).
        # Toute page en déclin de trafic (clics ou impressions en baisse) est
        # rafraîchie en profondeur, quelle que soit la sévérité. Prime sur la
        # règle CTR ci-dessous : un contenu qui perd du trafic ne se corrige pas
        # au seul titre.
        if gsc.is_declining or gsc.decline_severity in ("severe", "moderate"):
            return "FULL_REFRESH", 1

        # Priorité 2: CTR faible avec bonnes impressions (trafic stable, pas en
        # baisse) → optimisation du titre suffit.
        if (gsc.performance.ctr_30d < 2.0 and
            gsc.performance.impressions_30d > 500):
            return "TITLE_OPTIMIZATION", 2

        # Priorité 2: Shift d'intention détecté
        if intent and intent.intent_shift_detected:
            return "SEMANTIC_REORIENTATION", 2

        # Priorité 3: Format mismatch
        if intent and intent.format_shift_detected:
            return "FORMAT_ADAPTATION", 3

        # Priorité 4: Contenu obsolète
        if freshness_score < 50:
            return "FULL_REFRESH", 3
        elif freshness_score < 70:
            return "PARTIAL_REFRESH", 4

        # Pas d'action nécessaire
        return "NO_ACTION", 5

    def _kw_to_dict(self, kw) -> dict:
        """Convertit un KeywordPerformance en dict."""
        return {
            "query": kw.query,
            "clicks": kw.clicks,
            "impressions": kw.impressions,
            "ctr": kw.ctr,
            "position": kw.position,
            "trend_clicks": getattr(kw, "trend_clicks", 0),
        }

    def _serp_to_dict(self, result) -> dict:
        """Convertit un SERPResult en dict."""
        return {
            "position": result.position,
            "url": result.url,
            "title": result.title,
            "format_type": result.format_type,
        }

    def _feature_to_dict(self, feature) -> dict:
        """Convertit une SERPFeature en dict."""
        return {
            "type": feature.feature_type,
            "questions": feature.questions if hasattr(feature, "questions") else [],
        }

    def to_dict(self, report: AuditReport) -> dict:
        """Convertit le rapport en dictionnaire pour export/Sheets."""
        # Utiliser le keyword fourni, sinon le main_keyword trouvé sur DataforSEO MCP server
        main_keyword = report.provided_keyword or (report.gsc_analysis.performance.main_keyword if report.gsc_analysis else "")
        self.logger.debug(f"[to_dict] url={report.url}, report.provided_keyword='{report.provided_keyword}', gsc_main_keyword='{report.gsc_analysis.performance.main_keyword if report.gsc_analysis else 'N/A'}', final main_keyword='{main_keyword}'")

        return {
            "url": report.url,
            "blog_id": report.blog_id,
            "main_keyword": main_keyword,  # Inclure au niveau racine pour decision engine
            "audit_date": report.audit_date,
            "overall_score": report.overall_score,
            "eeat_score": report.eeat_score,
            "freshness_score": report.freshness_score,
            "suggested_action": report.suggested_action,
            "action_priority": report.action_priority,
            "alerts": report.alerts,
            "recommendations": report.recommendations,
            "content": {
                "title": report.html_analysis.title,
                "meta_description": report.html_analysis.meta_description,
                "word_count": report.html_analysis.word_count,
                "h2_count": len(report.html_analysis.headings.h2_list),
                "image_count": len(report.html_analysis.images),
                "internal_links": len(report.html_analysis.internal_links),
                "external_links": len(report.html_analysis.external_links),
                "has_faq": report.html_analysis.has_faq_section,
                "has_table": report.html_analysis.has_table,
            },
            "performance": {
                "clicks_30d": report.gsc_analysis.performance.clicks_30d if report.gsc_analysis else 0,
                "impressions_30d": report.gsc_analysis.performance.impressions_30d if report.gsc_analysis else 0,
                "ctr_30d": report.gsc_analysis.performance.ctr_30d if report.gsc_analysis else 0.0,
                "avg_position": report.gsc_analysis.performance.avg_position_30d if report.gsc_analysis else 0.0,
                "main_keyword": report.gsc_analysis.performance.main_keyword if report.gsc_analysis else "",
                "is_declining": report.gsc_analysis.is_declining if report.gsc_analysis else False,
                "indexation_status": report.gsc_analysis.indexation_status if report.gsc_analysis else "UNKNOWN",
                # NEW: Export top GSC queries for refresh optimization
                "keywords": [
                    {
                        "query": kw.query,
                        "clicks": kw.clicks,
                        "impressions": kw.impressions,
                        "ctr": kw.ctr,
                        "position": kw.position,
                    }
                    for kw in (report.gsc_analysis.performance.keywords[:20] if report.gsc_analysis else [])
                ],
            },
            "cannibalization": {
                "has_issue": report.cannibalization.has_cannibalization,
                "requires_action": report.cannibalization.requires_action,
                "suggested_action": report.cannibalization.suggested_action,
            },
            "intent": {
                "shift_detected": report.intent_analysis.intent_shift_detected if report.intent_analysis else False,
                "format_mismatch": report.intent_analysis.format_shift_detected if report.intent_analysis else False,
            } if report.intent_analysis else None,
            "assets": report.assets,
        }

    def save_report(self, report: AuditReport, output_path: Path):
        """Sauvegarde le rapport en JSON."""
        report_dict = self.to_dict(report)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
