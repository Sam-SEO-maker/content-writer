"""
Table CSV Extractor

Extracts HTML tables from refreshed articles and writes one CSV per table,
ready for import into the WordPress TablePress plugin.

Also maintains _index.csv in the output directory so each CSV can be traced
back to its source article and column structure.
"""

import csv
import logging
import re
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_INDEX_FILE = "_index.csv"
_INDEX_FIELDS = ["csv_file", "colonnes", "article_titre", "article_url", "tableau_n"]


def extract_tables_to_csv(
    html_content: str,
    csv_dir: Path,
    file_slug: str,
    article_title: str = "",
    article_url: str = "",
) -> list[Path]:
    """
    Parse all <table> elements from html_content and write one CSV per table.

    Files are named from the table's column headers (slugified), e.g.
    "pronom_present_passe.csv". Falls back to {file_slug}_table_{idx}.csv
    when no headers are found. Duplicate slugs get a numeric suffix.
    Encoding is utf-8-sig (BOM) for Excel / LibreOffice / TablePress compatibility.

    Also updates _index.csv in csv_dir with one row per table so each CSV
    can be traced back to its source article.

    Returns the list of Path objects created (empty if no tables found).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    if not tables:
        return []

    # Infer title from H1 if not provided
    if not article_title:
        h1 = soup.find("h1")
        article_title = h1.get_text(strip=True) if h1 else file_slug

    csv_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    seen_slugs: dict[str, int] = {}
    index_rows: list[dict] = []

    for idx, table in enumerate(tables, start=1):
        rows = _parse_table(table)
        if not rows:
            continue

        header_row = rows[0]
        base_slug = _slug_from_headers(header_row) if rows else ""
        if not base_slug:
            base_slug = f"{file_slug}_table_{idx}"

        if base_slug in seen_slugs:
            seen_slugs[base_slug] += 1
            name_slug = f"{base_slug}_{seen_slugs[base_slug]}"
        else:
            seen_slugs[base_slug] = 1
            name_slug = base_slug

        csv_path = csv_dir / f"{name_slug}.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
            writer.writerows(rows)

        created.append(csv_path)
        index_rows.append({
            "csv_file": csv_path.name,
            "colonnes": " | ".join(header_row),
            "article_titre": article_title,
            "article_url": article_url,
            "tableau_n": idx,
        })
        logger.debug(f"[CSV] tableau {idx} → {csv_path.name} ({len(rows)} lignes)")

    if index_rows:
        _update_index(csv_dir, index_rows)

    return created


def _update_index(csv_dir: Path, new_rows: list[dict]) -> None:
    """Append or overwrite rows in _index.csv, keyed on csv_file."""
    index_path = csv_dir / _INDEX_FILE
    existing: dict[str, dict] = {}

    if index_path.exists():
        with index_path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                existing[row["csv_file"]] = row

    for row in new_rows:
        existing[row["csv_file"]] = row

    with index_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=_INDEX_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(sorted(existing.values(), key=lambda r: r["csv_file"]))


def _slug_from_headers(header_row: list[str]) -> str:
    """Convert column names to a filesystem-safe slug (max 80 chars)."""
    joined = "_".join(h for h in header_row if h.strip())
    # Normalize accented chars → ASCII equivalents
    normalized = unicodedata.normalize("NFD", joined)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    # Lowercase, replace non-alphanumeric with underscores, collapse runs
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_str.lower()).strip("_")
    return slug[:80]


def _parse_table(table) -> list[list[str]]:
    """
    Return a list of rows (each row is a list of cell strings).
    <th> cells in <thead> form the first row; <td> cells in <tbody> follow.
    Falls back to reading every <tr> in order if no thead/tbody structure.
    """
    rows: list[list[str]] = []

    thead = table.find("thead")
    tbody = table.find("tbody")

    if thead or tbody:
        if thead:
            for tr in thead.find_all("tr"):
                rows.append([_cell_text(cell) for cell in tr.find_all(["th", "td"])])
        if tbody:
            for tr in tbody.find_all("tr"):
                rows.append([_cell_text(cell) for cell in tr.find_all(["th", "td"])])
    else:
        for tr in table.find_all("tr"):
            rows.append([_cell_text(cell) for cell in tr.find_all(["th", "td"])])

    return [row for row in rows if any(cell.strip() for cell in row)]


def _cell_text(cell) -> str:
    return cell.get_text(separator=" ", strip=True)
