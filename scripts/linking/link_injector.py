"""
Link Injector Module

Core engine for automated internal link injection into HTML articles.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from _shared.core.models.linking_models import (
    LinkMapping,
    InjectionPoint,
    InjectionResult,
    InjectionReport,
)
from .anchor_generator import AnchorGenerator
from .injection_planner import InjectionPlanner
from .injection_validator import InjectionValidator
from .link_mapping_loader import LinkMappingLoader

logger = logging.getLogger(__name__)


class LinkInjector:
    """
    Core engine for injecting internal links into HTML articles.

    Workflow per source article:
    1. Load HTML (local output files -> fallback scraping)
    2. Parse and extract existing links
    3. For each mapping: check duplicate -> generate anchor -> plan point -> inject
    4. Validate modified HTML
    5. Backup original, save modified
    6. Generate report
    """

    def __init__(self, site_id: str, base_path: Optional[Path] = None):
        self.site_id = site_id
        self.base_path = base_path or Path(__file__).parent.parent.parent
        self.domain = self._resolve_domain(site_id)

        self.planner = InjectionPlanner(self.domain)
        self.anchor_gen = AnchorGenerator()
        self.validator = InjectionValidator(self.domain)

        from _shared.core.tenant_paths import TenantPaths
        self.outputs_dir = TenantPaths(base_path=self.base_path).output_dir(site_id)
        self.html_dir = self.outputs_dir / "html"
        self.json_dir = self.outputs_dir / "json"

        # Ensure directories exist
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

    def inject_batch(self, mappings: list[LinkMapping]) -> list[InjectionReport]:
        """
        Process all mappings, grouped by source URL.

        Args:
            mappings: List of all LinkMapping objects

        Returns:
            List of InjectionReport, one per source URL
        """
        loader = LinkMappingLoader(self.base_path)
        groups = loader.group_by_source(mappings)

        reports = []
        total = len(groups)

        logger.info(f"[LinkInjector] Processing {len(mappings)} links across {total} source articles")

        for i, (url_source, source_mappings) in enumerate(groups.items(), 1):
            logger.info(f"[LinkInjector] [{i}/{total}] Processing {url_source[:60]}...")
            report = self.inject_single_source(url_source, source_mappings)
            reports.append(report)

            # Save individual report
            self._save_report(report)

        # Save batch summary
        self._save_batch_summary(reports)

        return reports

    def inject_single_source(
        self,
        url_source: str,
        mappings: list[LinkMapping],
    ) -> InjectionReport:
        """
        Inject all links into a single source article.

        Args:
            url_source: URL of the article to modify
            mappings: Links to inject into this article

        Returns:
            InjectionReport with results
        """
        report = InjectionReport(url_source=url_source, site_id=self.site_id)

        # 1. Load HTML
        html, source_path = self._load_html(url_source)
        if not html:
            report.links_failed = len(mappings)
            report.results = [
                InjectionResult(
                    url_cible=m.url_cible,
                    success=False,
                    anchor_text="",
                    placement="",
                    error="Failed to load source HTML",
                )
                for m in mappings
            ]
            return report

        original_html = html

        # 2. Parse HTML and count existing links
        soup = BeautifulSoup(html, "html.parser")
        report.internal_links_before = self._count_internal_links(soup)

        # Reset anchor generator for this article
        self.anchor_gen.reset()

        # 3. Process each mapping
        for mapping in mappings:
            result = self._process_single_link(soup, mapping)
            report.results.append(result)

            if result.success:
                report.links_injected += 1
            elif result.was_duplicate:
                report.links_skipped_duplicate += 1
            else:
                report.links_failed += 1

        # 4. Get modified HTML
        modified_html = str(soup)

        # 5. Validate
        validation = self.validator.validate(original_html, modified_html)
        report.validation_passed = validation["valid"]
        report.internal_links_after = validation["internal_links_after"]

        if validation["warnings"]:
            for warning in validation["warnings"]:
                logger.warning(f"[LinkInjector] Validation warning: {warning}")

        # 6. Save if any links were injected
        if report.links_injected > 0 and source_path:
            self._backup_and_save(source_path, original_html, modified_html)

        return report

    def inject_into_html(
        self,
        html: str,
        mappings: list[LinkMapping],
    ) -> tuple[str, list[InjectionResult]]:
        """
        Inject links into in-memory HTML (for workflow integration).

        Unlike inject_single_source, this does NOT read/write files.
        Used by orchestrator STEP 5.5 to inject links during refresh.

        Args:
            html: HTML content string
            mappings: Links to inject

        Returns:
            Tuple of (modified_html, list of InjectionResult)
        """
        soup = BeautifulSoup(html, "html.parser")

        # Reset anchor generator
        self.anchor_gen.reset()

        results = []
        for mapping in mappings:
            result = self._process_single_link(soup, mapping)
            results.append(result)

        return str(soup), results

    def _process_single_link(
        self,
        soup: BeautifulSoup,
        mapping: LinkMapping,
    ) -> InjectionResult:
        """
        Process a single link injection.

        Args:
            soup: Mutable BeautifulSoup object (modified in-place)
            mapping: Link to inject

        Returns:
            InjectionResult
        """
        # Check duplicate
        if self._link_exists(soup, mapping.url_cible):
            logger.info(
                f"[LinkInjector] SKIP duplicate: {mapping.url_cible[:50]} "
                f"already linked in article"
            )
            return InjectionResult(
                url_cible=mapping.url_cible,
                success=False,
                anchor_text="",
                placement="",
                was_duplicate=True,
            )

        # Auto-fetch H1 if not provided
        if not mapping.h1_cible:
            mapping.h1_cible = self._fetch_h1_from_output(mapping.url_cible)

        # Generate anchor text
        anchor = self.anchor_gen.generate_anchor(mapping)

        # Plan injection point
        point = self.planner.plan_injection(soup, mapping)
        if not point:
            logger.warning(
                f"[LinkInjector] FAIL: no valid injection point for "
                f"{mapping.url_cible[:50]}"
            )
            return InjectionResult(
                url_cible=mapping.url_cible,
                success=False,
                anchor_text=anchor,
                placement="",
                error="No valid injection point found",
            )

        # Inject the link
        success = self._inject_into_soup(soup, point, mapping, anchor)

        placement = self._format_placement(point)

        if success:
            logger.info(
                f"[LinkInjector] INJECTED: '{anchor}' -> {mapping.url_cible[:50]} "
                f"at {placement}"
            )

        return InjectionResult(
            url_cible=mapping.url_cible,
            success=success,
            anchor_text=anchor,
            placement=placement,
            error=None if success else "Injection failed",
        )

    def _inject_into_soup(
        self,
        soup: BeautifulSoup,
        point: InjectionPoint,
        mapping: LinkMapping,
        anchor: str,
    ) -> bool:
        """
        Inject a link into the HTML at the specified point.

        Technique: Append a complete sentence with <a> tag to the target paragraph.

        Args:
            soup: BeautifulSoup object (modified in-place)
            point: Where to inject
            mapping: Link details
            anchor: Anchor text

        Returns:
            True if injection succeeded
        """
        try:
            all_p_tags = list(soup.find_all("p"))
            if point.paragraph_index >= len(all_p_tags):
                logger.warning(
                    f"[LinkInjector] Paragraph index {point.paragraph_index} "
                    f"out of range (total: {len(all_p_tags)})"
                )
                return False

            target_p = all_p_tags[point.paragraph_index]

            # Generate the injection sentence
            sentence = self.anchor_gen.generate_sentence(mapping, anchor)

            # Parse the sentence into a soup fragment
            sentence_soup = BeautifulSoup(f" {sentence}", "html.parser")

            # Append to the target paragraph
            target_p.append(sentence_soup)

            return True

        except Exception as e:
            logger.error(f"[LinkInjector] Injection error: {e}")
            return False

    def _load_html(self, url: str) -> tuple[Optional[str], Optional[Path]]:
        """
        Load HTML from output files, with scraping fallback.

        Args:
            url: Article URL

        Returns:
            Tuple of (html_content, file_path) or (None, None) if not found
        """
        slug = LinkMappingLoader.url_to_slug(url)

        # Strategy 1: Check local output files
        # Try multiple filename patterns
        patterns = [
            self.html_dir / f"{slug}_refreshed.html",
            self.html_dir / f"https_www_{self.site_id.replace('.', '_').replace('-', '_')}_{slug.replace('-', '_')}_refreshed.html",
        ]

        # Also try matching by partial slug
        if self.html_dir.exists():
            for html_file in self.html_dir.glob("*_refreshed.html"):
                # Check if the slug is contained in the filename
                normalized_slug = slug.replace("-", "_").lower()
                normalized_file = html_file.stem.lower()
                if normalized_slug in normalized_file:
                    patterns.insert(0, html_file)

        for filepath in patterns:
            if filepath.exists():
                html = filepath.read_text(encoding="utf-8")
                logger.info(f"[LinkInjector] Loaded HTML from {filepath.name}")
                return html, filepath

        logger.warning(f"[LinkInjector] No local file found for {url[:60]}")
        return None, None

    def _fetch_h1_from_output(self, url: str) -> str:
        """
        Try to fetch the H1 title from an existing output file.

        Args:
            url: Target article URL

        Returns:
            H1 text or empty string
        """
        html, _ = self._load_html(url)
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Fallback: extract from first <p> if it looks like a title
        return ""

    def _link_exists(self, soup: BeautifulSoup, url_cible: str) -> bool:
        """
        Check if a link to url_cible already exists in the HTML.

        Normalizes URLs for comparison (trailing slash, www prefix).
        """
        normalized_target = self._normalize_url(url_cible)

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if self._normalize_url(href) == normalized_target:
                return True

        return False

    def _count_internal_links(self, soup: BeautifulSoup) -> int:
        """Count links pointing to the same domain."""
        count = 0
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if self.domain in href:
                count += 1
        return count

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        url = url.lower().strip()
        url = url.rstrip("/")
        url = url.replace("https://www.", "https://")
        url = url.replace("http://www.", "http://")
        url = url.replace("http://", "https://")
        return url

    def _format_placement(self, point: InjectionPoint) -> str:
        """Format placement description for reporting."""
        if point.insertion_type == "intro":
            return "Intro"
        elif point.insertion_type == "after_h2":
            h2_short = point.context_h2[:50] if point.context_h2 else "?"
            return f"H2: {h2_short}"
        else:
            h2_short = point.context_h2[:50] if point.context_h2 else "Body"
            return f"Body ({h2_short})"

    def _backup_and_save(self, filepath: Path, original_html: str, modified_html: str):
        """
        Backup original file and save modified HTML.

        Args:
            filepath: Path to the HTML file
            original_html: Original content for backup
            modified_html: Modified content to save
        """
        # Create backup
        backup_path = filepath.with_suffix(".backup.html")
        backup_path.write_text(original_html, encoding="utf-8")
        logger.info(f"[LinkInjector] Backup saved: {backup_path.name}")

        # Save modified
        filepath.write_text(modified_html, encoding="utf-8")
        logger.info(f"[LinkInjector] Modified HTML saved: {filepath.name}")

    def _save_report(self, report: InjectionReport):
        """Save individual injection report as JSON."""
        slug = LinkMappingLoader.url_to_slug(report.url_source)
        report_path = self.json_dir / f"{slug}_linking_report.json"

        report_data = {
            "url_source": report.url_source,
            "site_id": report.site_id,
            "execution_date": datetime.now().isoformat(),
            "links_injected": report.links_injected,
            "links_skipped_duplicate": report.links_skipped_duplicate,
            "links_failed": report.links_failed,
            "internal_links_before": report.internal_links_before,
            "internal_links_after": report.internal_links_after,
            "validation_passed": report.validation_passed,
            "results": [
                {
                    "url_cible": r.url_cible,
                    "success": r.success,
                    "anchor_text": r.anchor_text,
                    "placement": r.placement,
                    "was_duplicate": r.was_duplicate,
                    "error": r.error,
                }
                for r in report.results
            ],
        }

        report_path.write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"[LinkInjector] Report saved: {report_path.name}")

    def _save_batch_summary(self, reports: list[InjectionReport]):
        """Save batch summary report."""
        summary_path = self.json_dir / "linking_batch_summary.json"

        total_injected = sum(r.links_injected for r in reports)
        total_skipped = sum(r.links_skipped_duplicate for r in reports)
        total_failed = sum(r.links_failed for r in reports)

        summary = {
            "site_id": self.site_id,
            "execution_date": datetime.now().isoformat(),
            "articles_processed": len(reports),
            "total_links_injected": total_injected,
            "total_links_skipped_duplicate": total_skipped,
            "total_links_failed": total_failed,
            "all_validations_passed": all(r.validation_passed for r in reports),
            "per_article": [
                {
                    "url_source": r.url_source,
                    "injected": r.links_injected,
                    "skipped": r.links_skipped_duplicate,
                    "failed": r.links_failed,
                    "links_before": r.internal_links_before,
                    "links_after": r.internal_links_after,
                    "validation": r.validation_passed,
                }
                for r in reports
            ],
        }

        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"[LinkInjector] Batch summary saved: {summary_path.name}")

    def _resolve_domain(self, site_id: str) -> str:
        """
        Resolve site_id to domain.

        Args:
            site_id: Blog identifier (e.g., "enseigna.fr")

        Returns:
            Domain string for URL matching
        """
        # site_id IS the domain for most cases
        # But for safety, try to load from sites.json
        try:
            import json
            config_path = self.base_path / "_shared" / "config" / "sites.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    sites_config = json.load(f)
                for site in sites_config.get("sites", []):
                    if site.get("domain") == site_id or site.get("id") == site_id:
                        return site.get("domain", site_id)
        except Exception:
            pass

        return site_id
