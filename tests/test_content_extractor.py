"""Tests for ContentExtractor module"""

import pytest
from pathlib import Path
import tempfile
import json
from scripts.scraping.content_extractor import ContentExtractor


@pytest.fixture
def temp_config_dir(tmp_path):
    """Crée un base_path temporaire avec un tenant au layout monorepo.

    ContentExtractor charge les configs via TenantPaths (tenants/{id}/config/
    tenant.json), plus depuis un dossier plat blogs/.
    """
    tenant_cfg_dir = tmp_path / "tenants" / "test-blog.fr" / "config"
    tenant_cfg_dir.mkdir(parents=True)

    test_config = {
        "id": "test-blog.fr",
        "domain": "test-blog.fr",
        "scraping_config": {
            "article_body": "article.post-content",
            "exclude_selectors": ["nav", ".sidebar", ".comments"],
            "timeout": 30,
            "requires_playwright": False
        }
    }

    with (tenant_cfg_dir / "tenant.json").open("w", encoding="utf-8") as f:
        json.dump(test_config, f)

    return tmp_path


class TestContentExtractor:
    """Test ContentExtractor class"""

    def test_init(self, temp_config_dir):
        """Test ContentExtractor initialization"""
        extractor = ContentExtractor(base_path=temp_config_dir)

        assert "test-blog.fr" in extractor.blog_configs
        assert extractor.blog_configs["test-blog.fr"]["id"] == "test-blog.fr"

    def test_init_missing_config_dir(self):
        """Test initialization avec un base_path sans tenants/"""
        extractor = ContentExtractor(base_path=Path("/nonexistent/path"))

        # Should handle missing directory gracefully
        assert len(extractor.blog_configs) == 0

    def test_extract_article_body_site_specific_selector(self, temp_config_dir):
        """Test extraction using site-specific CSS selector"""
        extractor = ContentExtractor(base_path=temp_config_dir)

        html = """
        <html>
        <body>
            <nav>Navigation</nav>
            <article class="post-content">
                <h1>Article Title</h1>
                <p>This is the main article content.</p>
                <p>It has multiple paragraphs with substantial text.</p>
                <p>This is the content we want to extract.</p>
            </article>
            <aside class="sidebar">Sidebar content</aside>
            <div class="comments">Comments section</div>
        </body>
        </html>
        """

        clean_body, metadata = extractor.extract_article_body(html, "test-blog.fr", "https://test-blog.fr/article")

        assert metadata["method_used"] == "site_specific_selector"
        assert metadata["selector"] == "article.post-content"
        assert "Article Title" in clean_body
        assert "main article content" in clean_body
        # Excluded elements should not be in clean body
        assert "Navigation" not in clean_body
        assert "Sidebar content" not in clean_body
        assert "Comments section" not in clean_body

    def test_extract_article_body_wordpress_article_tag(self):
        """Test extraction using WordPress <article> tag"""
        extractor = ContentExtractor()

        html = """
        <html>
        <body>
            <header>Header</header>
            <article>
                <h1>WordPress Article</h1>
                <p>This is article content in WordPress format.</p>
                <p>It should be extracted using the article tag.</p>
                <p>This is the third paragraph with more content.</p>
                <aside>Related posts</aside>
            </article>
            <footer>Footer</footer>
        </body>
        </html>
        """

        clean_body, metadata = extractor.extract_article_body(html, "unknown-blog", "https://example.com")

        assert metadata["method_used"] == "wordpress_article_tag"
        assert "WordPress Article" in clean_body
        assert "article content in WordPress format" in clean_body
        # Aside should be removed during cleaning
        assert "Related posts" not in clean_body
        # Header/footer should not be in clean body
        assert "Header" not in clean_body
        assert "Footer" not in clean_body

    def test_extract_article_body_heuristic_largest_block(self):
        """Test extraction using heuristic (largest text block)"""
        extractor = ContentExtractor()

        html = """
        <html>
        <body>
            <div class="header">
                <p>Short header text</p>
            </div>
            <div class="main-content">
                <p>This is the main content area with lots of text.</p>
                <p>It has many paragraphs which makes it the largest block.</p>
                <p>The heuristic should identify this as the article body.</p>
                <p>Fourth paragraph with even more content here.</p>
                <p>Fifth paragraph to ensure substantial word count.</p>
            </div>
            <div class="sidebar">
                <p>Short sidebar</p>
            </div>
        </body>
        </html>
        """

        clean_body, metadata = extractor.extract_article_body(html, "unknown-blog", "https://example.com")

        assert metadata["method_used"] == "heuristic_largest_block"
        assert "main content area" in clean_body
        assert "many paragraphs" in clean_body
        assert metadata["paragraph_count"] >= 5
        assert metadata["word_count"] > 30

    def test_extract_article_body_fallback_cleanup(self):
        """Test extraction using fallback cleanup"""
        extractor = ContentExtractor()

        html = """
        <html>
        <head><title>Page Title</title></head>
        <body>
            <header>Header content</header>
            <nav>Navigation</nav>
            <p>First paragraph of actual content</p>
            <p>Second paragraph with more text</p>
            <p>Third paragraph to meet minimum requirements</p>
            <aside>Sidebar</aside>
            <footer>Footer</footer>
        </body>
        </html>
        """

        clean_body, metadata = extractor.extract_article_body(html, "unknown-blog", "https://example.com")

        assert metadata["method_used"] == "fallback_cleanup"
        # Content paragraphs should be present
        assert "First paragraph" in clean_body
        assert "Second paragraph" in clean_body
        # Navigation elements should be removed
        assert "Navigation" not in clean_body
        assert "Footer" not in clean_body

    def test_is_valid_content_valid(self):
        """Test content validation with valid content"""
        extractor = ContentExtractor()

        from bs4 import BeautifulSoup

        html = """
        <div>
            <p>Paragraph one with some text content here.</p>
            <p>Paragraph two with more substantial text.</p>
            <p>Paragraph three with additional content.</p>
            <p>Paragraph four with even more text to ensure we have enough words for validation to pass successfully.</p>
        </div>
        """

        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")

        assert extractor._is_valid_content(div) is True

    def test_is_valid_content_too_few_paragraphs(self):
        """Test content validation with too few paragraphs"""
        extractor = ContentExtractor()

        from bs4 import BeautifulSoup

        html = """
        <div>
            <p>Only one paragraph.</p>
        </div>
        """

        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")

        assert extractor._is_valid_content(div) is False

    def test_is_valid_content_too_few_words(self):
        """Test content validation with too few words"""
        extractor = ContentExtractor()

        from bs4 import BeautifulSoup

        html = """
        <div>
            <p>Short.</p>
            <p>Very.</p>
            <p>Brief.</p>
        </div>
        """

        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")

        assert extractor._is_valid_content(div) is False

    def test_get_text_stats(self):
        """Test text statistics extraction"""
        extractor = ContentExtractor()

        html = """
        <article>
            <h1>Title Here</h1>
            <p>First paragraph with some words.</p>
            <p>Second paragraph with more content.</p>
            <p>Third paragraph with additional text.</p>
        </article>
        """

        stats = extractor._get_text_stats(html)

        assert stats["paragraph_count"] == 3
        assert stats["word_count"] >= 15

    def test_extract_assets_baseline(self):
        """Test asset baseline extraction"""
        extractor = ContentExtractor()

        html = """
        <html>
        <body>
            <article>
                <h1>Article with Assets</h1>
                <img src="/image1.jpg" alt="Image 1">
                <p>Text content</p>
                <img src="/image2.jpg" alt="Image 2">
                <table>
                    <tr><td>Data</td></tr>
                </table>
                <video src="/video.mp4"></video>
                <a href="/internal-page">Internal link</a>
                <a href="https://external.com">External link</a>
            </article>
        </body>
        </html>
        """

        assets = extractor._extract_assets_baseline(html)

        assert assets["counts"]["images"] == 2
        assert assets["counts"]["tables"] == 1
        assert assets["counts"]["videos"] == 1
        assert assets["counts"]["internal_links"] >= 1  # At least the /internal-page link
        assert len(assets["details"]["image_urls"]) == 2
        assert "/image1.jpg" in assets["details"]["image_urls"]

    def test_extract_assets_baseline_youtube_iframe(self):
        """Test asset baseline with YouTube iframe"""
        extractor = ContentExtractor()

        html = """
        <html>
        <body>
            <iframe src="https://www.youtube.com/embed/ABC123"></iframe>
            <iframe src="https://vimeo.com/123456"></iframe>
            <iframe src="https://example.com/widget"></iframe>
        </body>
        </html>
        """

        assets = extractor._extract_assets_baseline(html)

        # YouTube and Vimeo iframes should be counted as videos
        assert assets["counts"]["videos"] == 2
        assert len(assets["details"]["video_urls"]) == 2

    def test_extract_with_assets(self, temp_config_dir):
        """Test full extraction with assets"""
        extractor = ContentExtractor(temp_config_dir)

        html = """
        <html>
        <body>
            <nav>Navigation</nav>
            <article class="post-content">
                <h1>Complete Article</h1>
                <p>This article has various assets to test extraction.</p>
                <img src="/test-image.jpg" alt="Test">
                <p>More content here with substance.</p>
                <p>Third paragraph with additional text content.</p>
                <table><tr><td>Table data</td></tr></table>
                <a href="/internal">Internal link</a>
            </article>
            <aside class="sidebar">Sidebar</aside>
        </body>
        </html>
        """

        result = extractor.extract_with_assets(html, "test-blog.fr", "https://test-blog.fr/article")

        assert "clean_body" in result
        assert "full_html" in result
        assert "extraction_metadata" in result
        assert "assets_baseline" in result

        # Verify clean body
        assert "Complete Article" in result["clean_body"]
        assert "Navigation" not in result["clean_body"]

        # Verify full HTML preserved
        assert result["full_html"] == html

        # Verify assets baseline
        assert result["assets_baseline"]["counts"]["images"] == 1
        assert result["assets_baseline"]["counts"]["tables"] == 1
        assert result["assets_baseline"]["counts"]["internal_links"] >= 1

        # Verify metadata
        assert result["extraction_metadata"]["method_used"] == "site_specific_selector"
        assert result["extraction_metadata"]["word_count"] >= 10


# Run with: pytest tests/test_content_extractor.py -v
