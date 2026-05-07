"""
Tests pour EditorialAuditor et FactChecker

Tests unitaires pour le système d'audit éditorial (Quality Gate).
"""

import pytest
from pathlib import Path
from scripts.audit.editorial_auditor import EditorialAuditor
from scripts.audit.fact_checker import FactChecker


class TestFactChecker:
    """Tests pour FactChecker (3-tier fact-checking)"""

    def test_check_parcoursup_dates_correct(self):
        """Test: Dates Parcoursup 2026 correctes → Aucune erreur"""
        checker = FactChecker()

        html_correct = """
        <html>
        <body>
            <h1>Parcoursup 2026 : Guide Complet</h1>
            <p>La plateforme Parcoursup ouvre le 19 janvier 2026.</p>
            <p>La date limite pour formuler vos vœux est fixée au 12 mars 2026.</p>
            <p>La finalisation du dossier doit être faite avant le 1er avril 2026.</p>
            <p>Les résultats de la phase principale seront publiés le 2 juin 2026.</p>
            <p>La phase complémentaire ouvrira le 11 juin 2026.</p>
        </body>
        </html>
        """

        results = checker.check_content(html_correct, topic="parcoursup_2026")

        # Vérifier qu'aucune erreur de date n'est détectée
        date_errors = [r for r in results if r.error_type in ["date_mismatch", "missing_date"]]
        assert len(date_errors) == 0, f"Dates correctes détectées comme erreurs: {date_errors}"

    def test_check_parcoursup_dates_incorrect(self):
        """Test: Dates Parcoursup 2025 (obsolètes) → Erreur détectée"""
        checker = FactChecker()

        html_incorrect = """
        <html>
        <body>
            <h1>Parcoursup 2026 : Guide</h1>
            <p>La date limite pour formuler vos vœux est le 12 mars 2025.</p>
        </body>
        </html>
        """

        results = checker.check_content(html_incorrect, topic="parcoursup_2026")

        # Vérifier qu'au moins une erreur de date est détectée
        date_errors = [r for r in results if r.error_type == "date_mismatch"]
        assert len(date_errors) > 0, "Année obsolète 2025 non détectée"

    def test_check_missing_entity(self):
        """Test: Entité CAES manquante → Erreur détectée"""
        checker = FactChecker()

        html_missing_entity = """
        <html>
        <body>
            <h1>Parcoursup 2026</h1>
            <p>Voici les informations importantes.</p>
        </body>
        </html>
        """

        results = checker.check_content(html_missing_entity, topic="parcoursup_2026")

        # Vérifier que l'entité manquante est détectée
        entity_errors = [r for r in results if r.error_type == "missing_entity" and "CAES" in (r.expected_value or "")]
        assert len(entity_errors) > 0, "Entité CAES manquante non détectée"

    def test_tier3_obsolete_stats(self):
        """Test: Statistiques > 24 mois → Avertissement"""
        checker = FactChecker()

        html_old_stats = """
        <html>
        <body>
            <p>Selon une étude de 2020, 75% des étudiants...</p>
            <p>En 2021, le taux de réussite était de 85%.</p>
        </body>
        </html>
        """

        results = checker.check_content(html_old_stats)

        # Vérifier que les stats obsolètes sont détectées
        obsolete_stats = [r for r in results if r.error_type == "obsolete_stat"]
        assert len(obsolete_stats) > 0, "Statistiques obsolètes 2020/2021 non détectées"


class TestEditorialAuditor:
    """Tests pour EditorialAuditor (orchestration audit)"""

    def test_topic_detection_parcoursup(self):
        """Test: Détection topic Parcoursup"""
        auditor = EditorialAuditor()

        html_parcoursup = """
        <html>
        <body>
            <h1>Parcoursup 2026 : Calendrier et Dates Clés</h1>
            <p>Le calendrier Parcoursup 2026 est désormais disponible.</p>
        </body>
        </html>
        """

        result = auditor.audit(
            url="https://example.fr/parcoursup-2026",
            html_content=html_parcoursup,
            blog_id="enseigna.fr"
        )

        assert result.topic == "parcoursup_2026", f"Topic détecté: {result.topic}, attendu: parcoursup_2026"

    def test_quality_gate_blocking(self):
        """Test: Quality Gate bloque si score < 4"""
        auditor = EditorialAuditor()

        # HTML avec erreurs multiples (dates incorrectes + stats obsolètes)
        html_mauvais = """
        <html>
        <body>
            <h1>Parcoursup 2026</h1>
            <p>La date limite est le 12 mars 2025.</p>
            <p>Selon une étude de 2020, 80% des étudiants...</p>
            <p>Il est important de bien préparer votre dossier.</p>
            <p>N'oubliez pas que Parcoursup est crucial.</p>
        </body>
        </html>
        """

        result = auditor.audit(
            url="https://example.fr/parcoursup-mauvais",
            html_content=html_mauvais,
            blog_id="enseigna.fr"
        )

        # Vérifier que le score est < 4 (seuil de blocage)
        assert result.overall_score < 4.0, f"Score: {result.overall_score}, attendu < 4.0"
        assert not result.should_proceed, "should_proceed devrait être False pour score < 4"
        assert len(result.blocking_issues) > 0, "blocking_issues devrait contenir des erreurs"

    def test_quality_gate_passing(self):
        """Test: Quality Gate passe si score >= 4"""
        auditor = EditorialAuditor()

        # HTML correct avec dates valides, toutes les entités requises et sources
        html_bon = """
        <html>
        <body>
            <h1>Parcoursup 2026 : Guide Complet</h1>
            <p>La plateforme Parcoursup ouvre le 19 janvier 2026.</p>
            <p>La date limite pour formuler vos vœux est le 12 mars 2026.</p>
            <p>La finalisation du dossier doit être faite avant le 1er avril 2026.</p>
            <p>Les résultats seront publiés le 2 juin 2026.</p>
            <p>La phase complémentaire ouvrira le 11 juin 2026.</p>
            <p>Source: <a href="https://parcoursup.gouv.fr">parcoursup.gouv.fr</a></p>
            <p>La CAES (Commission d'Accès à l'Enseignement Supérieur) accompagne les étudiants.</p>
            <p>Les étudiants ambassadeurs sont disponibles pour répondre à vos questions.</p>
            <p>Vous pouvez formuler des vœux multiples et des sous-vœux pour les formations en apprentissage.</p>
            <p>Référence: <a href="https://education.gouv.fr">education.gouv.fr</a></p>
        </body>
        </html>
        """

        result = auditor.audit(
            url="https://example.fr/parcoursup-bon",
            html_content=html_bon,
            blog_id="enseigna.fr"
        )

        # Vérifier que le score est >= 4
        assert result.overall_score >= 4.0, f"Score: {result.overall_score}, attendu >= 4.0"
        assert result.should_proceed, "should_proceed devrait être True pour score >= 4"

    def test_eeat_source_detection(self):
        """Test: Détection sources E-E-A-T"""
        auditor = EditorialAuditor()

        html_with_sources = """
        <html>
        <body>
            <h1>Article de qualité</h1>
            <p>Contenu informatif.</p>
            <p>Source: <a href="https://parcoursup.gouv.fr">parcoursup.gouv.fr</a></p>
            <p>Référence: <a href="https://education.gouv.fr">education.gouv.fr</a></p>
        </body>
        </html>
        """

        result = auditor.audit(
            url="https://example.fr/article-sources",
            html_content=html_with_sources,
            blog_id="enseigna.fr"
        )

        # Vérifier que les sources sont détectées
        assert result.eeat_score > 0, "E-E-A-T score devrait être > 0 avec sources"

    def test_markdown_report_generation(self):
        """Test: Génération rapport markdown"""
        auditor = EditorialAuditor()

        html_test = """
        <html>
        <body>
            <h1>Test Article</h1>
            <p>Contenu de test.</p>
        </body>
        </html>
        """

        result = auditor.audit(
            url="https://example.fr/test-report",
            html_content=html_test,
            blog_id="test.fr"
        )

        # Générer le rapport
        report_md = auditor.generate_markdown_report(result)

        # Vérifications basiques du format markdown
        assert "# Editorial Audit Report" in report_md, "Titre principal manquant"
        assert "## Score Breakdown" in report_md, "Section Scores manquante"
        assert result.url in report_md, "URL manquante dans le rapport"
        assert "**Overall Score**" in report_md, "Score global manquant"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
