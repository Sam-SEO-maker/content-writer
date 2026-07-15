"""
Script one-shot : redistribue les dates de publication SP Ressources
Onglet "New growing List" (gid=2023506053)
Règle : 10 lundi + 10 mardi par semaine, à compter de la ligne 19
        Ligne 18 intouchée (conserve mer. 03/06/2026)
"""

import os
import sys
from pathlib import Path

# Ajouter la racine du projet au path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from google.oauth2 import service_account
from googleapiclient.discovery import build

# spreadsheet_id / onglet lus depuis la config du tenant (§4bis-A), repli littéral.
from _shared.core.sheets_config import get_spreadsheet_id, get_primary_tab_name
_BLOG_ID = "superprof-ressources"
SPREADSHEET_ID = get_spreadsheet_id(_BLOG_ID, default="1Vutb06Fcm3awnANPbtLkI1EvhbE9d-TXrZRLTrmmLlQ")
SHEET_NAME = get_primary_tab_name(_BLOG_ID, default="New growing List")
SA_PATH = Path(os.environ.get("GOOGLE_SA_PATH", "~/.credentials/google/google-service-account.json")).expanduser()

# Colonne J (index 9, 0-based) = "Date de publication"
DATE_COL = "J"
FIRST_ROW = 19    # première ligne à modifier
LAST_ROW  = 163   # dernière ligne à modifier (145 articles)

# Génération du planning : 10 lun + 10 mar, semaines consécutives
# Première semaine : lun 08/06/2026 (première semaine disponible)
DAYS_FR = {0: "lun.", 1: "mar.", 2: "mer.", 3: "jeu.", 4: "ven.", 5: "sam.", 6: "dim."}

def build_schedule():
    """Retourne la liste des dates (format FR) pour les 145 articles (rows 19-163)."""
    from datetime import date, timedelta

    start = date(2026, 6, 8)  # lundi 08/06/2026
    dates = []
    current = start

    while len(dates) < (LAST_ROW - FIRST_ROW + 1):
        # Lundi : 10 articles
        day_label = DAYS_FR[current.weekday()]
        date_str = f"{day_label} {current.strftime('%d/%m/%Y')}"
        dates.extend([date_str] * 10)

        # Mardi : 10 articles
        tuesday = current + timedelta(days=1)
        day_label = DAYS_FR[tuesday.weekday()]
        date_str = f"{day_label} {tuesday.strftime('%d/%m/%Y')}"
        dates.extend([date_str] * 10)

        current += timedelta(weeks=1)  # semaine suivante

    return dates[:LAST_ROW - FIRST_ROW + 1]


def main():
    if not SA_PATH.exists():
        print(f"[ERREUR] Service account introuvable : {SA_PATH}")
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_file(
        str(SA_PATH),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=credentials)
    sheets = service.spreadsheets()

    schedule = build_schedule()
    print(f"[INFO] {len(schedule)} dates générées pour les rows {FIRST_ROW}-{LAST_ROW}")
    print(f"[INFO] Première date : {schedule[0]}  (row {FIRST_ROW})")
    print(f"[INFO] Dernière date : {schedule[-1]}  (row {LAST_ROW})")

    # Préparer le batch update
    data = []
    for i, date_str in enumerate(schedule):
        row = FIRST_ROW + i
        data.append({
            "range": f"'{SHEET_NAME}'!{DATE_COL}{row}",
            "values": [[date_str]]
        })

    body = {
        "valueInputOption": "USER_ENTERED",
        "data": data
    }

    result = sheets.values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body
    ).execute()

    updated = result.get("totalUpdatedCells", 0)
    print(f"[OK] {updated} cellules mises à jour")

    # Vérification spot-check des 3 premières et 3 dernières
    check = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!{DATE_COL}{FIRST_ROW}:{DATE_COL}{LAST_ROW}"
    ).execute()
    values = check.get("values", [])
    print(f"\n--- Vérification (premières lignes) ---")
    for j, v in enumerate(values[:6]):
        print(f"  Ligne {FIRST_ROW + j} → {v[0] if v else '(vide)'}")
    print("  ...")
    for j, v in enumerate(values[-3:]):
        row_n = LAST_ROW - 2 + j
        print(f"  Ligne {row_n} → {v[0] if v else '(vide)'}")


if __name__ == "__main__":
    main()
