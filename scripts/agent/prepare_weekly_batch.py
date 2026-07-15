"""Prépare un lot hebdomadaire d'URLs Superprof Ressources pour la génération (Phase 1).

Pour chaque URL d'une liste fournie :
1. Récupère main_keyword / secondary_keyword / status depuis l'onglet `New Growing List`
   Si absents, les découvre via GSC (12 mois) et les réinjecte dans le sheet (colonnes B/C).
2. Récupère le post_content via l'API WordPress REST (PAS de scraping)
3. Audit GSC (30j + 12 mois + top 3 queries) → écrit impressions_12m/clicks_12m
   directement dans `New Growing List` (colonnes D/E) — pas de passage par `GSC_Perfs`.
4. Écrit le bundle de contexte `_shared/context/{slug}/` prêt pour la Phase 2 (génération)

Les URLs en status "Redirection 301" (ou tout status != "A faire") sont ignorées.

Usage:
    python -m scripts.agent.prepare_weekly_batch <fichier_urls.txt>
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from _shared.core.models.sheets_models import RefreshAuditRow
from scripts.agent.orchestrator import RefreshOrchestrator

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("prepare_weekly_batch")
for noisy in ("googleapiclient", "google", "urllib3", "scripts.scraping.content_extractor"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

BLOG_ID = "superprof-ressources"
# Onglet + colonne de statut lus depuis la config du tenant (§4bis-A) ; repli sur
# les littéraux historiques si le bloc `sheets` est absent.
from _shared.core.sheets_config import get_primary_tab_name, get_status_col
NGL_SHEET = get_primary_tab_name(BLOG_ID, default="New Growing List")
NGL_STATUS_COL = get_status_col(BLOG_ID, default="F")
SKIP_STATUSES = {"redirection 301"}


def _norm(u: str) -> str:
    return (u or "").strip().rstrip("/").lower()


def load_url_list(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def read_ngl_metadata(sheets_client, wanted: set[str]) -> dict[str, dict]:
    """Retourne {url_norm: {url, main_kw, secondary_kw, status, row_index}} pour les URLs voulues."""
    data = sheets_client._read_sheet(NGL_SHEET)
    out: dict[str, dict] = {}
    for i, row in enumerate(data[1:], start=2):  # ligne 1 = header
        if not row:
            continue
        u = _norm(row[0])
        if u not in wanted:
            continue
        out[u] = {
            "url": row[0].strip(),
            "main_keyword": (row[1].strip() if len(row) > 1 else ""),
            "secondary_keyword": (row[2].strip() if len(row) > 2 else ""),
            "status": (row[5].strip() if len(row) > 5 else ""),
            "row_index": i,
        }
    return out


def discover_and_write_keywords(gsc_analyzer, sheets_api, url: str, row_index: int, info: dict) -> None:
    """Découvre main_keyword/secondary_keyword via GSC (12m) si absents et les écrit dans le sheet."""
    from scripts.utils.keyword_discovery_growing_list import (
        write_keyword,
        write_secondary_keyword,
        select_secondary_keyword,
    )

    if not info["main_keyword"]:
        main_kw = gsc_analyzer.fetch_top_keyword_12m(url)
        if main_kw:
            write_keyword(sheets_api, row_index, main_kw)
            info["main_keyword"] = main_kw
            logger.info("        + main_keyword découvert et écrit: '%s'", main_kw)

    if info["main_keyword"] and not info["secondary_keyword"]:
        candidates = gsc_analyzer.fetch_top_keywords_12m(url, limit=20)
        candidates = [c for c in candidates if c["query"].lower() != info["main_keyword"].lower()]
        secondary_kw = select_secondary_keyword(url, info["main_keyword"], candidates)
        if secondary_kw:
            write_secondary_keyword(sheets_api, row_index, secondary_kw)
            info["secondary_keyword"] = secondary_kw
            logger.info("        + secondary_keyword découvert et écrit: '%s'", secondary_kw)


def write_gsc_12m_metrics(sheets_api, row_index: int, impressions_12m: int, clicks_12m: int) -> None:
    """Écrit impressions_12m (col D) et clicks_12m (col E) dans New Growing List."""
    sheets_api.spreadsheets().values().update(
        spreadsheetId=os.environ["SPREADSHEET_ID_SUPERPROF"],
        range=f"'{NGL_SHEET}'!D{row_index}:E{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[impressions_12m, clicks_12m]]},
    ).execute()


def mark_ngl_status(sheets_api, row_index: int, status: str) -> None:
    """Écrit le statut éditorial (col F) dans New Growing List.

    À appeler après génération réussie du contenu refreshé (status="Rédigé"),
    ou pour toute autre transition (Draft in WP, Publié).
    """
    sheets_api.spreadsheets().values().update(
        spreadsheetId=os.environ["SPREADSHEET_ID_SUPERPROF"],
        range=f"'{NGL_SHEET}'!{NGL_STATUS_COL}{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[status]]},
    ).execute()


def mark_ngl_status_by_url(url: str, status: str) -> bool:
    """Trouve la ligne New Growing List correspondant à `url` et écrit son statut.

    Retourne True si l'URL a été trouvée et mise à jour, False sinon.
    Usage typique en fin de génération (Phase 2) :
        mark_ngl_status_by_url(url, "Rédigé")
    """
    from scripts.audit.superprof_gsc_audit import _build_clients

    sheets_api, _ = _build_clients()
    data = sheets_api.spreadsheets().values().get(
        spreadsheetId=os.environ["SPREADSHEET_ID_SUPERPROF"],
        range=f"'{NGL_SHEET}'!A:A",
    ).execute().get("values", [])

    target = _norm(url)
    for i, row in enumerate(data, start=1):
        if row and _norm(row[0]) == target:
            mark_ngl_status(sheets_api, i, status)
            return True
    return False


def main() -> int:
    load_dotenv()
    if len(sys.argv) < 2:
        logger.error("Usage: python -m scripts.agent.prepare_weekly_batch <fichier_urls.txt>")
        return 2

    url_file = Path(sys.argv[1])
    urls = load_url_list(url_file)
    logger.info("Lot: %d URLs depuis %s", len(urls), url_file)

    spreadsheet_id = os.environ["SPREADSHEET_ID_SUPERPROF"]
    orchestrator = RefreshOrchestrator(base_path=Path.cwd(), spreadsheet_id=spreadsheet_id)

    meta = read_ngl_metadata(orchestrator.sheets_client, {_norm(u) for u in urls})

    # GSC clients
    from scripts.audit.superprof_gsc_audit import _build_clients, audit_url
    from scripts.audit.gsc_analyzer import GSCAnalyzer

    sheets_api, gsc_api = _build_clients()
    gsc_analyzer = GSCAnalyzer(gsc_property="https://www.superprof.fr/ressources/")

    prepared, skipped, failed = [], [], []

    for i, url in enumerate(urls, start=1):
        n = _norm(url)
        info = meta.get(n)
        if info is None:
            logger.warning("[%2d/%d] ABSENT de '%s' — ignoré: %s", i, len(urls), NGL_SHEET, url)
            skipped.append((url, "not_in_sheet"))
            continue
        if info["status"].lower() in SKIP_STATUSES:
            logger.info("[%2d/%d] SKIP (status=%s): %s", i, len(urls), info["status"], url)
            skipped.append((url, info["status"]))
            continue

        logger.info("[%2d/%d] %s", i, len(urls), url)
        try:
            # 0. Découverte + écriture auto des mots-clés manquants (GSC 12m)
            try:
                discover_and_write_keywords(gsc_analyzer, sheets_api, url, info["row_index"], info)
            except Exception as kw_err:  # noqa: BLE001
                logger.warning("        ⚠ découverte mots-clés échouée: %s", str(kw_err)[:120])

            # 1. post_content via WP REST API
            extraction = orchestrator._fetch_html(url, BLOG_ID)
            html = extraction.get("clean_body") or ""
            method = extraction["extraction_metadata"].get("method_used", "?")
            if not html:
                logger.warning("        ✗ contenu vide (method=%s)", method)
                failed.append((url, f"empty_content_{method}"))
                continue
            if not method.startswith("wp_api"):
                logger.warning("        ⚠ méthode=%s (WP API attendue)", method)

            # 2. GSC audit (30j + 12m) → écriture directe dans New Growing List (D/E)
            try:
                audit = audit_url(gsc_api, info["row_index"], url, info["main_keyword"])
                metrics = {
                    "impressions_30d": audit.impressions_30d,
                    "clicks_30d": audit.clicks_30d,
                    "ctr_30d": audit.ctr_30d,
                }
                paa = " | ".join(q for q in [audit.top_query_1, audit.top_query_2, audit.top_query_3] if q)
                try:
                    write_gsc_12m_metrics(sheets_api, info["row_index"], audit.impressions_12m, audit.clicks_12m)
                    logger.info(
                        "        + 12m écrit (D/E): impressions=%s clicks=%s",
                        audit.impressions_12m, audit.clicks_12m,
                    )
                except Exception as write_err:  # noqa: BLE001
                    logger.warning("        ⚠ écriture 12m (D/E) échouée: %s", str(write_err)[:120])
            except Exception as gsc_err:  # noqa: BLE001
                logger.warning("        ⚠ GSC/upsert échoué: %s", str(gsc_err)[:120])
                metrics = {"impressions_30d": 0, "clicks_30d": 0, "ctr_30d": 0.0}
                paa = ""

            # 3. Context bundle pour la Phase 2
            row = RefreshAuditRow(
                blog_id=BLOG_ID,
                blogpost_url=url,
                main_keyword=info["main_keyword"],
                title="",
                post_type="",
                secondary_keywords=info["secondary_keyword"],
                people_also_ask=paa,
                impressions_30d=metrics["impressions_30d"],
                clicks_30d=metrics["clicks_30d"],
                ctr_30d=metrics["ctr_30d"],
            )
            ctx_dir = orchestrator._prepare_context_for_claude_code(
                original_html=html,
                action="FULL_REFRESH",
                row=row,
                extraction_result=extraction,
            )
            wc = extraction["extraction_metadata"].get("word_count", 0)
            logger.info(
                "        ✓ %s | %sw | imp30=%s | ctx=%s",
                method, wc, metrics["impressions_30d"], ctx_dir,
            )
            prepared.append(url)
        except Exception as exc:  # noqa: BLE001
            logger.exception("        ✗ échec: %s", str(exc)[:160])
            failed.append((url, str(exc)[:160]))

    logger.info("\n=== RÉSUMÉ ===")
    logger.info("Préparés : %d", len(prepared))
    logger.info("Ignorés  : %d  %s", len(skipped), [s[1] for s in skipped])
    logger.info("Échecs   : %d", len(failed))
    for u, e in failed:
        logger.info("  - %s :: %s", u, e)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
