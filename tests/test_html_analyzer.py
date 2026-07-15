"""
Tests pour le module html_analyzer.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.audit.html_analyzer import HTMLAnalyzer


class TestHTMLAnalyzer:
    """Tests pour HTMLAnalyzer."""

    def setup_method(self):
        """Setup avant chaque test."""
        self.analyzer = HTMLAnalyzer(domain="superprof.fr")

    def test_extract_title(self, sample_html):
        """Test extraction du titre H1."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        assert result["h1"] == "Comment apprendre les maths efficacement"

    def test_extract_meta_description(self, sample_html):
        """Test extraction meta description."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        assert "conseils pour apprendre les maths" in result["meta_description"]

    def test_count_images(self, sample_html):
        """Test comptage des images."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        assert result["images_count"] == 2
        assert len(result["images"]) == 2

    def test_extract_image_details(self, sample_html):
        """Test extraction détails images."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        images = result["images"]

        # Vérifier la première image
        assert any(img["src"] == "/images/math-formulas.jpg" for img in images)
        assert any(img["alt"] == "Formules mathématiques" for img in images)

    def test_count_headings(self, sample_html):
        """Test comptage des headings."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        assert result["h1_count"] == 1
        assert result["h2_count"] == 4  # bases, méthodes, ressources, FAQ

    def test_extract_internal_links(self, sample_html):
        """Test extraction liens internes."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        internal_links = result["internal_links"]

        # Liens commençant par /
        assert any(link["href"] == "/cours-maths" for link in internal_links)
        assert any(link["href"] == "/ressources-maths" for link in internal_links)

    def test_extract_external_links(self, sample_html):
        """Test extraction liens externes."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        external_links = result["external_links"]

        assert any("superprof.fr" in link["href"] for link in external_links)
        assert any("eduscol.education.fr" in link["href"] for link in external_links)

    def test_detect_superprof_link(self, sample_html):
        """Test détection lien Superprof."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        assert result["has_superprof_link"] is True
        assert result["superprof_link_count"] == 1

    def test_no_superprof_link(self, sample_html_no_superprof):
        """Test absence lien Superprof."""
        result = self.analyzer.analyze(sample_html_no_superprof, "https://superprof.fr/ressources/test.html")
        assert result["has_superprof_link"] is False
        assert result["superprof_link_count"] == 0

    def test_detect_blacklisted_links(self, sample_html_blacklisted):
        """Test détection liens blacklistés."""
        result = self.analyzer.analyze(sample_html_blacklisted, "https://superprof.fr/ressources/test.html")
        blacklisted = result.get("blacklisted_links", [])

        assert len(blacklisted) == 2
        assert any("acadomia.fr" in link["href"] for link in blacklisted)
        assert any("kelprof.com" in link["href"] for link in blacklisted)

    def test_word_count(self, sample_html):
        """Test comptage des mots."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        # Le HTML d'exemple contient environ 100-150 mots
        assert result["word_count"] > 50
        assert result["word_count"] < 500

    def test_has_faq_section(self, sample_html):
        """Test détection section FAQ."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        assert result["has_faq"] is True

    def test_extract_headings_structure(self, sample_html):
        """Test extraction structure des headings."""
        result = self.analyzer.analyze(sample_html, "https://superprof.fr/ressources/test.html")
        h2_titles = result["h2_titles"]

        assert "Les bases fondamentales" in h2_titles
        assert "Méthodes d'apprentissage" in h2_titles
        assert "FAQ" in h2_titles

    def test_empty_html(self):
        """Test avec HTML vide."""
        result = self.analyzer.analyze("")
        assert result["h1"] == ""
        assert result["images_count"] == 0
        assert result["word_count"] == 0

    def test_malformed_html(self):
        """Test avec HTML malformé."""
        malformed = "<h1>Titre<p>Pas fermé<img src='test.jpg'>"
        result = self.analyzer.analyze(malformed, "https://superprof.fr/ressources/test.html")
        # Doit parser sans erreur
        assert result["h1"] == "Titre"
        assert result["images_count"] == 1


class TestHTMLAnalyzerAssets:
    """Tests spécifiques pour l'extraction d'assets."""

    def setup_method(self):
        self.analyzer = HTMLAnalyzer(domain="superprof.fr")

    def test_extract_all_assets(self, sample_html):
        """Test extraction complète des assets."""
        assets = self.analyzer.extract_assets(sample_html)

        assert "images" in assets
        assert "internal_links" in assets
        assert "external_links" in assets
        assert "superprof_link" in assets

    def test_assets_preserve_context(self, sample_html):
        """Test que les assets préservent le contexte H2."""
        assets = self.analyzer.extract_assets(sample_html)

        # Les images devraient avoir un contexte de section
        for img in assets["images"]:
            assert "context_h2" in img or "section" in img

    def test_assets_counts(self, sample_html):
        """Test comptage des assets."""
        assets = self.analyzer.extract_assets(sample_html)

        assert assets["counts"]["images"] == 2
        assert assets["counts"]["internal_links"] >= 2
        assert assets["counts"]["external_links"] >= 2
