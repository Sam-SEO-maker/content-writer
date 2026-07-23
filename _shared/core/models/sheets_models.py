"""
Sheets Models Module

Modèles pour l'intégration avec Google Sheets.

Architecture (alignée sur les spreadsheets réels de production, pas un schéma théorique) :
- `EnseignaAvisRow`     — onglets "Avis" (14 col A-N) et "Versus" (16 col A-P) de la spreadsheet
                          Enseigna. Schémas DIFFÉRENTS par onglet : indices dans COLUMN_MAPS.
- `SuperprofAuditRow`   — onglet "GSC_Perfs" de la spreadsheet Superprof (15 colonnes)
- `RefreshAuditRow`     — modèle SRW legacy (28 colonnes A-AB, feuille "Refreshs_Audit") — hérité d'un
                          fork multi-blogs antérieur. Ne correspond à aucun onglet réel Enseigna/Superprof.
                          Ne pas recréer cet onglet : voir mémoire feedback_refresh_pipeline_gotchas.
(`ContentWriterRow`, modèle théorique jamais câblé, supprimé le 2026-07-23.)
"""

from dataclasses import dataclass, field

from .enums import TaskStatus, TriggerType


def _safe_int(val, default=0):
    if not val:
        return default
    try:
        return int(float(str(val).replace(",", ".")))
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    if not val:
        return default
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return default


@dataclass
class EnseignaAvisRow:
    """
    Modèle aligné sur les onglets réels "Avis" et "Versus" de la spreadsheet Enseigna.

    ⚠ Les deux onglets NE partagent PAS le même schéma (constat en-têtes réels
    2026-07-23) — le parsing est par index et dispatché par onglet (from_list).
    Les colonnes pilotées à la main (suggested_action, publish_date, refresh_date)
    NE DOIVENT PAS être écrasées par un refresh GSC.

    Avis (14 colonnes A-N) :
      A url · B top_keyword · C priority · D suggested_action (en-tête sheet
      mal libellé "FULL_REFRESH") · E impressions_30d · F clicks_30d ·
      G impressions_3m · H clicks_3m · I nb_kw · J ctr · K avg_position ·
      L snapshot_date · M publish_date · N refresh_date

    Versus (16 colonnes A-P + Q ajoutée par le pipeline) :
      A url · B priority · C suggested_action · D impressions · E clicks ·
      F ctr · G avg_position · H nb_kw · I top_keyword · J top_kw_impressions ·
      K snapshot_date · L impressions_30d · M clicks_30d · N impressions_3m ·
      O clicks_3m · P publish_date · Q refresh_date (colonne pipeline, absente
      du layout d'origine — écrite par update_refresh_status_enseigna)
    """

    url: str = ""                       # A
    top_keyword: str = ""               # B
    priority: str = ""                  # C
    suggested_action: str = ""          # D
    impressions_30d: int = 0            # E
    clicks_30d: int = 0                 # F
    impressions_3m: int = 0             # G
    clicks_3m: int = 0                  # H
    nb_kw: int = 0                      # I
    ctr: float = 0.0                    # J
    avg_position: float = 0.0           # K
    snapshot_date: str = ""             # L
    publish_date: str = ""              # M
    refresh_date: str = ""              # N

    row_index: int = 0                  # non-sheet — ligne dans le spreadsheet (1-indexed)
    tab_name: str = "Avis"              # non-sheet — "Avis" ou "Versus", pour savoir où réécrire

    # Index des champs par onglet (voir docstring). action_col est aussi utilisé
    # par sheets_client pour filtrer sans parser toute la ligne.
    COLUMN_MAPS = {
        "Avis": {
            "url": 0, "top_keyword": 1, "priority": 2, "suggested_action": 3,
            "impressions_30d": 4, "clicks_30d": 5, "impressions_3m": 6,
            "clicks_3m": 7, "nb_kw": 8, "ctr": 9, "avg_position": 10,
            "snapshot_date": 11, "publish_date": 12, "refresh_date": 13,
        },
        "Versus": {
            "url": 0, "priority": 1, "suggested_action": 2, "ctr": 5,
            "avg_position": 6, "nb_kw": 7, "top_keyword": 8,
            "snapshot_date": 10, "impressions_30d": 11, "clicks_30d": 12,
            "impressions_3m": 13, "clicks_3m": 14, "publish_date": 15,
            "refresh_date": 16,
        },
    }

    @staticmethod
    def from_list(row: list, row_index: int = 0, tab_name: str = "Avis") -> "EnseignaAvisRow":
        cols = EnseignaAvisRow.COLUMN_MAPS.get(tab_name, EnseignaAvisRow.COLUMN_MAPS["Avis"])

        def _get(field, default=""):
            i = cols.get(field)
            return row[i] if i is not None and len(row) > i else default

        return EnseignaAvisRow(
            url=_get("url"),
            top_keyword=_get("top_keyword"),
            priority=_get("priority"),
            suggested_action=_get("suggested_action"),
            impressions_30d=_safe_int(_get("impressions_30d", 0)),
            clicks_30d=_safe_int(_get("clicks_30d", 0)),
            impressions_3m=_safe_int(_get("impressions_3m", 0)),
            clicks_3m=_safe_int(_get("clicks_3m", 0)),
            nb_kw=_safe_int(_get("nb_kw", 0)),
            ctr=_safe_float(_get("ctr", 0.0)),
            avg_position=_safe_float(_get("avg_position", 0.0)),
            snapshot_date=_get("snapshot_date"),
            publish_date=_get("publish_date"),
            refresh_date=_get("refresh_date"),
            row_index=row_index,
            tab_name=tab_name,
        )


@dataclass
class URLTask:
    """Représente une tâche de refresh d'URL."""
    url: str
    title: str  # Titre de l'article (nouvelle colonne)
    site_slug: str
    row_index: int
    status: TaskStatus = TaskStatus.PENDING
    triggered_by: TriggerType = TriggerType.MANUAL
    added_date: str = ""
    processing_started: str = ""
    processing_completed: str = ""
    error_message: str = ""
    notes: str = ""
    main_keyword: str = ""  # Mot-clé principal fourni (colonne C)


@dataclass
class AuditResultRow:
    """Ligne de résultat d'audit pour le Sheet."""
    to_do: str = ""
    url: str = ""
    overall_score: int = 0
    impressions_30d: int = 0
    clicks_30d: int = 0
    ctr_30d: float = 0.0
    avg_position: float = 0.0
    main_keyword: str = ""
    keyword_trend: str = ""
    word_count: int = 0
    images_count: int = 0
    internal_links_count: int = 0
    has_faq: bool = False
    cannibalization_flag: bool = False
    cannibalization_severity: str = ""
    cannibalization_urls: str = ""
    intent_shift_detected: bool = False
    serp_format_expected: str = ""
    alerts: str = ""
    recommendations: str = ""
    audit_date: str = ""
    recommended_actions: str = ""


@dataclass
class RefreshResultRow:
    """Ligne de résultat de refresh pour le Sheet."""
    url: str
    refresh_date: str
    rewrite_type: str
    new_title: str
    new_meta: str
    sections_modified: int
    word_count_before: int
    word_count_after: int
    images_before: int
    images_after: int
    links_before: int
    links_after: int
    validation_passed: bool
    validation_errors: str
    content_preview: str
    full_content_link: str
    publish_queue: bool
    published_date: str
    tokens_used: int


@dataclass
class RefreshAuditRow:
    """
    Modèle unifié pour la feuille Refreshs_Audit (28 colonnes A-AB).

    Remplace URLTask + AuditResultRow + RefreshResultRow dans l'architecture single-sheet.
    NOTE: cocon_branch a été retiré du schéma — toutes les colonnes B+ ont été shiftées de -1.
    """

    # A: Core identification
    site_slug: str                                   # A

    # B-E: Article identification
    blogpost_url: str = ""                         # B
    main_keyword: str = ""                         # C
    title: str = ""                                # D
    post_type: str = ""                             # E

    # F-G: Action tracking
    action_blogpost: str = ""                     # F (NO ACTION, PARTIAL REFRESH, REFRESH TITLES, FULL REFRESH)
    status: str = ""                              # G (TODO, AUDITING, DONE, BLOCKED)

    # H-I: Audit status flags
    audit_gsc: str = ""                           # H (AUDITING, DONE, FAILED)
    audit_serp: str = ""                          # I (AUDITING, DONE, FAILED)

    # J-L: Performance metrics (GSC)
    impressions_30d: int = 0                      # J
    clicks_30d: int = 0                           # K
    ctr_30d: float = 0.0                          # L

    # M-N: SERP insights
    people_also_ask: str = ""                     # M (comma-separated PAA questions)
    secondary_keywords: str = ""                  # N (comma-separated keywords)

    # O-P: Optimization targets
    new_h1_title: str = ""                        # O
    new_h2_titles: str = ""                       # P (JSON list of H2 titles)

    # Q-S: Content metrics
    word_count_before: int = 0                    # Q
    images_count: int = 0                         # R
    internal_links_count: int = 0                 # S

    # T-U: Cannibalization
    cannibalization_flag: bool = False            # T (YES/NO)
    cannibalization_urls: str = ""                # U (comma-separated competing URLs)

    # V: Error tracking
    error_message: str = ""                       # V (short error message for audit/refresh failures)

    # W: Index diagnostic
    index_diagnostic: str = ""                    # W (JSON: diagnostic détaillé d'indexation)

    # X-AB: Editorial Audit
    editorial_audit_score: float = 0.0            # X (score 1-10)
    editorial_audit_date: str = ""                # Y (timestamp)
    editorial_verdict: str = ""                   # Z (PASSED, BLOCKED, REVIEW_REQUIRED)
    blocking_issues_count: int = 0                # AA (count of blocking issues)
    editorial_audit_report_url: str = ""          # AB (path to report markdown)

    # Metadata (non-sheet)
    row_index: int = 0                            # Row number in sheet (for updates)

    def to_list(self) -> list:
        """Convertit en liste pour écriture Google Sheets (28 colonnes A-AB)."""
        return [
            self.site_slug,                                                       # A
            self.blogpost_url,                                                   # B
            self.main_keyword,                                                   # C
            self.title,                                                          # D
            self.post_type,                                                      # E
            self.action_blogpost,                                                # F
            self.status,                                                         # G
            self.audit_gsc,                                                      # H
            self.audit_serp,                                                     # I
            self.impressions_30d,                                                # J
            self.clicks_30d,                                                     # K
            self.ctr_30d,                                                        # L
            self.people_also_ask,                                                # M
            self.secondary_keywords,                                             # N
            self.new_h1_title,                                                   # O
            self.new_h2_titles,                                                  # P
            self.word_count_before,                                              # Q
            self.images_count,                                                   # R
            self.internal_links_count,                                           # S
            "YES" if self.cannibalization_flag else "NO",                         # T
            self.cannibalization_urls,                                            # U
            self.error_message,                                                  # V
            self.index_diagnostic,                                               # W
            str(self.editorial_audit_score) if self.editorial_audit_score else "", # X
            self.editorial_audit_date,                                           # Y
            self.editorial_verdict,                                              # Z
            str(self.blocking_issues_count) if self.blocking_issues_count else "", # AA
            self.editorial_audit_report_url,                                     # AB
        ]

    @staticmethod
    def from_list(row: list, row_index: int = 0) -> "RefreshAuditRow":
        """Crée une instance à partir d'une liste (28 colonnes A-AB du sheet)."""
        return RefreshAuditRow(
            site_slug=row[0] if len(row) > 0 else "",                             # A
            blogpost_url=row[1] if len(row) > 1 else "",                         # B
            main_keyword=row[2] if len(row) > 2 else "",                         # C
            title=row[3] if len(row) > 3 else "",                                # D
            post_type=row[4] if len(row) > 4 else "",                            # E
            action_blogpost=row[5] if len(row) > 5 else "",                      # F
            status=row[6] if len(row) > 6 else "",                               # G
            audit_gsc=row[7] if len(row) > 7 else "",                            # H
            audit_serp=row[8] if len(row) > 8 else "",                           # I
            impressions_30d=_safe_int(row[9]) if len(row) > 9 else 0,            # J
            clicks_30d=_safe_int(row[10]) if len(row) > 10 else 0,               # K
            ctr_30d=_safe_float(row[11]) if len(row) > 11 else 0.0,              # L
            people_also_ask=row[12] if len(row) > 12 else "",                    # M
            secondary_keywords=row[13] if len(row) > 13 else "",                 # N
            new_h1_title=row[14] if len(row) > 14 else "",                       # O
            new_h2_titles=row[15] if len(row) > 15 else "",                      # P
            word_count_before=_safe_int(row[16]) if len(row) > 16 else 0,        # Q
            images_count=_safe_int(row[17]) if len(row) > 17 else 0,             # R
            internal_links_count=_safe_int(row[18]) if len(row) > 18 else 0,     # S
            cannibalization_flag=(row[19] == "YES") if len(row) > 19 else False, # T
            cannibalization_urls=row[20] if len(row) > 20 else "",               # U
            error_message=row[21] if len(row) > 21 else "",                      # V
            index_diagnostic=row[22] if len(row) > 22 else "",                   # W
            editorial_audit_score=_safe_float(row[23]) if len(row) > 23 else 0.0, # X
            editorial_audit_date=row[24] if len(row) > 24 else "",               # Y
            editorial_verdict=row[25] if len(row) > 25 else "",                  # Z
            blocking_issues_count=_safe_int(row[26]) if len(row) > 26 else 0,    # AA
            editorial_audit_report_url=row[27] if len(row) > 27 else "",         # AB
            row_index=row_index,
        )


# =============================================================================
# Superprof Ressources — modèle d'audit en mémoire
# =============================================================================
# NOTE: Pas de mapping vers les colonnes A-E de l'onglet "⬆️ Growing".
# `Growing` est lu en read-only (URLs uniquement). Les perfs GSC sont écrites
# dans un onglet séparé `GSC_Perfs` géré indépendamment.

@dataclass
class SuperprofAuditRow:
    """
    Audit en mémoire d'une URL Superprof Ressources.

    Cette dataclass sert :
    - de structure de travail pour le pipeline (audit GSC, decision tree, refresh)
    - de schéma pour les fichiers JSON dans `_shared/outputs/superprof.fr-ressources/audit/`

    Elle n'est PAS mappée sur les colonnes de l'onglet `Growing` (lecture seule).
    Elle alimente l'onglet séparé `GSC_Perfs` via `to_gsc_perfs_row()`.
    """

    # URL source (extraite de Growing)
    url: str = ""
    main_keyword: str = ""           # depuis Growing col B (à titre indicatif)

    # GSC metrics — fenêtre 30 jours
    impressions_30d: int = 0
    clicks_30d: int = 0
    ctr_30d: float = 0.0
    position_30d: float = 0.0

    # GSC metrics — fenêtre 12 mois
    impressions_12m: int = 0
    clicks_12m: int = 0
    position_12m: float = 0.0

    # Top queries (récupérées via dimension=query)
    top_query_1: str = ""
    top_query_2: str = ""
    top_query_3: str = ""

    # Métadonnées
    last_gsc_refresh: str = ""       # ISO timestamp ou "NO_DATA"
    error_message: str = ""

    # Horodatage du process pipeline (benchmark_runner)
    process_started_at: str = ""     # ISO "YYYY-MM-DD HH:MM:SS" — début fetch
    process_ended_at: str = ""       # ISO "YYYY-MM-DD HH:MM:SS" — fin livraison

    # Source row (1-indexed dans Growing) — utile pour traçabilité
    growing_row_index: int = 0

    def to_gsc_perfs_row(self) -> list:
        """
        Convertit en liste pour écriture dans l'onglet GSC_Perfs.

        Schéma 15 colonnes (validé) :
        A: URL
        B: Main Keyword
        C: Impressions 30d
        D: Clicks 30d
        E: CTR 30d (%)
        F: Position Avg 30d
        G: Impressions 12m
        H: Clicks 12m
        I: Position 12m
        J: Top Query 1
        K: Top Query 2
        L: Top Query 3
        M: Last GSC Refresh
        N: Process Started At
        O: Process Ended At
        """
        return [
            self.url,
            self.main_keyword,
            self.impressions_30d,
            self.clicks_30d,
            round(self.ctr_30d * 100, 2) if self.ctr_30d else 0,  # affichage en %
            round(self.position_30d, 1) if self.position_30d else 0,
            self.impressions_12m,
            self.clicks_12m,
            round(self.position_12m, 1) if self.position_12m else 0,
            self.top_query_1,
            self.top_query_2,
            self.top_query_3,
            self.last_gsc_refresh,
            self.process_started_at,
            self.process_ended_at,
        ]

    @staticmethod
    def gsc_perfs_headers() -> list:
        """En-têtes (Title Case) de l'onglet GSC_Perfs — single source of truth."""
        return [
            "URL",
            "Main Keyword",
            "Impressions 30d",
            "Clicks 30d",
            "CTR 30d (%)",
            "Position Avg 30d",
            "Impressions 12m",
            "Clicks 12m",
            "Position 12m",
            "Top Query 1",
            "Top Query 2",
            "Top Query 3",
            "Last GSC Refresh",
            "Process Started At",
            "Process Ended At",
        ]

    def to_dict(self) -> dict:
        """Sérialise pour dump JSON local."""
        return {
            "url": self.url,
            "main_keyword": self.main_keyword,
            "growing_row_index": self.growing_row_index,
            "gsc_30d": {
                "impressions": self.impressions_30d,
                "clicks": self.clicks_30d,
                "ctr": self.ctr_30d,
                "position": self.position_30d,
            },
            "gsc_12m": {
                "impressions": self.impressions_12m,
                "clicks": self.clicks_12m,
                "position": self.position_12m,
            },
            "top_queries": [self.top_query_1, self.top_query_2, self.top_query_3],
            "last_gsc_refresh": self.last_gsc_refresh,
            "process_started_at": self.process_started_at,
            "process_ended_at": self.process_ended_at,
            "error_message": self.error_message,
        }
