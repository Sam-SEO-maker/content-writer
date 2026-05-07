"""Tests for OutputManager"""

import pytest
from pathlib import Path
import json
import tempfile
import shutil

from scripts.utils.output_manager import OutputManager


@pytest.fixture
def temp_base_path(tmp_path):
    """Create temporary base path for testing"""
    return tmp_path


@pytest.fixture
def output_mgr(temp_base_path):
    """Create OutputManager with temp path"""
    return OutputManager(base_path=temp_base_path)


class TestOutputManagerInit:
    """Test OutputManager initialization"""

    def test_outputs_root_created(self, output_mgr, temp_base_path):
        """Test that outputs root directory is created"""
        expected = temp_base_path / "_shared" / "outputs"
        assert output_mgr.outputs_root == expected
        assert output_mgr.outputs_root.exists()

    def test_temp_root_created(self, output_mgr, temp_base_path):
        """Test that temp root directory is created"""
        expected = temp_base_path / "_shared" / "temp"
        assert output_mgr.temp_root == expected
        assert output_mgr.temp_root.exists()

    def test_valid_site_ids(self, output_mgr):
        """Test that valid site IDs are defined"""
        expected_sites = [
            "enseigna.fr",
            "superprof.fr",
        ]
        assert output_mgr.VALID_SITE_IDS == expected_sites


class TestInitWorkspace:
    """Test init_workspace() method"""

    def test_init_workspace_creates_site_directories(self, output_mgr):
        """Test that init_workspace creates all site output directories"""
        stats = output_mgr.init_workspace(purge_temp=False)

        # Check all sites have output directories
        for site_id in output_mgr.VALID_SITE_IDS:
            site_dir = output_mgr.outputs_root / site_id
            assert site_dir.exists(), f"Missing output dir for {site_id}"

        assert stats["output_dirs_created"] == 6

    def test_init_workspace_creates_subdirectories(self, output_mgr):
        """Test that html/, json/, editorial_audits/ subdirectories are created"""
        stats = output_mgr.init_workspace(purge_temp=False)

        for site_id in output_mgr.VALID_SITE_IDS:
            for subdir in ["html", "json", "editorial_audits"]:
                sub_path = output_mgr.outputs_root / site_id / subdir
                assert sub_path.exists(), f"Missing {subdir} for {site_id}"

        assert stats["subdirs_created"] == 18  # 6 sites * 3 subdirs

    def test_init_workspace_purges_temp_cache(self, output_mgr):
        """Test that init_workspace purges temp cache"""
        # Create some temp files
        temp_site_dir = output_mgr.temp_root / "enseigna.fr"
        temp_site_dir.mkdir(parents=True, exist_ok=True)
        (temp_site_dir / "test1.html").write_text("test")
        (temp_site_dir / "test2.html").write_text("test")

        # Init workspace with purge
        stats = output_mgr.init_workspace(purge_temp=True)

        # Temp should be purged (files removed count may vary)
        assert stats["temp_files_removed"] >= 0
        assert not (temp_site_dir / "test1.html").exists()
        assert not (temp_site_dir / "test2.html").exists()

    def test_init_workspace_no_purge(self, output_mgr):
        """Test that init_workspace can skip purging temp cache"""
        # Create temp file
        temp_site_dir = output_mgr.temp_root / "enseigna.fr"
        temp_site_dir.mkdir(parents=True, exist_ok=True)
        test_file = temp_site_dir / "test.html"
        test_file.write_text("test")

        # Init without purge
        stats = output_mgr.init_workspace(purge_temp=False)

        # File should still exist
        assert test_file.exists()
        assert stats["temp_files_removed"] == 0


class TestSiteValidation:
    """Test site_id validation"""

    def test_validate_valid_site_id(self, output_mgr):
        """Test that valid site IDs pass validation"""
        # Should not raise
        output_mgr._validate_site_id("enseigna.fr")
        output_mgr._validate_site_id("superprof.fr")

    def test_validate_invalid_site_id(self, output_mgr):
        """Test that invalid site IDs raise ValueError"""
        with pytest.raises(ValueError, match="Invalid site_id"):
            output_mgr._validate_site_id("invalid-site.com")

        with pytest.raises(ValueError, match="Invalid site_id"):
            output_mgr._validate_site_id("enseigna")  # Missing .fr


class TestTempCacheMethods:
    """Test temp cache management methods"""

    def test_save_temp_html(self, output_mgr):
        """Test saving HTML to temp cache"""
        html = "<html><body>Test content</body></html>"

        saved_path = output_mgr.save_temp_html(
            site_id="enseigna.fr",
            url_slug="test-article",
            html_content=html
        )

        assert saved_path.exists()
        assert saved_path.read_text(encoding="utf-8") == html
        assert saved_path.name == "test-article.html"
        assert "enseigna.fr" in str(saved_path)

    def test_get_temp_html_exists(self, output_mgr):
        """Test retrieving existing temp HTML"""
        html = "<html><body>Test</body></html>"
        output_mgr.save_temp_html("enseigna.fr", "test", html)

        retrieved = output_mgr.get_temp_html("enseigna.fr", "test")
        assert retrieved == html

    def test_get_temp_html_not_exists(self, output_mgr):
        """Test retrieving non-existent temp HTML returns None"""
        retrieved = output_mgr.get_temp_html("enseigna.fr", "nonexistent")
        assert retrieved is None

    def test_clear_temp_cache_single_site(self, output_mgr):
        """Test clearing temp cache for single site"""
        # Create temp files for multiple sites
        output_mgr.save_temp_html("enseigna.fr", "test1", "html1")
        output_mgr.save_temp_html("enseigna.fr", "test2", "html2")
        output_mgr.save_temp_html("superprof.fr", "test3", "html3")

        # Clear only enseigna.fr
        removed = output_mgr.clear_temp_cache("enseigna.fr")

        assert removed == 2
        assert output_mgr.get_temp_html("enseigna.fr", "test1") is None
        assert output_mgr.get_temp_html("enseigna.fr", "test2") is None
        assert output_mgr.get_temp_html("superprof.fr", "test3") is not None

    def test_clear_temp_cache_all_sites(self, output_mgr):
        """Test clearing temp cache for all sites"""
        # Create temp files for multiple sites
        output_mgr.save_temp_html("enseigna.fr", "test1", "html1")
        output_mgr.save_temp_html("superprof.fr", "test2", "html2")
        output_mgr.save_temp_html("superprof.fr", "test3", "html3")

        # Clear all
        removed = output_mgr.clear_temp_cache(site_id=None)

        assert removed == 3
        assert output_mgr.get_temp_html("enseigna.fr", "test1") is None
        assert output_mgr.get_temp_html("superprof.fr", "test2") is None


class TestOutputMethods:
    """Test permanent output methods"""

    def test_get_site_output_dir(self, output_mgr):
        """Test getting site output directory"""
        output_dir = output_mgr.get_site_output_dir("enseigna.fr")

        assert output_dir.exists()
        assert output_dir.name == "enseigna.fr"
        assert "enseigna.fr" in str(output_dir)

        # html/, json/, editorial_audits/ subdirectories should exist
        for subdir in ["html", "json", "editorial_audits"]:
            assert (output_dir / subdir).exists(), f"Missing {subdir}"

    def test_save_refreshed_html(self, output_mgr):
        """Test saving refreshed HTML in html/ subdirectory"""
        html = "<html><body>Refreshed content</body></html>"

        saved_path = output_mgr.save_refreshed_html(
            site_id="enseigna.fr",
            url_slug="test-article",
            html_content=html
        )

        assert saved_path.exists()
        assert saved_path.read_text(encoding="utf-8") == html
        assert saved_path.name == "test-article_refreshed.html"
        assert saved_path.parent.name == "html"

    def test_save_metadata(self, output_mgr):
        """Test saving metadata JSON"""
        metadata = {
            "title": "Test Article",
            "meta_description": "Test description",
            "word_count": 1500,
            "assets": {"images": 3, "tables": 1}
        }

        saved_path = output_mgr.save_metadata(
            site_id="enseigna.fr",
            url_slug="test-article",
            metadata=metadata
        )

        assert saved_path.exists()

        with saved_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded == metadata
        assert saved_path.name == "test-article_metadata.json"
        assert saved_path.parent.name == "json"

    def test_save_audit_report(self, output_mgr):
        """Test saving audit report"""
        audit_data = {
            "url": "https://enseigna.fr/test",
            "overall_score": 75,
            "eeat_score": 68
        }

        saved_path = output_mgr.save_audit_report(
            site_id="enseigna.fr",
            url_slug="test-article",
            audit_data=audit_data,
            report_type="audit"
        )

        assert saved_path.exists()
        assert saved_path.name == "test-article_audit.json"
        assert saved_path.parent.name == "json"

        with saved_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded == audit_data

    def test_save_editorial_audit(self, output_mgr):
        """Test saving editorial audit markdown"""
        markdown = """# Editorial Audit Report

**Verdict**: 8/10

## Summary
Content quality is good.
"""

        saved_path = output_mgr.save_editorial_audit(
            site_id="enseigna.fr",
            url_slug="test-article",
            markdown_content=markdown
        )

        assert saved_path.exists()
        assert saved_path.read_text(encoding="utf-8") == markdown
        assert saved_path.name == "test-article_editorial_audit.md"
        assert "editorial_audits" in str(saved_path)


class TestValidationMethods:
    """Test validation and utility methods"""

    def test_get_output_files(self, output_mgr):
        """Test getting expected output file paths"""
        outputs = output_mgr.get_output_files("enseigna.fr", "test-article")

        assert "refreshed_html" in outputs
        assert "metadata" in outputs
        assert "audit" in outputs
        assert "editorial_audit" in outputs
        assert "temp_html" in outputs

        # Check paths are correct
        assert outputs["refreshed_html"].name == "test-article_refreshed.html"
        assert outputs["refreshed_html"].parent.name == "html"
        assert outputs["metadata"].parent.name == "json"
        assert outputs["audit"].parent.name == "json"
        assert outputs["editorial_audit"].parent.name == "editorial_audits"

    def test_validate_outputs_exist_all_present(self, output_mgr):
        """Test validation when all required files exist"""
        # Create required files
        output_mgr.save_refreshed_html("enseigna.fr", "test", "<html/>")
        output_mgr.save_metadata("enseigna.fr", "test", {"title": "Test"})

        all_exist, missing = output_mgr.validate_outputs_exist(
            "enseigna.fr",
            "test",
            required=["refreshed_html", "metadata"]
        )

        assert all_exist is True
        assert missing == []

    def test_validate_outputs_exist_missing(self, output_mgr):
        """Test validation when files are missing"""
        all_exist, missing = output_mgr.validate_outputs_exist(
            "enseigna.fr",
            "nonexistent",
            required=["refreshed_html", "metadata", "editorial_audit"]
        )

        assert all_exist is False
        assert "refreshed_html" in missing
        assert "metadata" in missing
        assert "editorial_audit" in missing

    def test_get_workspace_stats(self, output_mgr):
        """Test getting workspace statistics"""
        # Create some files
        output_mgr.save_temp_html("enseigna.fr", "test1", "html content")
        output_mgr.save_refreshed_html("enseigna.fr", "test2", "<html/>")
        output_mgr.save_metadata("superprof.fr", "test3", {"title": "Test"})

        stats = output_mgr.get_workspace_stats()

        assert "temp_cache" in stats
        assert "outputs" in stats
        assert "total_temp_size_mb" in stats
        assert "total_output_size_mb" in stats

        assert stats["temp_cache"]["enseigna.fr"] == 1
        assert stats["outputs"]["enseigna.fr"] >= 1
        assert stats["outputs"]["superprof.fr"] >= 1


class TestURLToSlug:
    """Test URL to slug conversion"""

    def test_url_to_slug_full_url(self, output_mgr):
        """Test converting full URL to slug"""
        url = "https://enseigna.fr/avis-acadomia/"
        slug = output_mgr._url_to_slug(url)
        assert slug == "avis-acadomia"

    def test_url_to_slug_with_path(self, output_mgr):
        """Test converting URL with multiple path segments"""
        url = "https://enseigna.fr/avis/superprof-avis/"
        slug = output_mgr._url_to_slug(url)
        assert slug == "avis-superprof-avis"

    def test_url_to_slug_plain_string(self, output_mgr):
        """Test converting plain string"""
        slug = output_mgr._url_to_slug("test-article")
        assert slug == "test-article"

    def test_url_to_slug_sanitization(self, output_mgr):
        """Test that special characters are removed"""
        slug = output_mgr._url_to_slug("test!@#$%article")
        assert slug == "testarticle"

    def test_url_to_slug_length_limit(self, output_mgr):
        """Test that slug is limited to 150 chars"""
        long_url = "https://test.fr/" + "a" * 200
        slug = output_mgr._url_to_slug(long_url)
        assert len(slug) <= 150
