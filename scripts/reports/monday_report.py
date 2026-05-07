#!/usr/bin/env python3
"""
Monday Indexation & Performance Report

Rapport hebdomadaire multi-tenant :
- Recupere toutes les pages via GSC Performance API (1 appel bulk/blog)
- Compare avec sitemap pour detecter les URLs sans impressions
- URL Inspection API seulement sur les URLs suspectes (~10-30 au lieu de ~400)
- Met a jour le spreadsheet avec dedup intelligente

Usage:
    cw report monday-indexation
    cw report monday-indexation --blog enseigna --dry-run
"""

import sys
import io
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

def _ensure_utf8_stdout():
    """Force UTF-8 encoding for console output (Windows compatibility)."""
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.indexing.bulk_index_diagnostic import fetch_all_urls_for_blog
from scripts.audit.gsc_analyzer import GSCAnalyzer
from scripts.sheets.sheets_client import SheetsClient
from _shared.config.sites import ACTIVE_SITES, SITE_CONFIGS

# Statuses considered as "republished" (refresh done)
REPUBLISHED_STATUSES = {"termine", "DONE", "CONTENT DONE"}

# Default scenarios to detect
DEFAULT_SCENARIOS = [
    "URL_NOT_ON_GOOGLE",
    "DISCOVERED_NOT_INDEXED",
    "INDEXING_ISSUE",
    "URL_404",
    "URL_REDIRECTED",
]


class MondayIndexationReport:
    """
    Rapport d'indexation hebdomadaire multi-tenant.

    Approche optimisee :
    1. GSC Performance API bulk (1 appel/blog) pour lister les pages actives
    2. Sitemap pour lister toutes les URLs
    3. URLs sitemap absentes de GSC Performance = suspectes
    4. URL Inspection API seulement sur les suspectes
    """

    def __init__(self, spreadsheet_id: str, dry_run: bool = False, verbose: bool = False):
        self.spreadsheet_id = spreadsheet_id
        self.dry_run = dry_run
        self.verbose = verbose
        self.sheets = SheetsClient(spreadsheet_id)

    def run_all_blogs(
        self,
        blog_ids: Optional[List[str]] = None,
        delay: float = 1.5,
        limit: Optional[int] = None,
        include_scenarios: Optional[List[str]] = None,
    ) -> dict:
        _ensure_utf8_stdout()
        start_time = datetime.now()
        blogs_to_scan = blog_ids or ACTIVE_SITES
        scenarios = include_scenarios or DEFAULT_SCENARIOS

        print("=" * 70)
        print(f"MONDAY INDEXATION REPORT - {start_time.strftime('%Y-%m-%d')}")
        print("=" * 70)
        if self.dry_run:
            print("  MODE DRY-RUN : aucune ecriture spreadsheet")
        print(f"  Blogs: {', '.join(blogs_to_scan)}")
        print(f"  Scenarios: {', '.join(scenarios)}")
        if limit:
            print(f"  Limit: {limit} URLs/blog")
        print("=" * 70)

        url_map = self._load_spreadsheet_url_map()
        print(f"\n  Spreadsheet: {len(url_map)} URLs existantes chargees")

        blog_results = {}
        for blog_id in blogs_to_scan:
            if blog_id not in SITE_CONFIGS:
                print(f"\n  [SKIP] Blog inconnu: {blog_id}")
                continue

            result = self._scan_blog(
                blog_id=blog_id,
                delay=delay,
                limit=limit,
                include_scenarios=scenarios,
                url_map=url_map,
            )
            blog_results[blog_id] = result

        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()

        report = self._build_report(blog_results, start_time, elapsed)
        self._print_report(report)

        return report

    def _scan_blog(
        self,
        blog_id: str,
        delay: float,
        limit: Optional[int],
        include_scenarios: List[str],
        url_map: Dict[str, Tuple[int, str]],
    ) -> dict:
        """
        Scan optimise : GSC Performance bulk → sitemap diff → URL Inspection sur suspectes.
        """
        config = SITE_CONFIGS[blog_id]
        domain = config.get("domain", blog_id)
        gsc_property = config.get("gsc_property")

        print(f"\n{'=' * 50}")
        print(f"  {blog_id.upper()} ({domain})")
        print(f"{'=' * 50}")

        result = {
            "domain": domain,
            "urls_scanned": 0,
            "indexed": 0,
            "issues": [],
            "stats": {"inserted": 0, "updated": 0, "already_tracked": 0, "re_deindexed": 0},
            "error": None,
        }

        if not gsc_property:
            print(f"  Pas de gsc_property configure, skip")
            result["error"] = "No gsc_property"
            return result

        # Phase 1: GSC Performance bulk (1 appel = toutes les pages actives)
        try:
            analyzer = GSCAnalyzer(gsc_property)
        except Exception as e:
            print(f"  Erreur init GSC: {e}")
            result["error"] = str(e)
            return result

        print(f"  Phase 1: GSC Performance bulk...")
        active_urls = self._fetch_all_active_urls(analyzer)
        print(f"    {len(active_urls)} URLs avec impressions (90j)")

        # Phase 2: Sitemap (toutes les URLs du blog)
        print(f"  Phase 2: Sitemap fetch...")
        try:
            sitemap_urls = fetch_all_urls_for_blog(blog_id, verbose=self.verbose)
        except Exception as e:
            print(f"    Erreur sitemap: {e}")
            sitemap_urls = []

        if sitemap_urls:
            print(f"    {len(sitemap_urls)} URLs dans le sitemap")
        else:
            print(f"    Sitemap vide/erreur, fallback sur spreadsheet URLs")
            sitemap_urls = [url for url, (_, _) in url_map.items() if blog_id in url or domain in url]
            print(f"    {len(sitemap_urls)} URLs recuperees du spreadsheet")

        all_urls = set(sitemap_urls)
        result["urls_scanned"] = len(all_urls)

        # Phase 3: Detecter les suspectes (dans sitemap mais PAS dans GSC Performance)
        suspect_urls = all_urls - active_urls
        indexed_count = len(all_urls) - len(suspect_urls)
        result["indexed"] = indexed_count

        print(f"  Phase 3: {len(suspect_urls)} URLs suspectes (pas d'impressions)")

        if not suspect_urls:
            print(f"  Aucune URL suspecte detectee")
            return result

        # Phase 4: URL Inspection seulement sur les suspectes
        suspects_list = sorted(suspect_urls)
        if limit:
            suspects_list = suspects_list[:limit]

        print(f"  Phase 4: URL Inspection sur {len(suspects_list)} URLs suspectes...")
        issues = self._inspect_suspect_urls(
            analyzer=analyzer,
            urls=suspects_list,
            blog_id=blog_id,
            include_scenarios=include_scenarios,
            delay=delay,
        )

        if not issues:
            print(f"  Aucun probleme d'indexation confirme")
            return result

        # Phase 5: Smart upsert into spreadsheet
        upsert_stats = self._smart_upsert(issues, url_map)
        result["stats"] = upsert_stats
        result["issues"] = issues

        return result

    def _fetch_all_active_urls(self, analyzer: GSCAnalyzer) -> Set[str]:
        """
        1 appel GSC Performance API (dimension=page, 90j) pour toutes les URLs actives.
        """
        today = datetime.now()
        start_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        active_urls: Set[str] = set()

        try:
            # Paginate through all results (25000 max per call)
            start_row = 0
            page_size = 25000

            while True:
                request_body = {
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": ["page"],
                    "rowLimit": page_size,
                    "startRow": start_row,
                }

                response = analyzer._gsc_service.searchanalytics().query(
                    siteUrl=analyzer.gsc_property,
                    body=request_body
                ).execute()

                rows = response.get("rows", [])
                if not rows:
                    break

                for row in rows:
                    url = row["keys"][0]
                    active_urls.add(url)

                if len(rows) < page_size:
                    break
                start_row += page_size

        except Exception as e:
            print(f"    Erreur GSC Performance bulk: {e}")

        return active_urls

    def _inspect_suspect_urls(
        self,
        analyzer: GSCAnalyzer,
        urls: List[str],
        blog_id: str,
        include_scenarios: List[str],
        delay: float,
    ) -> List[Dict]:
        """URL Inspection API sur les URLs suspectes uniquement."""
        blog_id_clean = blog_id.replace(".fr", "").replace(".com", "")
        issues = []

        for i, url in enumerate(urls, 1):
            try:
                diagnostic = analyzer._check_indexation_detailed(url)
                scenario = diagnostic.get("scenario", "UNKNOWN")

                if scenario in include_scenarios:
                    issues.append({
                        "blog_id": blog_id_clean,
                        "url": url,
                        "scenario": scenario,
                        "verdict": diagnostic.get("verdict", "UNKNOWN"),
                        "coverage_state": diagnostic.get("coverage_state", "UNKNOWN"),
                        "recommended_action": diagnostic.get("recommended_action", "NO_ACTION"),
                        "performance": {"clicks_30d": 0, "impressions_30d": 0, "ctr_30d": 0, "position_avg": 0},
                    })
                    print(f"    [{i}/{len(urls)}] {scenario}: {url}")

                if i < len(urls):
                    time.sleep(delay)

            except Exception as e:
                error_str = str(e)
                if "quota" in error_str.lower() or "limit" in error_str.lower():
                    print(f"    GSC API quota exceeded at {i}/{len(urls)}, stopping")
                    break
                if self.verbose:
                    print(f"    Erreur inspection {url}: {e}")

        print(f"    {len(issues)} problemes confirmes")
        return issues

    def _load_spreadsheet_url_map(self) -> Dict[str, Tuple[int, str]]:
        try:
            data = self.sheets._read_sheet("Refreshs_Audit")
        except Exception as e:
            print(f"  Erreur lecture spreadsheet: {e}")
            return {}

        url_map = {}
        for i, row in enumerate(data[1:], start=2):
            if row and len(row) > 2:
                url = row[2]  # Column C = blogpost_url
                status = row[7] if len(row) > 7 else ""  # Column H = status
                url_map[url] = (i, status)

        return url_map

    def _smart_upsert(
        self,
        issues: List[Dict],
        url_map: Dict[str, Tuple[int, str]],
    ) -> dict:
        stats = {"inserted": 0, "updated": 0, "already_tracked": 0, "re_deindexed": 0}
        today = datetime.now().strftime("%Y-%m-%d")

        for issue in issues:
            url = issue["url"]
            blog_id = issue["blog_id"]
            scenario = issue["scenario"]

            if url not in url_map:
                issue["action_taken"] = "INSERTED"
                stats["inserted"] += 1

                if not self.dry_run:
                    row = self._build_new_row(blog_id, url, scenario)
                    try:
                        self.sheets._append_row("Refreshs_Audit", row)
                    except Exception as e:
                        print(f"    Erreur insert {url}: {e}")
                        continue

                if self.verbose:
                    print(f"    [INSERT] {url} ({scenario})")

            else:
                row_index, status = url_map[url]

                if status in REPUBLISHED_STATUSES:
                    issue["action_taken"] = "RE_DEINDEXED"
                    stats["re_deindexed"] += 1

                    if not self.dry_run:
                        try:
                            self.sheets._batch_update_cells([
                                {"cell": f"X{row_index}", "value": scenario},
                                {"cell": f"W{row_index}", "value": f"Re-desindexee detectee {today}"},
                            ])
                        except Exception as e:
                            print(f"    Erreur update {url}: {e}")
                            continue

                    if self.verbose:
                        print(f"    [RE-DEINDEX] {url} (was {status}, now {scenario})")

                else:
                    issue["action_taken"] = "ALREADY_TRACKED"
                    stats["already_tracked"] += 1

                    if not self.dry_run:
                        try:
                            self.sheets._update_cell("Refreshs_Audit", f"X{row_index}", scenario)
                        except Exception as e:
                            print(f"    Erreur update {url}: {e}")
                            continue

                    if self.verbose:
                        print(f"    [TRACKED] {url} (status={status}, updated X={scenario})")

        print(f"  Spreadsheet: {stats['inserted']} inserted, "
              f"{stats['re_deindexed']} re-deindexed, "
              f"{stats['already_tracked']} already tracked")

        return stats

    def _build_new_row(self, blog_id: str, url: str, scenario: str) -> list:
        """Construit une nouvelle ligne 28 colonnes pour le spreadsheet (post-suppression cocon_branch)."""
        return [
            blog_id,        # A - blog_id
            url,            # B - blogpost_url
            "",             # C - main_keyword
            "",             # D - title
            "",             # E - post_type
            "",             # F - action_blogpost
            "",             # G - status
            "DONE",         # H - audit_gsc (already done)
            "",             # I - audit_serp
            0,              # J - impressions_30d
            0,              # K - clicks_30d
            0.0,            # L - ctr_30d
            "",             # M - people_also_ask
            "",             # N - secondary_keywords
            "",             # O - new_h1_title
            "",             # P - new_h2_titles
            0,              # Q - word_count_before
            0,              # R - images_count
            0,              # S - internal_links_count
            "NO",           # T - cannibalization_flag
            "",             # U - cannibalization_urls
            "",             # V - error_message
            scenario,       # W - index_diagnostic
            "",             # X - editorial_audit_score
            "",             # Y - editorial_audit_date
            "",             # Z - editorial_verdict
            "",             # AA - blocking_issues_count
            "",             # AB - editorial_audit_report_url
        ]

    def _build_report(self, blog_results: dict, start_time: datetime, elapsed: float) -> dict:
        aggregate = {
            "total_scanned": 0,
            "total_indexed": 0,
            "total_issues": 0,
            "inserted": 0,
            "re_deindexed": 0,
            "already_tracked": 0,
        }

        for blog_id, result in blog_results.items():
            aggregate["total_scanned"] += result["urls_scanned"]
            aggregate["total_indexed"] += result["indexed"]
            aggregate["total_issues"] += len(result["issues"])
            aggregate["inserted"] += result["stats"]["inserted"]
            aggregate["re_deindexed"] += result["stats"]["re_deindexed"]
            aggregate["already_tracked"] += result["stats"]["already_tracked"]

        blogs_json = {}
        for blog_id, result in blog_results.items():
            blogs_json[blog_id] = {
                "domain": result["domain"],
                "urls_scanned": result["urls_scanned"],
                "indexed": result["indexed"],
                "issues": [
                    {
                        "url": i["url"],
                        "scenario": i["scenario"],
                        "action_taken": i.get("action_taken", "UNKNOWN"),
                        "performance": i.get("performance", {}),
                    }
                    for i in result["issues"]
                ],
                "stats": result["stats"],
                "error": result["error"],
            }

        return {
            "report_date": start_time.isoformat(),
            "execution_time_seconds": round(elapsed, 1),
            "blogs": blogs_json,
            "aggregate": aggregate,
        }

    def _print_report(self, report: dict):
        print(f"\n{'=' * 70}")
        print(f"RESULTATS")
        print(f"{'=' * 70}")

        for blog_id, data in report["blogs"].items():
            print(f"\n  {blog_id.upper()} ({data['domain']})")
            print(f"    URLs scannees:  {data['urls_scanned']}")
            print(f"    Indexees:       {data['indexed']}")
            print(f"    Problemes:      {len(data['issues'])}")

            if data["error"]:
                print(f"    ERREUR:         {data['error']}")

            if data["issues"]:
                scenario_counts: Dict[str, int] = {}
                for issue in data["issues"]:
                    s = issue["scenario"]
                    scenario_counts[s] = scenario_counts.get(s, 0) + 1
                for s, c in scenario_counts.items():
                    print(f"      {s}: {c}")

            print(f"    Spreadsheet: {data['stats']['inserted']} new, "
                  f"{data['stats']['re_deindexed']} re-deindex, "
                  f"{data['stats']['already_tracked']} tracked")

        agg = report["aggregate"]
        print(f"\n{'=' * 70}")
        print(f"AGGREGATE")
        print(f"{'=' * 70}")
        print(f"  Blogs:       {len(report['blogs'])}")
        print(f"  Scanned:     {agg['total_scanned']}")
        print(f"  Indexed:     {agg['total_indexed']}")
        print(f"  Issues:      {agg['total_issues']} "
              f"({agg['inserted']} new, {agg['re_deindexed']} re-deindex, {agg['already_tracked']} tracked)")

        elapsed = report["execution_time_seconds"]
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        print(f"  Time:        {mins}min {secs}s")
        print(f"{'=' * 70}")

    def save_json_report(self, report: dict, output_dir: str = "outputs/reports") -> str:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"monday_report_{date_str}.json"
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n  Rapport sauvegarde: {filepath}")
        return str(filepath)
