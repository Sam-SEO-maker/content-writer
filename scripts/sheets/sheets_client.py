"""
Google Sheets Client Module

Client pour interagir avec Google Sheets API via MCP ou API directe.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

from _shared.core.models import (
    TaskStatus,
    TriggerType,
    URLTask,
    AuditResultRow,
    RefreshResultRow,
    RefreshAuditRow,
    EnseignaAvisRow,
)
from _shared.core.models.sheets_models import _safe_int, _safe_float
from _shared.core.constants import canonical_site_slug

# Google API (optionnel, pour mode direct)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# Chemin du service account (via .env ou fallback)
import os
SERVICE_ACCOUNT_PATH = Path(os.environ.get("GOOGLE_SA_PATH", "~/.credentials/google/google-service-account.json")).expanduser()


class SheetsClient:
    """
    Client Google Sheets pour le pilotage du workflow.

    Gère les interactions avec le spreadsheet de pilotage.

    Surface volontairement minimale (purge 2026-07-23 : toute l'API liée à
    l'onglet retiré "Refreshs_Audit" a été supprimée). Onglets réels :
      - Enseigna  → "Avis" / "Versus" (ENSEIGNA_TABS, read_pending_for_refresh_enseigna)
      - Superprof → "New Growing List" & co (lecture via _read_sheet ; statuts via
        scripts/sheets/tab_status.py, config-driven)
    """

    def __init__(self, spreadsheet_id: str, **kwargs):
        """
        Initialise le client Sheets.

        Args:
            spreadsheet_id: ID du Google Sheet
        """
        self.spreadsheet_id = spreadsheet_id
        self.auth_mode = kwargs.get("auth_mode", "service_account")
        self._sheets_service = None

        # Utiliser l'API directe (auth selon auth_mode : SA par défaut, oauth_user en option)
        if GOOGLE_API_AVAILABLE:
            self._init_direct_api()
            # NOTE: _ensure_audit_columns() désactivé (legacy Audit_Results sheet)
            # Architecture V2.0 utilise Refreshs_Audit avec structure fixe

    def _init_direct_api(self):
        """Initialise la connexion directe a l'API Google Sheets (auth selon auth_mode)."""
        try:
            from _shared.core.google_auth import get_credentials
            credentials = get_credentials(
                scopes=['https://www.googleapis.com/auth/spreadsheets'],
                auth_mode=self.auth_mode,
            )
            if credentials is None:
                self._sheets_service = None
                return
            self._sheets_service = build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            print(f"Direct API init error: {e}")
            self._sheets_service = None

    def _read_sheet(self, sheet_name: str) -> list[list[str]]:
        """Lit toutes les donnees d'une feuille."""
        # Mode API directe
        if self._sheets_service:
            try:
                result = self._sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=sheet_name
                ).execute()
                return result.get("values", [])
            except Exception as e:
                print(f"Error reading sheet {sheet_name}: {e}")
                return []

        return []

    def _batch_update_cells(self, updates: list[dict]) -> bool:
        """
        Met à jour plusieurs cellules en une seule requête API (batch update).

        Args:
            updates: Liste de dict {"sheet": str, "cell": str, "value": Any}
                    Exemple: [
                        {"sheet": "Refreshs_Audit", "cell": "H5", "value": "DONE"},
                        {"sheet": "Refreshs_Audit", "cell": "J5", "value": 1000},
                    ]

        Returns:
            True si succès, False sinon

        Note: Utilise batchUpdate pour éviter le quota API (60 writes/min)
        """
        if not self._sheets_service or not updates:
            return False

        try:
            # Préparer les données pour batchUpdate
            data = []
            for update in updates:
                sheet_name = update["sheet"]
                cell = update["cell"]
                value = update["value"]

                data.append({
                    "range": f"{sheet_name}!{cell}",
                    "values": [[value]]
                })

            # Exécuter le batch update
            body = {
                "valueInputOption": "USER_ENTERED",
                "data": data
            }

            result = self._sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()

            updated = result.get("totalUpdatedCells", 0)
            if updated < len(updates):
                cells_list = [u.get("cell", "?") for u in updates]
                print(f"[SHEETS] ⚠ Partial batch update: {updated}/{len(updates)} cells written. Cells: {cells_list}")
            return True

        except Exception as e:
            cells_list = [u.get("cell", "?") for u in updates]
            print(f"[SHEETS] ✗ ERROR batch update cells {cells_list}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def ENSEIGNA_TABS(self) -> list[str]:
        from _shared.core.sheets_config import get_tab_names
        names = [t for t in get_tab_names("enseigna.fr")
                 if t not in self._ENSEIGNA_DISCOVERY_TABS]
        return names or ["Avis", "Versus"]

    def read_pending_for_refresh_enseigna(
        self, action: str, tabs: Optional[list[str]] = None
    ) -> list["EnseignaAvisRow"]:
        """
        Lit les lignes des onglets Avis/Versus où suggested_action = action.

        Contrairement à l'architecture V2 (Refreshs_Audit), il n'y a pas de colonne
        status TODO/DONE : une ligne est considérée "à traiter" si suggested_action
        matche et si elle n'a pas déjà un refresh_date (colonne N) — le pipeline ne
        maintient aucun état persisté au-delà de cette date.

        Args:
            action: Action recherchée (ex: "FULL_REFRESH", "PARTIAL_REFRESH", "TITLE_OPTIMIZATION")
            tabs: Onglets à scanner (défaut: Avis + Versus)

        Returns:
            Liste de EnseignaAvisRow avec suggested_action = action et refresh_date vide
        """
        action_variants = {action, action.replace("_", " "), action.replace(" ", "_")}
        rows: list[EnseignaAvisRow] = []

        for tab in (tabs or self.ENSEIGNA_TABS):
            data = self._read_sheet(tab)
            if not data:
                continue
            action_col = EnseignaAvisRow.COLUMN_MAPS.get(
                tab, EnseignaAvisRow.COLUMN_MAPS["Avis"])["suggested_action"]
            for i, raw_row in enumerate(data[1:], start=2):
                if len(raw_row) <= action_col:
                    continue
                suggested_action = raw_row[action_col]
                if suggested_action not in action_variants:
                    continue
                audit_row = EnseignaAvisRow.from_list(raw_row, row_index=i, tab_name=tab)
                if audit_row.refresh_date:
                    continue  # déjà refreshé, pas de re-traitement automatique
                rows.append(audit_row)

        return rows

    def update_refresh_status_enseigna(
        self, url: str, refresh_date: str, new_h1_title: Optional[str] = None
    ) -> bool:
        """
        Marque une URL Avis/Versus comme refreshée (colonne N) via update ciblé
        (jamais de clear+rewrite — préserve toutes les autres colonnes).

        Args:
            url: URL de l'article (colonne A)
            refresh_date: Timestamp ISO à écrire en colonne N
            new_h1_title: Optionnel — pas de colonne dédiée sur Avis/Versus,
                          ignoré ici (le nouveau H1 vit dans le HTML généré,
                          pas dans le sheet, contrairement à l'architecture V2)

        Returns:
            True si la ligne a été trouvée et mise à jour
        """
        for tab in self.ENSEIGNA_TABS:
            row_index = self._find_url_row_col_a(url, tab)
            if row_index is None:
                continue
            # Colonne refresh_date propre à l'onglet (Avis: N ; Versus: Q — voir
            # EnseignaAvisRow.COLUMN_MAPS ; écrire N sur Versus écraserait impressions_3m).
            col_idx = EnseignaAvisRow.COLUMN_MAPS.get(
                tab, EnseignaAvisRow.COLUMN_MAPS["Avis"])["refresh_date"]
            col_letter = chr(ord("A") + col_idx)
            ok = self._batch_update_cells([
                {"sheet": tab, "cell": f"{col_letter}{row_index}", "value": refresh_date},
            ])
            if not ok:
                print(f"[SHEETS] ✗ update_refresh_status_enseigna: write failed for {url[:60]}")
            return ok

        print(f"[SHEETS] ✗ update_refresh_status_enseigna: URL introuvable dans Avis/Versus: {url[:80]}")
        return False

    def _find_url_row_col_a(self, url: str, sheet_name: str) -> Optional[int]:
        """
        Trouve l'index de ligne d'une URL en colonne A.

        Contrairement à `_find_url_row` (câblé pour l'architecture V2 où
        l'URL est en colonne B), les onglets Avis/Versus/A ajouter ont l'URL
        en colonne A.
        """
        data = self._read_sheet(sheet_name)
        for i, row in enumerate(data[1:], start=2):
            if row and len(row) > 0 and row[0] == url:
                return i
        return None

    # =========================================================================
    # Sheet Creation (pour initialisation)
    # =========================================================================
