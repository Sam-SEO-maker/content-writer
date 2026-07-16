"""
Tests for the YearUpdater Module

Tests de détection et remplacement d'années obsolètes avec exclusions intelligentes.
"""

import unittest
from _shared.core.utils.year_updater import YearUpdater


class TestYearUpdaterDetection(unittest.TestCase):
    """Tests pour la détection des années obsolètes."""

    def setUp(self):
        """Initialise le YearUpdater pour chaque test."""
        self.updater = YearUpdater(target_year=2026)

    def test_detect_simple_years(self):
        """Test la détection simple d'années."""
        text = "Guide 2025 pour apprendre"
        matches = self.updater.detect_obsolete_years(text)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['match'], '2025')
        self.assertIn('Guide 2025', matches[0]['context'])

    def test_detect_multiple_years(self):
        """Test la détection de multiples années dans le même texte."""
        text = "En 2024 et 2025, les tendances..."
        matches = self.updater.detect_obsolete_years(text)

        self.assertEqual(len(matches), 2)
        years = {m['match'] for m in matches}
        self.assertEqual(years, {'2024', '2025'})

    def test_detect_2024_and_2025(self):
        """Test que à la fois 2024 et 2025 sont détectés."""
        text = "Mise à jour 2024 pour l'année 2025"
        matches = self.updater.detect_obsolete_years(text)

        self.assertEqual(len(matches), 2)
        years_found = [m['match'] for m in matches]
        self.assertIn('2024', years_found)
        self.assertIn('2025', years_found)

    def test_no_detection_of_future_years(self):
        """Test que les années futures ne sont pas détectées."""
        text = "Plan pour 2027 et 2028"
        matches = self.updater.detect_obsolete_years(text)

        self.assertEqual(len(matches), 0)

    def test_detect_in_parentheses(self):
        """Test la détection entre parenthèses (mais sera exclue comme citation)."""
        text = "Les données (Smith, 2025) montrent..."
        matches = self.updater.detect_obsolete_years(text)

        self.assertGreaterEqual(len(matches), 1)
        # L'année est détectée, mais marquée pour exclusion potentielle


class TestYearUpdaterExclusions(unittest.TestCase):
    """Tests pour les patterns d'exclusion."""

    def setUp(self):
        """Initialise le YearUpdater."""
        self.updater = YearUpdater(target_year=2026)

    def test_exclude_urls(self):
        """Test l'exclusion des URLs."""
        context = "https://example.com/guide-2025"
        self.assertTrue(self.updater.should_exclude(context))

    def test_exclude_citations(self):
        """Test l'exclusion des citations académiques."""
        context = "Selon Smith (2025), les données..."
        self.assertTrue(self.updater.should_exclude(context))

    def test_exclude_references(self):
        """Test l'exclusion des références bibliographiques."""
        context = "[Johnson 2025] étude publiée"
        self.assertTrue(self.updater.should_exclude(context))

    def test_exclude_historical_comparisons(self):
        """Test l'exclusion des comparaisons historiques."""
        context = "Évolution 2024 vs 2025 par rapport aux données"
        self.assertTrue(self.updater.should_exclude(context))

    def test_exclude_link_href(self):
        """Test l'exclusion des attributs href dans les balises <a>."""
        context = '<a href="/guide-2025">Lire l\'article</a>'
        self.assertTrue(self.updater.should_exclude(context))

    def test_not_exclude_regular_text(self):
        """Test que le texte régulier n'est pas exclu."""
        context = "Les tendances 2025 montrent une augmentation"
        self.assertFalse(self.updater.should_exclude(context))


class TestYearUpdaterReplacement(unittest.TestCase):
    """Tests pour le remplacement des années."""

    def setUp(self):
        """Initialise le YearUpdater."""
        self.updater = YearUpdater(target_year=2026)

    def test_simple_replacement(self):
        """Test le remplacement simple d'une année."""
        text = "Guide 2025 pour apprendre"
        modified, changes = self.updater.replace_years(text)

        self.assertEqual(modified, "Guide 2026 pour apprendre")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['original'], '2025')
        self.assertEqual(changes[0]['replacement'], '2026')

    def test_multiple_replacements(self):
        """Test le remplacement de multiples années."""
        text = "En 2024, les données montrent. En 2025, c'est plus clair."
        modified, changes = self.updater.replace_years(text)

        self.assertIn('2026', modified)
        self.assertEqual(len(changes), 2)

    def test_no_replacement_with_exclusions(self):
        """Test que les exclusions empêchent le remplacement."""
        text = "Voir https://example.com/guide-2025"
        modified, changes = self.updater.replace_years(
            text,
            exclude_patterns=['url']
        )

        # URL doit être préservée
        self.assertIn('2025', modified)
        self.assertEqual(len(changes), 0)

    def test_selective_replacement(self):
        """Test le remplacement sélectif avec exclusions partielles."""
        text = "Guide 2025 sur https://example.com/2025"
        modified, changes = self.updater.replace_years(
            text,
            exclude_patterns=['url']
        )

        # "Guide 2025" doit être remplacé
        self.assertIn('Guide 2026', modified)
        # "https://example.com/2025" doit être préservé
        self.assertIn('https://example.com/2025', modified)

    def test_preserve_citations(self):
        """Test la préservation des citations."""
        text = "Selon Smith (2025), les données... Guide 2025 complet"
        modified, changes = self.updater.replace_years(
            text,
            exclude_patterns=['citation']
        )

        # La citation doit être préservée
        self.assertIn('Smith (2025)', modified)
        # Le titre doit être remplacé
        self.assertIn('Guide 2026', modified)

    def test_preserve_references(self):
        """Test la préservation des références."""
        text = "[Johnson 2025]. Article 2025 mis à jour"
        modified, changes = self.updater.replace_years(
            text,
            exclude_patterns=['reference']
        )

        # La référence doit être préservée
        self.assertIn('[Johnson 2025]', modified)
        # "Article 2025" doit être remplacé
        self.assertIn('Article 2026', modified)


class TestYearUpdaterStatistics(unittest.TestCase):
    """Tests pour les statistiques et résumés."""

    def setUp(self):
        """Initialise le YearUpdater."""
        self.updater = YearUpdater(target_year=2026)

    def test_get_changes_summary_no_changes(self):
        """Test le résumé quand aucun changement."""
        text = "Contenu sans dates"
        self.updater.replace_years(text)
        summary = self.updater.get_changes_summary()

        self.assertEqual(summary, "Aucune année mise à jour")

    def test_get_changes_summary_with_changes(self):
        """Test le résumé avec changements."""
        text = "Guide 2025 et données 2024"
        self.updater.replace_years(text)
        summary = self.updater.get_changes_summary()

        self.assertIn("2", summary)  # Au moins 2 changements
        self.assertIn("2026", summary)  # Année cible

    def test_get_statistics(self):
        """Test les statistiques complètes."""
        text = "Guide 2025 et article 2025 et données 2024"
        self.updater.replace_years(text)
        stats = self.updater.get_statistics()

        self.assertEqual(stats['total_changes'], 3)
        self.assertIn('2025', stats['years_replaced'])
        self.assertIn('2024', stats['years_replaced'])
        self.assertEqual(stats['years_replaced']['2025'], 2)
        self.assertEqual(stats['years_replaced']['2024'], 1)


class TestYearUpdaterEdgeCases(unittest.TestCase):
    """Tests pour les cas limites."""

    def setUp(self):
        """Initialise le YearUpdater."""
        self.updater = YearUpdater(target_year=2026)

    def test_empty_text(self):
        """Test avec texte vide."""
        text = ""
        matches = self.updater.detect_obsolete_years(text)
        self.assertEqual(len(matches), 0)

    def test_year_at_text_boundaries(self):
        """Test avec année au début et fin du texte."""
        text = "2025 est l'année 2025"
        matches = self.updater.detect_obsolete_years(text)
        self.assertEqual(len(matches), 2)

    def test_custom_target_year(self):
        """Test avec année cible personnalisée."""
        updater = YearUpdater(target_year=2027)
        text = "Guide 2025"
        modified, changes = updater.replace_years(text)

        self.assertEqual(modified, "Guide 2027")
        self.assertEqual(changes[0]['replacement'], '2027')

    def test_auto_target_year(self):
        """Test avec année cible automatique (année courante)."""
        from datetime import datetime
        updater = YearUpdater(target_year=None)

        text = "Guide 2025"
        modified, changes = updater.replace_years(text)

        current_year = datetime.now().year
        expected = f"Guide {current_year}"
        self.assertEqual(modified, expected)

    def test_word_boundary_matching(self):
        """Test que seules les années complètes sont remplacées."""
        text = "Année20252 n'existe pas, mais 2025 oui"
        matches = self.updater.detect_obsolete_years(text)

        # Seul "2025" doit être détecté, pas "20252"
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['match'], '2025')


class TestYearUpdaterIntegration(unittest.TestCase):
    """Tests d'intégration complets."""

    def setUp(self):
        """Initialise le YearUpdater."""
        self.updater = YearUpdater(target_year=2026)

    def test_complex_html_content(self):
        """Test avec contenu HTML complexe."""
        html = """
        <h1>Guide 2025 pour apprendre l'anglais</h1>
        <p>En 2025, les méthodes d'apprentissage ont évolué.</p>
        <p>Selon Smith (2025), 70% des étudiants réussissent.</p>
        <p><a href="https://example.com/study-2025">Voir l'étude</a></p>
        """
        modified, changes = self.updater.replace_years(
            html,
            exclude_patterns=['citation', 'url', 'href']
        )

        # Le titre doit être mis à jour
        self.assertIn('Guide 2026', modified)
        # "En 2025" doit être mis à jour
        self.assertIn('En 2026', modified)
        # La citation doit être préservée
        self.assertIn('Smith (2025)', modified)
        # L'URL doit être préservée
        self.assertIn('study-2025', modified)

    def test_all_exclusion_patterns(self):
        """Test avec tous les patterns d'exclusion."""
        text = """
        Guide 2025 (Smith, 2025) [1] Étude 2025
        https://example.com/guide-2025
        Évolution 2024 vs 2025
        """
        modified, changes = self.updater.replace_years(
            text,
            exclude_patterns=['url', 'citation', 'reference', 'historical']
        )

        # "Guide 2025" (hors citation) → remplacé
        self.assertIn('Guide 2026', modified)
        # Citation (Smith, 2025) préservée
        self.assertIn('(Smith, 2025)', modified)
        # URL préservée (exclusion url)
        self.assertIn('guide-2025', modified)
        # Comparaison historique préservée (exclusion historical)
        self.assertIn('2024 vs 2025', modified)


if __name__ == '__main__':
    unittest.main()
