"""
Run Linking - CLI Entry Point

Usage:
    python -m scripts.linking.run_linking --site enseigna.fr
    python -m scripts.linking.run_linking --site enseigna.fr --csv path/to/custom.csv
    python -m scripts.linking.run_linking --site enseigna.fr --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path

# Force UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.linking.link_mapping_loader import LinkMappingLoader
from scripts.linking.link_injector import LinkInjector


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def print_report_summary(reports):
    """Print a formatted summary of injection results."""
    print("\n" + "=" * 70)
    print("RAPPORT DE MAILLAGE INTERNE")
    print("=" * 70)

    total_injected = 0
    total_skipped = 0
    total_failed = 0

    for report in reports:
        print(f"\n--- {report.url_source}")
        print(f"    Liens injectés : {report.links_injected}")
        print(f"    Doublons évités : {report.links_skipped_duplicate}")
        print(f"    Échecs : {report.links_failed}")
        print(f"    Liens internes : {report.internal_links_before} -> {report.internal_links_after}")
        print(f"    Validation : {'PASS' if report.validation_passed else 'FAIL'}")

        for result in report.results:
            if result.success:
                print(f"      + '{result.anchor_text}' -> {result.url_cible[:60]}")
                print(f"        Emplacement : {result.placement}")
            elif result.was_duplicate:
                print(f"      ~ DOUBLON : {result.url_cible[:60]}")
            else:
                print(f"      x ÉCHEC : {result.url_cible[:60]} ({result.error})")

        total_injected += report.links_injected
        total_skipped += report.links_skipped_duplicate
        total_failed += report.links_failed

    print(f"\n{'=' * 70}")
    print(f"TOTAL : {total_injected} injectés, {total_skipped} doublons, {total_failed} échecs")
    print(f"Articles traités : {len(reports)}")
    print(f"Validations OK : {sum(1 for r in reports if r.validation_passed)}/{len(reports)}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Injection automatique de maillage interne"
    )
    parser.add_argument(
        "--site",
        required=True,
        help="Site ID (e.g., enseigna.fr, enseigna.fr)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to custom CSV file (default: _shared/config/linking_maps/{site}.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate injection without saving files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # Load mappings
    loader = LinkMappingLoader(project_root)

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"ERROR: CSV file not found: {csv_path}")
            sys.exit(1)
        mappings = loader.load_from_file(csv_path)
    else:
        try:
            mappings = loader.load_csv(args.site)
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    if not mappings:
        print("No valid mappings found in CSV. Nothing to do.")
        sys.exit(0)

    print(f"Loaded {len(mappings)} link mappings for {args.site}")
    print(f"Source articles: {len(set(m.url_source for m in mappings))}")

    if args.dry_run:
        print("\n[DRY RUN] Simulating injection...")
        groups = loader.group_by_source(mappings)
        for url_source, source_mappings in groups.items():
            print(f"\n  Source: {url_source}")
            for m in source_mappings:
                print(f"    -> {m.url_cible[:60]} ({m.type_relation}, kw: {m.mot_cle_principal})")
        print("\n[DRY RUN] No files modified.")
        sys.exit(0)

    # Run injection
    injector = LinkInjector(args.site, project_root)
    reports = injector.inject_batch(mappings)

    # Print summary
    print_report_summary(reports)


if __name__ == "__main__":
    main()
