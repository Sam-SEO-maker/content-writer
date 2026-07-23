"""
Sitemap Fetcher Module

Fetches and parses XML sitemaps with intelligent caching.
Supports both standard sitemaps and sitemap index files.
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from _shared.core.models import (
    SitemapURL,
    SitemapCache,
    FetchResult,
    SiteConfig
)
from _shared.core.sites_registry import SitesRegistry


# XML namespaces for sitemap parsing
SITEMAP_NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'
}


class SitemapFetcher:
    """
    Fetches and caches sitemaps for a specific site.

    Features:
    - Auto-discovery of sitemap URL from domain
    - Support for sitemap index files (recursively fetches all sitemaps)
    - JSON-based caching with timestamp
    - Change detection (new/removed URLs)
    - Graceful error handling with fallback to cache

    Usage:
        fetcher = SitemapFetcher(site_config)

        # Fetch with change detection
        result = fetcher.fetch_and_detect_new(force_refresh=True)
        print(f"Found {len(result.new_urls)} new URLs")

        # Just get all URLs
        urls = fetcher.fetch(force_refresh=False)
    """

    def __init__(
        self,
        site_config: SiteConfig,
        base_path: Optional[Path] = None,
        timeout: int = 30
    ):
        """
        Initialize the fetcher.

        Args:
            site_config: Site configuration
            base_path: Project root path (auto-detected if None)
            timeout: HTTP request timeout in seconds
        """
        self.site_config = site_config
        self.timeout = timeout

        # Determine sitemap URL
        if site_config.sitemap_url:
            self.sitemap_url = site_config.sitemap_url
        else:
            # Auto-discover: https://domain/sitemap.xml
            self.sitemap_url = f"https://{site_config.domain}/sitemap.xml"

        # Set up cache directory (NEW: _shared/temp/sitemaps/)
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent

        self.cache_dir = base_path / "_shared" / "temp" / "sitemaps" / site_config.id
        self.cache_file = self.cache_dir / "sitemap_cache.json"

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, force_refresh: bool = False) -> list[SitemapURL]:
        """
        Fetch sitemap URLs.

        Args:
            force_refresh: If True, ignore cache and fetch fresh data

        Returns:
            List of SitemapURL objects
        """
        # Load from cache if available and not forcing refresh
        if not force_refresh:
            cached = self._load_cache()
            if cached and not cached.error:
                return cached.urls

        # Fetch fresh data
        try:
            urls = self._fetch_from_web()

            # Save to cache
            cache = SitemapCache(
                urls=urls,
                fetch_timestamp=datetime.now().isoformat(),
                sitemap_url=self.sitemap_url
            )
            self._save_cache(cache)

            return urls

        except Exception as e:
            print(f"Error fetching sitemap for {self.site_config.id}: {e}")

            # Fallback to cache if available
            cached = self._load_cache()
            if cached:
                print(f"Using cached sitemap data from {cached.fetch_timestamp}")
                return cached.urls

            # Save error cache
            error_cache = SitemapCache(
                urls=[],
                fetch_timestamp=datetime.now().isoformat(),
                sitemap_url=self.sitemap_url,
                error=str(e)
            )
            self._save_cache(error_cache)

            return []

    def fetch_and_detect_new(self, force_refresh: bool = True) -> FetchResult:
        """
        Fetch sitemap and detect changes since last fetch.

        Args:
            force_refresh: Whether to fetch fresh data (recommended: True)

        Returns:
            FetchResult with new_urls, removed_urls, and counts
        """
        # Load previous cache for comparison
        previous_cache = self._load_cache()
        previous_urls = set(url.loc for url in previous_cache.urls) if previous_cache else set()
        total_previous = len(previous_urls)

        # Fetch current URLs
        current_urls_list = self.fetch(force_refresh=force_refresh)
        current_urls = {url.loc: url for url in current_urls_list}
        total_current = len(current_urls)

        # Detect changes
        new_url_locs = set(current_urls.keys()) - previous_urls
        removed_url_locs = previous_urls - set(current_urls.keys())

        new_urls = [current_urls[loc] for loc in new_url_locs]
        removed_urls = list(removed_url_locs)

        return FetchResult(
            new_urls=new_urls,
            removed_urls=removed_urls,
            total_previous=total_previous,
            total_current=total_current
        )

    def _fetch_from_web(self) -> list[SitemapURL]:
        """
        Fetch sitemap from web and parse.

        Returns:
            List of SitemapURL objects

        Raises:
            requests.RequestException: On network error
            ET.ParseError: On XML parsing error
        """
        response = requests.get(
            self.sitemap_url,
            timeout=self.timeout,
            headers={'User-Agent': 'SEO-Refresh-Bot/1.0'}
        )
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Detect sitemap type
        if root.tag.endswith('sitemapindex'):
            # Sitemap index: fetch all child sitemaps
            return self._parse_sitemap_index(root)
        else:
            # Standard sitemap
            return self._parse_sitemap(root)

    def _parse_sitemap_index(self, root: ET.Element) -> list[SitemapURL]:
        """
        Parse sitemap index and fetch all child sitemaps.

        Args:
            root: XML root element of sitemap index

        Returns:
            Combined list of all URLs from child sitemaps
        """
        all_urls = []

        # Extract sitemap URLs
        for sitemap_elem in root.findall('sm:sitemap', SITEMAP_NS):
            loc_elem = sitemap_elem.find('sm:loc', SITEMAP_NS)
            if loc_elem is None or not loc_elem.text:
                continue

            child_sitemap_url = loc_elem.text.strip()

            try:
                # Fetch child sitemap
                response = requests.get(
                    child_sitemap_url,
                    timeout=self.timeout,
                    headers={'User-Agent': 'SEO-Refresh-Bot/1.0'}
                )
                response.raise_for_status()

                # Parse child sitemap
                child_root = ET.fromstring(response.content)
                child_urls = self._parse_sitemap(child_root)
                all_urls.extend(child_urls)

            except Exception as e:
                print(f"Error fetching child sitemap {child_sitemap_url}: {e}")
                continue

        return all_urls

    def _parse_sitemap(self, root: ET.Element) -> list[SitemapURL]:
        """
        Parse standard sitemap XML.

        Args:
            root: XML root element

        Returns:
            List of SitemapURL objects
        """
        urls = []

        for url_elem in root.findall('sm:url', SITEMAP_NS):
            # Required: loc
            loc_elem = url_elem.find('sm:loc', SITEMAP_NS)
            if loc_elem is None or not loc_elem.text:
                continue

            loc = loc_elem.text.strip()

            # Optional fields
            lastmod_elem = url_elem.find('sm:lastmod', SITEMAP_NS)
            lastmod = lastmod_elem.text.strip() if lastmod_elem is not None and lastmod_elem.text else None

            changefreq_elem = url_elem.find('sm:changefreq', SITEMAP_NS)
            changefreq = changefreq_elem.text.strip() if changefreq_elem is not None and changefreq_elem.text else None

            priority_elem = url_elem.find('sm:priority', SITEMAP_NS)
            priority = float(priority_elem.text) if priority_elem is not None and priority_elem.text else None

            sitemap_url = SitemapURL(
                loc=loc,
                lastmod=lastmod,
                changefreq=changefreq,
                priority=priority
            )
            urls.append(sitemap_url)

        return urls

    def _load_cache(self) -> Optional[SitemapCache]:
        """
        Load cached sitemap data.

        Returns:
            SitemapCache object or None if no cache exists
        """
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return SitemapCache.from_dict(data)
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None

    def _save_cache(self, cache: SitemapCache):
        """
        Save sitemap cache to disk.

        Args:
            cache: SitemapCache object to save
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def clear_cache(self):
        """Delete cached sitemap data."""
        if self.cache_file.exists():
            self.cache_file.unlink()


def load_fetcher_from_config(
    site_id: str,
    config_path: Optional[Path] = None
) -> SitemapFetcher:
    """
    Load a SitemapFetcher from site configuration.

    Args:
        site_id: Site identifier (e.g., "enseigna")
        config_path: Path to sites.json (auto-detected if None)

    Returns:
        Configured SitemapFetcher instance

    Raises:
        ValueError: If site not found or inactive

    Usage:
        fetcher = load_fetcher_from_config("enseigna")
        result = fetcher.fetch_and_detect_new()
    """
    registry = SitesRegistry(config_path=config_path)
    site_config = registry.get_site(site_id)

    if not site_config:
        raise ValueError(f"Site not found: {site_id}")

    if not site_config.active:
        raise ValueError(f"Site is inactive: {site_id}")

    return SitemapFetcher(site_config)
