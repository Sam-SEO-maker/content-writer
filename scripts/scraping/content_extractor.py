"""
Content Extractor Module

Multi-layer extraction: site-specific selectors → WordPress → heuristics → cleanup
Preserves assets from full HTML for Rule of Gold validation.
"""

from bs4 import BeautifulSoup, Tag
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import json
import logging
import re

logger = logging.getLogger(__name__)

# Pre-compiled regex for WordPress [caption] shortcode conversion
# Captures: [caption attrs]<img .../> Caption text[/caption]
# Also handles: [caption attrs]<a href="..."><img .../></a> Caption text[/caption]
_CAPTION_RE = re.compile(
    r'\[caption[^\]]*\]'                                           # opening [caption ...]
    r'\s*((?:<a[^>]*>\s*)?<img[^>]*(?:/>|>)\s*(?:</a>)?)'         # group 1: optional <a><img/></a>
    r'\s*(.*?)'                                                    # group 2: caption text
    r'\s*\[/caption\]',                                            # closing [/caption]
    re.DOTALL
)


def _convert_wp_shortcodes(html: str) -> str:
    """
    Convert WordPress shortcodes to standard HTML before BeautifulSoup parsing.

    Handles [caption]<img .../> Caption text[/caption]
        → <figure><img .../><figcaption>Caption text</figcaption></figure>
    """
    def _replace_caption(match):
        img_tag = match.group(1).strip()
        caption_text = match.group(2).strip()
        if caption_text:
            return f'<figure>{img_tag}<figcaption>{caption_text}</figcaption></figure>'
        return f'<figure>{img_tag}</figure>'

    return _CAPTION_RE.sub(_replace_caption, html)


class ContentExtractor:
    """
    Multi-layer content extraction with asset preservation.

    Extraction layers (in order):
    1. Site-specific CSS selectors (from blog config)
    2. WordPress <article> tag detection
    3. Heuristic: largest text block (paragraph count + word count)
    4. Fallback: Remove nav/aside/footer tags

    Critical: Always extract assets from FULL HTML before cleaning.
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize content extractor.

        Args:
            base_path: Racine projet (défaut: auto). Les configs tenant sont
                résolues via TenantPaths (tenants/{id}/config/tenant.json).
        """
        from _shared.core.tenant_paths import TenantPaths
        self._tenant_paths = TenantPaths(base_path=base_path) if base_path else TenantPaths()
        self.blog_configs = self._load_blog_configs()

    def _load_blog_configs(self) -> Dict[str, dict]:
        """Load all tenant configs (avec scraping_config) via TenantPaths."""
        configs = {}
        for tenant_id, config_file in self._tenant_paths.blog_config_files():
            try:
                with config_file.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                    site_id = config.get("id") or config.get("blog_id") or tenant_id
                    configs[site_id] = config
            except Exception as e:
                logger.error(f"Failed to load config {config_file}: {e}")

        logger.info(f"Loaded {len(configs)} tenant configurations")
        return configs

    def extract_article_body(
        self,
        html: str,
        site_id: str,
        url: str = ""
    ) -> Tuple[str, Dict[str, any]]:
        """
        Extract clean article body using multi-layer approach.

        Args:
            html: Full HTML content
            site_id: Blog identifier (e.g., "enseigna.fr")
            url: Source URL for logging

        Returns:
            Tuple of (clean_body_html, extraction_metadata)
        """
        html = _convert_wp_shortcodes(html)
        soup = BeautifulSoup(html, "lxml")
        extraction_metadata = {
            "method_used": None,
            "selector": None,
            "word_count": 0,
            "paragraph_count": 0,
            "excluded_elements": 0
        }

        # Layer 1: Site-specific selectors
        if site_id in self.blog_configs:
            scraping_config = self.blog_configs[site_id].get("scraping_config", {})
            article_selector = scraping_config.get("article_body")
            exclude_selectors = scraping_config.get("exclude_selectors", [])

            if article_selector:
                body = self._extract_by_selector(soup, article_selector, exclude_selectors)
                if body:
                    extraction_metadata["method_used"] = "site_specific_selector"
                    extraction_metadata["selector"] = article_selector
                    extraction_metadata["excluded_elements"] = len(exclude_selectors)
                    clean_html = str(body)
                    extraction_metadata.update(self._get_text_stats(clean_html))
                    logger.info(f"Extracted via site-specific selector: {article_selector[:50]}")
                    return clean_html, extraction_metadata

        # Layer 2: WordPress <article> tag
        article_tag = soup.find("article")
        if article_tag:
            body = self._clean_wordpress_article(article_tag)
            if self._is_valid_content(body):
                extraction_metadata["method_used"] = "wordpress_article_tag"
                clean_html = str(body)
                extraction_metadata.update(self._get_text_stats(clean_html))
                logger.info("Extracted via WordPress <article> tag")
                return clean_html, extraction_metadata

        # Layer 3: Heuristic - largest text block
        body = self._extract_largest_text_block(soup)
        if body:
            extraction_metadata["method_used"] = "heuristic_largest_block"
            clean_html = str(body)
            extraction_metadata.update(self._get_text_stats(clean_html))
            logger.info("Extracted via heuristic largest text block")
            return clean_html, extraction_metadata

        # Layer 4: Fallback - remove navigation elements
        body = self._fallback_cleanup(soup)
        extraction_metadata["method_used"] = "fallback_cleanup"
        clean_html = str(body)
        extraction_metadata.update(self._get_text_stats(clean_html))
        logger.warning(f"Used fallback cleanup for {url[:50]}")
        return clean_html, extraction_metadata

    def _extract_by_selector(
        self,
        soup: BeautifulSoup,
        selector: str,
        exclude_selectors: List[str]
    ) -> Optional[Tag]:
        """
        Extract content using CSS selector and remove excluded elements.

        Handles comma-separated selectors by trying each individually.

        Args:
            soup: BeautifulSoup object
            selector: CSS selector(s) for article body (comma-separated)
            exclude_selectors: List of selectors to remove

        Returns:
            Cleaned Tag or None
        """
        try:
            # Split comma-separated selectors and try each one
            selectors = [s.strip() for s in selector.split(',')]

            for sel in selectors:
                body = soup.select_one(sel)
                if body:
                    # Remove excluded elements
                    for exclude_selector in exclude_selectors:
                        for element in body.select(exclude_selector):
                            element.decompose()

                    if self._is_valid_content(body):
                        return body

            return None

        except Exception as e:
            logger.error(f"Selector extraction failed: {e}")
            return None

    def _clean_wordpress_article(self, article: Tag) -> Tag:
        """
        Extract clean editorial content from WordPress article tag.

        Strategy:
        1. Find the entry-content div (actual editorial content)
        2. Strip WordPress wrappers (article, header, featured image, TOC)
        3. Remove noise elements (related posts, navigation, sharing)
        4. Return only editorial HTML tags (p, h2, h3, ul, ol, table, figure, img, blockquote, a)
        """
        # Step 1: Try to find the entry-content div (editorial body)
        content_div = article.find(class_=re.compile(r'entry-content', re.I))
        working_element = content_div if content_div else article

        # Step 2: Remove noise elements (exact CSS selectors)
        noise_selectors = [
            "nav",
            "aside",
            "header",
            ".navigation",
            ".sidebar",
            ".comments",
            "#comments",
            ".related-posts",
            ".related",
            ".post-meta",
            ".entry-meta",
            ".entry-categories",
            "footer",
            ".sharedaddy",  # Jetpack sharing
            ".wp-block-latest-posts",
            ".wp-block-tag-cloud",
            ".article-featured-image",
            ".wp-post-image",
        ]

        for selector in noise_selectors:
            for element in working_element.select(selector):
                element.decompose()

        # Step 3: Remove elements with class names containing theme-specific patterns
        for element in working_element.find_all(class_=re.compile(
            r'related|post-navigation|ez-toc|toc-container|featured-image', re.I
        )):
            element.decompose()

        # Step 4: Remove HTML comments
        from bs4 import Comment
        for comment in working_element.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Step 5: Remove H1 (WordPress manages it)
        for h1 in working_element.find_all("h1"):
            h1.decompose()

        # Step 6: Extract only editorial content tags, strip wrapper divs
        allowed_tags = {"p", "h2", "h3", "h4", "ul", "ol", "li", "table", "thead",
                        "tbody", "tr", "th", "td", "figure", "figcaption", "img",
                        "blockquote", "a", "strong", "em", "br", "span", "div"}

        # Create a clean container with only the inner content
        new_soup = BeautifulSoup("<div></div>", "html.parser")
        container = new_soup.find("div")

        for child in working_element.children:
            if isinstance(child, Tag):
                container.append(child.extract())
            elif isinstance(child, str) and child.strip():
                container.append(child)

        return container

    def _extract_largest_text_block(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find largest text block using paragraph count + word count heuristic.

        Args:
            soup: BeautifulSoup object

        Returns:
            Tag with most content or None
        """
        candidates = []

        # Search in common container elements
        for tag_name in ["article", "main", "div", "section"]:
            for element in soup.find_all(tag_name):
                # Skip small containers
                if element.name == "div" and not element.get("class"):
                    continue

                paragraphs = element.find_all("p")
                if len(paragraphs) < 3:
                    continue

                text = element.get_text(separator=" ", strip=True)
                word_count = len(text.split())

                # Score: paragraph count * 10 + word count
                score = len(paragraphs) * 10 + word_count

                candidates.append({
                    "element": element,
                    "score": score,
                    "paragraphs": len(paragraphs),
                    "words": word_count
                })

        if not candidates:
            return None

        # Return highest scoring element
        best = max(candidates, key=lambda x: x["score"])
        logger.debug(
            f"Largest block: {best['paragraphs']} paragraphs, "
            f"{best['words']} words, score={best['score']}"
        )

        return best["element"]

    def _fallback_cleanup(self, soup: BeautifulSoup) -> Tag:
        """
        Last resort: remove navigation and keep body.

        Removes:
        - header, nav, aside, footer
        - Common navigation classes
        """
        # Clone soup to avoid modifying original
        body = soup.find("body") or soup

        # Remove structural noise
        for tag_name in ["header", "nav", "aside", "footer", "script", "style"]:
            for element in body.find_all(tag_name):
                element.decompose()

        # Remove by class
        noise_classes = [
            "navigation",
            "sidebar",
            "menu",
            "header",
            "footer",
            "comments",
            "related"
        ]

        for noise_class in noise_classes:
            for element in body.find_all(class_=re.compile(noise_class, re.I)):
                element.decompose()

        return body

    def _is_valid_content(self, element: Tag) -> bool:
        """
        Validate that extracted content is substantial.

        Criteria:
        - At least 3 paragraphs AND minimum 10 words total
        - OR at least 100 words (even if few paragraphs)
        """
        if not element:
            return False

        # Get all text content
        text = element.get_text(separator=" ", strip=True)
        if not text:
            return False

        word_count = len(text.split())

        # Count paragraphs (recursively)
        paragraphs = element.find_all("p", recursive=True)
        paragraph_count = len(paragraphs)

        # Valid if either:
        # - At least 3 paragraphs AND at least 10 words
        # - OR at least 100 words (even if few paragraphs)
        has_enough_paragraphs_and_words = paragraph_count >= 3 and word_count >= 10
        has_enough_words_alone = word_count >= 100

        return has_enough_paragraphs_and_words or has_enough_words_alone

    def _get_text_stats(self, html: str) -> Dict[str, int]:
        """
        Get text statistics from HTML.

        Returns:
            {"word_count": int, "paragraph_count": int}
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        word_count = len(text.split())
        paragraph_count = len(soup.find_all("p"))

        return {
            "word_count": word_count,
            "paragraph_count": paragraph_count
        }

    def extract_with_assets(
        self,
        html: str,
        site_id: str,
        url: str = ""
    ) -> Dict[str, any]:
        """
        Extract clean body AND preserve asset baseline from full HTML.

        This is the primary method for the autonomous workflow.
        Ensures Rule of Gold: asset preservation.

        Args:
            html: Full HTML content
            site_id: Blog identifier
            url: Source URL

        Returns:
            {
                "clean_body": str,           # Extracted article body
                "full_html": str,            # Original HTML (for asset comparison)
                "extraction_metadata": dict, # Method used, stats
                "assets_baseline": dict      # Asset counts from FULL HTML
            }
        """
        # Extract clean body
        clean_body, extraction_metadata = self.extract_article_body(html, site_id, url)

        # Extract assets from CLEAN BODY (not full HTML)
        # Full HTML includes sidebar, related posts, footer images that pollute
        # the asset baseline — e.g. yoga-chaise images appearing in Pilates articles
        assets_baseline = self._extract_assets_baseline(clean_body)

        return {
            "clean_body": clean_body,
            "full_html": html,
            "extraction_metadata": extraction_metadata,
            "assets_baseline": assets_baseline
        }

    def _extract_assets_baseline(self, html: str) -> Dict[str, any]:
        """
        Extract asset counts AND full tags from full HTML for Rule of Gold.

        Extracts complete <img> tags (with src, alt, width, height, class...)
        so they can be passed to the ghostwriter for contextual placement.

        Args:
            html: Full HTML content

        Returns:
            {
                "counts": { "images": int, "tables": int, "videos": int, "internal_links": int },
                "details": { "image_urls": list, "video_urls": list },
                "image_tags": list[dict],  # Full <img> tag data for ghostwriter
                "internal_link_tags": list[dict]  # Full <a> tag data for ghostwriter
            }
        """
        html = _convert_wp_shortcodes(html)
        soup = BeautifulSoup(html, "lxml")

        # Extract images with full tag data (including figure/figcaption captions)
        # Filter: only keep WordPress content images (wp-image class) or images in figures
        all_images = soup.find_all("img")
        images = []
        for img in all_images:
            src = img.get("src", "")
            if not src:
                continue
            css_class = img.get("class", [])
            css_str = " ".join(css_class) if isinstance(css_class, list) else str(css_class)
            is_wp_content = "wp-image" in css_str
            is_in_caption = img.find_parent(text=re.compile(r"\[caption")) is not None or img.find_parent("figure") is not None
            if is_wp_content or is_in_caption:
                images.append(img)
        image_urls = [img.get("src", "") for img in images if img.get("src")]
        image_tags = []
        for img in images:
            src = img.get("src", "")
            if not src:
                continue

            caption = ""
            figure_html = None

            # Check if image is inside a <figure> with <figcaption>
            parent_figure = img.find_parent("figure")
            if parent_figure:
                figcaption = parent_figure.find("figcaption")
                if figcaption:
                    caption = figcaption.get_text(strip=True)
                figure_html = str(parent_figure)

            # Fallback: check for WordPress wp-caption div
            if not caption:
                parent_wp = img.find_parent("div", class_=re.compile(r"wp-caption", re.I))
                if parent_wp:
                    cap_el = parent_wp.find("p", class_=re.compile(r"wp-caption-text", re.I))
                    if cap_el:
                        caption = cap_el.get_text(strip=True)
                    figure_html = str(parent_wp)

            image_tags.append({
                "html": figure_html or str(img),
                "src": src,
                "alt": img.get("alt", ""),
                "caption": caption,
            })

        # Count tables
        tables = soup.find_all("table")

        # Count videos (iframe, video tags)
        videos = soup.find_all("video")
        iframes = soup.find_all("iframe")
        video_iframes = [
            iframe for iframe in iframes
            if any(domain in iframe.get("src", "").lower()
                   for domain in ["youtube", "vimeo", "dailymotion"])
        ]
        total_videos = len(videos) + len(video_iframes)
        video_urls = [v.get("src", "") for v in videos if v.get("src")]
        video_urls += [i.get("src", "") for i in video_iframes if i.get("src")]

        # Extract internal links with full tag data
        links = soup.find_all("a", href=True)
        internal_links = [
            link for link in links
            if link["href"].startswith("/") or not link["href"].startswith("http")
        ]
        internal_link_tags = []
        for link in internal_links:
            href = link.get("href", "")
            anchor = link.get_text(strip=True)
            if href and anchor:
                internal_link_tags.append({
                    "html": str(link),
                    "href": href,
                    "anchor": anchor,
                })

        return {
            "counts": {
                "images": len(images),
                "tables": len(tables),
                "videos": total_videos,
                "internal_links": len(internal_links)
            },
            "details": {
                "image_urls": image_urls[:10],
                "video_urls": video_urls
            },
            "image_tags": image_tags,
            "internal_link_tags": internal_link_tags,
        }
