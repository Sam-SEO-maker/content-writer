#!/usr/bin/env python3
"""
Bulk Index Diagnostic Tool

Scanne les URLs d'un blog via sitemap, diagnostique leur indexation GSC,
et inscrit les URLs à problème dans le spreadsheet Refreshs_Audit.

Usage:
    # Dry-run pour tester (10 URLs)
    python scripts/indexing/bulk_index_diagnostic.py \
        --blog enseigna.fr \
        --spreadsheet-id <SHEET_ID> \
        --limit 10 \
        --dry-run \
        --verbose

    # Production (scan complet)
    python scripts/indexing/bulk_index_diagnostic.py \
        --blog enseigna.fr \
        --spreadsheet-id <SHEET_ID>

    # Update-only (URLs existantes seulement)
    python scripts/indexing/bulk_index_diagnostic.py \
        --blog enseigna.fr \
        --spreadsheet-id <SHEET_ID> \
        --update-only
"""

import argparse
import sys
import io
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Force UTF-8 encoding for Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    if not isinstance(sys.stdout, io.TextIOWrapper) or getattr(sys.stdout, 'encoding', '').lower() not in ('utf-8', 'utf8'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.sitemap.config_adapter import load_fetcher_from_blog_config
from scripts.sitemap.fetcher import SitemapFetcher
from scripts.audit.gsc_analyzer import GSCAnalyzer
from scripts.sheets.sheets_client import SheetsClient
from _shared.core.models import SitemapURL


# =========================================================================
# PHASE 1: Récupération des URLs via Sitemap
# =========================================================================

def fetch_all_urls_for_blog(blog_id: str, verbose: bool = False) -> List[str]:
    """
    Récupère toutes les URLs d'un blog depuis son sitemap.

    Args:
        blog_id: Identifiant du blog (ex: "enseigna")
        verbose: Mode verbose pour logs détaillés

    Returns:
        Liste d'URLs (strings)
    """
    if verbose:
        print(f"\n[Phase 1] Fetching URLs from sitemap for {blog_id}...")

    try:
        # Nettoyer le blog_id (retirer .fr/.com si présent)
        blog_id_clean = blog_id.replace(".fr", "").replace(".com", "")

        # Charger le fetcher depuis la config
        fetcher = load_fetcher_from_blog_config(blog_id_clean)

        # Récupérer les URLs (force_refresh pour avoir les données fraîches)
        sitemap_urls: List[SitemapURL] = fetcher.fetch(force_refresh=True)

        # Extraire les URLs (strings)
        urls = [url.loc for url in sitemap_urls]

        print(f"  ✅ {len(urls)} URLs found in sitemap")

        if verbose and urls:
            print(f"  📋 Sample URLs:")
            for url in urls[:3]:
                print(f"    - {url}")

        return urls

    except Exception as e:
        print(f"  ❌ Error fetching sitemap: {e}")
        import traceback
        traceback.print_exc()
        return []


# =========================================================================
# PHASE 2: Diagnostic GSC d'Indexation
# =========================================================================

def diagnose_indexation_issues(
    blog_id: str,
    urls: List[str],
    include_scenarios: List[str],
    delay: float = 1.0,
    limit: Optional[int] = None,
    verbose: bool = False
) -> List[Dict]:
    """
    Diagnostique l'indexation GSC pour chaque URL et filtre les problèmes.

    Args:
        blog_id: Identifiant du blog
        urls: Liste des URLs à diagnostiquer
        include_scenarios: Scenarios à inclure (ex: ["URL_NOT_ON_GOOGLE", "DISCOVERED_NOT_INDEXED"])
        delay: Délai entre appels API GSC (secondes)
        limit: Limiter le nombre d'URLs à traiter (None = toutes)
        verbose: Mode verbose

    Returns:
        Liste de dicts avec URLs à problème et métadonnées
    """
    if verbose:
        print(f"\n[Phase 2] Diagnosing indexation for {len(urls)} URLs...")
        print(f"  Scenarios included: {', '.join(include_scenarios)}")
        print(f"  Delay between calls: {delay}s")

    # Charger la config blog pour obtenir gsc_property
    from scripts.sitemap.config_adapter import load_blog_config_as_site_config
    blog_id_clean = blog_id.replace(".fr", "").replace(".com", "")

    try:
        site_config = load_blog_config_as_site_config(blog_id_clean)
        gsc_property = site_config.gsc_property
    except FileNotFoundError as e:
        print(f"  ❌ Error: {e}")
        return []

    # Initialiser GSC Analyzer
    analyzer = GSCAnalyzer(gsc_property)

    issues = []
    urls_to_process = urls[:limit] if limit else urls

    for i, url in enumerate(urls_to_process, 1):
        try:
            if verbose:
                print(f"\n  [{i}/{len(urls_to_process)}] {url}")

            # Appeler _check_indexation_detailed
            diagnostic = analyzer._check_indexation_detailed(url)

            scenario = diagnostic.get("scenario", "UNKNOWN")
            verdict = diagnostic.get("verdict", "UNKNOWN")
            coverage_state = diagnostic.get("coverage_state", "UNKNOWN")
            recommended_action = diagnostic.get("recommended_action", "NO_ACTION")

            if verbose:
                print(f"    Verdict: {verdict}")
                print(f"    Scenario: {scenario}")
                print(f"    Coverage: {coverage_state}")

            # Filtrer les scenarios à inclure
            if scenario in include_scenarios:
                issues.append({
                    "blog_id": blog_id_clean,
                    "url": url,
                    "scenario": scenario,
                    "verdict": verdict,
                    "coverage_state": coverage_state,
                    "recommended_action": recommended_action
                })

                print(f"    ⚠️  Issue detected: {scenario}")

            # Rate limiting
            if i < len(urls_to_process):
                time.sleep(delay)

        except Exception as e:
            error_str = str(e)

            # Détecter quota exceeded
            if "quota" in error_str.lower() or "limit" in error_str.lower():
                print(f"\n  ⚠️  GSC API quota exceeded at URL {i}/{len(urls_to_process)}")
                print(f"  Stopping diagnostic. {len(issues)} issues found so far.")
                break

            print(f"    ❌ Error diagnosing URL: {e}")

            if verbose:
                import traceback
                traceback.print_exc()

    print(f"\n  ✅ Diagnostic complete: {len(issues)} issues found")

    # Statistiques par scenario
    if issues:
        scenario_counts = {}
        for issue in issues:
            scenario = issue["scenario"]
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

        print(f"\n  📊 Issues by scenario:")
        for scenario, count in scenario_counts.items():
            print(f"    - {scenario}: {count}")

    return issues


# =========================================================================
# PHASE 3: Insertion dans Spreadsheet
# =========================================================================

def insert_or_update_in_spreadsheet(
    spreadsheet_id: str,
    issues: List[Dict],
    update_only: bool = False,
    dry_run: bool = False,
    verbose: bool = False
) -> Dict:
    """
    Insère ou met à jour les URLs à problème dans le spreadsheet Refreshs_Audit.

    Args:
        spreadsheet_id: ID du Google Spreadsheet
        issues: Liste de dicts avec URLs à problème
        update_only: Si True, seulement mettre à jour URLs existantes
        dry_run: Si True, simuler sans écrire
        verbose: Mode verbose

    Returns:
        Dict avec statistiques:
        {
            "total_issues": int,
            "updated": int,
            "inserted": int,
            "skipped": int
        }
    """
    if verbose:
        print(f"\n[Phase 3] Inserting/updating {len(issues)} issues in spreadsheet...")
        if dry_run:
            print(f"  🔍 DRY-RUN MODE: No actual writes will be performed")
        if update_only:
            print(f"  📝 UPDATE-ONLY MODE: Only existing URLs will be updated")

    # Initialiser SheetsClient
    sheets = SheetsClient(spreadsheet_id)

    stats = {
        "total_issues": len(issues),
        "updated": 0,
        "inserted": 0,
        "skipped": 0
    }

    for i, issue in enumerate(issues, 1):
        url = issue["url"]
        blog_id = issue["blog_id"]
        scenario = issue["scenario"]

        if verbose:
            print(f"\n  [{i}/{len(issues)}] {url}")

        try:
            # Vérifier si URL existe déjà dans Refreshs_Audit
            row_index = sheets._find_url_row(url, "Refreshs_Audit")

            if row_index is not None:
                # URL existe → UPDATE colonne X (index_diagnostic)
                if verbose:
                    print(f"    ✏️  URL exists at row {row_index} → UPDATE column X")

                if not dry_run:
                    sheets._update_cell("Refreshs_Audit", f"X{row_index}", scenario)

                stats["updated"] += 1

            else:
                # URL n'existe pas
                if update_only:
                    if verbose:
                        print(f"    ⏭️  URL not found, skipping (update-only mode)")
                    stats["skipped"] += 1
                    continue

                # INSERT nouvelle ligne
                if verbose:
                    print(f"    ➕ URL not found → INSERT new row")

                # Créer nouvelle ligne avec structure complète (28 colonnes A-AB, post-suppression cocon_branch)
                row = [
                    blog_id,                    # A - blog_id
                    url,                        # B - blogpost_url
                    "",                         # C - main_keyword (vide)
                    "",                         # D - title (vide, sera scrapé par workflow)
                    "STANDALONE",               # E - post_type
                    "",                         # F - action_blogpost (vide, décision à venir)
                    "",                         # G - status
                    "",                         # H - audit_gsc (vide → sera traité par batch audit-gsc)
                    "",                         # I - audit_serp (vide)
                    0,                          # J - impressions_30d
                    0,                          # K - clicks_30d
                    0.0,                        # L - ctr_30d
                    "",                         # M - people_also_ask
                    "",                         # N - secondary_keywords
                    "",                         # O - new_h1_title
                    "",                         # P - new_h2_titles
                    0,                          # Q - word_count_before
                    0,                          # R - images_count
                    0,                          # S - internal_links_count
                    "NO",                       # T - cannibalization_flag
                    "",                         # U - cannibalization_urls
                    "",                         # V - error_message
                    scenario,                   # W - index_diagnostic
                    "",                         # X - editorial_audit_score
                    "",                         # Y - editorial_audit_date
                    "",                         # Z - editorial_verdict
                    "",                         # AA - blocking_issues_count
                    ""                          # AB - editorial_audit_report_url
                ]

                if not dry_run:
                    sheets._append_row("Refreshs_Audit", row)

                stats["inserted"] += 1

        except Exception as e:
            print(f"    ❌ Error processing URL: {e}")
            stats["skipped"] += 1

            if verbose:
                import traceback
                traceback.print_exc()

    return stats


# =========================================================================
# PHASE 4: CLI et Orchestration
# =========================================================================

def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(
        description="Bulk Index Diagnostic Tool - Détecte les problèmes d'indexation GSC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Dry-run pour tester (10 URLs)
  python scripts/indexing/bulk_index_diagnostic.py \\
    --blog enseigna.fr \\
    --spreadsheet-id <SHEET_ID> \\
    --limit 10 \\
    --dry-run \\
    --verbose

  # Production (scan complet)
  python scripts/indexing/bulk_index_diagnostic.py \\
    --blog enseigna.fr \\
    --spreadsheet-id <SHEET_ID>

  # Update-only (URLs existantes seulement)
  python scripts/indexing/bulk_index_diagnostic.py \\
    --blog enseigna.fr \\
    --spreadsheet-id <SHEET_ID> \\
    --update-only
        """
    )

    # Arguments obligatoires
    parser.add_argument(
        "--blog",
        type=str,
        required=True,
        help="Blog unique à traiter (enseigna.fr, superprof.fr, etc.)"
    )
    parser.add_argument(
        "--spreadsheet-id",
        type=str,
        required=True,
        help="ID du Google Spreadsheet"
    )

    # Options
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limiter le nombre d'URLs à traiter (pour tests)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation sans écriture dans le spreadsheet"
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Seulement mettre à jour URLs existantes (pas de nouvelles lignes)"
    )
    parser.add_argument(
        "--include-scenarios",
        type=str,
        default="URL_NOT_ON_GOOGLE,DISCOVERED_NOT_INDEXED",
        help="Scenarios à inclure (séparés par virgule)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Délai entre appels GSC API (secondes, défaut: 1.0)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mode verbose avec logs détaillés"
    )

    args = parser.parse_args()

    # Parse include_scenarios
    include_scenarios = [s.strip() for s in args.include_scenarios.split(",")]

    # Header
    print("=" * 70)
    print("BULK INDEX DIAGNOSTIC TOOL")
    print("=" * 70)
    print(f"Blog: {args.blog}")
    print(f"Spreadsheet ID: {args.spreadsheet_id}")
    print(f"Include scenarios: {', '.join(include_scenarios)}")
    if args.limit:
        print(f"Limit: {args.limit} URLs")
    if args.dry_run:
        print(f"Mode: DRY-RUN (no writes)")
    if args.update_only:
        print(f"Mode: UPDATE-ONLY (existing URLs only)")
    print(f"Delay: {args.delay}s between GSC calls")
    print("=" * 70)

    start_time = datetime.now()

    # Phase 1: Récupérer URLs via sitemap
    urls = fetch_all_urls_for_blog(args.blog, verbose=args.verbose)

    if not urls:
        print("\n❌ No URLs found. Exiting.")
        return

    # Phase 2: Diagnostiquer indexation GSC
    issues = diagnose_indexation_issues(
        blog_id=args.blog,
        urls=urls,
        include_scenarios=include_scenarios,
        delay=args.delay,
        limit=args.limit,
        verbose=args.verbose
    )

    if not issues:
        print("\n✅ No indexation issues found. Nothing to do.")
        return

    # Phase 3: Insérer/mettre à jour dans spreadsheet
    stats = insert_or_update_in_spreadsheet(
        spreadsheet_id=args.spreadsheet_id,
        issues=issues,
        update_only=args.update_only,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Résumé final
    end_time = datetime.now()
    elapsed = end_time - start_time
    elapsed_str = f"{int(elapsed.total_seconds() // 60)}min {int(elapsed.total_seconds() % 60)}s"

    print("\n" + "=" * 70)
    print(f"RÉSUMÉ - {args.blog}")
    print("=" * 70)
    print(f"URLs scannées : {len(urls) if not args.limit else args.limit}")
    print(f"URLs avec problèmes : {len(issues)}")

    # Statistiques par scenario
    scenario_counts = {}
    for issue in issues:
        scenario = issue["scenario"]
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

    for scenario, count in scenario_counts.items():
        print(f"  - {scenario}: {count}")

    print(f"\nSpreadsheet :")
    print(f"  - Lignes mises à jour : {stats['updated']}")
    print(f"  - Lignes insérées : {stats['inserted']}")
    print(f"  - Lignes skippées : {stats['skipped']}")

    print(f"\nTemps d'exécution : {elapsed_str}")
    print("=" * 70)

    if args.dry_run:
        print("\n💡 Mode DRY-RUN: No actual writes performed. Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
