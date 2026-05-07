"""
Batch Workflow Auto - Orchestrateur Automatisé et Scalable

Gère l'exécution complète du workflow pour 50+ URLs sans intervention manuelle:
- Auto-marquer les URLs pour audit
- Normaliser les formats
- Paralléliser les opérations
- Retry automatique en cas d'erreur
- Dashboard de progression
- Support de 50+ URLs en ~5 minutes
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field

from scripts.sheets import SheetsClient


@dataclass
class BatchConfig:
    """Configuration du batch workflow."""
    spreadsheet_id: str
    max_parallel: int = 5  # Max 5 URLs en parallèle (respecte rate limiting)
    max_retries: int = 3
    retry_delay: float = 2.0  # secondes
    timeout_per_url: float = 60.0  # secondes par URL
    blog_id_filter: Optional[str] = None  # Filtrer par blog (optionnel)


@dataclass
class URLTask:
    """Une tâche d'audit pour une URL."""
    row_number: int
    url: str
    blog_id: str
    keyword: str
    status: str = "pending"  # pending, gsc_done, serp_done, decision_done, failed
    error_message: Optional[str] = None
    retries: int = 0


@dataclass
class BatchProgress:
    """Progression du workflow."""
    total_urls: int = 0
    pending: int = 0
    gsc_done: int = 0
    serp_done: int = 0
    decision_done: int = 0
    failed: int = 0
    start_time: float = field(default_factory=time.time)

    def elapsed(self) -> str:
        """Temps écoulé formaté."""
        secs = int(time.time() - self.start_time)
        return f"{secs//60}m{secs%60}s"

    def eta_remaining(self) -> str:
        """ETA basée sur la progression actuelle."""
        if self.gsc_done + self.serp_done == 0:
            return "?"

        elapsed = time.time() - self.start_time
        processed = self.gsc_done + self.serp_done
        rate = processed / elapsed if elapsed > 0 else 0

        remaining = self.total_urls - self.gsc_done
        if rate > 0:
            eta_secs = int(remaining / rate)
            return f"{eta_secs//60}m{eta_secs%60}s"
        return "?"


class AutoBatchWorkflow:
    """Orchestrateur automatisé pour le workflow batch."""

    def __init__(self, config: BatchConfig):
        self.config = config
        self.sheets_client = SheetsClient(config.spreadsheet_id)
        self.progress = BatchProgress()
        self.tasks: List[URLTask] = []

    def log(self, level: str, message: str):
        """Log avec timestamp."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{level}] {message}")

    # =========================================================================
    # PHASE 1: PRÉPARATION - Charger et marquer les URLs
    # =========================================================================

    def prepare_urls(self) -> bool:
        """
        Charge les URLs du spreadsheet et les marque pour audit.

        Returns:
            True si succès, False sinon
        """
        self.log("INFO", "Phase 1: Préparation des URLs")

        try:
            # Lire les données du spreadsheet
            data = self.sheets_client._read_sheet('Refreshs_Audit')

            if not data or len(data) < 2:
                self.log("ERROR", "Spreadsheet vide ou invalide")
                return False

            # Créer une tâche pour chaque ligne (sauf header)
            for row_idx, row in enumerate(data[1:], start=2):
                if not row or len(row) < 3:  # Minimum: blog_id, url, keyword
                    continue

                blog_id = row[0] if len(row) > 0 else ""
                url = row[2] if len(row) > 2 else ""
                keyword = row[3] if len(row) > 3 else ""

                # Filtrer par blog si spécifié
                if self.config.blog_id_filter and blog_id != self.config.blog_id_filter:
                    continue

                if not url or not keyword:
                    continue

                task = URLTask(
                    row_number=row_idx,
                    url=url,
                    blog_id=blog_id,
                    keyword=keyword
                )
                self.tasks.append(task)

            self.progress.total_urls = len(self.tasks)
            self.progress.pending = len(self.tasks)

            self.log("INFO", f"Chargé {len(self.tasks)} URLs")

            # Normaliser les formats de nombres
            if not self._normalize_number_formats():
                self.log("WARNING", "Normalisation échouée, continuation...")

            # Marquer toutes les URLs pour audit GSC et SERP
            if not self._mark_all_for_audit():
                return False

            self.log("INFO", "[OK] Phase 1 complétée")
            return True

        except Exception as e:
            self.log("ERROR", f"Erreur préparation: {e}")
            return False

    def _normalize_number_formats(self) -> bool:
        """
        Normalise les formats de nombres (virgule → point).

        Google Sheets peut retourner des nombres avec virgule selon la locale.
        Cela cause des erreurs lors du parsing (float conversion).
        """
        try:
            self.log("INFO", "Normalisation des formats de nombres...")

            # Lire les données brutes
            data = self.sheets_client._read_sheet('Refreshs_Audit')

            # Colonnes numériques à vérifier : K (impressions), L (clicks), M (ctr)
            numeric_cols = [
                (10, f"Refreshs_Audit!K"),   # K = index 10
                (11, f"Refreshs_Audit!L"),   # L = index 11
                (12, f"Refreshs_Audit!M"),   # M = index 12
            ]

            updates_made = 0

            for col_idx, col_prefix in numeric_cols:
                for row_idx, row in enumerate(data[1:], start=2):
                    if col_idx < len(row) and row[col_idx]:
                        # Vérifier si le nombre a une virgule
                        value_str = str(row[col_idx]).strip()
                        if ',' in value_str:
                            # Remplacer virgule par point
                            fixed_value = value_str.replace(',', '.')
                            try:
                                # Vérifier que c'est un nombre valide
                                float(fixed_value)

                                # Mettre à jour le spreadsheet
                                cell = f"{col_prefix}{row_idx}"
                                self.sheets_client._sheets_service.spreadsheets().values().update(
                                    spreadsheetId=self.sheets_client.spreadsheet_id,
                                    range=cell,
                                    valueInputOption="USER_ENTERED",
                                    body={"values": [[fixed_value]]}
                                ).execute()

                                updates_made += 1
                                self.log("DEBUG", f"Normalisé {cell}: {value_str} → {fixed_value}")
                            except ValueError:
                                pass

            if updates_made > 0:
                self.log("INFO", f"[OK] {updates_made} formats de nombres normalisés")
            return True

        except Exception as e:
            self.log("ERROR", f"Erreur normalisation: {e}")
            return False

    def _mark_all_for_audit(self) -> bool:
        """Marque toutes les URLs avec 'AUDITING' dans I et J."""
        try:
            self.log("INFO", f"Marquage de {len(self.tasks)} URLs pour audit...")

            # Batch update: préparer toutes les mises à jour
            requests = []
            for task in self.tasks:
                # Marquer I{row} = AUDITING
                requests.append({
                    "range": f"Refreshs_Audit!I{task.row_number}",
                    "values": [["AUDITING"]]
                })
                # Marquer J{row} = AUDITING
                requests.append({
                    "range": f"Refreshs_Audit!J{task.row_number}",
                    "values": [["AUDITING"]]
                })

            # Exécuter les mises à jour par batch de 100 (limite API)
            for i in range(0, len(requests), 100):
                batch = requests[i:i+100]
                for req in batch:
                    self.sheets_client._sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.sheets_client.spreadsheet_id,
                        range=req["range"],
                        valueInputOption="USER_ENTERED",
                        body={"values": req["values"]}
                    ).execute()

            self.log("INFO", f"[OK] {len(self.tasks)} URLs marquées pour audit")
            return True

        except Exception as e:
            self.log("ERROR", f"Erreur marquage: {e}")
            return False

    # =========================================================================
    # PHASE 2: AUDIT GSC - Parallélisé
    # =========================================================================

    async def run_gsc_audits_parallel(self) -> bool:
        """
        Exécute les audits GSC en parallèle (respecte rate limiting).

        Returns:
            True si au moins 1 succès, False sinon
        """
        self.log("INFO", "Phase 2: Audit GSC (parallélisé)")

        # Lancer batch-audit-gsc (gère les retries internes)
        success_count = 0
        for attempt in range(self.config.max_retries):
            try:
                # Appeler batch-audit-gsc
                from scripts.agent import RefreshOrchestrator
                orchestrator = RefreshOrchestrator(
                    spreadsheet_id=self.config.spreadsheet_id
                )
                result = orchestrator.batch_audit_gsc(blog_id=self.config.blog_id_filter)

                success_count = result.get("success", 0)
                failed_count = result.get("failed", 0)

                self.progress.gsc_done += success_count
                self.progress.pending -= success_count

                self.log("INFO", f"GSC Audit: {success_count} succès, {failed_count} échecs")

                if success_count > 0:
                    self.log("INFO", "[OK] Phase 2 complétée")
                    return True

            except Exception as e:
                self.log("WARNING", f"Tentative {attempt+1}: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    continue

        self.log("ERROR", "[FAIL] Tous les audits GSC ont échoué")
        return False

    # =========================================================================
    # PHASE 3: AUDIT SERP - Parallélisé
    # =========================================================================

    async def run_serp_audits_parallel(self) -> bool:
        """
        Exécute les audits SERP en parallèle.

        Returns:
            True si au moins 1 succès, False sinon
        """
        self.log("INFO", "Phase 3: Audit SERP (parallélisé)")

        success_count = 0
        for attempt in range(self.config.max_retries):
            try:
                # Appeler batch-audit-serp
                from scripts.agent import RefreshOrchestrator
                orchestrator = RefreshOrchestrator(
                    spreadsheet_id=self.config.spreadsheet_id
                )
                result = orchestrator.batch_audit_serp(blog_id=self.config.blog_id_filter)

                success_count = result.get("success", 0)
                failed_count = result.get("failed", 0)

                self.progress.serp_done += success_count

                self.log("INFO", f"SERP Audit: {success_count} succès, {failed_count} échecs")

                if success_count > 0:
                    self.log("INFO", "[OK] Phase 3 complétée")
                    return True

            except Exception as e:
                self.log("WARNING", f"Tentative {attempt+1}: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    continue

        self.log("ERROR", "[FAIL] Tous les audits SERP ont échoué")
        return False

    # =========================================================================
    # PHASE 4: DÉCISION - Déterminer les actions
    # =========================================================================

    async def run_decision(self) -> dict:
        """
        Exécute le moteur de décision.

        Returns:
            dict avec les résultats des décisions
        """
        self.log("INFO", "Phase 4: Décision (stratégie de refresh)")

        try:
            from scripts.agent import RefreshOrchestrator
            orchestrator = RefreshOrchestrator(
                spreadsheet_id=self.config.spreadsheet_id
            )
            result = orchestrator.batch_decision(blog_id=self.config.blog_id_filter)

            self.progress.decision_done = (
                result.get("no_action", 0) +
                result.get("partial_refresh", 0) +
                result.get("refresh_titles", 0) +
                result.get("full_refresh", 0)
            )

            self.log("INFO", f"""
Décisions:
  - NO ACTION: {result.get('no_action', 0)}
  - PARTIAL REFRESH: {result.get('partial_refresh', 0)}
  - REFRESH TITLES: {result.get('refresh_titles', 0)}
  - FULL REFRESH: {result.get('full_refresh', 0)}
""")

            self.log("INFO", "[OK] Phase 4 complétée")
            return result

        except Exception as e:
            self.log("ERROR", f"Erreur décision: {e}")
            return {}

    # =========================================================================
    # PHASE 5: BATCH-REFRESH - Exécuter la rédaction
    # =========================================================================

    async def run_batch_refresh(self, decision_results: dict = None) -> bool:
        """
        Exécute le batch-refresh pour les actions déterminées OU existantes.

        Traite les actions dans cet ordre:
        1. REFRESH_TITLES
        2. PARTIAL_REFRESH
        3. FULL_REFRESH

        Modes:
        - Si decision_results fourni: Utilise les résultats de batch-decision
        - Sinon: Utilise les actions existantes dans action_blogpost (colonne G)

        Args:
            decision_results: Résultats de la Phase 4 (optionnel)

        Returns:
            True si au moins 1 succès, False sinon
        """
        self.log("INFO", "Phase 5: Batch-Refresh (rédaction)")

        # Déterminer les actions à exécuter
        if decision_results and any(decision_results.values()):
            # Mode 1: Utiliser les résultats de batch-decision
            self.log("INFO", "Mode: Actions de batch-decision")
            actions_to_run = [
                ("REFRESH_TITLES", decision_results.get("refresh_titles", 0)),
                ("PARTIAL_REFRESH", decision_results.get("partial_refresh", 0)),
                ("FULL_REFRESH", decision_results.get("full_refresh", 0)),
            ]
        else:
            # Mode 2: Analyser les actions existantes dans le spreadsheet
            self.log("INFO", "Mode: Actions existantes du spreadsheet")
            actions_to_run = self._analyze_existing_actions()

            if not actions_to_run:
                self.log("WARNING", "Aucune action trouvée à traiter")
                return True

        total_refreshed = 0

        for action_name, count in actions_to_run:
            if count == 0:
                continue

            self.log("INFO", f"Exécution {action_name} ({count} URLs)...")

            for attempt in range(self.config.max_retries):
                try:
                    from scripts.agent import RefreshOrchestrator
                    orchestrator = RefreshOrchestrator(
                        spreadsheet_id=self.config.spreadsheet_id
                    )
                    result = orchestrator.batch_refresh(
                        action=action_name,
                        blog_id=self.config.blog_id_filter
                    )

                    success_count = result.get("success", 0)
                    failed_count = result.get("failed", 0)
                    assets_restored = result.get("assets_restored", 0)

                    total_refreshed += success_count

                    self.log("INFO", f"""
{action_name} Résultats:
  [OK] Succès: {success_count}
  [FAIL] Échecs: {failed_count}
   Assets restaurés: {assets_restored}
""")

                    if success_count > 0:
                        break

                except Exception as e:
                    self.log("WARNING", f"Tentative {attempt+1} {action_name}: {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay)
                        continue

        if total_refreshed > 0:
            self.log("INFO", "[OK] Phase 5 complétée")
            return True
        else:
            self.log("WARNING", "[WARN] Aucun refresh exécuté")
            return False

    def _analyze_existing_actions(self) -> list[tuple[str, int]]:
        """
        Analyse les actions existantes dans action_blogpost (colonne G).

        Retourne une liste des actions trouvées avec leur count.
        Note: Les actions du spreadsheet utilisent des espaces (ex: "REFRESH TITLES")
        mais batch_refresh les attend avec des underscores. La conversion se fait ici.
        """
        try:
            data = self.sheets_client._read_sheet('Refreshs_Audit')

            # Mapping: valeurs spreadsheet → valeurs batch_refresh
            action_mapping = {
                "REFRESH TITLES": "REFRESH_TITLES",    # Avec espace dans sheet
                "PARTIAL REFRESH": "PARTIAL_REFRESH",  # Avec espace dans sheet
                "FULL REFRESH": "FULL_REFRESH",        # Avec espace dans sheet
                # Aussi accepter les variantes avec underscore
                "REFRESH_TITLES": "REFRESH_TITLES",
                "PARTIAL_REFRESH": "PARTIAL_REFRESH",
                "FULL_REFRESH": "FULL_REFRESH",
            }

            action_counts = {
                "REFRESH_TITLES": 0,
                "PARTIAL_REFRESH": 0,
                "FULL_REFRESH": 0,
            }

            for row in data[1:]:
                if len(row) > 6:  # G is index 6
                    action = row[6]
                    if action in action_mapping:
                        mapped_action = action_mapping[action]
                        action_counts[mapped_action] += 1

            # Retourner dans l'ordre de priorité
            return [
                ("REFRESH_TITLES", action_counts["REFRESH_TITLES"]),
                ("PARTIAL_REFRESH", action_counts["PARTIAL_REFRESH"]),
                ("FULL_REFRESH", action_counts["FULL_REFRESH"]),
            ]

        except Exception as e:
            self.log("WARNING", f"Erreur analyse actions: {e}")
            return []

    # =========================================================================
    # DASHBOARD
    # =========================================================================

    def print_progress_dashboard(self):
        """Affiche un dashboard de progression."""
        total = self.progress.total_urls
        gsc = self.progress.gsc_done
        serp = self.progress.serp_done
        decision = self.progress.decision_done
        failed = self.progress.failed

        # Barres de progression
        gsc_pct = int((gsc / total * 100)) if total > 0 else 0
        serp_pct = int((serp / total * 100)) if total > 0 else 0
        decision_pct = int((decision / total * 100)) if total > 0 else 0

        print(f"\n{'='*80}")
        print(f"PROGRESSION DU WORKFLOW - {self.progress.elapsed()} écoulé | ETA: {self.progress.eta_remaining()}")
        print(f"{'='*80}")

        bar_width = 40
        gsc_bar = ('█' * int(gsc_pct * bar_width / 100) + '░' * (bar_width - int(gsc_pct * bar_width / 100)))
        serp_bar = ('█' * int(serp_pct * bar_width / 100) + '░' * (bar_width - int(serp_pct * bar_width / 100)))
        decision_bar = ('█' * int(decision_pct * bar_width / 100) + '░' * (bar_width - int(decision_pct * bar_width / 100)))

        print(f"\nGSC Audit:       [{gsc_pct:3d}%] {gsc_bar} {gsc}/{total}")
        print(f"SERP Audit:      [{serp_pct:3d}%] {serp_bar} {serp}/{total}")
        print(f"Decision:        [{decision_pct:3d}%] {decision_bar} {decision}/{total}")
        print(f"\nÉchecs: {failed}")
        print(f"{'='*80}\n")

    # =========================================================================
    # ORCHESTRATION
    # =========================================================================

    async def run_complete_workflow(self) -> bool:
        """
        Exécute le workflow complet de bout en bout.

        Returns:
            True si succès, False sinon
        """
        self.log("INFO", "[START] DÉMARRAGE DU WORKFLOW COMPLET")
        self.log("INFO", f"Configuration: max_parallel={self.config.max_parallel}, max_retries={self.config.max_retries}")

        # Phase 1: Préparation
        if not self.prepare_urls():
            self.log("ERROR", "[FAIL] Échec phase 1")
            return False

        self.print_progress_dashboard()

        # Phase 2: Audit GSC
        if not await self.run_gsc_audits_parallel():
            self.log("ERROR", "[FAIL] Échec phase 2")
            return False

        self.print_progress_dashboard()

        # Phase 3: Audit SERP
        if not await self.run_serp_audits_parallel():
            self.log("ERROR", "[FAIL] Échec phase 3")
            return False

        self.print_progress_dashboard()

        # Phase 4: Décision
        decision_results = await self.run_decision()
        if not decision_results:
            self.log("ERROR", "[FAIL] Échec phase 4")
            return False

        self.print_progress_dashboard()

        # Phase 5: Batch-Refresh (optionnel)
        refresh_enabled = True  # Peut être rendez configurable
        if refresh_enabled and decision_results:
            if not await self.run_batch_refresh(decision_results):
                self.log("WARNING", "[WARN] Échec phase 5 (mais audit/décision réussie)")

        self.print_progress_dashboard()

        self.log("INFO", "[OK] WORKFLOW COMPLET - SUCCÈS!")
        return True


# =========================================================================
# POINT D'ENTRÉE
# =========================================================================

async def main():
    """Point d'entrée pour exécution autonome."""
    import sys

    # Configuration (peut être personnalisée)
    config = BatchConfig(
        spreadsheet_id="1F99FtN8fWQlQm0ZTJphBRz_c64iDs2DvohyHyM2Tk1M",
        max_parallel=5,
        max_retries=3,
        retry_delay=2.0,
        # blog_id_filter="enseigna"  # Optionnel
    )

    workflow = AutoBatchWorkflow(config)
    success = await workflow.run_complete_workflow()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
