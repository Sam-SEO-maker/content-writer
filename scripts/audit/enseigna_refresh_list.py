"""Refresh list enseigna : pull GSC, filtre Avis / Versus, push 2 onglets."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

from scripts.audit.ahrefs_state import REPO_ROOT
from scripts.audit.gsc_state import fetch_gsc_keywords, _site_gsc_property
from scripts.sheets.sheets_client import SheetsClient

SPREADSHEET_ID = "1rNRU2WzlqfsAvFDjJHDN3ChCZ3u0NIfRaPoM4s1MzEM"

# Ordre EXACT des colonnes de l'onglet réel "Avis"/"Versus" (voir EnseignaAvisRow) :
#   A: url  B: top_keyword  C: priority  D: suggested_action  E: impressions_30d
#   F: clicks_30d  G: impressions_3m  H: clicks_3m  I: nb_kw  J: ctr  K: avg_position
#   L: snapshot_date  M: publish_date  N: refresh_date
# D (suggested_action), M (publish_date) et N (refresh_date) sont pilotées séparément
# (remplissage manuel / autre outil) et ne doivent JAMAIS être écrasées par un snapshot
# GSC — la fonction de merge ci-dessous met à jour uniquement B,C,E,F,G,H,I,J,K,L.
HEADERS = [
    "url", "top_keyword", "priority",
    "impressions_30d", "clicks_30d", "impressions_3m", "clicks_3m",
    "nb_kw", "ctr", "avg_position", "snapshot_date",
]


def _write_avis_versus_preserving_manual_cols(
    service, spreadsheet_id: str, title: str, gsc_rows: list[list]
) -> None:
    """
    Met à jour les colonnes GSC de "Avis"/"Versus" par URL (B,C,E-L), sans jamais
    toucher D (suggested_action), M (publish_date) ni N (refresh_date) — colonnes
    pilotées séparément (remplissage manuel / autre outil).

    Les URLs déjà présentes sont mises à jour en place (deux plages disjointes par
    ligne : B:C puis E:L, pour sauter D) ; les nouvelles URLs sont ajoutées en fin de
    feuille avec D/M/N vides.

    Args:
        gsc_rows: lignes au format [url, top_keyword, priority, impressions_30d,
                  clicks_30d, impressions_3m, clicks_3m, nb_kw, ctr, avg_position,
                  snapshot_date] (ordre HEADERS, 11 valeurs — PAS le format sheet 14 col)
    """
    existing = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{title}!A:N"
    ).execute().get("values", [])

    url_to_row_index = {
        row[0]: i for i, row in enumerate(existing[1:], start=2) if row
    }

    updates = []
    new_rows = []
    for gsc_row in gsc_rows:
        url, top_keyword, priority = gsc_row[0], gsc_row[1], gsc_row[2]
        tail = gsc_row[3:]  # impressions_30d ... snapshot_date (E:L, 8 valeurs)
        if url in url_to_row_index:
            row_index = url_to_row_index[url]
            updates.append({"range": f"{title}!B{row_index}:C{row_index}", "values": [[top_keyword, priority]]})
            updates.append({"range": f"{title}!E{row_index}:L{row_index}", "values": [tail]})
        else:
            # Nouvelle ligne : D (suggested_action) vide, M/N (publish_date/refresh_date) vides
            new_rows.append([url, top_keyword, priority, ""] + tail)

    if updates:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()

    if new_rows:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": new_rows},
        ).execute()


def _slug(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def _bucket(slug: str) -> str | None:
    if slug.startswith("superprof-vs-"):
        return "Versus"
    if "avis" in slug:
        return "Avis"
    return None


def _priority(impressions: int, clicks: int) -> str:
    if impressions >= 1000 or clicks >= 50:
        return "HIGH"
    if impressions >= 200 or clicks >= 10:
        return "MEDIUM"
    return "LOW"


def _aggregate_window(raw: list[dict]) -> dict[str, dict]:
    """Agrège les métriques GSC brutes par URL pour UNE fenêtre temporelle."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in raw:
        groups[r["url"]].append(r)

    out: dict[str, dict] = {}
    for url, items in groups.items():
        sum_clicks = sum(i["clicks"] for i in items)
        sum_impr = sum(i["impressions"] for i in items)
        weighted_pos = (
            sum(i["position"] * i["impressions"] for i in items) / sum_impr
            if sum_impr else 0
        )
        ctr = round((sum_clicks / sum_impr * 100), 2) if sum_impr else 0
        top = max(items, key=lambda x: x["impressions"])
        out[url] = {
            "clicks": sum_clicks,
            "impressions": sum_impr,
            "ctr": ctr,
            "avg_position": round(weighted_pos, 2),
            "nb_kw": len(items),
            "top_keyword": top["keyword"],
        }
    return out


def _aggregate(raw_30d: list[dict], raw_3m: list[dict], snapshot: str) -> dict[str, list[list]]:
    """
    Combine deux fenêtres GSC (30j + 3m) en lignes au format HEADERS
    (url, top_keyword, priority, impressions_30d, clicks_30d, impressions_3m,
    clicks_3m, nb_kw, ctr, avg_position, snapshot_date).
    """
    by_30d = _aggregate_window(raw_30d)
    by_3m = _aggregate_window(raw_3m)

    buckets: dict[str, list[list]] = {"Avis": [], "Versus": []}
    for url, m30 in by_30d.items():
        bucket = _bucket(_slug(url))
        if not bucket:
            continue
        m3m = by_3m.get(url, {})
        priority = _priority(m30["impressions"], m30["clicks"])
        buckets[bucket].append([
            url, m30["top_keyword"], priority,
            m30["impressions"], m30["clicks"],
            m3m.get("impressions", 0), m3m.get("clicks", 0),
            m30["nb_kw"], m30["ctr"], m30["avg_position"], snapshot,
        ])

    _prio_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    for b in buckets:
        buckets[b].sort(key=lambda row: (_prio_order[row[2]], -row[3]))
    return buckets


def _print_summary(buckets: dict[str, list[list]]) -> None:
    for name, rows in buckets.items():
        highs = [r for r in rows if r[2] == "HIGH"]
        meds = [r for r in rows if r[2] == "MEDIUM"]
        lows = [r for r in rows if r[2] == "LOW"]
        print(f"\n[{name}] total={len(rows)} | HIGH={len(highs)} MEDIUM={len(meds)} LOW={len(lows)}")
        print(f"  Top 5 by priority:")
        for r in rows[:5]:
            print(f"    [{r[2]}] impr_30d={r[3]} clicks_30d={r[4]} pos={r[9]} — {r[0]}")


def run(months: int = 6, dry_run: bool = False) -> dict:
    gsc_property = _site_gsc_property("enseigna")
    print(f"[enseigna-refresh-list] pull GSC 30j ({gsc_property})")
    raw_30d = fetch_gsc_keywords(gsc_property, months=1)
    print(f"[enseigna-refresh-list] pull GSC {months}m ({gsc_property})")
    raw_3m = fetch_gsc_keywords(gsc_property, months=months)
    print(f"[enseigna-refresh-list] {len(raw_30d)} rows 30j, {len(raw_3m)} rows {months}m")

    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    buckets = _aggregate(raw_30d, raw_3m, snapshot)
    _print_summary(buckets)

    if dry_run:
        from _shared.core.tenant_paths import TenantPaths
        out_dir = TenantPaths(base_path=REPO_ROOT).output_dir("enseigna") / "audit"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"refresh_list_{snapshot}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot_date": snapshot, "buckets": buckets}, f, ensure_ascii=False, indent=2)
        print(f"\n[enseigna-refresh-list] DRY-RUN dump: {out_path}")
        return {"avis": len(buckets["Avis"]), "versus": len(buckets["Versus"]), "output_path": str(out_path)}

    print(f"\n[enseigna-refresh-list] push → {SPREADSHEET_ID}")
    sheets = SheetsClient(SPREADSHEET_ID)
    if not sheets._sheets_service:
        raise RuntimeError("SheetsClient: API directe indisponible")
    svc = sheets._sheets_service
    _write_avis_versus_preserving_manual_cols(svc, SPREADSHEET_ID, "Avis", buckets["Avis"])
    _write_avis_versus_preserving_manual_cols(svc, SPREADSHEET_ID, "Versus", buckets["Versus"])
    print("[enseigna-refresh-list] ✓ 2 onglets mis à jour (colonnes K-N préservées)")

    return {
        "avis": len(buckets["Avis"]),
        "versus": len(buckets["Versus"]),
        "spreadsheet_id": SPREADSHEET_ID,
    }
