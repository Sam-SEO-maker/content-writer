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

    ⚠️ OBSOLÈTE : l'onglet "Refreshs_Audit" (et le modèle RefreshAuditRow associé)
    n'existe PLUS dans les Google Sheets réels — le lire provoque un HTTP 400.
    Onglets réels utilisés aujourd'hui :
      - Enseigna  → "Avis" / "Versus" (voir ENSEIGNA_TABS, read_pending_for_refresh_enseigna)
      - Superprof → "New Growing List" (voir scripts/agent/prepare_weekly_batch.py)
    Les méthodes read_pending_* ci-dessous qui pointent SHEET_REFRESHS_AUDIT sont
    de l'ancien système fork ; elles loguent désormais une erreur explicite au lieu
    de retourner silencieusement 0 ligne.
    """

    # Nom d'onglet LEGACY (obsolète — voir docstring de classe).
    SHEET_REFRESHS_AUDIT = "Refreshs_Audit"  # ⚠️ n'existe plus dans les Sheets réels
    SHEET_DECISION_LOG = "Decision_Log"      # Archive for traceability
    SHEET_REFRESH_RESULTS = "Refresh_Results"  # Archive for traceability

    # Legacy sheet names (for backwards compatibility during migration)
    SHEET_URLS_INPUT = "URLs_Input"
    SHEET_AUDIT_RESULTS = "Audit_Results"
    SHEET_ASSETS = "Assets_Inventory"

    # Structure des colonnes Refreshs_Audit (28 colonnes A-AB, post-suppression cocon_branch)
    COLS_REFRESHS_AUDIT = [
        "blog_id",                  # A
        "blogpost_url",             # B
        "main_keyword",             # C
        "title",                    # D
        "post_type",                # E
        "action_blogpost",          # F
        "status",                   # G
        "audit_gsc",                # H
        "audit_serp",               # I
        "impressions_30d",          # J
        "clicks_30d",               # K
        "ctr_30d",                  # L
        "people_also_ask",          # M
        "secondary_keywords",       # N
        "new_h1_title",             # O
        "new_h2_titles",            # P
        "word_count_before",        # Q
        "images_count",             # R
        "internal_links_count",     # S
        "cannibalization_flag",     # T
        "cannibalization_urls",     # U
        "error_message",            # V
        "index_diagnostic",         # W
        "editorial_audit_score",    # X (Phase 4: Editorial Audit)
        "editorial_audit_date",     # Y
        "editorial_verdict",        # Z
        "blocking_issues_count",    # AA
        "editorial_audit_report_url",  # AB
    ]

    # LEGACY: Structure des colonnes URLs_Input (kept for backwards compatibility)
    COLS_URLS_INPUT = [
        "blog_id", "url", "main_keyword", "title", "post_type", "status", "triggered_by",
        "processing_started", "processing_completed", "error_message", "notes",
        "child_url_1", "child_url_2", "child_url_3", "child_url_4", "child_url_5", "child_url_6"
    ]

    # LEGACY: Structure des colonnes Audit_Results
    COLS_AUDIT_RESULTS = [
        "to_do", "url", "overall_score", "impressions_30d", "clicks_30d",
        "ctr_30d", "avg_position", "main_keyword", "keyword_trend", "word_count",
        "images_count", "internal_links_count", "has_faq", "cannibalization_flag",
        "cannibalization_severity", "cannibalization_urls", "intent_shift_detected",
        "serp_format_expected", "alerts", "recommendations", "audit_date", "recommended_actions"
    ]

    # LEGACY: Structure des colonnes Refresh_Results
    COLS_REFRESH_RESULTS = [
        "url", "refresh_date", "rewrite_type", "new_title", "new_meta",
        "sections_modified", "word_count_before", "word_count_after",
        "images_before", "images_after", "links_before", "links_after",
        "validation_passed", "validation_errors", "content_preview",
        "full_content_link", "publish_queue", "published_date", "tokens_used"
    ]

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
            print(f"Erreur init API directe: {e}")
            self._sheets_service = None

    def _ensure_audit_columns(self):
        """
        Vérifie et ajoute les colonnes manquantes 'to_do' et 'recommended_actions'
        à la feuille Audit_Results.
        """
        if not self._sheets_service:
            return

        try:
            # Récupérer les en-têtes actuels
            result = self._sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SHEET_AUDIT_RESULTS}!1:1"
            ).execute()

            values = result.get('values', [])
            if not values or not values[0]:
                return

            current_headers = values[0]
            needs_update = False
            new_headers = current_headers.copy()

            # Vérifier et ajouter les colonnes manquantes
            if "to_do" not in new_headers:
                new_headers.append("to_do")
                needs_update = True

            if "recommended_actions" not in new_headers:
                new_headers.append("recommended_actions")
                needs_update = True

            if needs_update:
                # Calculer la plage des en-têtes
                end_col = chr(64 + len(new_headers))
                range_name = f"{self.SHEET_AUDIT_RESULTS}!A1:{end_col}1"

                # Mettre à jour les en-têtes
                self._sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    body={'values': [new_headers]}
                ).execute()

                # Ajouter la validation de données pour la colonne "to_do"
                try:
                    to_do_col_index = new_headers.index("to_do")
                    requests = [
                        {
                            "setDataValidation": {
                                "range": {
                                    "sheetId": 0,  # ID de la feuille (0 pour la première)
                                    "dimension": "COLUMNS",
                                    "startIndex": to_do_col_index,
                                    "endIndex": to_do_col_index + 1,
                                    "startRowIndex": 1,  # Commencer à la ligne 2
                                },
                                "rule": {
                                    "condition": {
                                        "type": "ONE_OF_LIST",
                                        "values": [
                                            {"userEnteredValue": "Aucune action nécessaire"},
                                            {"userEnteredValue": "Optimiser titres (H1 et H2)"},
                                            {"userEnteredValue": "Réécriture partielle (mise à jour dates et statistiques)"},
                                            {"userEnteredValue": "Réécriture totale (contenu obsolète)"},
                                            {"userEnteredValue": "[CAUTION] Redirection 301 (cannibalisation sévère)"},
                                        ]
                                    },
                                    "inputMessage": "Sélectionnez l'action à mener",
                                    "strict": False,
                                    "showCustomUi": True,
                                }
                            }
                        }
                    ]

                    self._sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body={'requests': requests}
                    ).execute()
                except Exception as e:
                    # Si la validation de données échoue, ce n'est pas critique
                    print(f"Attention: Validation de données non configurée: {e}")

        except Exception as e:
            # Les erreurs ici ne doivent pas bloquer l'initialisation
            print(f"Attention: Impossible de vérifier/ajouter les colonnes: {e}")

    # =========================================================================
    # URLs_Input Operations
    # =========================================================================

    def read_pending_urls(self, blog_id: Optional[str] = None) -> list[URLTask]:
        """
        Recupere les URLs en attente de traitement.

        Args:
            blog_id: Filtrer par blog (optionnel)

        Returns:
            Liste de URLTask en status PENDING
        """
        if self._sheets_service is None:
            return []

        try:
            # Lire toutes les données de la feuille
            data = self._read_sheet(self.SHEET_URLS_INPUT)

            tasks = []
            for i, row in enumerate(data[1:], start=2):  # Skip header, 1-indexed
                if len(row) < len(self.COLS_URLS_INPUT):
                    row.extend([""] * (len(self.COLS_URLS_INPUT) - len(row)))

                # Indices (NEW STRUCTURE): blog_id(0), url(1), main_keyword(2), title(3), post_type(4), status(5), triggered_by(6), ...
                blog_id_val = row[0] if len(row) > 0 else ""
                status = row[5] if len(row) > 5 else "PENDING"
                main_keyword = row[2] if len(row) > 2 else ""

                # Filtrer par statut PENDING
                if status != TaskStatus.PENDING.value:
                    continue

                # Filtrer par blog_id si spécifié
                if blog_id and blog_id_val != blog_id:
                    continue

                tasks.append(URLTask(
                    url=row[1],
                    title=row[3] if len(row) > 3 else "",
                    blog_id=blog_id_val,
                    row_index=i,
                    status=TaskStatus(status) if status else TaskStatus.PENDING,
                    triggered_by=TriggerType(row[6]) if len(row) > 6 and row[6] else TriggerType.MANUAL,
                    added_date="",
                    processing_started=row[7] if len(row) > 7 else "",
                    processing_completed=row[8] if len(row) > 8 else "",
                    error_message=row[9] if len(row) > 9 else "",
                    notes=row[10] if len(row) > 10 else "",
                    main_keyword=main_keyword,
                ))

            return tasks

        except Exception as e:
            print(f"Erreur lecture URLs: {e}")
            return []

    def add_url(self, url: str, blog_id: str,
                title: str = "",
                triggered_by: TriggerType = TriggerType.MANUAL,
                notes: str = "") -> bool:
        """
        Ajoute une URL à la file de traitement.

        Args:
            url: URL à ajouter
            title: Titre de l'article
            blog_id: Identifiant du blog
            triggered_by: Source du déclenchement
            notes: Notes optionnelles

        Returns:
            True si succès
        """
        if self._sheets_service is None:
            return False

        try:
            row = [
                url,
                title,
                blog_id,
                "",  # post_type (empty — column kept for backwards compat)
                TaskStatus.PENDING.value,
                triggered_by.value,
                "",  # processing_started
                "",  # processing_completed
                "",  # error_message
                notes,
            ]

            self._append_row(self.SHEET_URLS_INPUT, row)
            return True

        except Exception as e:
            print(f"Erreur ajout URL: {e}")
            return False

    def update_status(self, url: str, status: TaskStatus,
                      error_message: str = "") -> bool:
        """
        Met à jour le statut d'une URL.

        Args:
            url: URL à mettre à jour
            status: Nouveau statut
            error_message: Message d'erreur (si FAILED)

        Returns:
            True si succès
        """
        if self._sheets_service is None:
            return False

        try:
            # Trouver la ligne de l'URL
            row_index = self._find_url_row(url, self.SHEET_URLS_INPUT)
            if row_index is None:
                return False

            # Préparer les mises à jour
            # Colonnes: url(A), title(B), blog_id(C), post_type(D), status(E), triggered_by(F),
            #           processing_started(G), processing_completed(H), error_message(I), notes(J)
            updates = {
                "E": status.value,  # Colonne status
            }

            if status == TaskStatus.PROCESSING:
                updates["G"] = datetime.now().strftime("%Y-%m-%d %H:%M")  # processing_started
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                updates["H"] = datetime.now().strftime("%Y-%m-%d %H:%M")  # processing_completed

            if error_message:
                updates["I"] = error_message  # error_message

            # Appliquer les mises à jour
            for col, value in updates.items():
                self._update_cell(self.SHEET_URLS_INPUT, f"{col}{row_index}", value)

            return True

        except Exception as e:
            print(f"Erreur mise à jour statut: {e}")
            return False

    # =========================================================================
    # Audit_Results Operations
    # =========================================================================

    def log_audit(self, audit_result: AuditResultRow) -> bool:
        """
        Enregistre un résultat d'audit.

        Args:
            audit_result: Données d'audit à enregistrer

        Returns:
            True si succès
        """
        if self._sheets_service is None:
            return False

        try:
            # Ordre aligné avec setup_sheets_api.py SHEETS_CONFIG["Audit_Results"]
            row = [
                audit_result.to_do,
                audit_result.url,
                str(audit_result.overall_score),
                str(audit_result.impressions_30d),
                str(audit_result.clicks_30d),
                f"{audit_result.ctr_30d:.2f}",
                f"{audit_result.avg_position:.1f}",
                audit_result.main_keyword,
                audit_result.keyword_trend,
                str(audit_result.word_count),
                str(audit_result.images_count),
                str(audit_result.internal_links_count),
                "OUI" if audit_result.has_faq else "NON",
                "OUI" if audit_result.cannibalization_flag else "NON",
                audit_result.cannibalization_severity,
                audit_result.cannibalization_urls,
                "OUI" if audit_result.intent_shift_detected else "NON",
                audit_result.serp_format_expected,
                audit_result.alerts,
                audit_result.recommendations,
                audit_result.audit_date,
                audit_result.recommended_actions,
            ]

            self._append_row(self.SHEET_AUDIT_RESULTS, row)
            return True

        except Exception as e:
            print(f"Erreur log audit: {e}")
            return False

    # =========================================================================
    # Refresh_Results Operations
    # =========================================================================

    def log_refresh(self, refresh_result: RefreshResultRow) -> bool:
        """
        Enregistre un résultat de refresh.

        Args:
            refresh_result: Données de refresh à enregistrer

        Returns:
            True si succès
        """
        if self._sheets_service is None:
            return False

        try:
            row = [
                refresh_result.url,
                refresh_result.refresh_date,
                refresh_result.rewrite_type,
                refresh_result.new_title,
                refresh_result.new_meta,
                str(refresh_result.sections_modified),
                str(refresh_result.word_count_before),
                str(refresh_result.word_count_after),
                str(refresh_result.images_before),
                str(refresh_result.images_after),
                str(refresh_result.links_before),
                str(refresh_result.links_after),
                "OUI" if refresh_result.validation_passed else "NON",
                refresh_result.validation_errors,
                refresh_result.content_preview[:500],  # Limiter à 500 chars
                refresh_result.full_content_link,
                "OUI" if refresh_result.publish_queue else "NON",
                refresh_result.published_date,
                str(refresh_result.tokens_used),
            ]

            self._append_row(self.SHEET_REFRESH_RESULTS, row)
            return True

        except Exception as e:
            print(f"Erreur log refresh: {e}")
            return False

    def queue_for_publish(self, url: str) -> bool:
        """
        Marque une URL comme prête pour publication.

        Args:
            url: URL à marquer

        Returns:
            True si succès
        """
        row_index = self._find_url_row(url, self.SHEET_REFRESH_RESULTS)
        if row_index:
            return self._update_cell(
                self.SHEET_REFRESH_RESULTS,
                f"Q{row_index}",  # Colonne publish_queue
                "OUI"
            )
        return False

    # =========================================================================
    # Decision_Log Operations
    # =========================================================================

    def log_decision(self, url: str, rules_triggered: list[str],
                     primary_action: str, rewrite_scope: str,
                     estimated_tokens: int, prompt_template: str) -> bool:
        """
        Enregistre une décision de stratégie.

        Args:
            url: URL concernée
            rules_triggered: Règles déclenchées
            primary_action: Action principale
            rewrite_scope: Scope de réécriture
            estimated_tokens: Tokens estimés
            prompt_template: Template de prompt utilisé

        Returns:
            True si succès
        """
        if self._sheets_service is None:
            return False

        try:
            row = [
                url,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                ", ".join(rules_triggered),
                primary_action,
                "",  # secondary_actions
                rewrite_scope,
                str(estimated_tokens),
                prompt_template,
                "",  # subject_prompt
                "NON",  # approved
                "",  # approved_by
                "",  # approval_notes
            ]

            self._append_row(self.SHEET_DECISION_LOG, row)
            return True

        except Exception as e:
            print(f"Erreur log décision: {e}")
            return False

    def set_action_required(self, url: str, action: str) -> bool:
        """
        Définit une action requise (ex: pour cannibalisation).

        Args:
            url: URL concernée
            action: Action requise (ex: "Redirect 301 vers ...")

        Returns:
            True si succès
        """
        # Trouver la ligne et mettre à jour la colonne notes avec l'action
        # Colonnes: url(A), title(B), blog_id(C), ..., notes(J)
        row_index = self._find_url_row(url, self.SHEET_URLS_INPUT)
        if row_index:
            return self._update_cell(
                self.SHEET_URLS_INPUT,
                f"J{row_index}",  # Colonne notes
                f"ACTION REQUISE: {action}"
            )
        return False

    # =========================================================================
    # Helper Methods
    # =========================================================================

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
                print(f"Erreur lecture sheet {sheet_name}: {e}")
                return []

        return []

    def _append_row(self, sheet_name: str, row: list[str]) -> bool:
        """Ajoute une ligne a la fin d'une feuille."""
        # Mode API directe
        if self._sheets_service:
            try:
                self._sheets_service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=sheet_name,
                    valueInputOption="USER_ENTERED",
                    body={"values": [row]}
                ).execute()
                return True
            except Exception as e:
                print(f"Erreur append row: {e}")
                return False

        return False

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
                sheet_name = update.get("sheet", self.SHEET_REFRESHS_AUDIT)
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
                print(f"[SHEETS] ⚠ Batch update partiel: {updated}/{len(updates)} cellules écrites. Cellules: {cells_list}")
            return True

        except Exception as e:
            cells_list = [u.get("cell", "?") for u in updates]
            print(f"[SHEETS] ✗ ERREUR batch update cells {cells_list}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _reset_and_prepare_statuses(self, blog_id: Optional[str] = None, post_type: Optional[str] = None) -> dict:
        """
        Réinitialise et prépare les statuts pour le workflow automatisé.

        REFONTE STATUTS (Feb 2026):
        - Colonne H (status): Remplace anciens statuts (NO ACTION, TITLES DONE, etc.) par TODO
        - Colonne I (audit_gsc): Laisse vide si vide (auto-détection par read_pending_for_gsc_audit)
        - Colonne J (audit_serp): Laisse vide si vide (auto-détection par read_pending_for_serp_audit)

        Args:
            blog_id: Filtrer par blog_id (optionnel)

        Returns:
            Dict avec statistiques: {"status_reset": int, "urls_prepared": int}
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            updates = []
            stats = {"status_reset": 0, "urls_prepared": 0}

            # Anciens statuts à remplacer par TODO
            OLD_STATUSES = [
                "NO ACTION", "TITLES DONE", "CONTENT DONE", "READY FOR REFRESH",
                "READY_FOR_REFRESH", "TITLES_DONE", "CONTENT_DONE", "NO_ACTION",
                "blocked_quality_issues", "EDITORIAL_AUDIT", "DECISION",
                "CANNIBALIZATION_CHECK", "REFRESHING", "FAILED"
            ]

            for i, row in enumerate(data[1:], start=2):
                if len(row) < 1:
                    continue

                # Filter by blog_id if specified
                if blog_id and row[0] != blog_id:
                    continue

                # Filter by post_type if specified (column F, index 5)
                if post_type:
                    row_post_type = row[4] if len(row) > 4 else ""
                    if row_post_type != post_type:
                        continue

                # H (status) - index 7: Remplacer anciens statuts par TODO
                status = row[6] if len(row) > 6 else ""
                if status in OLD_STATUSES or status == "":
                    updates.append({"cell": f"H{i}", "value": "TODO"})
                    stats["status_reset"] += 1
                    stats["urls_prepared"] += 1

            # Apply batch update if there are changes
            if updates:
                self._batch_update_cells(updates)
                print(f"[STATUS RESET] {stats['status_reset']} statuts réinitialisés à TODO")

            return stats

        except Exception as e:
            print(f"Erreur reset_and_prepare_statuses: {e}")
            return {"status_reset": 0, "urls_prepared": 0}

    def _update_cell(self, sheet_name: str, cell: str, value: str) -> bool:
        """Met a jour une cellule specifique."""
        # Mode API directe
        if self._sheets_service:
            try:
                self._sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!{cell}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[value]]}
                ).execute()
                return True
            except Exception as e:
                print(f"Erreur update cell: {e}")
                return False

        return False

    def _find_url_row(self, url: str, sheet_name: str) -> Optional[int]:
        """Trouve l'index de ligne d'une URL.

        Note: Pour Refreshs_Audit, l'URL est en colonne B (index 1).
        Colonne A = blog_id, Colonne B = blogpost_url.
        Pour les autres sheets (legacy), l'URL est en colonne B (index 1).
        """
        data = self._read_sheet(sheet_name)
        url_col_idx = 1  # Column B for both Refreshs_Audit and legacy
        for i, row in enumerate(data[1:], start=2):  # Skip header
            if row and len(row) > url_col_idx and row[url_col_idx] == url:
                return i
        return None

    # =========================================================================
    # NEW: v2.0 Single-Sheet Architecture Methods
    # =========================================================================

    def read_pending_for_gsc_audit(self, blog_id: Optional[str] = None) -> list["RefreshAuditRow"]:
        """
        Lit les lignes où audit_gsc est vide ou AUDITING.

        REFONTE: Auto-initialise les URLs qui n'ont jamais été auditées (I vide).
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            rows = []
            for i, row in enumerate(data[1:], start=2):
                # NEW: Accepter I vide (auto-init) ou I="AUDITING"
                audit_gsc = row[7] if len(row) > 7 else ""
                if audit_gsc in ("", "AUDITING"):
                        try:
                            audit_row = RefreshAuditRow.from_list(row, i)
                            if not blog_id or audit_row.blog_id == blog_id:
                                rows.append(audit_row)
                        except Exception as e:
                            # Fallback: créer une row minimale avec les champs essentiels
                            print(f"[WARNING] Impossible de parser ligne {i} pour GSC audit: {e}. Création d'une row minimale...")
                            try:
                                # Créer une row minimale
                                try:
                                    post_type = row[4] if len(row) > 4 else ""
                                except (ValueError, KeyError):
                                    post_type = ""

                                audit_row = RefreshAuditRow(
                                    blog_id=row[0] if len(row) > 0 else "",
                                    blogpost_url=row[1] if len(row) > 1 else "",
                                    main_keyword=row[2] if len(row) > 2 else "",
                                    title=row[3] if len(row) > 3 else "",
                                    post_type=post_type,
                                    action_blogpost=row[5] if len(row) > 5 else "",
                                    status=row[6] if len(row) > 6 else "",
                                    audit_gsc=row[7] if len(row) > 7 else "",
                                    audit_serp=row[8] if len(row) > 8 else "",
                                    impressions_30d=_safe_int(row[9]),
                                    clicks_30d=_safe_int(row[10]),
                                    ctr_30d=_safe_float(row[11]),
                                    people_also_ask=row[12] if len(row) > 12 else "",
                                    secondary_keywords=row[13] if len(row) > 13 else "",
                                    new_h1_title=row[14] if len(row) > 14 else "",
                                    new_h2_titles=row[15] if len(row) > 15 else "",
                                    word_count_before=_safe_int(row[16]),
                                    images_count=_safe_int(row[17]),
                                    internal_links_count=_safe_int(row[18]),
                                    cannibalization_flag=(row[19] == "YES") if len(row) > 19 else False,
                                    cannibalization_urls=row[20] if len(row) > 20 else "",
                                    error_message=row[21] if len(row) > 21 else "",
                                    row_index=i,
                                )
                                if not blog_id or audit_row.blog_id == blog_id:
                                    rows.append(audit_row)
                                    print(f"[INFO] Row minimale créée pour ligne {i}")
                            except Exception as fallback_error:
                                print(f"[ERROR] Impossible de créer même une row minimale pour ligne {i}: {fallback_error}")
                                continue
            return rows
        except Exception:
            return []

    def read_rows_missing_keyword(self, blog_id: Optional[str] = None) -> list["RefreshAuditRow"]:
        """
        Lit les lignes où main_keyword (col D, index 3) est vide.

        STEP 0: Keyword Discovery - identifie les URLs qui nécessitent
        une découverte automatique du mot-clé principal.
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            rows = []
            for i, row in enumerate(data[1:], start=2):
                # Vérifier que main_keyword (col D, index 3) est vide
                main_kw = row[2] if len(row) > 2 else ""
                if main_kw.strip():
                    continue  # Déjà rempli, skip

                # Vérifier qu'on a au moins une URL
                url = row[1] if len(row) > 1 else ""
                if not url.strip():
                    continue

                # Vérifier que le status n'est pas BLOCKED/DONE (pas besoin de re-découvrir)
                status = row[6] if len(row) > 6 else ""
                if status in ("DONE",):
                    continue

                try:
                    audit_row = RefreshAuditRow.from_list(row, i)
                    if not blog_id or audit_row.blog_id == blog_id:
                        rows.append(audit_row)
                except Exception:
                    # Fallback minimal
                    try:
                        audit_row = RefreshAuditRow(
                            blog_id=row[0] if len(row) > 0 else "",
                            blogpost_url=url,
                            main_keyword="",
                            title=row[3] if len(row) > 3 else "",
                            post_type=row[4] if len(row) > 4 else "",
                            action_blogpost=row[5] if len(row) > 5 else "",
                            status=status,
                            audit_gsc="",
                            audit_serp="",
                            impressions_30d=0,
                            clicks_30d=0,
                            ctr_30d=0.0,
                            people_also_ask="",
                            secondary_keywords="",
                            new_h1_title="",
                            new_h2_titles="",
                            word_count_before=0,
                            images_count=0,
                            internal_links_count=0,
                            cannibalization_flag=False,
                            cannibalization_urls="",
                            error_message="",
                            row_index=i,
                        )
                        if not blog_id or audit_row.blog_id == blog_id:
                            rows.append(audit_row)
                    except Exception:
                        continue
            return rows
        except Exception:
            return []

    def update_main_keyword(self, url: str, keyword: str, source: str = "") -> bool:
        """
        Écrit le main_keyword découvert en colonne D.

        Args:
            url: URL de l'article
            keyword: Mot-clé principal découvert
            source: Source de la découverte (dataforseo/gsc/slug)
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            for i, row in enumerate(data[1:], start=2):
                if row and len(row) > 1 and row[1] == url:
                    updates = [{"cell": f"D{i}", "value": keyword}]
                    self._batch_update_cells(updates)
                    logger.info(f"[STEP 0] main_keyword='{keyword}' written to D{i} (source: {source})")
                    return True
            return False
        except Exception as e:
            logger.error(f"update_main_keyword error for {url}: {e}")
            return False

    def read_rows_with_keyword(self, blog_id: Optional[str] = None) -> list["RefreshAuditRow"]:
        """
        Lit les lignes qui ont déjà un main_keyword (col D non vide).

        Utilisé par batch_keyword_re_discovery pour re-vérifier le volume
        des keywords existants et en trouver de meilleurs si volume < seuil.
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            rows = []
            for i, row in enumerate(data[1:], start=2):
                # Ne prendre que les lignes avec un keyword existant
                main_kw = row[2] if len(row) > 2 else ""
                if not main_kw.strip():
                    continue

                url = row[1] if len(row) > 1 else ""
                if not url.strip():
                    continue

                # Ne pas re-traiter les lignes déjà terminées
                status = row[6] if len(row) > 6 else ""
                if status == "DONE":
                    continue

                try:
                    audit_row = RefreshAuditRow.from_list(row, i)
                    if not blog_id or audit_row.blog_id == blog_id:
                        rows.append(audit_row)
                except Exception:
                    try:
                        audit_row = RefreshAuditRow(
                            blog_id=row[0] if len(row) > 0 else "",
                            blogpost_url=url,
                            main_keyword=main_kw,
                            title=row[3] if len(row) > 3 else "",
                            post_type=row[4] if len(row) > 4 else "",
                            action_blogpost=row[5] if len(row) > 5 else "",
                            status=status,
                            audit_gsc="",
                            audit_serp="",
                            impressions_30d=0,
                            clicks_30d=0,
                            ctr_30d=0.0,
                            people_also_ask="",
                            secondary_keywords="",
                            new_h1_title="",
                            new_h2_titles="",
                            word_count_before=0,
                            images_count=0,
                            internal_links_count=0,
                            cannibalization_flag=False,
                            cannibalization_urls="",
                            error_message="",
                            row_index=i,
                        )
                        if not blog_id or audit_row.blog_id == blog_id:
                            rows.append(audit_row)
                    except Exception:
                        continue
            return rows
        except Exception:
            return []

    def read_pending_for_editorial_audit(self, blog_id: Optional[str] = None) -> list["RefreshAuditRow"]:
        """
        Lit les lignes où l'audit éditorial n'a pas encore été fait.

        Critère: editorial_verdict (colonne AA, index 26) vide ou absent
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            rows = []
            for i, row in enumerate(data[1:], start=2):
                # Check if editorial audit not done yet (column AA empty)
                editorial_verdict = row[25] if len(row) > 25 else ""

                if not editorial_verdict or editorial_verdict.strip() == "":
                    try:
                        audit_row = RefreshAuditRow.from_list(row, i)
                        if not blog_id or audit_row.blog_id == blog_id:
                            rows.append(audit_row)
                    except Exception as e:
                        print(f"[WARNING] Impossible de parser ligne {i} pour editorial audit: {e}")
                        continue
            return rows
        except Exception as e:
            print(f"[ERROR] read_pending_for_editorial_audit: {e}")
            return []

    def read_pending_for_serp_audit(self, blog_id: Optional[str] = None) -> list["RefreshAuditRow"]:
        """
        Lit les lignes où audit_serp est vide ou AUDITING.

        REFONTE: Auto-initialise les URLs qui n'ont jamais été auditées (J vide).
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            rows = []
            for i, row in enumerate(data[1:], start=2):
                # NEW: Accepter J vide (auto-init) ou J="AUDITING"
                audit_serp = row[8] if len(row) > 8 else ""
                if audit_serp in ("", "AUDITING"):
                        try:
                            audit_row = RefreshAuditRow.from_list(row, i)
                            if not blog_id or audit_row.blog_id == blog_id:
                                rows.append(audit_row)
                        except Exception as e:
                            # Fallback: créer une row minimale avec les champs essentiels
                            print(f"[WARNING] Impossible de parser ligne {i}: {e}. Création d'une row minimale...")
                            try:
                                # Créer une row minimale
                                try:
                                    post_type = row[4] if len(row) > 4 else ""
                                except (ValueError, KeyError):
                                    post_type = ""

                                audit_row = RefreshAuditRow(
                                    blog_id=row[0] if len(row) > 0 else "",
                                    blogpost_url=row[1] if len(row) > 1 else "",
                                    main_keyword=row[2] if len(row) > 2 else "",
                                    title=row[3] if len(row) > 3 else "",
                                    post_type=post_type,
                                    action_blogpost=row[5] if len(row) > 5 else "",
                                    status=row[6] if len(row) > 6 else "",
                                    audit_gsc=row[7] if len(row) > 7 else "",
                                    audit_serp=row[8] if len(row) > 8 else "",
                                    impressions_30d=_safe_int(row[9]),
                                    clicks_30d=_safe_int(row[10]),
                                    ctr_30d=_safe_float(row[11]),
                                    people_also_ask=row[12] if len(row) > 12 else "",
                                    secondary_keywords=row[13] if len(row) > 13 else "",
                                    new_h1_title=row[14] if len(row) > 14 else "",
                                    new_h2_titles=row[15] if len(row) > 15 else "",
                                    word_count_before=_safe_int(row[16]),
                                    images_count=_safe_int(row[17]),
                                    internal_links_count=_safe_int(row[18]),
                                    cannibalization_flag=(row[19] == "YES") if len(row) > 19 else False,
                                    cannibalization_urls=row[20] if len(row) > 20 else "",
                                    error_message=row[21] if len(row) > 21 else "",
                                    row_index=i,
                                )
                                if not blog_id or audit_row.blog_id == blog_id:
                                    rows.append(audit_row)
                                    print(f"[INFO] Row minimale créée pour ligne {i}")
                            except Exception as fallback_error:
                                print(f"[ERROR] Impossible de créer même une row minimale pour ligne {i}: {fallback_error}")
                                continue
            return rows
        except Exception:
            return []

    def read_pending_for_decision(self, blog_id: Optional[str] = None) -> list["RefreshAuditRow"]:
        """Lit les lignes où audit_gsc=DONE ET audit_serp=DONE ET action_blogpost=''."""
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            rows = []
            for i, row in enumerate(data[1:], start=2):
                if len(row) > 8:
                    # I=audit_gsc (8), J=audit_serp (9), G=action_blogpost (6)
                    if row[7] == "DONE" and row[8] == "DONE" and (len(row) <= 6 or not row[5]):
                        try:
                            audit_row = RefreshAuditRow.from_list(row, i)
                            if not blog_id or audit_row.blog_id == blog_id:
                                rows.append(audit_row)
                        except Exception as e:
                            # Fallback: créer une row minimale avec les champs essentiels
                            print(f"[WARNING] Impossible de parser ligne {i} pour décision: {e}. Création d'une row minimale...")
                            try:
                                # Créer une row minimale
                                try:
                                    post_type = row[4] if len(row) > 4 else ""
                                except (ValueError, KeyError):
                                    post_type = ""

                                audit_row = RefreshAuditRow(
                                    blog_id=row[0] if len(row) > 0 else "",
                                    blogpost_url=row[1] if len(row) > 1 else "",
                                    main_keyword=row[2] if len(row) > 2 else "",
                                    title=row[3] if len(row) > 3 else "",
                                    post_type=post_type,
                                    action_blogpost=row[5] if len(row) > 5 else "",
                                    status=row[6] if len(row) > 6 else "",
                                    audit_gsc=row[7] if len(row) > 7 else "",
                                    audit_serp=row[8] if len(row) > 8 else "",
                                    impressions_30d=_safe_int(row[9]),
                                    clicks_30d=_safe_int(row[10]),
                                    ctr_30d=_safe_float(row[11]),
                                    people_also_ask=row[12] if len(row) > 12 else "",
                                    secondary_keywords=row[13] if len(row) > 13 else "",
                                    new_h1_title=row[14] if len(row) > 14 else "",
                                    new_h2_titles=row[15] if len(row) > 15 else "",
                                    word_count_before=_safe_int(row[16]),
                                    images_count=_safe_int(row[17]),
                                    internal_links_count=_safe_int(row[18]),
                                    cannibalization_flag=(row[19] == "YES") if len(row) > 19 else False,
                                    cannibalization_urls=row[20] if len(row) > 20 else "",
                                    error_message=row[21] if len(row) > 21 else "",
                                    row_index=i,
                                )
                                if not blog_id or audit_row.blog_id == blog_id:
                                    rows.append(audit_row)
                                    print(f"[INFO] Row minimale créée pour ligne {i}")
                            except Exception as fallback_error:
                                print(f"[ERROR] Impossible de créer même une row minimale pour ligne {i}: {fallback_error}")
                                continue
            return rows
        except Exception:
            return []

    def read_pending_for_refresh(self, action: str, blog_id: Optional[str] = None) -> list["RefreshAuditRow"]:
        """Lit les lignes où action_blogpost = action ET status != CONTENT DONE."""
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            rows = []

            # Normaliser l'action (accepter les deux formats : avec espace et underscore)
            # "REFRESH TITLES" vs "REFRESH_TITLES"
            action_variants = [
                action,  # Format original
                action.replace("_", " "),  # Si on reçoit "REFRESH_TITLES", chercher "REFRESH TITLES"
                action.replace(" ", "_"),  # Si on reçoit "REFRESH TITLES", chercher "REFRESH_TITLES"
            ]

            for i, row in enumerate(data[1:], start=2):
                if len(row) > 6:
                    # G=action_blogpost (6), H=status (7)
                    action_value = row[5] if len(row) > 5 else ""
                    if action_value in action_variants and row[6] not in ("DONE", "CONTENT DONE"):
                        try:
                            audit_row = RefreshAuditRow.from_list(row, i)
                            if not blog_id or audit_row.blog_id == blog_id:
                                rows.append(audit_row)
                        except Exception as e:
                            # Fallback: créer une row minimale avec les champs essentiels
                            print(f"[WARNING] Impossible de parser ligne {i}: {e}. Création d'une row minimale...")
                            try:
                                # Créer une row minimale avec essentiels pour batch_refresh
                                try:
                                    post_type = row[4] if len(row) > 4 else ""
                                except (ValueError, KeyError):
                                    post_type = ""

                                audit_row = RefreshAuditRow(
                                    blog_id=row[0] if len(row) > 0 else "",
                                    blogpost_url=row[1] if len(row) > 1 else "",
                                    main_keyword=row[2] if len(row) > 2 else "",
                                    title=row[3] if len(row) > 3 else "",
                                    post_type=post_type,
                                    action_blogpost=row[5] if len(row) > 5 else "",
                                    status=row[6] if len(row) > 6 else "",
                                    audit_gsc=row[7] if len(row) > 7 else "",
                                    audit_serp=row[8] if len(row) > 8 else "",
                                    impressions_30d=_safe_int(row[9]),
                                    clicks_30d=_safe_int(row[10]),
                                    ctr_30d=_safe_float(row[11]),
                                    people_also_ask=row[12] if len(row) > 12 else "",
                                    secondary_keywords=row[13] if len(row) > 13 else "",
                                    new_h1_title=row[14] if len(row) > 14 else "",
                                    new_h2_titles=row[15] if len(row) > 15 else "",
                                    word_count_before=_safe_int(row[16]),
                                    images_count=_safe_int(row[17]),
                                    internal_links_count=_safe_int(row[18]),
                                    cannibalization_flag=(row[19] == "YES") if len(row) > 19 else False,
                                    cannibalization_urls=row[20] if len(row) > 20 else "",
                                    error_message=row[21] if len(row) > 21 else "",
                                    row_index=i,
                                )
                                if not blog_id or audit_row.blog_id == blog_id:
                                    rows.append(audit_row)
                                    print(f"[INFO] Row minimale créée pour ligne {i}")
                            except Exception as fallback_error:
                                print(f"[ERROR] Impossible de créer même une row minimale pour ligne {i}: {fallback_error}")
                                continue
            return rows
        except Exception as e:
            # NE PAS avaler silencieusement : l'onglet "Refreshs_Audit" n'existe plus
            # dans les Google Sheets réels (HTTP 400). Ce log rend visible toute
            # erreur d'onglet au lieu de retourner 0 ligne sans explication.
            print(
                f"[ERROR] read_pending_for_refresh({action!r}, blog={blog_id!r}) a échoué "
                f"sur l'onglet '{self.SHEET_REFRESHS_AUDIT}': {e}. "
                "Cet onglet est obsolète — le pipeline Superprof passe par 'New Growing List' "
                "(prepare_weekly_batch.py) et Enseigna par 'Avis'/'Versus'."
            )
            return []

    def update_audit_gsc(
        self,
        url: str,
        status: str,
        metrics: Optional[dict] = None,
        index_diagnostic: Optional[str] = None,
        error_message: str = ""
    ) -> bool:
        """
        Met à jour colonne I + optionnellement K-M + X + W.

        IMPORTANT: Si status="DONE", met automatiquement audit_serp (col J) à "AUDITING"
        pour préparer l'étape suivante du workflow.
        """
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)

            for i, row in enumerate(data[1:], start=2):
                if row and len(row) > 1 and row[1] == url:  # C=blogpost_url (2)
                    # OPTIMIZED: Use batch update to avoid API quota (60 writes/min)
                    updates = [
                        {"cell": f"I{i}", "value": status}
                    ]

                    if metrics:
                        updates.extend([
                            {"cell": f"K{i}", "value": metrics.get("impressions_30d", 0)},
                            {"cell": f"L{i}", "value": metrics.get("clicks_30d", 0)},
                            {"cell": f"M{i}", "value": metrics.get("ctr_30d", 0.0)}
                        ])

                    if index_diagnostic:
                        updates.append({"cell": f"X{i}", "value": index_diagnostic})

                    if error_message:
                        updates.append({"cell": f"W{i}", "value": error_message})

                    # FIX: Auto-transition to next workflow step
                    # Si GSC audit réussi (DONE), préparer l'audit SERP
                    if status == "DONE":
                        updates.append({"cell": f"J{i}", "value": "AUDITING"})

                    # Batch update all cells in one API call
                    self._batch_update_cells(updates)
                    return True
            return False
        except Exception as e:
            logger.error(f"update_audit_gsc error for URL {url}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_audit_serp(
        self,
        url: str,
        status: str,
        serp_data: Optional[dict] = None,
        error_message: str = ""
    ) -> bool:
        """Met à jour colonne J + optionnellement N-O + W."""
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)

            for i, row in enumerate(data[1:], start=2):
                if row and len(row) > 1 and row[1] == url:
                    # OPTIMIZED: Use batch update to avoid API quota
                    updates = [
                        {"cell": f"J{i}", "value": status}
                    ]

                    if serp_data:
                        updates.extend([
                            {"cell": f"N{i}", "value": serp_data.get("people_also_ask", "")},
                            {"cell": f"O{i}", "value": serp_data.get("secondary_keywords", "")}
                        ])

                    if error_message:
                        updates.append({"cell": f"W{i}", "value": error_message})

                    # Batch update all cells in one API call
                    ok = self._batch_update_cells(updates)
                    if not ok:
                        print(f"[SHEETS] ✗ update_audit_serp: _batch_update_cells a échoué pour {url[:60]}")
                    return ok
            print(f"[SHEETS] ✗ update_audit_serp: URL introuvable dans la spreadsheet: {url[:80]}")
            return False
        except Exception as e:
            logger.error(f"update_audit_serp error for URL {url}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_decision(
        self,
        url: str,
        action_blogpost: str,
        content_metrics: dict,
        cannibalization: dict,
        title: str = None  # NEW: optional title parameter
    ) -> bool:
        """Met à jour colonnes E (title), G, R-V après décision."""
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)

            for i, row in enumerate(data[1:], start=2):
                if row and len(row) > 1 and row[1] == url:
                    # OPTIMIZED: Use batch update to avoid API quota
                    updates = [
                        {"cell": f"G{i}", "value": action_blogpost},
                        {"cell": f"R{i}", "value": content_metrics.get("word_count_before", 0)},
                        {"cell": f"S{i}", "value": content_metrics.get("images_count", 0)},
                        {"cell": f"T{i}", "value": content_metrics.get("internal_links_count", 0)},
                        {"cell": f"U{i}", "value": "YES" if cannibalization.get("flag") else "NO"},
                        {"cell": f"V{i}", "value": cannibalization.get("urls", "")}
                    ]

                    # NEW: Update column E (title) if provided
                    if title:
                        updates.insert(0, {"cell": f"E{i}", "value": title})

                    # Batch update all cells in one API call
                    self._batch_update_cells(updates)
                    return True
            return False
        except Exception as e:
            logger.error(f"update_decision error for URL {url}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_refresh_status(
        self,
        url: str,
        status: str,
        new_titles: Optional[dict] = None
    ) -> bool:
        """Met à jour colonne H + optionnellement P-Q."""
        try:
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)

            for i, row in enumerate(data[1:], start=2):
                if row and len(row) > 1 and row[1] == url:
                    # OPTIMIZED: Use batch update to avoid API quota
                    updates = [
                        {"cell": f"H{i}", "value": status}
                    ]

                    if new_titles:
                        updates.extend([
                            {"cell": f"P{i}", "value": new_titles.get("new_h1_title", "")},
                            {"cell": f"Q{i}", "value": new_titles.get("new_h2_titles", "")}
                        ])

                    # Batch update all cells in one API call
                    ok = self._batch_update_cells(updates)
                    if not ok:
                        print(f"[SHEETS] ✗ update_refresh_status: _batch_update_cells a échoué pour {url[:60]}")
                    return ok
            print(f"[SHEETS] ✗ update_refresh_status: URL introuvable dans la spreadsheet: {url[:80]}")
            return False
        except Exception as e:
            logger.error(f"update_refresh_status error for URL {url}: {e}")
            import traceback
            traceback.print_exc()
            return False

    # =========================================================================
    # Enseigna Avis/Versus Operations (onglets réels de production)
    # =========================================================================
    #
    # "Avis" et "Versus" partagent le même schéma 14 colonnes A-N (voir EnseignaAvisRow).
    # Ces onglets sont régénérés en colonnes A-J par scripts/audit/enseigna_refresh_list.py
    # (snapshot GSC). Les colonnes K-N (suggested_action, publish_date, refresh_date) sont
    # pilotées séparément — on ne les touche donc qu'en cellule ciblée, jamais en clear+rewrite.

    # Onglets de refresh Enseigna. Source de vérité : bloc `sheets` de
    # tenants/enseigna/config/tenant.json (§4bis-A). On exclut l'onglet de
    # découverte "A ajouter" (col_keyword=3) qui n'est pas un onglet de refresh.
    # Repli sur le littéral historique si la config est absente.
    _ENSEIGNA_DISCOVERY_TABS = {"A ajouter"}

    @property
    def ENSEIGNA_TABS(self) -> list[str]:
        from _shared.core.sheets_config import get_tab_names
        names = [t for t in get_tab_names("enseigna")
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
            for i, raw_row in enumerate(data[1:], start=2):
                if len(raw_row) < 4:
                    continue
                suggested_action = raw_row[3]
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
            ok = self._batch_update_cells([
                {"sheet": tab, "cell": f"N{row_index}", "value": refresh_date},
            ])
            if not ok:
                print(f"[SHEETS] ✗ update_refresh_status_enseigna: échec écriture pour {url[:60]}")
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

    def ensure_column_x_header(self) -> bool:
        """
        Vérifie et ajoute la colonne X 'Index Diagnostic' si manquante.

        Appelé automatiquement au lancement de batch_audit_gsc.

        Returns:
            True si colonne X présente ou ajoutée avec succès
        """
        if not self._sheets_service:
            return False

        try:
            # Get sheet metadata to check current column count
            spreadsheet = self._sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            # Find Refreshs_Audit sheet
            sheet_id = None
            current_cols = 0
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == self.SHEET_REFRESHS_AUDIT:
                    sheet_id = sheet['properties']['sheetId']
                    current_cols = sheet['properties']['gridProperties']['columnCount']
                    break

            if sheet_id is None:
                return False

            # If less than 24 columns, extend the grid first
            if current_cols < 24:
                requests = [{
                    "appendDimension": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "length": 24 - current_cols
                    }
                }]

                self._sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"requests": requests}
                ).execute()

            # Now add the header
            data = self._read_sheet(self.SHEET_REFRESHS_AUDIT)
            if data and len(data) >= 1:
                header = data[0]

                # Check if X column already has a header
                if len(header) < 24 or not header[23]:
                    self._update_cell(self.SHEET_REFRESHS_AUDIT, "X1", "Index Diagnostic")

            return True

        except Exception as e:
            print(f"Attention: Impossible d'ajouter la colonne X: {e}")
            return False

    # Backward compatibility alias
    ensure_column_w_header = ensure_column_x_header

    def create_sheet_structure(self) -> bool:
        """
        Crée la structure complète du spreadsheet.

        Crée les feuilles avec leurs en-têtes si elles n'existent pas.
        """
        sheets_to_create = [
            (self.SHEET_URLS_INPUT, self.COLS_URLS_INPUT),
            (self.SHEET_AUDIT_RESULTS, self.COLS_AUDIT_RESULTS),
            (self.SHEET_REFRESH_RESULTS, self.COLS_REFRESH_RESULTS),
            (self.SHEET_DECISION_LOG, [
                "url", "decision_date", "rules_triggered", "primary_action",
                "secondary_actions", "rewrite_scope", "estimated_tokens",
                "prompt_template", "subject_prompt", "approved",
                "approved_by", "approval_notes"
            ]),
            (self.SHEET_ASSETS, [
                "url", "asset_type", "asset_html", "src_or_href",
                "alt_or_anchor", "context_h2", "restored", "modified",
                "modification_reason"
            ]),
        ]

        success = True
        for sheet_name, columns in sheets_to_create:
            try:
                # Vérifier si la feuille existe
                existing = self._read_sheet(sheet_name)
                if not existing:
                    # Créer avec en-têtes
                    self._append_row(sheet_name, columns)
            except Exception as e:
                print(f"Erreur création feuille {sheet_name}: {e}")
                success = False

        return success

    def setup_sheet_formatting(self) -> bool:
        """
        Configure la mise en forme visuelle du sheet Refreshs_Audit.

        Applique:
        - Data Validation (menus déroulants) pour colonnes F, G, H, I, J
        - Conditional Formatting (couleurs de fond) basées sur les valeurs

        Colonnes:
        - F (post_type - Architecture sémantique):
            * PARENT (violet foncé #4B0082 + texte blanc) → Articles piliers
            * CHILD (violet clair #DDA0DD) → Articles de maillage
            * STANDALONE (gris neutre #C0C0C0) → Articles isolés
        - G (action_blogpost):
            * NO ACTION (gris #CCCCCC)
            * PARTIAL REFRESH (bleu clair #ADD8E6)
            * REFRESH TITLES (jaune #FFFF00)
            * FULL REFRESH (orange #FFA500)
        - H (status):
            * NO ACTION (gris #CCCCCC)
            * TITLES DONE (vert clair #90EE90)
            * CONTENT DONE (vert foncé #228B22)
        - I & J (audit_gsc/audit_serp):
            * AUDITING (jaune #FFFF00)
            * DONE (vert #00FF00)
            * FAILED (rouge #FF0000)

        Returns:
            True si succès, False sinon
        """
        if not self._sheets_service:
            print("Warning: Sheet formatting requires direct API access")
            return False

        try:
            # Récupérer l'ID de la feuille Refreshs_Audit
            sheets_metadata = self._sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            sheet_id = None
            for sheet in sheets_metadata.get('sheets', []):
                if sheet['properties']['title'] == self.SHEET_REFRESHS_AUDIT:
                    sheet_id = sheet['properties']['sheetId']
                    break

            if sheet_id is None:
                print(f"Erreur: Sheet '{self.SHEET_REFRESHS_AUDIT}' non trouvée")
                return False

            # Préparer les requêtes batch update
            requests = []

            # ================================================================
            # COLONNE F: post_type (Architecture sémantique)
            # ================================================================
            # Data validation
            requests.append({
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": 5,  # Column F
                        "endColumnIndex": 6,
                        "startRowIndex": 1,  # Row 2 onwards
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "PARENT"},
                                {"userEnteredValue": "CHILD"},
                                {"userEnteredValue": "STANDALONE"},
                            ]
                        },
                        "inputMessage": "Sélectionnez le type d'article (architecture sémantique)",
                        "strict": True,
                        "showCustomUi": True,
                    }
                }
            })

            # Conditional formatting for column F (post_type)
            # PARENT: Violet foncé (#4B0082) avec texte blanc
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{"sheetId": sheet_id, "startColumnIndex": 5, "endColumnIndex": 6, "startRowIndex": 1}],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": '=F2="PARENT"'}]
                            },
                            "format": {
                                "backgroundColor": {"red": 0.294, "green": 0.0, "blue": 0.510},  # Violet foncé
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}  # Texte blanc
                                }
                            }
                        }
                    },
                    "index": 0
                }
            })

            # CHILD: Violet clair (#DDA0DD)
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{"sheetId": sheet_id, "startColumnIndex": 5, "endColumnIndex": 6, "startRowIndex": 1}],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": '=F2="CHILD"'}]
                            },
                            "format": {
                                "backgroundColor": {"red": 0.866, "green": 0.627, "blue": 0.866},  # Violet clair
                                "textFormat": {"bold": True}
                            }
                        }
                    },
                    "index": 0
                }
            })

            # STANDALONE: Gris neutre (#C0C0C0)
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{"sheetId": sheet_id, "startColumnIndex": 5, "endColumnIndex": 6, "startRowIndex": 1}],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": '=F2="STANDALONE"'}]
                            },
                            "format": {
                                "backgroundColor": {"red": 0.753, "green": 0.753, "blue": 0.753},  # Gris neutre
                                "textFormat": {"bold": True}
                            }
                        }
                    },
                    "index": 0
                }
            })

            # ================================================================
            # COLONNE G: action_blogpost
            # ================================================================
            # Data validation
            requests.append({
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": 6,  # Column G
                        "endColumnIndex": 7,
                        "startRowIndex": 1,  # Row 2 onwards
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "NO ACTION"},
                                {"userEnteredValue": "PARTIAL REFRESH"},
                                {"userEnteredValue": "REFRESH TITLES"},
                                {"userEnteredValue": "FULL REFRESH"},
                            ]
                        },
                        "inputMessage": "Sélectionnez l'action à appliquer",
                        "strict": True,
                        "showCustomUi": True,
                    }
                }
            })

            # Conditional formatting for column G
            color_rules_g_action = [
                ("NO ACTION", {"red": 0.8, "green": 0.8, "blue": 0.8}),  # Gris
                ("PARTIAL REFRESH", {"red": 0.678, "green": 0.847, "blue": 0.902}),  # Bleu clair
                ("REFRESH TITLES", {"red": 1.0, "green": 1.0, "blue": 0.0}),  # Jaune
                ("FULL REFRESH", {"red": 1.0, "green": 0.647, "blue": 0.0}),  # Orange
            ]

            for idx, (value, color) in enumerate(color_rules_g_action):
                requests.append({
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{"sheetId": sheet_id, "startColumnIndex": 6, "endColumnIndex": 7, "startRowIndex": 1}],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": f'=G2="{value}"'}]
                                },
                                "format": {
                                    "backgroundColor": color,
                                    "textFormat": {"bold": True}
                                }
                            }
                        },
                        "index": 0
                    }
                })

            # ================================================================
            # COLONNE H: status
            # ================================================================
            requests.append({
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": 7,  # Column H
                        "endColumnIndex": 8,
                        "startRowIndex": 1,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "NO ACTION"},
                                {"userEnteredValue": "TITLES DONE"},
                                {"userEnteredValue": "CONTENT DONE"},
                            ]
                        },
                        "inputMessage": "Sélectionnez le statut",
                        "strict": True,
                        "showCustomUi": True,
                    }
                }
            })

            # Conditional formatting for column H
            color_rules_h_status = [
                ("NO ACTION", {"red": 0.8, "green": 0.8, "blue": 0.8}),  # Gris
                ("TITLES DONE", {"red": 0.565, "green": 0.933, "blue": 0.565}),  # Vert clair
                ("CONTENT DONE", {"red": 0.133, "green": 0.545, "blue": 0.133}),  # Vert foncé
            ]

            for idx, (value, color) in enumerate(color_rules_h_status):
                requests.append({
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{"sheetId": sheet_id, "startColumnIndex": 7, "endColumnIndex": 8, "startRowIndex": 1}],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": f'=H2="{value}"'}]
                                },
                                "format": {
                                    "backgroundColor": color,
                                    "textFormat": {"bold": True}
                                }
                            }
                        },
                        "index": 0
                    }
                })

            # ================================================================
            # COLONNE I: audit_gsc
            # ================================================================
            requests.append({
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": 8,  # Column I
                        "endColumnIndex": 9,
                        "startRowIndex": 1,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "AUDITING"},
                                {"userEnteredValue": "DONE"},
                                {"userEnteredValue": "FAILED"},
                            ]
                        },
                        "inputMessage": "État de l'audit GSC",
                        "strict": True,
                        "showCustomUi": True,
                    }
                }
            })

            # Conditional formatting for column I
            color_rules_i = [
                ("AUDITING", {"red": 1.0, "green": 1.0, "blue": 0.0}),  # Jaune
                ("DONE", {"red": 0.0, "green": 1.0, "blue": 0.0}),  # Vert
                ("FAILED", {"red": 1.0, "green": 0.0, "blue": 0.0}),  # Rouge
            ]

            for idx, (value, color) in enumerate(color_rules_i):
                requests.append({
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{"sheetId": sheet_id, "startColumnIndex": 8, "endColumnIndex": 9, "startRowIndex": 1}],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": f'=I2="{value}"'}]
                                },
                                "format": {
                                    "backgroundColor": color,
                                    "textFormat": {"bold": True}
                                }
                            }
                        },
                        "index": 0
                    }
                })

            # ================================================================
            # COLONNE J: audit_serp
            # ================================================================
            requests.append({
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": 9,  # Column J
                        "endColumnIndex": 10,
                        "startRowIndex": 1,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "AUDITING"},
                                {"userEnteredValue": "DONE"},
                                {"userEnteredValue": "FAILED"},
                            ]
                        },
                        "inputMessage": "État de l'audit SERP",
                        "strict": True,
                        "showCustomUi": True,
                    }
                }
            })

            # Conditional formatting for column J (same as I)
            for idx, (value, color) in enumerate(color_rules_i):
                requests.append({
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{"sheetId": sheet_id, "startColumnIndex": 9, "endColumnIndex": 10, "startRowIndex": 1}],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": f'=J2="{value}"'}]
                                },
                                "format": {
                                    "backgroundColor": color,
                                    "textFormat": {"bold": True}
                                }
                            }
                        },
                        "index": 0
                    }
                })

            # Exécuter les requêtes batch
            body = {"requests": requests}
            response = self._sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()

            print(f"[OK] Mise en forme appliquée au sheet {self.SHEET_REFRESHS_AUDIT}")
            print(f"  Colonne F (post_type - Architecture sémantique):")
            print(f"    [OK] Data Validation (3 options: PARENT, CHILD, STANDALONE)")
            print(f"    [OK] Conditional Formatting:")
            print(f"      - PARENT: Violet foncé #4B0082 (texte blanc)")
            print(f"      - CHILD: Violet clair #DDA0DD")
            print(f"      - STANDALONE: Gris neutre #C0C0C0")
            print(f"  Colonne G (action_blogpost):")
            print(f"    [OK] Data Validation (4 options)")
            print(f"    [OK] Conditional Formatting (Gris, Bleu, Jaune, Orange)")
            print(f"  Colonne H (status):")
            print(f"    [OK] Data Validation (3 options)")
            print(f"    [OK] Conditional Formatting (Gris, Vert clair, Vert foncé)")
            print(f"  Colonne I (audit_gsc):")
            print(f"    [OK] Data Validation (3 options)")
            print(f"    [OK] Conditional Formatting (Jaune, Vert, Rouge)")
            print(f"  Colonne J (audit_serp):")
            print(f"    [OK] Data Validation (3 options)")
            print(f"    [OK] Conditional Formatting (Jaune, Vert, Rouge)")

            return True

        except Exception as e:
            print(f"Erreur setup_sheet_formatting: {e}")
            return False

    def log_editorial_audit(
        self,
        url: str,
        score: float,
        verdict: str,
        blocking_issues_count: int,
        blocking_issues: str = "",
        report_url: str = ""
    ) -> bool:
        """
        Enregistre le résultat d'un audit éditorial dans les colonnes dédiées.

        Args:
            url: URL de l'article audité
            score: Score éditorial (1-10)
            verdict: PASSED, BLOCKED, ou REVIEW_REQUIRED
            blocking_issues_count: Nombre de problèmes bloquants
            blocking_issues: Description des problèmes (optionnel)
            report_url: URL du rapport markdown (optionnel)

        Returns:
            True si succès, False sinon
        """
        if self._sheets_service is None:
            return False

        try:
            # Trouver la ligne correspondant à l'URL
            row_index = self._find_url_row(url, self.SHEET_REFRESHS_AUDIT)

            if row_index is None:
                print(f"⚠️ URL not found in sheet for editorial audit log: {url[:50]}")
                return False

            # OPTIMIZED: Use batch update to avoid API quota (60 writes/min)
            updates = [
                # Y: editorial_audit_score
                {"cell": f"Y{row_index}", "value": str(round(score, 1))},
                # Z: editorial_audit_date
                {"cell": f"Z{row_index}", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                # AA: editorial_verdict
                {"cell": f"AA{row_index}", "value": verdict},
                # AB: blocking_issues_count
                {"cell": f"AB{row_index}", "value": str(blocking_issues_count)}
            ]

            # AC: editorial_audit_report_url
            if report_url:
                updates.append({"cell": f"AC{row_index}", "value": report_url})

            # Mettre à jour le statut si audit bloqué
            if verdict == "BLOCKED":
                updates.append({"cell": f"H{row_index}", "value": "BLOCKED"})

                # Ajouter une note dans error_message pour visibilité
                if blocking_issues:
                    error_msg = f"Editorial Audit BLOCKED: {blocking_issues[:200]}"
                    updates.append({"cell": f"W{row_index}", "value": error_msg})

            # Batch update all cells in one API call
            self._batch_update_cells(updates)

            return True

        except Exception as e:
            print(f"Erreur log_editorial_audit: {e}")
            return False
