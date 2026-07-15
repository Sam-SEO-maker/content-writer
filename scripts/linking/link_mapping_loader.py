"""
Link Mapping Loader Module

Loads and validates link injection mappings from CSV files.
"""

import csv
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from _shared.core.models.linking_models import LinkMapping

logger = logging.getLogger(__name__)

VALID_RELATIONS = {"Parent", "Enfant", "Soeur"}


class LinkMappingLoader:
    """
    Loads link injection mappings from CSV files.

    CSV format:
        url_source,url_cible,mot_cle_principal,type_relation
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path(__file__).parent.parent.parent
        from _shared.core.tenant_paths import TenantPaths
        self._tenant_paths = TenantPaths(base_path=self.base_path)

    def load_csv(self, site_id: str) -> list[LinkMapping]:
        """
        Load linking map CSV for a specific tenant.

        Args:
            site_id: identifiant tenant (ex: "superprof-ressources")

        Returns:
            List of validated LinkMapping objects
        """
        filepath = self._tenant_paths.linking_maps_dir(site_id) / "links.csv"
        if not filepath.exists():
            raise FileNotFoundError(
                f"Linking map not found: {filepath}\n"
                f"Create it with columns: url_source,url_cible,mot_cle_principal,type_relation"
            )
        return self.load_from_file(filepath)

    def load_from_file(self, filepath: Path) -> list[LinkMapping]:
        """
        Load and validate a linking map from a CSV file.

        Args:
            filepath: Path to the CSV file

        Returns:
            List of validated LinkMapping objects
        """
        mappings = []
        seen_pairs = set()
        errors = []

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            required_columns = {"url_source", "url_cible", "mot_cle_principal", "type_relation"}
            if not required_columns.issubset(set(reader.fieldnames or [])):
                missing = required_columns - set(reader.fieldnames or [])
                raise ValueError(
                    f"CSV missing required columns: {missing}\n"
                    f"Expected: url_source,url_cible,mot_cle_principal,type_relation"
                )

            for i, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
                error = self._validate_row(row, i, seen_pairs)
                if error:
                    errors.append(error)
                    continue

                pair = (row["url_source"].strip(), row["url_cible"].strip())
                seen_pairs.add(pair)

                mappings.append(LinkMapping(
                    url_source=row["url_source"].strip(),
                    url_cible=row["url_cible"].strip(),
                    mot_cle_principal=row["mot_cle_principal"].strip(),
                    type_relation=row["type_relation"].strip(),
                    h1_cible=row.get("h1_cible", "").strip(),
                ))

        if errors:
            logger.warning(f"[LinkMappingLoader] {len(errors)} validation errors:")
            for err in errors:
                logger.warning(f"  - {err}")

        logger.info(
            f"[LinkMappingLoader] Loaded {len(mappings)} mappings from {filepath.name} "
            f"({len(errors)} errors skipped)"
        )
        return mappings

    def group_by_source(self, mappings: list[LinkMapping]) -> dict[str, list[LinkMapping]]:
        """
        Group mappings by url_source for batch processing.

        Args:
            mappings: List of LinkMapping objects

        Returns:
            Dict mapping url_source -> list of LinkMappings targeting that source
        """
        groups: dict[str, list[LinkMapping]] = {}
        for mapping in mappings:
            groups.setdefault(mapping.url_source, []).append(mapping)
        return groups

    def _validate_row(self, row: dict, line_number: int, seen_pairs: set) -> Optional[str]:
        """
        Validate a single CSV row.

        Returns:
            Error message string, or None if valid
        """
        url_source = row.get("url_source", "").strip()
        url_cible = row.get("url_cible", "").strip()
        mot_cle = row.get("mot_cle_principal", "").strip()
        relation = row.get("type_relation", "").strip()

        if not url_source:
            return f"Line {line_number}: url_source is empty"

        if not url_cible:
            return f"Line {line_number}: url_cible is empty"

        if not mot_cle:
            return f"Line {line_number}: mot_cle_principal is empty"

        if relation not in VALID_RELATIONS:
            return f"Line {line_number}: type_relation '{relation}' must be one of {VALID_RELATIONS}"

        if url_source == url_cible:
            return f"Line {line_number}: url_source cannot equal url_cible (self-link)"

        pair = (url_source, url_cible)
        if pair in seen_pairs:
            return f"Line {line_number}: duplicate pair ({url_source[:40]}... -> {url_cible[:40]}...)"

        return None

    @staticmethod
    def url_to_slug(url: str) -> str:
        """
        Convert URL to safe filename slug.

        Mirrors OutputManager._url_to_slug() logic for consistency.

        Examples:
            https://www.enseigna.fr/origines-styles-yoga/ -> origines-styles-yoga
            https://www.enseigna.fr/cours-de-yoga/bienfaits/ -> cours-de-yoga-bienfaits
        """
        parsed = urlparse(url) if url.startswith("http") else None
        if parsed:
            slug = parsed.path.strip("/").replace("/", "-")
        else:
            slug = url

        slug = re.sub(r"[^\w\-]", "", slug)
        slug = slug[:150]

        return slug or "unknown"
