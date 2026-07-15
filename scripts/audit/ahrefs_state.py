"""
État des lieux SEO via Ahrefs → Google Sheets.

Pull les KW positionnés (Ahrefs site-explorer-organic-keywords),
les groupe par catégorie/page selon le slug, et pousse 3 onglets
dans une Google Sheet dédiée par site.

Usage:
    from scripts.audit.ahrefs_state import run_ahrefs_state
    run_ahrefs_state("superprof-ressources", dry_run=False)
"""

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from scripts.seo.ahrefs_client import AhrefsClient
from scripts.sheets.sheets_client import SheetsClient


# Mapping des en-têtes CSV Ahrefs (export Site Explorer → Organic keywords)
# vers nos clés internes. Tolérant à la casse / variantes.
CSV_HEADER_ALIASES = {
    "keyword": ["keyword", "mot-clé", "mot cle"],
    "volume": ["volume"],
    "cpc": ["cpc"],
    "kd": ["kd", "keyword difficulty", "difficulté"],
    "position": ["current position", "position", "current top position"],
    "url": ["current url", "url", "current top url"],
    "traffic": ["traffic", "current organic traffic", "organic traffic"],
    "serp_features": ["serp features", "current serp features"],
}


def _normalize_header(h: str) -> str:
    return h.strip().lower().lstrip("\ufeff")


def _build_header_map(fieldnames: list[str]) -> dict[str, str]:
    """Retourne {clé_interne: nom_colonne_csv} en matchant les alias."""
    norm = {_normalize_header(f): f for f in fieldnames}
    out: dict[str, str] = {}
    for key, aliases in CSV_HEADER_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                out[key] = norm[alias]
                break
    return out


def _to_int(v) -> int:
    if v is None or v == "":
        return 0
    try:
        return int(float(str(v).replace(",", ".").replace(" ", "")))
    except Exception:
        return 0


def _to_float(v) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except Exception:
        return 0.0


def load_keywords_from_csv(csv_path: Path) -> list[dict]:
    """
    Lit un export CSV Ahrefs (organic keywords) et retourne la liste normalisée.

    Auto-détecte le séparateur (`,` ou `;` ou `\\t`) et l'encodage (utf-8 / utf-16).
    """
    # Détecter encodage : Ahrefs UI exporte souvent en UTF-16 avec BOM
    raw = csv_path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig", errors="replace")

    # Sniff dialect
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except Exception:
        class _D(csv.Dialect):
            delimiter = ","
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        dialect = _D()

    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError(f"CSV vide ou en-têtes manquants: {csv_path}")

    hmap = _build_header_map(reader.fieldnames)
    missing = [k for k in ("keyword", "url", "position") if k not in hmap]
    if missing:
        raise ValueError(
            f"CSV {csv_path.name}: colonnes manquantes {missing}. "
            f"En-têtes détectés: {reader.fieldnames}"
        )

    rows: list[dict] = []
    for r in reader:
        rows.append({
            "keyword": (r.get(hmap["keyword"], "") or "").strip(),
            "volume": _to_int(r.get(hmap.get("volume", ""), 0)),
            "cpc": _to_float(r.get(hmap.get("cpc", ""), 0)),
            "kd": _to_int(r.get(hmap.get("kd", ""), 0)),
            "position": _to_int(r.get(hmap["position"], 0)),
            "url": (r.get(hmap["url"], "") or "").strip(),
            "traffic": _to_int(r.get(hmap.get("traffic", ""), 0)),
            "serp_features": (r.get(hmap.get("serp_features", ""), "") or "").strip(),
        })
    return rows

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "_shared" / "config" / "ahrefs_state.json"

RAW_HEADERS = [
    "keyword", "url", "position", "volume", "cpc", "kd",
    "traffic", "category", "subcategory", "serp_features", "snapshot_date",
]
BY_CAT_HEADERS = [
    "category", "nb_kw", "nb_kw_top10", "nb_kw_top3",
    "sum_traffic", "avg_position", "sum_volume", "top_5_kw",
]
BY_PAGE_HEADERS = [
    "url", "category", "nb_kw", "nb_kw_top10",
    "sum_traffic", "avg_position", "top_kw", "top_kw_position",
]

SHEET_RAW = "Ahrefs_KW_Raw"
SHEET_BY_CAT = "Ahrefs_By_Category"
SHEET_BY_PAGE = "Ahrefs_By_Page"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def categorize(url: str, cfg: dict) -> tuple[str, str]:
    """Retourne (category, subcategory) depuis l'URL selon la config du site."""
    if not url:
        return ("(unknown)", "")

    path = urlparse(url).path or "/"
    ctype = cfg.get("type")

    if ctype == "regex":
        m = re.match(cfg["pattern"], path)
        if m:
            cat = m.group(1) or "(home)"
            sub = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            return (cat, sub or "")
        return ("(home)" if path == "/" else "Autres", "")

    if ctype == "prefix_rules":
        slug = path.strip("/").split("/")[0] if path != "/" else ""
        if not slug and path == "/":
            return ("(home)", "")
        for rule in cfg.get("rules", []):
            kind = rule.get("kind", "slug_prefix")
            needle = rule["match"]
            if kind == "path_prefix":
                if path.startswith(needle):
                    return (rule["category"], "")
            elif kind == "slug_contains":
                if needle in slug:
                    return (rule["category"], slug)
            else:  # slug_prefix
                if slug.startswith(needle):
                    sub = slug[len(needle):] if rule.get("extract_subcategory") else ""
                    return (rule["category"], sub)
        return (cfg.get("fallback_category", "Autres"), slug)

    return ("(unknown)", "")


def aggregate_by_category(rows: list[dict]) -> list[list]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["category"]].append(r)

    out = []
    for cat, items in sorted(groups.items(), key=lambda kv: -sum(i["traffic"] for i in kv[1])):
        nb = len(items)
        nb_top10 = sum(1 for i in items if 0 < i["position"] <= 10)
        nb_top3 = sum(1 for i in items if 0 < i["position"] <= 3)
        sum_traf = sum(i["traffic"] for i in items)
        sum_vol = sum(i["volume"] for i in items)
        positions = [i["position"] for i in items if i["position"] > 0]
        avg_pos = round(sum(positions) / len(positions), 2) if positions else 0
        top5 = sorted(items, key=lambda x: -x["traffic"])[:5]
        top5_str = " | ".join(f"{i['keyword']} (#{i['position']})" for i in top5)
        out.append([cat, nb, nb_top10, nb_top3, sum_traf, avg_pos, sum_vol, top5_str])
    return out


def aggregate_by_page(rows: list[dict]) -> list[list]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["url"]].append(r)

    out = []
    for url, items in sorted(groups.items(), key=lambda kv: -sum(i["traffic"] for i in kv[1])):
        nb = len(items)
        nb_top10 = sum(1 for i in items if 0 < i["position"] <= 10)
        sum_traf = sum(i["traffic"] for i in items)
        positions = [i["position"] for i in items if i["position"] > 0]
        avg_pos = round(sum(positions) / len(positions), 2) if positions else 0
        top = max(items, key=lambda x: x["traffic"])
        cat = items[0]["category"]
        out.append([url, cat, nb, nb_top10, sum_traf, avg_pos, top["keyword"], top["position"]])
    return out


def _ensure_tab(service, spreadsheet_id: str, title: str):
    """Crée l'onglet s'il n'existe pas."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if title in existing:
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()


def _write_tab(service, spreadsheet_id: str, title: str, headers: list[str], rows: list[list]):
    _ensure_tab(service, spreadsheet_id, title)
    # Clear
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"{title}!A:Z",
        body={},
    ).execute()
    # Write
    values = [headers] + rows
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def run_ahrefs_state(
    site_id: str,
    months: Optional[int] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    from_csv: Optional[str] = None,
) -> dict:
    """
    Exécute l'état des lieux Ahrefs pour un site.

    Returns: dict avec stats (nb_kw, nb_categories, nb_pages, output_path)
    """
    config = load_config()
    site_cfg = config["sites"].get(site_id)
    if not site_cfg:
        raise ValueError(f"site_id inconnu: {site_id} (dispo: {list(config['sites'])})")

    defaults = config.get("defaults", {})
    months = months or defaults.get("months", 3)
    limit = limit or defaults.get("limit", 10000)
    country = defaults.get("country", "fr")
    mode = defaults.get("mode", "prefix")

    target = site_cfg["ahrefs_target"]
    spreadsheet_id = site_cfg["spreadsheet_id"]
    cat_cfg = site_cfg["categorization"]

    # 1. Fetch (CSV ou API)
    if from_csv:
        csv_path = Path(from_csv)
        if not csv_path.is_absolute():
            csv_path = REPO_ROOT / csv_path
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV introuvable: {csv_path}")
        print(f"[ahrefs-state] {site_id}: lecture CSV {csv_path}")
        raw = load_keywords_from_csv(csv_path)
    else:
        print(f"[ahrefs-state] {site_id}: fetch API (target={target}, mode={mode}, limit={limit})")
        client = AhrefsClient()
        if not client.available:
            raise RuntimeError("AhrefsClient non configuré (AHREFS_API_TOKEN manquant) — utilise --from-csv")
        raw = client.get_organic_keywords(target=target, country=country, mode=mode, limit=limit)

    print(f"[ahrefs-state] {len(raw)} keywords récupérés")

    if not raw:
        print("[ahrefs-state] ⚠ Aucun résultat — arrêt")
        return {"nb_kw": 0, "nb_categories": 0, "nb_pages": 0}

    # 2. Categorize
    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    for r in raw:
        cat, sub = categorize(r["url"], cat_cfg)
        rows.append({**r, "category": cat, "subcategory": sub, "snapshot_date": snapshot})

    # 3. Aggregate
    by_cat = aggregate_by_category(rows)
    by_page = aggregate_by_page(rows)
    print(f"[ahrefs-state] {len(by_cat)} catégories, {len(by_page)} pages")

    # 4. Build raw rows
    raw_values = [
        [r["keyword"], r["url"], r["position"], r["volume"], r["cpc"], r["kd"],
         r["traffic"], r["category"], r["subcategory"], r["serp_features"], r["snapshot_date"]]
        for r in rows
    ]

    # 5. Dump local backup
    from _shared.core.tenant_paths import TenantPaths
    out_dir = TenantPaths(base_path=REPO_ROOT).output_dir(site_id) / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ahrefs_state_{snapshot}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "site_id": site_id,
            "snapshot_date": snapshot,
            "nb_kw": len(rows),
            "nb_categories": len(by_cat),
            "nb_pages": len(by_page),
            "rows": rows,
        }, f, ensure_ascii=False, indent=2)
    print(f"[ahrefs-state] dump local: {out_path}")

    if dry_run:
        print("[ahrefs-state] DRY-RUN — pas de push Sheets")
        return {"nb_kw": len(rows), "nb_categories": len(by_cat), "nb_pages": len(by_page), "output_path": str(out_path)}

    # 6. Push Sheets
    print(f"[ahrefs-state] push → spreadsheet {spreadsheet_id}")
    sheets = SheetsClient(spreadsheet_id)
    if not sheets._sheets_service:
        raise RuntimeError("SheetsClient: API directe indisponible (GOOGLE_SA_PATH ?)")
    svc = sheets._sheets_service

    _write_tab(svc, spreadsheet_id, SHEET_RAW, RAW_HEADERS, raw_values)
    _write_tab(svc, spreadsheet_id, SHEET_BY_CAT, BY_CAT_HEADERS, by_cat)
    _write_tab(svc, spreadsheet_id, SHEET_BY_PAGE, BY_PAGE_HEADERS, by_page)
    print(f"[ahrefs-state] ✓ 3 onglets mis à jour")

    return {
        "nb_kw": len(rows),
        "nb_categories": len(by_cat),
        "nb_pages": len(by_page),
        "output_path": str(out_path),
        "spreadsheet_id": spreadsheet_id,
    }
