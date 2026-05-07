"""
Output Manager Module

Centralized handler for all file outputs in the autonomous "Scrape & Refresh" workflow.

Architecture:
- Temp cache: _shared/temp/{site_id}/ (scraped HTML for comparison)
- Permanent outputs:
  - _shared/outputs/{site_id}/html/ (refreshed HTML files)
  - _shared/outputs/{site_id}/metadata/ (metadata and audit JSON files)
  - _shared/outputs/{site_id}/editorial_audits/ (editorial audit markdown files)

Multi-tenant support:
- enseigna.fr
- superprof.fr (ressources)
"""

from pathlib import Path
from typing import Optional, Dict, List, Tuple
import json
import re
import shutil
import unicodedata
from datetime import datetime
import logging


def title_to_slug(title: str) -> str:
    """Convert an article title to a clean URL/filename slug."""
    s = unicodedata.normalize('NFD', title)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower()
    s = re.sub(r'[^a-z0-9\s]', '', s)
    s = re.sub(r'\s+', '-', s.strip())
    s = re.sub(r'-+', '-', s)
    return s[:150] or "unknown"

logger = logging.getLogger(__name__)


class OutputManager:
    """
    Manages all file outputs for the autonomous workflow.

    Ensures:
    - Single output location (_shared/outputs/)
    - Temporary cache for scraped HTML (_shared/temp/)
    - Consistent directory structure
    - Validation before writes
    - Atomic file operations
    - Multi-tenant isolation
    """

    # Valid site IDs from CLAUDE.md multi-tenant architecture
    VALID_SITE_IDS = [
        "enseigna.fr",
        "superprof.fr",
    ]

    # Mapping blog_id (sans extension) → domain (avec extension)
    _BLOG_ID_TO_DOMAIN = {
        "enseigna": "enseigna.fr",
        "superprof-ressources": "superprof.fr",
    }

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize output manager.

        Args:
            base_path: Project root (defaults to auto-detect)
        """
        self.base_path = base_path or Path(__file__).parent.parent.parent
        self.outputs_root = self.base_path / "_shared" / "outputs"
        self.temp_root = self.base_path / "_shared" / "temp"

        # Ensure base directories exist
        self.outputs_root.mkdir(parents=True, exist_ok=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def init_workspace(self, purge_temp: bool = True) -> Dict[str, int]:
        """
        Initialize workspace: purge temp cache and ensure outputs structure.

        Cette fonction garantit:
        1. _shared/temp/ est purgé (si purge_temp=True)
        2. _shared/outputs/{site_id}/ existe pour chaque site
        3. _shared/outputs/{site_id}/editorial_audits/ existe

        Args:
            purge_temp: Si True, supprime tout le contenu de _shared/temp/

        Returns:
            {
                "temp_files_removed": int,
                "output_dirs_created": int,
                "editorial_audit_dirs_created": int
            }
        """
        stats = {
            "temp_files_removed": 0,
            "output_dirs_created": 0,
            "subdirs_created": 0
        }

        # Purge temp cache
        if purge_temp and self.temp_root.exists():
            for item in self.temp_root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                    stats["temp_files_removed"] += sum(1 for _ in item.rglob("*") if _.is_file())
                else:
                    item.unlink()
                    stats["temp_files_removed"] += 1
            logger.info(f"Purged temp cache: {stats['temp_files_removed']} files removed")

        # Ensure outputs structure for all sites
        for site_id in self.VALID_SITE_IDS:
            # Create site output directory
            site_dir = self.outputs_root / site_id
            if not site_dir.exists():
                site_dir.mkdir(parents=True, exist_ok=True)
                stats["output_dirs_created"] += 1

            # Create html/, metadata/, editorial_audits/ subdirectories
            for subdir in ["html", "metadata", "editorial_audits"]:
                sub_path = site_dir / subdir
                if not sub_path.exists():
                    sub_path.mkdir(parents=True, exist_ok=True)
                    stats["subdirs_created"] += 1

        logger.info(
            f"Workspace initialized: "
            f"{stats['output_dirs_created']} output dirs, "
            f"{stats['subdirs_created']} subdirs created"
        )

        return stats

    def _normalize_site_id(self, site_id: str) -> str:
        """Normalise blog_id vers le domaine complet si nécessaire."""
        if site_id in self.VALID_SITE_IDS:
            return site_id
        return self._BLOG_ID_TO_DOMAIN.get(site_id, site_id)

    def _validate_site_id(self, site_id: str) -> str:
        """Valide et normalise le site_id. Retourne le domaine complet."""
        normalized = self._normalize_site_id(site_id)
        if normalized not in self.VALID_SITE_IDS:
            raise ValueError(
                f"Invalid site_id '{site_id}'. "
                f"Must be one of: {', '.join(self.VALID_SITE_IDS)}"
            )
        return normalized

    def _url_to_slug(self, url: str) -> str:
        """
        Convert URL to safe filename slug.

        Examples:
            https://enseigna.fr/avis-acadomia/ → avis-acadomia
            https://www.superprof.fr/ressources/maths/calcul/ → calcul
        """
        from urllib.parse import urlparse
        import re

        parsed = urlparse(url) if url.startswith("http") else None
        if parsed:
            slug = parsed.path.strip('/').replace('/', '-')
        else:
            slug = url

        # Sanitize: keep only alphanumeric, dash, underscore
        slug = re.sub(r'[^\w\-]', '', slug)

        # Limit length
        slug = slug[:150]

        return slug or "unknown"

    @staticmethod
    def _title_to_slug(title: str) -> str:
        return title_to_slug(title)

    # =========================================================================
    # TEMP CACHE METHODS (for scraped HTML)
    # =========================================================================

    def save_temp_html(self, site_id: str, url_slug: str, html_content: str) -> Path:
        """
        Save scraped HTML to temp cache for editorial audit comparison.

        Args:
            site_id: Blog identifier (e.g., "enseigna.fr")
            url_slug: URL slug for filename
            html_content: Scraped HTML content

        Returns:
            Path to saved temp file
        """
        site_id = self._validate_site_id(site_id)

        # Create site temp directory
        temp_dir = self.temp_root / site_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Save HTML
        temp_file = temp_dir / f"{url_slug}.html"
        temp_file.write_text(html_content, encoding="utf-8")

        logger.debug(f"Saved temp HTML: {temp_file}")
        return temp_file

    def get_temp_html(self, site_id: str, url_slug: str) -> Optional[str]:
        """
        Retrieve scraped HTML from temp cache.

        Args:
            site_id: Blog identifier
            url_slug: URL slug

        Returns:
            HTML content if exists, None otherwise
        """
        site_id = self._validate_site_id(site_id)

        temp_file = self.temp_root / site_id / f"{url_slug}.html"
        if temp_file.exists():
            return temp_file.read_text(encoding="utf-8")
        return None

    def _cleanup_temp(self, site_id: str, url_slug: str):
        """Remove temp file for a delivered article."""
        temp_file = self.temp_root / site_id / f"{url_slug}.html"
        if temp_file.exists():
            temp_file.unlink()
            logger.debug(f"Cleaned up temp file: {temp_file}")

    def clear_temp_cache(self, site_id: Optional[str] = None) -> int:
        """
        Clear temp cache for a specific site or all sites.

        Args:
            site_id: If provided, clear only this site's cache. If None, clear all.

        Returns:
            Number of files removed
        """
        if site_id:
            site_id = self._validate_site_id(site_id)
            temp_dir = self.temp_root / site_id
            if temp_dir.exists():
                file_count = sum(1 for _ in temp_dir.rglob("*.html"))
                shutil.rmtree(temp_dir)
                temp_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Cleared temp cache for {site_id}: {file_count} files")
                return file_count
            return 0
        else:
            # Clear all sites
            total = 0
            for site in self.VALID_SITE_IDS:
                total += self.clear_temp_cache(site)
            return total

    # =========================================================================
    # OUTPUT METHODS (for permanent results)
    # =========================================================================

    def get_site_output_dir(self, site_id: str) -> Path:
        """
        Get output directory for a site.

        Args:
            site_id: Blog identifier

        Returns:
            Path to site output directory
        """
        site_id = self._validate_site_id(site_id)

        site_dir = self.outputs_root / site_id
        site_dir.mkdir(parents=True, exist_ok=True)

        # Ensure html/, metadata/, editorial_audits/ subdirectories exist
        for subdir in ["html", "metadata", "editorial_audits"]:
            (site_dir / subdir).mkdir(parents=True, exist_ok=True)

        return site_dir

    def save_refreshed_html(
        self,
        site_id: str,
        url_slug: str,
        html_content: str,
        title: Optional[str] = None,
        post_type: Optional[str] = None  # kept for backwards compat, ignored
    ) -> Path:
        """
        Save refreshed HTML content (WordPress-ready).

        Args:
            site_id: Blog identifier
            url_slug: URL slug for filename (fallback if no title)
            html_content: Refreshed HTML content
            title: Article title (column E) — used for filename if provided

        Returns:
            Path to saved file
        """
        site_id = self._validate_site_id(site_id)
        html_dir = self.get_site_output_dir(site_id) / "html"
        html_dir.mkdir(parents=True, exist_ok=True)

        file_slug = self._title_to_slug(title) if title else url_slug
        output_file = html_dir / f"{file_slug}_refreshed.html"

        output_file.write_text(html_content, encoding="utf-8")
        logger.info(f"Saved refreshed HTML: {output_file}")

        from scripts.utils.gutenberg_formatter import to_gutenberg
        gutenberg_file = html_dir / f"{file_slug}_refreshed.gutenberg.html"
        gutenberg_file.write_text(to_gutenberg(html_content), encoding="utf-8")
        logger.info(f"Saved Gutenberg HTML: {gutenberg_file}")

        from scripts.utils.table_csv_extractor import extract_tables_to_csv
        csv_dir = self.get_site_output_dir(site_id) / "csv"
        csv_files = extract_tables_to_csv(html_content, csv_dir, file_slug)
        if csv_files:
            logger.info(f"[CSV] {len(csv_files)} tableau(x) extrait(s) → {csv_dir}")

        # Clean up temp file for this article after successful delivery
        self._cleanup_temp(site_id, url_slug)

        return output_file

    def save_metadata(
        self,
        site_id: str,
        url_slug: str,
        metadata: dict
    ) -> Path:
        """
        Save metadata JSON (title, meta_description, keywords, etc.).

        Args:
            site_id: Blog identifier
            url_slug: URL slug for filename
            metadata: Metadata dictionary

        Returns:
            Path to saved file
        """
        site_id = self._validate_site_id(site_id)

        metadata_dir = self.get_site_output_dir(site_id) / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        output_file = metadata_dir / f"{url_slug}_metadata.json"

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved metadata: {output_file}")
        return output_file

    def save_audit_report(
        self,
        site_id: str,
        url_slug: str,
        audit_data: dict,
        report_type: str = "audit"
    ) -> Path:
        """
        Save audit report JSON.

        Args:
            site_id: Blog identifier
            url_slug: URL slug for filename
            audit_data: Audit data dictionary
            report_type: Type of report (audit, serp, gsc)

        Returns:
            Path to saved file
        """
        site_id = self._validate_site_id(site_id)

        metadata_dir = self.get_site_output_dir(site_id) / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        output_file = metadata_dir / f"{url_slug}_{report_type}.json"

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved {report_type} report: {output_file}")
        return output_file

    def save_editorial_audit(
        self,
        site_id: str,
        url_slug: str,
        markdown_content: str
    ) -> Path:
        """
        Save editorial audit markdown report.

        Stocké dans: _shared/outputs/{site_id}/editorial_audits/{url_slug}_editorial_audit.md

        Args:
            site_id: Blog identifier
            url_slug: URL slug for filename
            markdown_content: Markdown content of editorial audit

        Returns:
            Path to saved file
        """
        site_id = self._validate_site_id(site_id)

        output_dir = self.get_site_output_dir(site_id)
        editorial_dir = output_dir / "editorial_audits"
        editorial_dir.mkdir(parents=True, exist_ok=True)

        output_file = editorial_dir / f"{url_slug}_editorial_audit.md"
        output_file.write_text(markdown_content, encoding="utf-8")

        logger.info(f"Saved editorial audit: {output_file}")
        return output_file

    # =========================================================================
    # VALIDATION & UTILITY METHODS
    # =========================================================================

    def get_output_files(
        self,
        site_id: str,
        url_slug: str,
        title: Optional[str] = None,
        post_type: Optional[str] = None
    ) -> Dict[str, Path]:
        """
        Get paths to expected output files.

        Args:
            site_id: Blog identifier
            url_slug: URL slug
            title: Article title — used for HTML filename if provided
        Returns:
            Dictionary of output file paths
        """
        site_id = self._validate_site_id(site_id)

        output_dir = self.get_site_output_dir(site_id)
        html_dir = output_dir / "html"
        metadata_dir = output_dir / "metadata"
        editorial_dir = output_dir / "editorial_audits"

        return {
            "refreshed_html": html_dir / f"{self._title_to_slug(title) if title else url_slug}_refreshed.html",
            "metadata": metadata_dir / f"{url_slug}_metadata.json",
            "audit": metadata_dir / f"{url_slug}_audit.json",
            "serp": metadata_dir / f"{url_slug}_serp.json",
            "gsc": metadata_dir / f"{url_slug}_gsc.json",
            "editorial_audit": editorial_dir / f"{url_slug}_editorial_audit.md",
            "temp_html": self.temp_root / site_id / f"{url_slug}.html"
        }

    def validate_outputs_exist(
        self,
        site_id: str,
        url_slug: str,
        required: List[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate that required output files exist.

        Args:
            site_id: Blog identifier
            url_slug: URL slug
            required: List of required file types (default: ["refreshed_html", "metadata"])

        Returns:
            Tuple of (all_exist: bool, missing_files: list)
        """
        if required is None:
            required = ["refreshed_html", "metadata"]

        site_id = self._validate_site_id(site_id)

        outputs = self.get_output_files(site_id, url_slug)
        missing = [
            file_type
            for file_type in required
            if not outputs[file_type].exists()
        ]

        return (len(missing) == 0, missing)

    def get_workspace_stats(self) -> Dict[str, any]:
        """
        Get statistics about workspace usage.

        Returns:
            {
                "temp_cache": {site_id: file_count},
                "outputs": {site_id: file_count},
                "total_temp_size_mb": float,
                "total_output_size_mb": float
            }
        """
        stats = {
            "temp_cache": {},
            "outputs": {},
            "total_temp_size_mb": 0.0,
            "total_output_size_mb": 0.0
        }

        # Temp cache stats
        for site_id in self.VALID_SITE_IDS:
            temp_dir = self.temp_root / site_id
            if temp_dir.exists():
                files = list(temp_dir.rglob("*.html"))
                stats["temp_cache"][site_id] = len(files)
                stats["total_temp_size_mb"] += sum(f.stat().st_size for f in files) / (1024 * 1024)

        # Output stats
        for site_id in self.VALID_SITE_IDS:
            output_dir = self.outputs_root / site_id
            if output_dir.exists():
                files = list(output_dir.rglob("*"))
                files = [f for f in files if f.is_file()]
                stats["outputs"][site_id] = len(files)
                stats["total_output_size_mb"] += sum(f.stat().st_size for f in files) / (1024 * 1024)

        return stats
