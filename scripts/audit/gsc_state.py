"""
État des lieux SEO via GSC API → Google Sheets.

Pull tous les KW positionnés (top N par défaut) sur les 3 derniers mois,
catégorise via les règles ahrefs_state.json (slug-based), agrège, et push
3 onglets `GSC_*` dans la même Sheet dédiée que l'état Ahrefs.

Usage:
    python content_writer.py audit gsc-state --site superprof-ressources
    python content_writer.py audit gsc-state --site enseigna --top-pos 20 --months 6
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from scripts.audit.ahrefs_state import (
    REPO_ROOT,
    CONFIG_PATH,
    aggregate_by_category,
    aggregate_by_page,
    categorize,
    _ensure_tab,
    _write_tab,
)
from scripts.audit.gsc_analyzer import GSCAnalyzer  # auth service account réutilisée
from scripts.sheets.sheets_client import SheetsClient

GSC_RAW_HEADERS = [
    "keyword", "url", "position", "clicks", "impressions", "ctr",
    "category", "subcategory", "snapshot_date",
]
GSC_BY_CAT_HEADERS = [
    "category", "nb_kw", "nb_kw_top10", "nb_kw_top3",
    "sum_clicks", "sum_impressions", "avg_position", "avg_ctr", "top_5_kw",
]
GSC_BY_PAGE_HEADERS = [
    "url", "category", "nb_kw", "nb_kw_top10",
    "sum_clicks", "sum_impressions", "avg_position", "avg_ctr",
    "top_kw", "top_kw_position",
]

SHEET_GSC_RAW = "GSC_KW_Raw"
SHEET_GSC_BY_CAT = "GSC_By_Category"
SHEET_GSC_BY_PAGE = "GSC_By_Page"

GSC_PAGE_SIZE = 25000  # max API


def _site_gsc_property(site_id: str) -> str:
    """Charge la gsc_property depuis sites.json."""
    sites_path = REPO_ROOT / "_shared" / "config" / "sites.json"
    with open(sites_path, encoding="utf-8") as f:
        data = json.load(f)
    for s in data.get("sites", []):
        if s.get("id") == site_id:
            prop = s.get("gsc_property")
            if not prop:
                raise ValueError(f"gsc_property manquante pour {site_id}")
            return prop
    raise ValueError(f"site_id inconnu dans sites.json: {site_id}")


def fetch_gsc_keywords(
    gsc_property: str,
    months: int = 3,
) -> list[dict]:
    """
    Pull paginé de tous les couples (query, page) sur la période.

    Returns liste de dicts: {keyword, url, position, clicks, impressions, ctr}
    """
    analyzer = GSCAnalyzer(gsc_property)
    if not analyzer._gsc_service:
        raise RuntimeError("GSC API indisponible (service account ?)")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=months * 30)

    rows: list[dict] = []
    start_row = 0
    while True:
        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query", "page"],
            "rowLimit": GSC_PAGE_SIZE,
            "startRow": start_row,
            "dataState": "final",
        }
        resp = analyzer._gsc_service.searchanalytics().query(
            siteUrl=gsc_property, body=body
        ).execute()
        batch = resp.get("rows", [])
        if not batch:
            break
        for r in batch:
            keys = r.get("keys", ["", ""])
            rows.append({
                "keyword": keys[0],
                "url": keys[1],
                "position": round(r.get("position", 0), 2),
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": round(r.get("ctr", 0) * 100, 2),
            })
        print(f"[gsc-state]   page startRow={start_row} → +{len(batch)} (total {len(rows)})")
        if len(batch) < GSC_PAGE_SIZE:
            break
        start_row += GSC_PAGE_SIZE

    return rows


def aggregate_by_category_gsc(rows: list[dict]) -> list[list]:
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["category"]].append(r)
    out = []
    for cat, items in sorted(groups.items(), key=lambda kv: -sum(i["clicks"] for i in kv[1])):
        nb = len(items)
        nb_top10 = sum(1 for i in items if 0 < i["position"] <= 10)
        nb_top3 = sum(1 for i in items if 0 < i["position"] <= 3)
        sum_clicks = sum(i["clicks"] for i in items)
        sum_impr = sum(i["impressions"] for i in items)
        positions = [i["position"] for i in items if i["position"] > 0]
        avg_pos = round(sum(positions) / len(positions), 2) if positions else 0
        avg_ctr = round((sum_clicks / sum_impr * 100), 2) if sum_impr else 0
        top5 = sorted(items, key=lambda x: -x["clicks"])[:5]
        top5_str = " | ".join(f"{i['keyword']} (#{i['position']})" for i in top5)
        out.append([cat, nb, nb_top10, nb_top3, sum_clicks, sum_impr, avg_pos, avg_ctr, top5_str])
    return out


def aggregate_by_page_gsc(rows: list[dict]) -> list[list]:
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["url"]].append(r)
    out = []
    for url, items in sorted(groups.items(), key=lambda kv: -sum(i["clicks"] for i in kv[1])):
        nb = len(items)
        nb_top10 = sum(1 for i in items if 0 < i["position"] <= 10)
        sum_clicks = sum(i["clicks"] for i in items)
        sum_impr = sum(i["impressions"] for i in items)
        positions = [i["position"] for i in items if i["position"] > 0]
        avg_pos = round(sum(positions) / len(positions), 2) if positions else 0
        avg_ctr = round((sum_clicks / sum_impr * 100), 2) if sum_impr else 0
        top = max(items, key=lambda x: x["clicks"])
        cat = items[0]["category"]
        out.append([url, cat, nb, nb_top10, sum_clicks, sum_impr, avg_pos, avg_ctr, top["keyword"], top["position"]])
    return out


def run_gsc_state(
    site_id: str,
    months: int = 3,
    top_pos: int = 30,
    min_impressions: int = 0,
    dry_run: bool = False,
) -> dict:
    """Pull GSC + catégorise + push 3 onglets GSC_* dans la Sheet dédiée."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    site_cfg = config["sites"].get(site_id)
    if not site_cfg:
        raise ValueError(f"site_id inconnu dans ahrefs_state.json: {site_id}")

    spreadsheet_id = site_cfg["spreadsheet_id"]
    cat_cfg = site_cfg["categorization"]
    gsc_property = _site_gsc_property(site_id)

    print(f"[gsc-state] {site_id}: pull GSC ({gsc_property}, {months}m, top {top_pos})")
    raw = fetch_gsc_keywords(gsc_property, months=months)
    print(f"[gsc-state] {len(raw)} rows brutes")

    # Filtre top N + impressions min
    filtered = [
        r for r in raw
        if 0 < r["position"] <= top_pos and r["impressions"] >= min_impressions
    ]
    print(f"[gsc-state] {len(filtered)} rows après filtre (pos<={top_pos}, impr>={min_impressions})")

    if not filtered:
        return {"nb_kw": 0, "nb_categories": 0, "nb_pages": 0}

    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    for r in filtered:
        cat, sub = categorize(r["url"], cat_cfg)
        rows.append({**r, "category": cat, "subcategory": sub, "snapshot_date": snapshot})

    by_cat = aggregate_by_category_gsc(rows)
    by_page = aggregate_by_page_gsc(rows)
    print(f"[gsc-state] {len(by_cat)} catégories, {len(by_page)} pages")

    raw_values = [
        [r["keyword"], r["url"], r["position"], r["clicks"], r["impressions"], r["ctr"],
         r["category"], r["subcategory"], r["snapshot_date"]]
        for r in rows
    ]

    from _shared.core.tenant_paths import TenantPaths
    out_dir = TenantPaths(base_path=REPO_ROOT).output_dir(site_id) / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gsc_state_{snapshot}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "site_id": site_id,
            "snapshot_date": snapshot,
            "months": months,
            "top_pos": top_pos,
            "nb_kw": len(rows),
            "nb_categories": len(by_cat),
            "nb_pages": len(by_page),
            "rows": rows,
        }, f, ensure_ascii=False, indent=2)
    print(f"[gsc-state] dump local: {out_path}")

    if dry_run:
        print("[gsc-state] DRY-RUN — pas de push Sheets")
        return {"nb_kw": len(rows), "nb_categories": len(by_cat), "nb_pages": len(by_page), "output_path": str(out_path)}

    print(f"[gsc-state] push → spreadsheet {spreadsheet_id}")
    sheets = SheetsClient(spreadsheet_id)
    if not sheets._sheets_service:
        raise RuntimeError("SheetsClient: API directe indisponible")
    svc = sheets._sheets_service

    _write_tab(svc, spreadsheet_id, SHEET_GSC_RAW, GSC_RAW_HEADERS, raw_values)
    _write_tab(svc, spreadsheet_id, SHEET_GSC_BY_CAT, GSC_BY_CAT_HEADERS, by_cat)
    _write_tab(svc, spreadsheet_id, SHEET_GSC_BY_PAGE, GSC_BY_PAGE_HEADERS, by_page)
    print(f"[gsc-state] ✓ 3 onglets GSC_* mis à jour")

    return {
        "nb_kw": len(rows),
        "nb_categories": len(by_cat),
        "nb_pages": len(by_page),
        "output_path": str(out_path),
        "spreadsheet_id": spreadsheet_id,
    }
