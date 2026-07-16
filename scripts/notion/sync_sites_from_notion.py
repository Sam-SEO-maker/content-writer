"""Sync unidirectionnel : base Notion « Config blogs » → catalogue Superprof.

Phase 6d (révisé 2026-07-16). La base Notion « Config blogs Superprof dans le
monde » est un annuaire HUMAIN : `Pays` (libellé), `URL du blog`, `Région`,
`Drapeau` (emoji). Elle NE porte PAS les champs machine (tenant_id, gsc_property,
langue) — ceux-ci vivent déjà, plus complets, dans le catalogue généré
`_shared/config/superprof_blogs_catalog.json` (source machine).

Rôle du sync (décision 2026-07-16) : **enrichir le catalogue** avec les libellés
humains de Notion, en joignant par `URL du blog` ↔ `gsc_property`. Notion devient
la source des libellés (country_label / region / flag) ; le catalogue reste la
source machine et le pilote de l'onboarding (`cw tenant init`). Le registre
runtime `sites.json` n'est PAS touché ici (Notion ne porte pas ses champs).

API Notion 2025-09-03 : une "database" (conteneur, ID de l'URL) référence un ou
plusieurs `data_source`. On résout d'abord le data_source_id via le conteneur,
puis on requête `/v1/data_sources/{id}/query` (l'ancien `/databases/{id}/query`
ne fonctionne plus).

Usage :
    python -m scripts.notion.sync_sites_from_notion --dump-schema
    python -m scripts.notion.sync_sites_from_notion            # dry-run (diff)
    python -m scripts.notion.sync_sites_from_notion --apply     # écrit le catalogue
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

# Conteneur database « Config blogs Superprof dans le monde » (ID de l'URL Notion).
CONFIG_PAYS_DB_ID = "b4f6b521eeb14e29a56a527febd9d278"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_PATH = _PROJECT_ROOT / "_shared" / "config" / "superprof_blogs_catalog.json"

# Mapping propriété Notion → champ d'enrichissement du catalogue.
PROPERTY_MAP = {
    "Pays": "country_label",
    "Région": "region",
    "Drapeau": "flag",
    "URL du blog": "_url",  # clé de jointure (non stockée telle quelle)
}


def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_token() -> str:
    return os.environ.get("NOTION_TOKEN", "").strip()


def resolve_data_source_id(token: str, db_id: str = CONFIG_PAYS_DB_ID) -> str:
    """Résout le data_source_id depuis le conteneur database (API 2025-09-03)."""
    resp = requests.get(f"{NOTION_API}/databases/{db_id}",
                        headers=notion_headers(token), timeout=30)
    data = resp.json()
    if data.get("object") == "error":
        raise RuntimeError(f"Notion: {data.get('message', 'erreur inconnue')}")
    sources = data.get("data_sources") or []
    if not sources:
        raise RuntimeError("Aucun data_source dans ce conteneur database.")
    return sources[0]["id"]


def fetch_schema(token: str) -> dict:
    ds_id = resolve_data_source_id(token)
    resp = requests.get(f"{NOTION_API}/data_sources/{ds_id}",
                        headers=notion_headers(token), timeout=30)
    data = resp.json()
    if data.get("object") == "error":
        raise RuntimeError(f"Notion: {data.get('message', 'erreur inconnue')}")
    return data.get("properties", {})


def fetch_all_rows(token: str) -> list[dict]:
    """Toutes les lignes de la base config pays (pagination)."""
    ds_id = resolve_data_source_id(token)
    rows, payload = [], {"page_size": 100}
    while True:
        resp = requests.post(f"{NOTION_API}/data_sources/{ds_id}/query",
                             headers=notion_headers(token), json=payload, timeout=30)
        data = resp.json()
        if data.get("object") == "error":
            raise RuntimeError(f"Notion: {data.get('message', 'erreur inconnue')}")
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return rows


def _plain_value(prop: dict):
    t = prop.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in prop.get(t, []))
    if t == "select":
        sel = prop.get("select")
        return sel.get("name") if sel else None
    if t == "url":
        return prop.get("url")
    return None


def _norm_url(url: Optional[str]) -> str:
    """Normalise une URL pour la jointure (minuscules, un seul slash final)."""
    if not url:
        return ""
    return url.strip().lower().rstrip("/") + "/"


def row_to_labels(row: dict) -> Optional[dict]:
    """Extrait {country_label, region, flag, _url} d'une ligne Notion."""
    props = row.get("properties", {})
    out = {}
    for notion_name, target in PROPERTY_MAP.items():
        if notion_name in props:
            val = _plain_value(props[notion_name])
            if val:
                out[target] = val
    return out if out.get("_url") else None


def enrich_catalog(catalog: dict, notion_rows: list[dict]) -> tuple[dict, list[str], list[str]]:
    """Enrichit les entrées du catalogue avec les libellés Notion (join par URL).

    Retourne (catalogue, changements, non_appariés_notion).
    """
    # Index catalogue par gsc_property normalisée.
    entries = catalog.get("ressources_sites", []) + catalog.get("blogs", [])
    by_url = {_norm_url(e.get("gsc_property")): e for e in entries}

    changes, unmatched = [], []
    for row in notion_rows:
        labels = row_to_labels(row)
        if not labels:
            continue
        url = _norm_url(labels.pop("_url"))
        entry = by_url.get(url)
        if not entry:
            unmatched.append(f"{labels.get('country_label', '?')} ({url})")
            continue
        for k, v in labels.items():
            if entry.get(k) != v:
                changes.append(f"~ {entry['tenant_id']}.{k} = {v!r}")
                entry[k] = v
    return catalog, changes, unmatched


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Sync Notion config pays → catalogue")
    ap.add_argument("--apply", action="store_true", help="Écrit le catalogue (sinon dry-run).")
    ap.add_argument("--dump-schema", action="store_true", help="Affiche les propriétés Notion et sort.")
    args = ap.parse_args()

    token = get_token()
    if not token:
        print("[SYNC] NOTION_TOKEN absent — abandon.")
        return 2

    try:
        if args.dump_schema:
            schema = fetch_schema(token)
            print("[SYNC] Propriétés de la base « Config blogs » :")
            for name, meta in schema.items():
                mapped = PROPERTY_MAP.get(name, "— (non mappé)")
                print(f"  • {name!r} ({meta.get('type')}) → {mapped}")
            return 0
        rows = fetch_all_rows(token)
    except RuntimeError as e:
        print(f"[SYNC] {e} — abandon.")
        return 2

    if not CATALOG_PATH.exists():
        print(f"[SYNC] Catalogue absent ({CATALOG_PATH}) — générer d'abord "
              "via build_superprof_catalog. Abandon.")
        return 2

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog, changes, unmatched = enrich_catalog(catalog, rows)

    print(f"[SYNC] {len(rows)} ligne(s) Notion lues.")
    if unmatched:
        print(f"[SYNC] {len(unmatched)} ligne(s) Notion sans correspondance catalogue "
              "(non enrichies) :")
        for u in unmatched:
            print(f"   ⚠ {u}")

    if not changes:
        print("[SYNC] Aucun enrichissement — catalogue déjà à jour.")
        return 0

    print(f"[SYNC] {len(changes)} enrichissement(s) :")
    for c in changes[:40]:
        print(f"   {c}")
    if len(changes) > 40:
        print(f"   … (+{len(changes) - 40})")

    if not args.apply:
        print("\n[SYNC] Dry-run — relancer avec --apply pour écrire le catalogue.")
        return 0

    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(f"\n[SYNC] ✓ catalogue enrichi ({CATALOG_PATH}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
