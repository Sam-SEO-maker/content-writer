"""
Fix image captions in refreshed HTML files.

Compares <figure>/<figcaption> tags in refreshed HTML against the original
live article to detect caption drift.
"""

import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

BLOGS = ["enseigna.fr", "superprof.fr"]
SUBDIRS = ["html_child_posts", "html_parent_posts"]


def filename_to_url(filename: str, blog_domain: str) -> str:
    """Reconstruct URL from refreshed/corrected filename."""
    slug = filename.replace("_refreshed.html", "").replace("_corrected.html", "")
    prefix = "https_" + blog_domain.replace(".", "_").replace("-", "_") + "_"
    if slug.startswith(prefix):
        path = slug[len(prefix):].replace("_", "-")
    else:
        path = slug
    return f"https://{blog_domain}/{path}/"


def extract_wp_image_id(html_fragment: str) -> str:
    """Extract wp-image-XXXXX ID from an HTML fragment."""
    match = re.search(r"wp-image-(\d+)", html_fragment)
    return match.group(1) if match else ""


def extract_image_filename(html_fragment: str) -> str:
    """Extract image filename from src attribute."""
    match = re.search(r'src="([^"]+)"', html_fragment)
    if match:
        return match.group(1).split("/")[-1].split("?")[0]
    return ""


def build_caption_map(original_content: str) -> tuple:
    """
    Build maps for matching [caption] blocks from original HTML.

    Returns:
        (by_id, by_filename):
            by_id: {wp_image_id: full_caption_shortcode}
            by_filename: {image_filename: full_caption_shortcode}
    """
    captions = re.findall(r"\[caption[^\]]*\].*?\[/caption\]", original_content, re.S)
    by_id = {}
    by_filename = {}
    for cap in captions:
        img_id = extract_wp_image_id(cap)
        if img_id:
            by_id[img_id] = cap
        fname = extract_image_filename(cap)
        if fname:
            by_filename[fname] = cap
    return by_id, by_filename


def fix_file(filepath: str, by_id: dict, by_filename: dict) -> dict:
    """
    Replace <figure>/<figcaption> blocks with [caption] shortcodes.

    Matching strategy:
    1. Match by wp-image-ID (exact)
    2. Fallback: match by image filename

    Args:
        filepath: Path to the refreshed HTML file
        by_id: {wp_image_id: caption_shortcode} from original HTML
        by_filename: {image_filename: caption_shortcode} from original HTML

    Returns:
        {"replaced": int, "unmatched": int, "total_figures": int}
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    figures = list(re.finditer(r"<figure[^>]*>.*?</figure>", content, re.S))
    if not figures:
        return {"replaced": 0, "unmatched": 0, "total_figures": 0}

    replaced = 0
    unmatched = 0
    new_content = content

    # Process in reverse order to preserve positions
    for match in reversed(figures):
        figure_html = match.group(0)
        img_id = extract_wp_image_id(figure_html)
        caption = None

        # Strategy 1: Match by wp-image-ID
        if img_id and img_id in by_id:
            caption = by_id[img_id]

        # Strategy 2: Fallback by image filename
        if not caption:
            fname = extract_image_filename(figure_html)
            if fname and fname in by_filename:
                caption = by_filename[fname]

        if caption:
            new_content = (
                new_content[:match.start()]
                + caption
                + new_content[match.end():]
            )
            replaced += 1
        else:
            unmatched += 1

    if replaced > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    return {"replaced": replaced, "unmatched": unmatched, "total_figures": len(figures)}


def main():
    import requests
    base = Path(__file__).parent.parent.parent / "_shared" / "outputs"

    total_files = 0
    total_replaced = 0
    total_failed = 0
    total_skipped = 0

    for blog in BLOGS:
        logger.info(f"\n{'='*60}")
        logger.info(f"  {blog}")
        logger.info(f"{'='*60}")

        for subdir in SUBDIRS:
            dirpath = base / blog / subdir
            if not dirpath.exists():
                continue

            files = sorted(
                f for f in os.listdir(dirpath)
                if f.endswith("_refreshed.html") or f.endswith("_corrected.html")
            )
            for filename in files:
                filepath = dirpath / filename
                url = filename_to_url(filename, blog)

                # Fetch original from live site
                try:
                    resp = requests.get(
                        url,
                        timeout=20,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; ContentWriter/1.0)"},
                        allow_redirects=True,
                    )
                    if not resp.ok:
                        logger.warning(f"SKIP {filename} (HTTP {resp.status_code}: {url})")
                        total_skipped += 1
                        continue
                    original_html = resp.text
                except Exception as e:
                    logger.warning(f"SKIP {filename} (fetch error: {e})")
                    total_skipped += 1
                    continue

                # Build caption maps from original
                by_id, by_filename = build_caption_map(original_html)

                # Fix the file
                stats = fix_file(str(filepath), by_id, by_filename)
                total_files += 1
                total_replaced += stats["replaced"]
                total_failed += stats["unmatched"]

                status = "OK" if stats["unmatched"] == 0 else "PARTIAL"
                logger.info(
                    f"{status} {filename}: "
                    f"{stats['replaced']}/{stats['total_figures']} figures replaced"
                )

    logger.info(f"\n{'='*60}")
    logger.info(f"DONE")
    logger.info(f"  Files processed: {total_files}")
    logger.info(f"  Figures replaced: {total_replaced}")
    logger.info(f"  Unmatched figures: {total_failed}")
    logger.info(f"  Files skipped (HTTP miss): {total_skipped}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
