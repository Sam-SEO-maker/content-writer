"""Benchmark runner — measures the automated refresh pipeline on a set of URLs.

Reads URLs from a source sheet/range, runs the mechanical portion of the pipeline
(fetch HTML + audit + decision + sheets writes + context prep) for each URL, and
records timing traces (console + JSON).

Scope: Phase 1 (mechanical pipeline). Phase 2 (actual LLM content generation) is
performed out-of-process by Claude Code operator and must be measured separately.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from _shared.core.models.sheets_models import RefreshAuditRow
from _shared.core.utils.timing import (
    BatchTimingReport,
    OperationTimer,
    TimingReport,
)

from .orchestrator import RefreshOrchestrator

logger = logging.getLogger("BenchmarkRunner")


def _parse_row_range(row_range: str) -> Tuple[int, int]:
    """Parse 'a:b' (1-indexed, inclusive) to (a, b)."""
    if ":" not in row_range:
        a = int(row_range)
        return a, a
    a, b = row_range.split(":", 1)
    return int(a), int(b)


def _url_to_slug(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_") or "url"


def read_urls_from_sheet(
    orchestrator: RefreshOrchestrator,
    source_sheet: str,
    row_range: str,
) -> List[Tuple[int, str, str]]:
    """Read URLs from the given sheet/row range.

    Assumes col A = URL and col B = main_keyword (standard GSC_Perfs schema).
    Returns list of (row_index_1_based, url, main_keyword).
    """
    if orchestrator.sheets_client is None:
        raise RuntimeError("SheetsClient not initialised on orchestrator")

    rows = orchestrator.sheets_client._read_sheet(source_sheet)
    if not rows:
        raise RuntimeError(
            f"Sheet '{source_sheet}' returned no data (empty or access denied)"
        )

    start, end = _parse_row_range(row_range)
    selected: List[Tuple[int, str, str]] = []
    for idx_1 in range(start, end + 1):
        row_idx_0 = idx_1 - 1
        if row_idx_0 >= len(rows):
            logger.warning("Row %d out of range (sheet has %d rows)", idx_1, len(rows))
            continue
        row = rows[row_idx_0]
        if not row:
            continue
        url = row[0].strip() if row else ""
        if not url.startswith("http"):
            logger.warning("Row %d: col A does not look like a URL (%r) — skipped", idx_1, url)
            continue
        main_keyword = row[1].strip() if len(row) > 1 else ""
        selected.append((idx_1, url, main_keyword))
    return selected


def run_benchmark(
    blog_id: str,
    source_sheet: str,
    row_range: str,
    spreadsheet_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> BatchTimingReport:
    """Execute the benchmark across URLs in the given sheet/row range.

    Returns the BatchTimingReport after dumping JSON traces to disk.
    """
    base_path = Path.cwd()

    # Resolve spreadsheet_id from blog config if not provided
    if not spreadsheet_id:
        from _shared.core.tenant_paths import TenantPaths
        config_path = TenantPaths(base_path=base_path).blog_config(blog_id)
        if not config_path.exists():
            raise FileNotFoundError(f"Blog config not found: {config_path}")
        blog_config = json.loads(config_path.read_text())
        spreadsheet_id = blog_config.get("sheets_config", {}).get("spreadsheet_id")
        if not spreadsheet_id:
            raise ValueError(f"No spreadsheet_id found in config for blog '{blog_id}'")

    orchestrator = RefreshOrchestrator(base_path=base_path, spreadsheet_id=spreadsheet_id)

    urls = read_urls_from_sheet(orchestrator, source_sheet, row_range)
    if not urls:
        raise RuntimeError("No URLs selected — check sheet name and row range")

    logger.info("Selected %d URL(s) from %s!%s", len(urls), source_sheet, row_range)

    report = BatchTimingReport(
        blog_id=blog_id,
        source_sheet=source_sheet,
        row_range=row_range,
    )
    report.start()

    if output_dir is None:
        output_dir = base_path / "_shared" / "outputs" / "benchmarks"
    per_url_dir = output_dir / "runs" / report.run_id
    per_url_dir.mkdir(parents=True, exist_ok=True)

    # Pre-build shared clients for GSC_Perfs upserts (superprof-ressources only)
    gsc_perfs_enabled = blog_id == "superprof-ressources"
    gsc_perfs_clients = None
    if gsc_perfs_enabled:
        try:
            from scripts.audit.superprof_gsc_audit import (
                _build_clients,
                audit_url,
                ensure_gsc_perfs_sheet,
                upsert_gsc_perfs,
            )
            sheets_api, gsc_api = _build_clients()
            ensure_gsc_perfs_sheet(sheets_api)
            gsc_perfs_clients = (sheets_api, gsc_api, audit_url, upsert_gsc_perfs)
        except Exception as build_err:  # noqa: BLE001
            logger.warning(
                "GSC_Perfs upsert disabled (client build failed): %s", build_err
            )
            gsc_perfs_clients = None

    for row_idx, url, main_keyword in urls:
        logger.info("[BENCHMARK] (%d) %s", row_idx, url)
        timer = OperationTimer(url=url, blog_id=blog_id, row_index=row_idx)

        # Captured process wall-clock — written to GSC_Perfs cols N/O
        process_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        process_ended_at = ""
        audit_row = None

        timer.start()
        try:
            extraction = orchestrator._fetch_html(url, blog_id)
            html = extraction.get("clean_body") or ""
            if not html:
                timer.success = False
                timer.errors.append("html_fetch_failed")
            else:
                result = orchestrator.process_url(
                    url=url,
                    blog_id=blog_id,
                    html_content=html,
                    timer=timer,
                )
                if not result.success:
                    timer.success = False
                    if result.errors:
                        timer.errors.extend(str(e)[:200] for e in result.errors[:3])

            # GSC fetch for GSC_Perfs sink (superprof-ressources only).
            # Upsert is deferred to after context delivery so we can stamp
            # process_ended_at in the same row.
            if gsc_perfs_clients is not None:
                sheets_api, gsc_api, audit_url_fn, upsert_fn = gsc_perfs_clients
                try:
                    with timer.measure("gsc_fetch"):
                        audit_row = audit_url_fn(gsc_api, row_idx, url, main_keyword)
                except Exception as gsc_err:  # noqa: BLE001
                    logger.warning("GSC audit failed for %s: %s", url, gsc_err)
                    timer.errors.append(f"gsc_audit: {str(gsc_err)[:150]}")
                    audit_row = None

            # Write the on-disk context bundle for Claude Code generation
            # (orchestrator.process_url only does in-memory prep; the file bundle
            # under _shared/context/{slug}/ is required for Phase-2 generation).
            if html:
                try:
                    minimal_row = RefreshAuditRow(
                        blog_id=blog_id,
                        blogpost_url=url,
                        main_keyword=main_keyword,
                        title="",
                        post_type="",
                    )
                    with timer.measure("context_write"):
                        ctx_dir = orchestrator._prepare_context_for_claude_code(
                            original_html=html,
                            action="FULL_REFRESH",
                            row=minimal_row,
                            extraction_result=extraction,
                            ytg_data=None,
                        )
                        logger.info("Context bundle written to %s", ctx_dir)
                except Exception as ctx_err:  # noqa: BLE001
                    logger.warning("Context write failed for %s: %s", url, ctx_err)
                    timer.errors.append(f"context_write: {str(ctx_err)[:150]}")
        except Exception as exc:  # noqa: BLE001 — benchmark should continue on per-URL failures
            logger.exception("Benchmark failed for %s", url)
            timer.success = False
            timer.errors.append(str(exc)[:200])
        finally:
            # Process is considered "delivered" once context bundle is on disk
            process_ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Final upsert with both timestamps + GSC metrics (single write
            # per URL → cols A:O in GSC_Perfs).
            if audit_row is not None and gsc_perfs_clients is not None:
                _, _, _, upsert_fn = gsc_perfs_clients
                sheets_api = gsc_perfs_clients[0]
                audit_row.process_started_at = process_started_at
                audit_row.process_ended_at = process_ended_at
                try:
                    with timer.measure("sheets_write"):
                        upsert_fn(sheets_api, audit_row)
                except Exception as upsert_err:  # noqa: BLE001
                    logger.warning("GSC_Perfs upsert failed for %s: %s", url, upsert_err)
                    timer.errors.append(f"gsc_perfs_upsert: {str(upsert_err)[:150]}")

            timer.stop()
            report.add(timer)
            TimingReport.dump(timer, per_url_dir / f"{_url_to_slug(url)[:80]}.json")

    report.stop()

    aggregate_path = output_dir / f"{report.run_id}_{blog_id}_benchmark.json"
    report.dump(aggregate_path)

    summary = report.render_console_summary()
    print("\n" + summary)
    print(f"\nTrace files:")
    print(f"  - {aggregate_path}")
    print(f"  - {per_url_dir}/ ({len(report.timers)} fichiers)")

    return report
