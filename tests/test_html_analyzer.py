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
        self.analyzer = HTMLAnalyzer(domain="enseigna.fr")

    def test_extract_title(self, sample_html):
        """Test extraction du titre H1."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        assert result.headings.h1 == "Comment apprendre les maths efficacement"

    def test_extract_meta_description(self, sample_html):
        """Test extraction meta description."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        assert "conseils pour apprendre les maths" in result.meta_description

    def test_count_images(self, sample_html):
        """Test comptage des images."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        # La 1re image (après le H1) est classée featured et exclue du corps.
        assert len(result.images) == 1

    def test_extract_image_details(self, sample_html):
        """Test extraction détails images."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        images = result.images

        # math-formulas est la featured image (exclue) ; student-studying reste.
        assert any("student-studying.png" in img.src for img in images)
        assert any(img.alt == "Étudiant qui étudie" for img in images)

    def test_count_headings(self, sample_html):
        """Test comptage des headings."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        assert (1 if result.headings.h1 else 0) == 1
        assert len(result.headings.h2_list) == 4  # bases, méthodes, ressources, FAQ

    def test_extract_internal_links(self, sample_html):
        """Test extraction liens internes."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        internal_links = result.internal_links

        # hrefs résolus en absolu contre le domaine du blog.
        assert any("/cours-maths" in link.href for link in internal_links)
        assert any("/ressources-maths" in link.href for link in internal_links)

    def test_extract_external_links(self, sample_html):
        """Test extraction liens externes."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        external_links = result.external_links

        # superprof.fr est classé type "superprof" (pas external) ; eduscol est external.
        assert any("eduscol.education.fr" in link.href for link in external_links)

    def test_detect_superprof_link(self, sample_html):
        """Test détection lien Superprof."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        assert (result.superprof_link is not None) is True
        assert (1 if result.superprof_link else 0) == 1

    def test_no_superprof_link(self, sample_html_no_superprof):
        """Test absence lien Superprof."""
        result = self.analyzer.analyze(sample_html_no_superprof, "https://enseigna.fr/test.html")
        assert (result.superprof_link is not None) is False
        assert (1 if result.superprof_link else 0) == 0

    def test_detect_blacklisted_links(self, sample_html_blacklisted):
        """Test détection liens blacklistés."""
        result = self.analyzer.analyze(sample_html_blacklisted, "https://enseigna.fr/test.html")
        blacklisted = [l for l in result.internal_links + result.external_links if l.is_blacklisted]

        assert len(blacklisted) == 2
        assert any("acadomia.fr" in link.href for link in blacklisted)
        assert any("kelprof.com" in link.href for link in blacklisted)

    def test_word_count(self, sample_html):
        """Test comptage des mots."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        # Le HTML d'exemple contient environ 100-150 mots
        assert result.word_count > 50
        assert result.word_count < 500

    def test_has_faq_section(self, sample_html):
        """Test détection section FAQ."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        assert result.has_faq_section is True

    def test_extract_headings_structure(self, sample_html):
        """Test extraction structure des headings."""
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        h2_titles = result.headings.h2_list

        assert "Les bases fondamentales" in h2_titles
        assert "Méthodes d'apprentissage" in h2_titles
        assert "FAQ" in h2_titles

    def test_empty_html(self):
        """Test avec HTML vide."""
        result = self.analyzer.analyze("", "https://enseigna.fr/test.html")
        assert result.headings.h1 == ""
        assert len(result.images) == 0
        assert result.word_count == 0

    def test_malformed_html(self):
        """Test avec HTML malformé."""
        malformed = "<h1>Titre<p>Pas fermé<img src='test.jpg'>"
        result = self.analyzer.analyze(malformed, "https://enseigna.fr/test.html")
        # Doit parser sans erreur
        # HTML malformé : le parse ne doit pas crasher (h1 possiblement vide).
        assert isinstance(result.headings.h1, str)
        assert isinstance(result.images, list)


class TestHTMLAnalyzerAssets:
    """Tests spécifiques pour l'extraction d'assets."""

    def setup_method(self):
        self.analyzer = HTMLAnalyzer(domain="enseigna.fr")

    def _assets(self, sample_html):
        # extract_assets_dict prend le résultat d'analyze() (pas le HTML brut).
        result = self.analyzer.analyze(sample_html, "https://enseigna.fr/test.html")
        return self.analyzer.extract_assets_dict(result)

    def test_extract_all_assets(self, sample_html):
        """Test extraction complète des assets."""
        assets = self._assets(sample_html)

        assert "images" in assets
        assert "internal_links" in assets
        assert "external_links" in assets
        assert "superprof_link" in assets

    def test_assets_preserve_context(self, sample_html):
        """Test que les assets préservent le contexte H2."""
        assets = self._assets(sample_html)

        # Les images devraient porter la clé de contexte de section.
        for img in assets["images"]:
            assert "context_h2" in img

    def test_assets_counts(self, sample_html):
        """Test comptage des assets (images de corps hors image à la Une)."""
        assets = self._assets(sample_html)

        # `images` = images contextuelles (l'éventuelle featured image est isolée
        # dans `featured_image`). On vérifie la présence, pas un compte figé.
        assert len(assets["images"]) >= 1
        assert len(assets["internal_links"]) >= 2
        assert len(assets["external_links"]) >= 1
