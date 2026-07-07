"""
WordPress REST API v2 Client

Fetches post content (Gutenberg raw + rendered HTML) directly from WordPress
without scraping the public page. Requires the WP REST API to be accessible
and Application Passwords enabled on the WordPress instance.

Credentials are read from environment variables — never hardcoded.
"""

import logging
import os
import re
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class WordPressAPIClient:
    """
    Client for WordPress REST API v2.

    Fetches post content by URL (slug extraction) or post ID.
    Returns raw Gutenberg source and rendered HTML.

    Usage:
        client = WordPressAPIClient(
            api_base_url="https://www.superprof.fr/ressources/wp-json/wp/v2",
            user_env_var="WP_SP_RESSOURCES_USER",
            password_env_var="WP_SP_RESSOURCES_PASSWORD",
        )
        post = client.get_post_by_url("https://www.superprof.fr/ressources/apprendre-python/")
        # post["raw"]      → Gutenberg source with <!-- wp:* --> blocks
        # post["rendered"] → Clean rendered HTML, no page chrome
    """

    def __init__(
        self,
        api_base_url: str,
        user_env_var: str,
        password_env_var: str,
        timeout: int = 30,
    ):
        """
        Args:
            api_base_url: WP REST API base URL, e.g.
                "https://www.superprof.fr/ressources/wp-json/wp/v2"
            user_env_var: Name of the env var holding the WP username.
            password_env_var: Name of the env var holding the WP Application Password.
            timeout: HTTP request timeout in seconds.
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = timeout

        user = os.getenv(user_env_var)
        password = os.getenv(password_env_var)

        if not user or not password:
            raise ValueError(
                f"WordPress API credentials not found. "
                f"Set env vars {user_env_var} and {password_env_var}."
            )

        self._auth = (user, password)

    def get_post_by_url(self, url: str) -> Optional[dict]:
        """
        Fetch post data from a public article URL.

        Extracts the slug from the last path segment and queries the REST API.

        Returns:
            {
                "id": int,
                "slug": str,
                "title": str,
                "link": str,
                "raw": str,       # Gutenberg source (content.raw, context=edit)
                "rendered": str,  # Rendered HTML (content.rendered)
            }
            or None if the post cannot be found or the API is unreachable.
        """
        slug = self._extract_slug(url)
        if not slug:
            logger.warning(f"Could not extract slug from URL: {url}")
            return None
        return self.get_post_by_slug(slug)

    def get_post_by_slug(self, slug: str) -> Optional[dict]:
        """Fetch post data by WP slug, including featured image and body images."""
        endpoint = f"{self.api_base_url}/posts"
        try:
            resp = requests.get(
                endpoint,
                params={"slug": slug, "context": "edit", "_embed": "wp:featuredmedia"},
                auth=self._auth,
                timeout=self.timeout,
                headers={"User-Agent": "ContentWriter/1.0"},
            )
            resp.raise_for_status()
            posts = resp.json()

            if not posts:
                logger.warning(f"No post found for slug '{slug}'")
                return None

            return self._normalize(posts[0])

        except requests.RequestException as e:
            logger.error(f"WP API error for slug '{slug}': {e}")
            return None

    def get_post_by_id(self, post_id: int) -> Optional[dict]:
        """Fetch post data by WP post ID, including featured image and body images."""
        endpoint = f"{self.api_base_url}/posts/{post_id}"
        try:
            resp = requests.get(
                endpoint,
                params={"context": "edit", "_embed": "wp:featuredmedia"},
                auth=self._auth,
                timeout=self.timeout,
                headers={"User-Agent": "ContentWriter/1.0"},
            )
            resp.raise_for_status()
            return self._normalize(resp.json())

        except requests.RequestException as e:
            logger.error(f"WP API error for post_id {post_id}: {e}")
            return None

    def get_media_by_id(self, media_id: int) -> Optional[dict]:
        """
        Fetch a single media attachment by ID.

        Useful when `_embed` is unavailable (e.g. authenticated-only APIs).

        Returns:
            {"id": int, "url": str, "alt": str, "caption": str} or None.
        """
        endpoint = f"{self.api_base_url}/media/{media_id}"
        try:
            resp = requests.get(
                endpoint,
                auth=self._auth,
                timeout=self.timeout,
                headers={"User-Agent": "ContentWriter/1.0"},
            )
            resp.raise_for_status()
            return self._normalize_media(resp.json())

        except requests.RequestException as e:
            logger.error(f"WP API error for media_id {media_id}: {e}")
            return None

    def update_post(
        self,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        meta: Optional[dict] = None,
        status: Optional[str] = None,
    ) -> dict:
        """
        Update an existing post via the REST API (authenticated, write).

        Only the provided fields are sent. Returns:
            {"ok": bool, "status_code": int, "id": int, "error": str|None}
        """
        endpoint = f"{self.api_base_url}/posts/{post_id}"
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        if status is not None:
            payload["status"] = status
        if meta:
            payload["meta"] = meta

        try:
            resp = requests.post(
                endpoint,
                json=payload,
                auth=self._auth,
                timeout=max(self.timeout, 60),
                headers={"User-Agent": "ContentWriter/1.0"},
            )
            ok = resp.status_code in (200, 202)
            err = None if ok else (resp.text[:300])
            return {"ok": ok, "status_code": resp.status_code, "id": post_id, "error": err}
        except requests.RequestException as e:
            return {"ok": False, "status_code": 0, "id": post_id, "error": str(e)[:300]}

    @staticmethod
    def _extract_slug(url: str) -> str:
        """
        Extract the WP post slug from the last non-empty path segment.

        Handles Superprof's permalink structure (ends in .html) and
        standard trailing-slash URLs.

        Examples:
            https://www.superprof.fr/ressources/cat/sub/apprendre-python.html → apprendre-python
            https://www.superprof.fr/ressources/apprendre-python/              → apprendre-python
            https://enseigna.fr/avis-superprof/                                → avis-superprof
        """
        path = urlparse(url).path
        parts = [p for p in path.split("/") if p]
        if not parts:
            return ""
        last = parts[-1]
        if last.endswith(".html"):
            last = last[:-5]
        return last

    @staticmethod
    def _normalize(post: dict) -> dict:
        """
        Normalize a WP REST API post object to our internal format.

        Returns:
            {
                "id": int,
                "slug": str,
                "title": str,
                "link": str,
                "raw": str,             # Gutenberg source with <!-- wp:* --> blocks
                "rendered": str,        # Rendered HTML
                "featured_image": {     # None if no featured image set
                    "id": int,
                    "url": str,
                    "alt": str,
                    "caption": str,
                } | None,
                "body_images": [        # wp:image blocks found in raw content
                    {
                        "id": int | None,   # WP attachment ID (None for external imgs)
                        "url": str,
                        "alt": str,
                        "gutenberg_block": str,  # Full <!-- wp:image -->..<!-- /wp:image -->
                    },
                    ...
                ],
            }
        """
        raw = post.get("content", {}).get("raw", "")

        # Featured image via _embed (single request, no extra API call)
        featured_image = None
        embedded = post.get("_embedded", {})
        featured_media_list = embedded.get("wp:featuredmedia", [])
        if featured_media_list and isinstance(featured_media_list[0], dict):
            featured_image = WordPressAPIClient._normalize_media(featured_media_list[0])

        return {
            "id": post.get("id"),
            "slug": post.get("slug", ""),
            "title": post.get("title", {}).get("rendered", ""),
            "link": post.get("link", ""),
            "raw": raw,
            "rendered": post.get("content", {}).get("rendered", ""),
            "featured_image": featured_image,
            "body_images": WordPressAPIClient._extract_body_images(raw),
        }

    @staticmethod
    def _normalize_media(media: dict) -> dict:
        """Normalize a WP media attachment object."""
        sizes = media.get("media_details", {}).get("sizes", {})
        # Prefer full size, fall back to source_url
        url = (
            sizes.get("full", {}).get("source_url")
            or media.get("source_url", "")
        )
        caption_raw = media.get("caption", {})
        caption = (
            caption_raw.get("raw", "")
            or caption_raw.get("rendered", "")
        ).strip()
        return {
            "id": media.get("id"),
            "url": url,
            "alt": media.get("alt_text", ""),
            "caption": caption,
        }

    @staticmethod
    def _extract_body_images(raw: str) -> list:
        """
        Extract images from raw post content, handling both formats:

        1. Gutenberg blocks:
               <!-- wp:image {"id":123,"sizeSlug":"large"} -->
               <figure class="wp-block-image size-large">
                   <img src="https://..." alt="..." class="wp-image-123"/>
               </figure>
               <!-- /wp:image -->

        2. Classic editor / wp:html: plain <img> tags embedded directly in the HTML.

        Returns a list of dicts with id, url, alt, and gutenberg_block.
        For classic images, gutenberg_block is a generated wp:image block (no id).
        """
        src_re = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
        alt_re = re.compile(r'<img[^>]+alt=["\']([^"\']*)["\']', re.IGNORECASE)
        id_re  = re.compile(r'"id"\s*:\s*(\d+)')
        w_re   = re.compile(r'width=["\'](\d+)["\']', re.IGNORECASE)
        h_re   = re.compile(r'height=["\'](\d+)["\']', re.IGNORECASE)

        images = []
        seen_urls: set = set()

        # --- Pass 1: Gutenberg wp:image blocks ---
        block_re = re.compile(
            r'(<!-- wp:image(?P<attrs>\s+\{[^}]*\})?\s*-->.*?<!-- /wp:image -->)',
            re.DOTALL,
        )
        for match in block_re.finditer(raw):
            block = match.group(1)
            attrs_str = match.group("attrs") or ""
            src_m = src_re.search(block)
            if not src_m:
                continue
            url = src_m.group(1)
            seen_urls.add(url)
            images.append({
                "id": int(id_re.search(attrs_str).group(1)) if id_re.search(attrs_str) else None,
                "url": url,
                "alt": alt_re.search(block).group(1) if alt_re.search(block) else "",
                "gutenberg_block": block,
            })

        # --- Pass 2: Classic <img> tags not already captured ---
        # Match the full <img .../> tag to preserve width/height for block generation
        img_tag_re = re.compile(r'<img\b[^>]+/?>', re.IGNORECASE | re.DOTALL)
        for match in img_tag_re.finditer(raw):
            tag = match.group()
            src_m = src_re.search(tag)
            if not src_m:
                continue
            url = src_m.group(1)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            alt   = alt_re.search(tag).group(1) if alt_re.search(tag) else ""
            w_m   = w_re.search(tag)
            h_m   = h_re.search(tag)
            size_attrs = ""
            img_size = ""
            if w_m and h_m:
                size_attrs = f' width="{w_m.group(1)}" height="{h_m.group(1)}"'
                img_size = f' style="width:{w_m.group(1)}px"'

            gutenberg_block = (
                '<!-- wp:image {"sizeSlug":"full","linkDestination":"none"} -->\n'
                f'<figure class="wp-block-image size-full">'
                f'<img src="{url}" alt="{alt}"{size_attrs}/>'
                f'</figure>\n'
                '<!-- /wp:image -->'
            )
            images.append({
                "id": None,
                "url": url,
                "alt": alt,
                "gutenberg_block": gutenberg_block,
            })

        return images
