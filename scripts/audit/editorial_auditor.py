"""
Editorial Auditor Module

Orchestrates editorial audit for quality gate (pre-refresh).

Scoring algorithm (1-10):
- Truth (40%): Factual accuracy
- E-E-A-T (30%): Experience, Expertise, Authority, Trust
- Freshness (20%): Data recency
- Genericness (10%): Avoid generic statements

Quality Gate: Score < 4 → BLOCK refresh
"""

from pathlib import Path
from typing import List, Optional
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import re

from _shared.core.models.audit_models import (
    EditorialAuditResult,
    FactCheckResult,
    EEATDiagnosis
)
from .fact_checker import FactChecker

logger = logging.getLogger(__name__)


class EditorialAuditor:
    """
    Editorial audit orchestrator with quality gate.

    Workflow:
    1. Detect topic (if applicable)
    2. Fact-check content (Tier 1-3)
    3. Evaluate E-E-A-T
    4. Check freshness
    5. Detect generic statements
    6. Calculate final score (1-10)
    7. Quality gate decision
    8. Generate markdown report
    """

    def __init__(
        self,
        rules_path: Optional[Path] = None,
        llm_client=None
    ):
        """
        Initialize editorial auditor.

        Args:
            rules_path: Path to editorial_rules.json
            llm_client: Optional LLM client for Tier 2 verification
        """
        self.rules_path = rules_path or (
            Path(__file__).parent.parent.parent / "_shared" / "config" / "editorial_rules.json"
        )
        self.llm_client = llm_client
        self.fact_checker = FactChecker(self.rules_path, llm_client)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        """Load editorial rules."""
        if not self.rules_path.exists():
            return {"topics": {}, "global_rules": {}, "scoring": {}}

        with self.rules_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def audit(
        self,
        url: str,
        html_content: str,
        blog_id: str = "",
        use_llm_verification: bool = False
    ) -> EditorialAuditResult:
        """
        Run full editorial audit.

        Args:
            url: Article URL
            html_content: HTML content
            blog_id: Blog identifier (for YMYL level detection)
            use_llm_verification: Enable expensive LLM verification (Tier 2)

        Returns:
            EditorialAuditResult with score and quality gate decision
        """
        start_time = datetime.now()

        # Step 1: Detect topic
        topic = self._detect_topic(html_content)

        # Step 2: Detect YMYL level
        ymyl_level = self._detect_ymyl_level(topic, blog_id)

        # Step 3: Fact-check content
        fact_checks = self.fact_checker.check_content(
            html_content,
            topic=topic,
            use_llm=use_llm_verification
        )

        # Count errors by severity
        factual_errors_count = sum(1 for fc in fact_checks if not fc.is_valid)
        critical_errors_count = sum(
            1 for fc in fact_checks
            if not fc.is_valid and fc.severity == "critical"
        )

        # Step 4: Evaluate E-E-A-T
        eeat_diagnosis = self._evaluate_eeat(html_content, topic, ymyl_level)

        # Step 5: Check freshness
        obsolete_stats_count = sum(
            1 for fc in fact_checks
            if fc.error_type == "obsolete_stat"
        )
        missing_dates_count = sum(
            1 for fc in fact_checks
            if fc.error_type == "missing_date"
        )

        # Step 6: Detect generic statements
        generic_statements, forbidden_found = self._detect_generic_statements(
            html_content,
            topic
        )

        # Step 7: Calculate scores
        truth_score = self._calculate_truth_score(fact_checks)
        eeat_score = eeat_diagnosis.overall_score
        freshness_score = self._calculate_freshness_score(
            obsolete_stats_count,
            missing_dates_count
        )
        genericness_score = self._calculate_genericness_score(len(generic_statements))

        # Step 8: Calculate final score (1-10) with penalties
        overall_score = self._calculate_overall_score(
            truth_score,
            eeat_score,
            freshness_score,
            genericness_score,
            critical_errors_count,
            factual_errors_count,
            len(generic_statements)
        )

        # Step 9: Quality gate decision
        threshold = self.rules.get("scoring", {}).get("quality_gate_threshold", 4)
        should_proceed = overall_score >= threshold

        # Step 10: Generate recommendations and blocking issues
        blocking_issues = []
        recommendations = []

        if critical_errors_count > 0:
            blocking_issues.append(
                f"{critical_errors_count} erreur(s) factuelle(s) critique(s) détectée(s)"
            )

        if eeat_score < 50 and ymyl_level in ["very_high", "high"]:
            blocking_issues.append(
                f"Score E-E-A-T trop faible ({eeat_score}/100) pour contenu YMYL {ymyl_level}"
            )

        if not should_proceed:
            recommendations.extend(self._generate_recommendations(
                fact_checks,
                eeat_diagnosis,
                obsolete_stats_count,
                generic_statements
            ))

        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return EditorialAuditResult(
            url=url,
            topic=topic,
            ymyl_level=ymyl_level,
            truth_score=truth_score,
            eeat_score=eeat_score,
            freshness_score=freshness_score,
            genericness_score=genericness_score,
            overall_score=round(overall_score, 1),
            fact_checks=fact_checks,
            factual_errors_count=factual_errors_count,
            critical_errors_count=critical_errors_count,
            eeat_diagnosis=eeat_diagnosis,
            obsolete_stats_count=obsolete_stats_count,
            missing_dates_count=missing_dates_count,
            generic_statements_count=len(generic_statements),
            forbidden_generics_found=forbidden_found,
            should_proceed=should_proceed,
            blocking_issues=blocking_issues,
            recommendations=recommendations,
            audit_date=datetime.now().isoformat(),
            execution_time_ms=execution_time_ms
        )

    def _detect_topic(self, html_content: str) -> Optional[str]:
        """
        Detect topic from content (basic keyword matching).

        Args:
            html_content: HTML content

        Returns:
            Topic identifier (e.g., "parcoursup_2026") or None
        """
        soup = BeautifulSoup(html_content, "lxml")
        text = soup.get_text(separator=" ", strip=True).lower()

        # Simple keyword matching (can be enhanced with ML)
        topic_keywords = {
            "parcoursup_2026": ["parcoursup", "2026", "vœux", "admission"],
            "brevet_2026": ["brevet", "dnb", "collège", "2026"],
            "bac_2026": ["baccalauréat", "bac", "lycée", "2026", "spécialités"],
            "yoga_health": ["yoga", "posture", "asana", "pranayama"],
            "sport_fitness": ["musculation", "fitness", "exercice", "entraînement"]
        }

        for topic, keywords in topic_keywords.items():
            matches = sum(1 for kw in keywords if kw in text)
            # Need at least 2 keyword matches
            if matches >= 2:
                return topic

        return None

    def _detect_ymyl_level(self, topic: Optional[str], blog_id: str) -> str:
        """
        Detect YMYL level from topic or blog.

        Args:
            topic: Detected topic
            blog_id: Blog identifier

        Returns:
            YMYL level: "very_high", "high", "medium", "low"
        """
        # From topic rules
        if topic and topic in self.rules.get("topics", {}):
            return self.rules["topics"][topic].get("ymyl_level", "low")

        # From blog ID (fallback)
        ymyl_by_blog = {
            "enseigna.fr": "high",
            "superprof.fr": "low",
        }

        return ymyl_by_blog.get(blog_id, "low")

    def _evaluate_eeat(
        self,
        html_content: str,
        topic: Optional[str],
        ymyl_level: str
    ) -> EEATDiagnosis:
        """
        Evaluate E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness).

        Args:
            html_content: HTML content
            topic: Detected topic
            ymyl_level: YMYL level

        Returns:
            EEATDiagnosis
        """
        soup = BeautifulSoup(html_content, "lxml")
        text = soup.get_text(separator=" ", strip=True).lower()

        # Count sources (links to authoritative domains)
        sources_count = 0
        sources_authoritative_count = 0

        authoritative_domains = self._get_authoritative_domains(topic)

        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            sources_count += 1

            # Check if authoritative
            if any(domain in href for domain in authoritative_domains):
                sources_authoritative_count += 1

        # Check disclaimers
        disclaimers_required = False
        disclaimers_present = False

        if topic and topic in self.rules.get("topics", {}):
            topic_rules = self.rules["topics"][topic]
            required_disclaimers = topic_rules.get("required_disclaimers", [])

            if required_disclaimers:
                disclaimers_required = True
                disclaimers_present = any(
                    disclaimer.lower() in text
                    for disclaimer in required_disclaimers
                )

        # Calculate scores (simplified heuristics)
        # Experience score: Based on storytelling indicators
        experience_score = min(100, sources_count * 10)

        # Expertise score: Based on authoritative sources
        expertise_score = min(100, sources_authoritative_count * 20)

        # Authoritativeness score: Based on source quality
        authority_ratio = sources_authoritative_count / max(sources_count, 1)
        authoritativeness_score = int(authority_ratio * 100)

        # Trustworthiness score: Based on disclaimers + transparency
        trustworthiness_score = 50  # Base score
        if disclaimers_required and disclaimers_present:
            trustworthiness_score += 50
        elif disclaimers_required and not disclaimers_present:
            trustworthiness_score -= 30

        # Overall E-E-A-T score (weighted average)
        overall_score = int(
            experience_score * 0.2 +
            expertise_score * 0.3 +
            authoritativeness_score * 0.3 +
            trustworthiness_score * 0.2
        )

        issues = []
        strengths = []

        if sources_authoritative_count == 0 and ymyl_level in ["very_high", "high"]:
            issues.append("Aucune source autoritaire pour contenu YMYL")

        if disclaimers_required and not disclaimers_present:
            issues.append("Disclaimers requis manquants")

        if sources_authoritative_count >= 2:
            strengths.append(f"{sources_authoritative_count} sources autoritaires")

        return EEATDiagnosis(
            experience_score=experience_score,
            expertise_score=expertise_score,
            authoritativeness_score=authoritativeness_score,
            trustworthiness_score=trustworthiness_score,
            overall_score=overall_score,
            sources_count=sources_count,
            sources_authoritative_count=sources_authoritative_count,
            disclaimers_present=disclaimers_present,
            disclaimers_required=disclaimers_required,
            issues=issues,
            strengths=strengths
        )

    def _get_authoritative_domains(self, topic: Optional[str]) -> List[str]:
        """Get list of authoritative domains for topic."""
        if not topic or topic not in self.rules.get("topics", {}):
            return []

        return self.rules["topics"][topic].get("authoritative_sources", [])

    def _detect_generic_statements(
        self,
        html_content: str,
        topic: Optional[str]
    ) -> tuple[List[str], List[str]]:
        """
        Detect generic/vague statements.

        Returns:
            (list of generic statements found, list of forbidden generics found)
        """
        soup = BeautifulSoup(html_content, "lxml")
        text = soup.get_text(separator=" ", strip=True).lower()

        # Get forbidden generics from rules
        forbidden_global = self.rules.get("global_rules", {}).get("forbidden_generics_global", [])
        forbidden_topic = []

        if topic and topic in self.rules.get("topics", {}):
            forbidden_topic = self.rules["topics"][topic].get("forbidden_generics", [])

        forbidden_all = forbidden_global + forbidden_topic

        # Find matches
        found_generics = []
        for generic in forbidden_all:
            if generic.lower() in text:
                found_generics.append(generic)

        return found_generics, found_generics

    def _calculate_truth_score(self, fact_checks: List[FactCheckResult]) -> int:
        """
        Calculate truth score (0-100) from fact checks.

        Args:
            fact_checks: List of fact check results

        Returns:
            Truth score (0-100)
        """
        if not fact_checks:
            return 100  # No checks = assume true

        errors = [fc for fc in fact_checks if not fc.is_valid]
        critical_errors = [fc for fc in errors if fc.severity == "critical"]

        # Severe penalty for critical errors
        score = 100
        score -= len(critical_errors) * 30  # -30 per critical error
        score -= (len(errors) - len(critical_errors)) * 10  # -10 per other error

        return max(0, score)

    def _calculate_freshness_score(
        self,
        obsolete_stats_count: int,
        missing_dates_count: int
    ) -> int:
        """Calculate freshness score (0-100)."""
        score = 100
        score -= obsolete_stats_count * 15  # -15 per obsolete stat
        score -= missing_dates_count * 10  # -10 per missing date

        return max(0, score)

    def _calculate_genericness_score(self, generic_count: int) -> int:
        """Calculate genericness score (0-100)."""
        max_allowed = self.rules.get("global_rules", {}).get("max_generic_statements", 3)

        score = 100
        if generic_count > max_allowed:
            score -= (generic_count - max_allowed) * 15

        return max(0, score)

    def _calculate_overall_score(
        self,
        truth_score: int,
        eeat_score: int,
        freshness_score: int,
        genericness_score: int,
        critical_errors: int,
        factual_errors: int,
        generic_count: int
    ) -> float:
        """
        Calculate overall score (1-10) with weighted components + penalties.

        Formula:
        Base = Truth*0.4 + EEAT*0.3 + Freshness*0.2 + Genericness*0.1
        Final = (Base / 10) - Penalties
        """
        scoring_config = self.rules.get("scoring", {})
        weights = {
            "truth": scoring_config.get("truth_weight", 0.40),
            "eeat": scoring_config.get("eeat_weight", 0.30),
            "freshness": scoring_config.get("freshness_weight", 0.20),
            "genericness": scoring_config.get("genericness_weight", 0.10)
        }

        # Weighted average (0-100)
        base_score = (
            truth_score * weights["truth"] +
            eeat_score * weights["eeat"] +
            freshness_score * weights["freshness"] +
            genericness_score * weights["genericness"]
        )

        # Convert to 1-10 scale
        score_1_10 = base_score / 10

        # Apply penalties
        penalties = scoring_config.get("penalties", {})
        penalty = 0

        penalty += critical_errors * penalties.get("critical_factual_error", -2)
        penalty += max(0, factual_errors - critical_errors) * penalties.get("obsolete_stat", -1)
        penalty += min(generic_count * penalties.get("generic_statement", -0.5),
                       penalties.get("max_generic_penalty", -2))

        final_score = max(1.0, min(10.0, score_1_10 + penalty))

        return final_score

    def _generate_recommendations(
        self,
        fact_checks: List[FactCheckResult],
        eeat_diagnosis: EEATDiagnosis,
        obsolete_count: int,
        generic_statements: List[str]
    ) -> List[str]:
        """Generate recommendations for improvement."""
        recommendations = []

        # Factual errors
        critical_errors = [fc for fc in fact_checks if not fc.is_valid and fc.severity == "critical"]
        if critical_errors:
            recommendations.append(
                f"Corriger {len(critical_errors)} erreur(s) factuelle(s) critique(s)"
            )

        # E-E-A-T improvements
        if eeat_diagnosis.sources_authoritative_count == 0:
            recommendations.append("Ajouter au moins 2 sources autoritaires")

        if eeat_diagnosis.disclaimers_required and not eeat_diagnosis.disclaimers_present:
            recommendations.append("Ajouter disclaimers requis (santé/sécurité)")

        # Freshness
        if obsolete_count > 0:
            recommendations.append(f"Mettre à jour {obsolete_count} statistique(s) obsolète(s)")

        # Genericness
        if len(generic_statements) > 3:
            recommendations.append(
                f"Supprimer {len(generic_statements) - 3} formulation(s) générique(s) en trop"
            )

        return recommendations

    def generate_markdown_report(self, result: EditorialAuditResult) -> str:
        """
        Generate markdown editorial audit report.

        Args:
            result: EditorialAuditResult

        Returns:
            Markdown report
        """
        verdict = "✅ PASSED" if result.should_proceed else "🚫 BLOCKED"
        score_color = "🟢" if result.overall_score >= 7 else "🟡" if result.overall_score >= 4 else "🔴"

        report = f"""# Editorial Audit Report

**URL**: {result.url}
**Verdict**: {verdict} ({score_color} {result.overall_score}/10)
**Date**: {result.audit_date}
**Topic**: {result.topic or "Non détecté"}
**YMYL Level**: {result.ymyl_level}

---

## Score Breakdown

| Component | Score | Weight |
|-----------|-------|--------|
| **Truth** | {result.truth_score}/100 | 40% |
| **E-E-A-T** | {result.eeat_score}/100 | 30% |
| **Freshness** | {result.freshness_score}/100 | 20% |
| **Genericness** | {result.genericness_score}/100 | 10% |

**Overall Score**: **{result.overall_score}/10**

---

## Issues Detected

"""

        if result.blocking_issues:
            report += "### 🚫 Blocking Issues\n\n"
            for issue in result.blocking_issues:
                report += f"- {issue}\n"
            report += "\n"

        if result.factual_errors_count > 0:
            report += f"### Factual Errors ({result.factual_errors_count})\n\n"
            for fc in result.fact_checks:
                if not fc.is_valid:
                    severity_icon = "🔴" if fc.severity == "critical" else "🟡"
                    report += f"{severity_icon} **{fc.error_type}**: {fc.context}\n"
                    if fc.expected_value:
                        report += f"  - Expected: `{fc.expected_value}`\n"
                    if fc.found_value:
                        report += f"  - Found: `{fc.found_value}`\n"
                    report += "\n"

        if result.eeat_diagnosis and result.eeat_diagnosis.issues:
            report += "### E-E-A-T Issues\n\n"
            for issue in result.eeat_diagnosis.issues:
                report += f"- {issue}\n"
            report += "\n"

        if result.generic_statements_count > 0:
            report += f"### Generic Statements ({result.generic_statements_count})\n\n"
            for generic in result.forbidden_generics_found[:5]:
                report += f"- \"{generic}\"\n"
            report += "\n"

        # Recommendations
        if result.recommendations:
            report += "## Recommendations\n\n"
            for i, rec in enumerate(result.recommendations, 1):
                report += f"{i}. {rec}\n"
            report += "\n"

        # E-E-A-T Strengths
        if result.eeat_diagnosis and result.eeat_diagnosis.strengths:
            report += "## Strengths\n\n"
            for strength in result.eeat_diagnosis.strengths:
                report += f"- ✅ {strength}\n"
            report += "\n"

        report += "---\n\n"
        report += f"*Execution time: {result.execution_time_ms}ms*\n"

        return report
