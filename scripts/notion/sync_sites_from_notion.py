"""Sync unidirectionnel : page Notion « config pays » → `_shared/config/sites.json`.

Phase 6d. La page Notion (base de données) est la source éditée par les humains ;
`sites.json` en est la **projection machine**. Le moteur ne lit JAMAIS Notion au
runtime — il lit `sites.json`. Ce script est le seul pont, et il est
**unidirectionnel** (Notion → sites.json), jamais l'inverse.

Principes de sûreté :
- **Merge additif** : on ne réécrit pas `sites.json` via une dataclass (ce qui
  perdrait les champs riches d'enseigna/superprof et la clé top-level
  `notion_refresh_tracker_db_id`). On charge le JSON brut, on met à jour/ajoute
  entrée par entrée en préservant tout champ existant non géré par Notion.
- **Dry-run par défaut** : `--apply` requis pour écrire.
- **Token invalide / absent → no-op** explicite (pas d'écrasement).

Le schéma exact de la base Notion n'étant pas figé, le mapping propriété Notion →
champ sites.json est déclaré dans `PROPERTY_MAP` et facilement ajustable. Au
premier run réel, `--dump-schema` affiche les propriétés réelles de la base pour
caler le mapping.

Usage :
    python -m scripts.notion.sync_sites_from_notion --dump-schema
    python -m scripts.notion.sync_sites_from_notion           # dry-run (diff)
    python -m scripts.notion.sync_sites_from_notion --apply    # écrit sites.json
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

# Base « config pays » (extrait de l'URL de la page Notion, cf. plan §Étape 6).
CONFIG_PAYS_DB_ID = "b4f6b521eeb14e29a56a527febd9d278"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SITES_JSON = _PROJECT_ROOT / "_shared" / "config" / "sites.json"

# Mapping propriété Notion → champ sites.json. Clés = noms de colonnes Notion
# (à confirmer via --dump-schema au 1er run). Valeurs = champ cible sites.json.
# `id` est OBLIGATOIRE (clé de merge) ; on tente plusieurs noms usuels.
PROPERTY_MAP = {
    "id": "id",
    "ID": "id",
    "tenant_id": "id",
    "Name": "name",
    "name": "name",
    "domain": "domain",
    "Domain": "domain",
    "gsc_property": "gsc_property",
    "GSC Property": "gsc_property",
    "url_base": "url_base",
    "language": "language",
    "active": "active",
    "subject_category": "subject_category",
    "content_type": "content_type",
    "ymyl_level": "ymyl_level",
    "registre": "registre",
}


def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_token() -> str:
    return os.environ.get("NOTION_TOKEN", "").strip()


def fetch_database_schema(token: str, db_id: str = CONFIG_PAYS_DB_ID) -> dict:
    """Retourne le dict `properties` de la base (ou {} + message d'erreur)."""
    resp = requests.get(f"{NOTION_API}/databases/{db_id}",
                        headers=notion_headers(token), timeout=30)
    data = resp.json()
    if data.get("object") == "error":
        raise RuntimeError(f"Notion: {data.get('message', 'erreur inconnue')}")
    return data.get("properties", {})


def fetch_all_rows(token: str, db_id: str = CONFIG_PAYS_DB_ID) -> list[dict]:
    """Récupère toutes les pages (lignes) de la base, avec pagination."""
    rows = []
    payload: dict = {"page_size": 100}
    while True:
        resp = requests.post(f"{NOTION_API}/databases/{db_id}/query",
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
    """Extrait la valeur scalaire d'une propriété Notion, quel que soit son type."""
    t = prop.get("type")
    if t == "title" or t == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get(t, []))
    if t == "select":
        sel = prop.get("select")
        return sel.get("name") if sel else None
    if t == "multi_select":
        return [x.get("name") for x in prop.get("multi_select", [])]
    if t == "checkbox":
        return prop.get("checkbox")
    if t == "url":
        return prop.get("url")
    if t == "number":
        return prop.get("number")
    if t == "email":
        return prop.get("email")
    if t == "phone_number":
        return prop.get("phone_number")
    return None


def row_to_site(row: dict) -> Optional[dict]:
    """Convertit une ligne Notion en dict partiel sites.json via PROPERTY_MAP.

    Retourne None si aucun `id` exploitable (ligne ignorée, loggée par l'appelant).
    """
    props = row.get("properties", {})
    site: dict = {}
    for notion_name, value in props.items():
        target = PROPERTY_MAP.get(notion_name)
        if not target:
            continue
        val = _plain_value(value)
        if val is None or val == "":
            continue
        site[target] = val
    return site if site.get("id") else None


def merge_into_sites(existing: dict, notion_sites: list[dict]) -> tuple[dict, list[str]]:
    """Merge additif des sites Notion dans le JSON existant. Préserve tout champ
    existant non fourni par Notion et les clés top-level.

    Retourne (nouveau_dict, journal_des_changements).
    """
    by_id = {s["id"]: s for s in existing.get("sites", [])}
    changes: list[str] = []

    for ns in notion_sites:
        sid = ns["id"]
        if sid in by_id:
            before = dict(by_id[sid])
            for k, v in ns.items():
                if by_id[sid].get(k) != v:
                    changes.append(f"~ {sid}.{k}: {before.get(k)!r} → {v!r}")
                    by_id[sid][k] = v
        else:
            by_id[sid] = ns
            changes.append(f"+ nouveau tenant '{sid}' ({', '.join(ns.keys())})")

    result = dict(existing)  # préserve notion_refresh_tracker_db_id etc.
    result["sites"] = list(by_id.values())
    return result, changes


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Sync Notion config pays → sites.json")
    ap.add_argument("--apply", action="store_true", help="Écrit sites.json (sinon dry-run).")
    ap.add_argument("--dump-schema", action="store_true",
                    help="Affiche les propriétés réelles de la base Notion et sort.")
    args = ap.parse_args()

    token = get_token()
    if not token:
        print("[SYNC] NOTION_TOKEN absent — abandon (aucune écriture).")
        return 2

    try:
        if args.dump_schema:
            schema = fetch_database_schema(token)
            print(f"[SYNC] Propriétés de la base {CONFIG_PAYS_DB_ID} :")
            for name, meta in schema.items():
                mapped = PROPERTY_MAP.get(name, "— (non mappé)")
                print(f"  • {name!r} ({meta.get('type')}) → {mapped}")
            return 0

        rows = fetch_all_rows(token)
    except RuntimeError as e:
        print(f"[SYNC] {e} — abandon (aucune écriture).")
        return 2

    notion_sites, ignored = [], 0
    for r in rows:
        site = row_to_site(r)
        if site:
            notion_sites.append(site)
        else:
            ignored += 1
    print(f"[SYNC] {len(notion_sites)} tenant(s) lus depuis Notion, {ignored} ligne(s) ignorée(s) (pas d'id).")

    existing = json.loads(SITES_JSON.read_text(encoding="utf-8")) if SITES_JSON.exists() else {"sites": []}
    merged, changes = merge_into_sites(existing, notion_sites)

    if not changes:
        print("[SYNC] Aucun changement — sites.json déjà à jour.")
        return 0

    print(f"[SYNC] {len(changes)} changement(s) :")
    for c in changes:
        print(f"   {c}")

    if not args.apply:
        print("\n[SYNC] Dry-run — relancer avec --apply pour écrire sites.json.")
        return 0

    SITES_JSON.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n[SYNC] ✓ sites.json mis à jour ({SITES_JSON}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
