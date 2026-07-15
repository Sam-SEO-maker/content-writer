"""
Superprof Ressources — Phase 1 GSC audit.

Pour chaque URL fournie :
1. Appelle GSC API (fenêtre 30j + 12 mois)
2. Récupère impressions / clicks / CTR / position + top 3 queries
3. Upsert dans l'onglet `GSC_Perfs` de la spreadsheet "Articles Ressources"
4. Dump JSON local dans `_shared/outputs/superprof-ressources/audit/`

Onglet `⬆️ Growing` :
- Lecture : URL (col A), main_keyword (col B), statuts (col F)
- Écriture : colonne F uniquement, via `write_growing_statuts`
  · "Rédigé"     — après génération du contenu refreshé
  · "Draft in WP" — après envoi via l'API WordPress (à implémenter)
  · "Publié"     — après publication effective
  · "A faire"    — valeur par défaut, URL non encore traitée
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from _shared.core.models.sheets_models import SuperprofAuditRow

# -----------------------------------------------------------------------------
# Constantes — single source of truth
# -----------------------------------------------------------------------------

# spreadsheet_id lu depuis la config du tenant (§4bis-A), repli littéral. Les
# onglets ci-dessous sont spécifiques à cet audit (hors bloc `sheets` autoritatif).
from _shared.core.sheets_config import get_spreadsheet_id
SPREADSHEET_ID = get_spreadsheet_id("superprof-ressources", default="1Vutb06Fcm3awnANPbtLkI1EvhbE9d-TXrZRLTrmmLlQ")
GROWING_SHEET = "⬆️ Growing"
GSC_PERFS_SHEET = "GSC_Perfs"

GSC_PROPERTY = "https://www.superprof.fr/ressources/"

# Chemin credentials (1 SA partagé Sheets + GSC)
SA_PATH = Path(
    os.environ.get(
        "GOOGLE_SA_PATH",
        "~/.credentials/google/google-service-account.json",
    )
).expanduser()

from _shared.core.tenant_paths import TenantPaths
OUTPUT_DIR = TenantPaths(base_path=Path(__file__).resolve().parents[2]).output_dir("superprof-ressources") / "audit"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


# -----------------------------------------------------------------------------
# Clients
# -----------------------------------------------------------------------------

def _build_clients():
    """Construit les clients Sheets + Search Console."""
    creds = service_account.Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)
    sheets = build("sheets", "v4", credentials=creds)
    gsc = build("searchconsole", "v1", credentials=creds)
    return sheets, gsc


# -----------------------------------------------------------------------------
# Sheet ops — Growing (read col A/B/F + write col F) + GSC_Perfs (read/write)
# -----------------------------------------------------------------------------

GROWING_STATUTS_COL = "F"  # Colonne du menu déroulant statuts dans Growing
STATUTS_VALUES = ("A faire", "Rédigé", "Draft in WP", "Publié")


def read_growing_bottom(sheets, n: int = 10) -> list[tuple[int, str, str, str]]:
    """
    Lit les `n` dernières URLs de l'onglet Growing.

    Returns:
        Liste de tuples (row_index, url, main_keyword, statuts)
        statuts vaut "A faire" si la colonne F est vide ou absente.
    """
    r = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{GROWING_SHEET}'!A1:F2000",
    ).execute()
    rows = r.get("values", [])

    indexed = [
        (
            i + 1,
            row[0],
            row[1] if len(row) > 1 else "",
            row[5] if len(row) > 5 and row[5] else "A faire",
        )
        for i, row in enumerate(rows)
        if row and row[0].startswith("http")
    ]
    return indexed[-n:]


def find_growing_row_by_url(sheets, url: str) -> Optional[int]:
    """Retourne le numéro de ligne 1-indexed de l'URL dans Growing, ou None."""
    r = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{GROWING_SHEET}'!A:A",
    ).execute()
    for i, row in enumerate(r.get("values", []), start=1):
        if row and row[0] == url:
            return i
    return None


def write_growing_statuts(sheets, row_index: int, statuts: str) -> None:
    """Écrit la valeur statuts en colonne F de l'onglet Growing."""
    sheets.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{GROWING_SHEET}'!{GROWING_STATUTS_COL}{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[statuts]]},
    ).execute()


def ensure_gsc_perfs_sheet(sheets) -> None:
    """Crée l'onglet GSC_Perfs s'il n'existe pas et (re)synchronise les en-têtes.

    Idempotent : si le tab existe déjà avec un schéma plus ancien (moins de
    colonnes), on met à jour la ligne 1 pour refléter le schéma actuel défini
    par `SuperprofAuditRow.gsc_perfs_headers()`. Les données existantes en
    col A-M sont préservées ; les nouvelles colonnes (ex: N/O timestamps)
    restent vides pour les lignes antérieures.
    """
    headers = SuperprofAuditRow.gsc_perfs_headers()
    col_count = len(headers)

    meta = sheets.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

    if GSC_PERFS_SHEET not in existing:
        print(f"[INFO] Creating sheet '{GSC_PERFS_SHEET}'...")
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": GSC_PERFS_SHEET,
                                "gridProperties": {"rowCount": 1000, "columnCount": col_count},
                            }
                        }
                    }
                ]
            },
        ).execute()
        sheets.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{GSC_PERFS_SHEET}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [headers]},
        ).execute()
        print(f"[INFO] Sheet '{GSC_PERFS_SHEET}' created with {col_count} headers.")
        return

    # Sheet exists — check if headers match and sync if not
    current = (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"'{GSC_PERFS_SHEET}'!1:1")
        .execute()
        .get("values", [[]])
    )
    current_row = current[0] if current else []
    if current_row != headers:
        sheets.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{GSC_PERFS_SHEET}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [headers]},
        ).execute()
        print(
            f"[INFO] Sheet '{GSC_PERFS_SHEET}' headers synced "
            f"({len(current_row)} → {col_count} cols)."
        )


def _col_letter(n: int) -> str:
    """Convert a 1-based column index to its spreadsheet letter (1→A, 27→AA)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def upsert_gsc_perfs(sheets, audit: SuperprofAuditRow) -> None:
    """
    Insère ou met à jour une ligne dans GSC_Perfs (clé = URL en col A).
    """
    # 1. Lire les URLs existantes en col A pour trouver la ligne
    r = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{GSC_PERFS_SHEET}'!A:A",
    ).execute()
    existing = r.get("values", [])
    target_row = None
    for i, row in enumerate(existing):
        if row and row[0] == audit.url:
            target_row = i + 1  # 1-indexed
            break

    payload = audit.to_gsc_perfs_row()
    last_col = _col_letter(len(payload))

    if target_row:
        # UPDATE
        sheets.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{GSC_PERFS_SHEET}'!A{target_row}:{last_col}{target_row}",
            valueInputOption="USER_ENTERED",
            body={"values": [payload]},
        ).execute()
    else:
        # APPEND
        sheets.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{GSC_PERFS_SHEET}'!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [payload]},
        ).execute()


# -----------------------------------------------------------------------------
# GSC API calls
# -----------------------------------------------------------------------------

def _date_range(days: int) -> tuple[str, str]:
    """Retourne (start_date, end_date) pour une fenêtre N jours.

    GSC a un délai de ~3 jours sur les données → end_date = today - 3.
    """
    end = datetime.now(timezone.utc).date() - timedelta(days=3)
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def fetch_url_metrics(gsc, url: str, days: int) -> dict:
    """
    Récupère impressions / clicks / CTR / position pour une URL sur une fenêtre.

    Returns:
        dict avec keys : impressions, clicks, ctr, position. Tout à 0 si NO_DATA.
    """
    start, end = _date_range(days)
    body = {
        "startDate": start,
        "endDate": end,
        "dimensionFilterGroups": [
            {
                "filters": [
                    {
                        "dimension": "page",
                        "operator": "equals",
                        "expression": url,
                    }
                ]
            }
        ],
        "rowLimit": 1,
    }
    try:
        r = gsc.searchanalytics().query(siteUrl=GSC_PROPERTY, body=body).execute()
    except HttpError as e:
        return {"impressions": 0, "clicks": 0, "ctr": 0.0, "position": 0.0, "error": str(e)[:200]}

    rows = r.get("rows", [])
    if not rows:
        return {"impressions": 0, "clicks": 0, "ctr": 0.0, "position": 0.0}

    row = rows[0]
    return {
        "impressions": int(row.get("impressions", 0)),
        "clicks": int(row.get("clicks", 0)),
        "ctr": float(row.get("ctr", 0.0)),
        "position": float(row.get("position", 0.0)),
    }


def fetch_top_queries(gsc, url: str, days: int = 30, limit: int = 3) -> list[str]:
    """Récupère le top N queries pour une URL sur une fenêtre."""
    start, end = _date_range(days)
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": ["query"],
        "dimensionFilterGroups": [
            {
                "filters": [
                    {
                        "dimension": "page",
                        "operator": "equals",
                        "expression": url,
                    }
                ]
            }
        ],
        "rowLimit": limit,
    }
    try:
        r = gsc.searchanalytics().query(siteUrl=GSC_PROPERTY, body=body).execute()
    except HttpError:
        return []
    return [row["keys"][0] for row in r.get("rows", [])]


# -----------------------------------------------------------------------------
# Pipeline
# -----------------------------------------------------------------------------

def slugify_url(url: str) -> str:
    """Transforme une URL en slug valide pour un nom de fichier."""
    slug = re.sub(r"^https?://(www\.)?", "", url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug)
    return slug.strip("_")[:120]


def audit_url(gsc, row_index: int, url: str, main_keyword: str) -> SuperprofAuditRow:
    """Audit GSC complet d'une URL → SuperprofAuditRow."""
    audit = SuperprofAuditRow(
        url=url,
        main_keyword=main_keyword,
        growing_row_index=row_index,
    )

    m30 = fetch_url_metrics(gsc, url, days=30)
    audit.impressions_30d = m30["impressions"]
    audit.clicks_30d = m30["clicks"]
    audit.ctr_30d = m30["ctr"]
    audit.position_30d = m30["position"]
    if "error" in m30:
        audit.error_message = m30["error"]

    m12m = fetch_url_metrics(gsc, url, days=365)
    audit.impressions_12m = m12m["impressions"]
    audit.clicks_12m = m12m["clicks"]
    audit.position_12m = m12m["position"]

    queries = fetch_top_queries(gsc, url, days=30, limit=3)
    if len(queries) >= 1:
        audit.top_query_1 = queries[0]
    if len(queries) >= 2:
        audit.top_query_2 = queries[1]
    if len(queries) >= 3:
        audit.top_query_3 = queries[2]

    has_data = audit.impressions_30d > 0 or audit.impressions_12m > 0
    audit.last_gsc_refresh = (
        datetime.now(timezone.utc).isoformat(timespec="seconds") if has_data else "NO_DATA"
    )
    return audit


def dump_json(audit: SuperprofAuditRow) -> Path:
    """Dump l'audit dans `outputs/superprof-ressources/audit/{slug}_audit.json`."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify_url(audit.url)
    path = OUTPUT_DIR / f"{slug}_audit.json"
    path.write_text(
        json.dumps(audit.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def run(n: int = 10) -> None:
    """Pipeline complet : lit n dernières URLs de Growing → audit GSC → upsert + dump."""
    sheets, gsc = _build_clients()

    print(f"[1/4] Reading bottom {n} URLs from '{GROWING_SHEET}'...")
    urls = read_growing_bottom(sheets, n=n)
    if not urls:
        print("[ERROR] No URLs found in Growing.")
        return
    print(f"      Got {len(urls)} URLs (rows {urls[0][0]} to {urls[-1][0]}).")

    print(f"[2/4] Ensuring sheet '{GSC_PERFS_SHEET}' exists...")
    ensure_gsc_perfs_sheet(sheets)

    print(f"[3/4] Auditing each URL via GSC API...")
    audits: list[SuperprofAuditRow] = []
    for i, (row_idx, url, kw, _statuts) in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] L{row_idx} : {url[:80]}")
        audit = audit_url(gsc, row_idx, url, kw)
        audits.append(audit)
        dump_json(audit)
        print(
            f"      30d: imp={audit.impressions_30d:>6} clicks={audit.clicks_30d:>4} "
            f"pos={audit.position_30d:.1f} | 12m: imp={audit.impressions_12m:>7} "
            f"clicks={audit.clicks_12m:>5} | {audit.last_gsc_refresh}"
        )

    print(f"[4/4] Upserting {len(audits)} rows into '{GSC_PERFS_SHEET}'...")
    for audit in audits:
        upsert_gsc_perfs(sheets, audit)

    print()
    print(f"[DONE] {len(audits)} URLs audited.")
    print(f"       Sheet  : https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    print(f"       Local  : {OUTPUT_DIR}")


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    run(n=n)
