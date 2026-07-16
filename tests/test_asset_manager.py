"""
Tests pour le module asset_manager.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.assets.asset_manager import AssetManager
# AssetValidation a été renommé AssetValidationResult (modèles) ; alias rétro-compat.
from _shared.core.models import AssetValidationResult as AssetValidation


class TestAssetManager:
    """Tests pour AssetManager."""

    def setup_method(self):
        """Setup avant chaque test."""
        self.manager = AssetManager()

    def test_extract_images(self, sample_html):
        """Test extraction des images."""
        assets = self.manager.extract_assets(sample_html, exclude_featured_image=False)

        assert "images" in assets
        assert len(assets["images"]) == 2

        # Vérifier les détails
        srcs = [img["src"] for img in assets["images"]]
        assert "/images/math-formulas.jpg" in srcs
        assert "/images/student-studying.png" in srcs

    def test_extract_internal_links(self, sample_html):
        """Test extraction liens internes."""
        assets = self.manager.extract_assets(sample_html)

        internal = assets["internal_links"]
        hrefs = [link["href"] for link in internal]

        assert "/cours-maths" in hrefs
        assert "/ressources-maths" in hrefs

    def test_extract_superprof_link(self, sample_html):
        """Test extraction lien Superprof."""
        assets = self.manager.extract_assets(sample_html)

        assert assets["superprof_link"] is not None
        assert "superprof.fr" in assets["superprof_link"]["href"]
        assert assets["superprof_link"]["anchor"] == "Superprof"

    def test_no_superprof_link(self, sample_html_no_superprof):
        """Test absence lien Superprof."""
        assets = self.manager.extract_assets(sample_html_no_superprof)
        assert assets["superprof_link"] is None

    def test_detect_blacklisted_links(self, sample_html_blacklisted):
        """Détection des liens blacklistés — via validate() (pas extract_assets).

        La blacklist est une préoccupation de VALIDATION du nouveau contenu, pas
        de l'extraction des assets d'origine → elle vit dans validation.blacklist_violations.
        """
        original_assets = {
            "images": [], "internal_links": [], "external_links": [],
            "superprof_link": {"href": "https://superprof.fr", "anchor": "SP"},
            "counts": {"images": 0, "internal_links": 0, "superprof_links": 1},
        }
        validation = self.manager.validate(original_assets, sample_html_blacklisted)
        violations = " ".join(validation.blacklist_violations).lower()
        assert "acadomia.fr" in violations
        assert "kelprof.com" in violations

    def test_assets_counts(self, sample_html):
        """Test comptage des assets."""
        assets = self.manager.extract_assets(sample_html, exclude_featured_image=False)
        counts = assets["counts"]

        assert counts["images"] == 2
        assert counts["internal_links"] >= 2
        assert counts["superprof_links"] == 1


class TestAssetValidation:
    """Tests pour la validation des assets."""

    def setup_method(self):
        self.manager = AssetManager()

    def test_valid_content(self, sample_html):
        """Test contenu valide (assets préservés)."""
        original_assets = self.manager.extract_assets(sample_html)

        # Contenu qui préserve tous les assets
        new_content = sample_html  # Même contenu

        validation = self.manager.validate(original_assets, new_content)

        assert validation.is_valid is True
        assert validation.images_valid is True
        assert validation.links_valid is True
        assert validation.superprof_valid is True

    def test_missing_images(self, sample_html):
        """Test détection images manquantes."""
        original_assets = self.manager.extract_assets(sample_html)

        # Contenu sans images
        new_content = """
        <h1>Article sans images</h1>
        <p>Contenu texte uniquement.</p>
        <a href="https://www.superprof.fr">Superprof</a>
        """

        validation = self.manager.validate(original_assets, new_content)

        assert validation.is_valid is False
        assert validation.images_valid is False
        assert validation.images_new < validation.images_original

    def test_missing_internal_links(self, sample_html):
        """Test détection liens internes manquants."""
        original_assets = self.manager.extract_assets(sample_html)

        # Contenu sans liens internes
        new_content = """
        <h1>Article</h1>
        <img src="/images/math-formulas.jpg" alt="Math">
        <img src="/images/student-studying.png" alt="Student">
        <a href="https://www.superprof.fr">Superprof</a>
        """

        validation = self.manager.validate(original_assets, new_content)

        assert validation.links_valid is False
        assert validation.links_new < validation.links_original

    def test_missing_superprof(self, sample_html):
        """Test détection lien Superprof manquant."""
        original_assets = self.manager.extract_assets(sample_html)

        # Contenu sans Superprof
        new_content = """
        <h1>Article</h1>
        <img src="/images/math-formulas.jpg" alt="Math">
        <img src="/images/student-studying.png" alt="Student">
        <a href="/cours-maths">Cours</a>
        """

        validation = self.manager.validate(original_assets, new_content)

        assert validation.superprof_valid is False

    def test_multiple_superprof(self, sample_html):
        """Test détection plusieurs liens Superprof."""
        original_assets = self.manager.extract_assets(sample_html)

        # Contenu avec 2 liens Superprof
        new_content = sample_html + """
        <p>Voir aussi <a href="https://www.superprof.fr/autre">Autre Superprof</a></p>
        """

        validation = self.manager.validate(original_assets, new_content)

        # Devrait échouer: exactement 1 lien Superprof requis
        assert validation.superprof_valid is False
        assert validation.superprof_count > 1

    def test_blacklisted_links_detected(self, sample_html_blacklisted):
        """Test détection liens blacklistés dans nouveau contenu."""
        # Assets originaux
        original_assets = {
            "images": [],
            "internal_links": [],
            "superprof_link": {"href": "https://superprof.fr", "anchor": "SP"},
            "counts": {"images": 0, "internal_links": 0, "superprof_links": 1},
        }

        validation = self.manager.validate(original_assets, sample_html_blacklisted)

        assert len(validation.blacklist_violations) == 2


class TestAssetRestoration:
    """Tests pour la restauration des assets."""

    def setup_method(self):
        self.manager = AssetManager()

    def test_restore_missing_images(self, sample_html):
        """Test restauration images manquantes."""
        # exclude_featured_image=False : on veut restaurer TOUTES les images du
        # corps (l'exclusion featured-image par défaut en écarterait une).
        original_assets = self.manager.extract_assets(sample_html, exclude_featured_image=False)

        # Contenu sans images
        new_content = """
        <h1>Article</h1>
        <h2>Section 1</h2>
        <p>Contenu section 1.</p>
        <h2>Section 2</h2>
        <p>Contenu section 2.</p>
        <a href="https://www.superprof.fr">Superprof</a>
        """

        # Créer validation pour identifier les manquants
        validation = self.manager.validate(original_assets, new_content)

        # Restaurer
        restored = self.manager.restore_missing_assets(
            new_content,
            original_assets,
            validation
        )

        # Vérifier que les images sont restaurées
        assert "/images/math-formulas.jpg" in restored
        assert "/images/student-studying.png" in restored

    def test_restore_superprof(self, sample_html):
        """Test restauration lien Superprof."""
        original_assets = self.manager.extract_assets(sample_html)

        # Contenu sans Superprof
        new_content = """
        <h1>Article</h1>
        <img src="/images/math-formulas.jpg" alt="Math">
        <p>Contenu.</p>
        """

        validation = self.manager.validate(original_assets, new_content)
        restored = self.manager.restore_missing_assets(
            new_content,
            original_assets,
            validation
        )

        assert "superprof.fr" in restored

    def test_no_restoration_needed(self, sample_html):
        """Test pas de restauration si tout est présent."""
        original_assets = self.manager.extract_assets(sample_html)

        # Même contenu
        validation = self.manager.validate(original_assets, sample_html)
        restored = self.manager.restore_missing_assets(
            sample_html,
            original_assets,
            validation
        )

        # Contenu ne devrait pas changer significativement
        assert "math-formulas.jpg" in restored


class TestAssetReport:
    """Tests pour la génération de rapport."""

    def setup_method(self):
        self.manager = AssetManager()

    def test_generate_report(self, sample_html):
        """Test génération rapport complet."""
        original_assets = self.manager.extract_assets(sample_html)
        validation = self.manager.validate(original_assets, sample_html)

        report = self.manager.generate_assets_report(original_assets, validation)

        # Le rapport est un markdown (string).
        assert isinstance(report, str)
        assert "## Validation" in report
        assert "VALIDE" in report

    def test_report_with_issues(self, sample_html):
        """Test rapport avec problèmes."""
        original_assets = self.manager.extract_assets(sample_html)

        # Contenu avec problèmes
        new_content = "<h1>Vide</h1>"

        validation = self.manager.validate(original_assets, new_content)
        report = self.manager.generate_assets_report(original_assets, validation)

        assert isinstance(report, str)
        assert "INVALIDE" in report
