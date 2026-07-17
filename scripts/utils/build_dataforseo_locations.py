"""Génère `_shared/config/dataforseo_locations.json` (country ISO -> location_name).

`serp_location` doit être un `location_name` exact de DataForSEO : une valeur
inventée fait échouer l'appel SERP. Ce script résout chaque pays du catalogue
Superprof contre /v3/serp/google/locations et fige le résultat, pour que
l'onboarding d'un tenant n'ait pas besoin du réseau.

Usage : python3 scripts/utils/build_dataforseo_locations.py [--dry-run]

Deux irrégularités traitées ici (vérifiées contre l'API, 2026-07-17) :
  - le catalogue écrit `UK`, qui n'est pas un code ISO : DataForSEO attend `GB` ;
  - HK / TW / PR n'existent pas en `location_type: Country` : repli sur la
    `Region` homonyme ("Hong Kong", "Taiwan", "Puerto Rico").
"""

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Exécutable directement (python3 scripts/utils/build_dataforseo_locations.py)
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
CATALOG_PATH = _PROJECT_ROOT / "_shared" / "config" / "superprof_blogs_catalog.json"
OUTPUT_PATH = _PROJECT_ROOT / "_shared" / "config" / "dataforseo_locations.json"
LOCATIONS_ENDPOINT = "https://api.dataforseo.com/v3/serp/google/locations"

# Le catalogue Superprof n'utilise pas l'ISO pour le Royaume-Uni.
ISO_ALIASES = {"UK": "GB"}


def _auth_header() -> str:
    from scripts.audit.serp_analyzer import DATAFORSEO_CREDENTIALS_PATH

    if not DATAFORSEO_CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Credentials DataForSEO introuvables : {DATAFORSEO_CREDENTIALS_PATH}"
        )
    creds = json.loads(DATAFORSEO_CREDENTIALS_PATH.read_text())
    if "dataforseo" in creds:
        creds = creds["dataforseo"]
    login, password = creds.get("login", ""), creds.get("password", "")
    if not login or not password:
        raise ValueError("login/password DataForSEO manquants.")
    return base64.b64encode(f"{login}:{password}".encode()).decode()


def fetch_locations(timeout: int = 180) -> list[dict]:
    req = urllib.request.Request(
        LOCATIONS_ENDPOINT, headers={"Authorization": f"Basic {_auth_header()}"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
    return payload["tasks"][0]["result"]


def build_map(items: list[dict], countries: list[str]) -> tuple[dict, list[str]]:
    """Résout chaque pays en location_name. Retourne (map, non résolus)."""
    by_country = {
        it["country_iso_code"]: it["location_name"]
        for it in items
        if it.get("location_type") == "Country" and it.get("country_iso_code")
    }
    # Territoires sans entrée "Country" : la Region racine porte le nom nu
    # ("Hong Kong"), les subdivisions sont suffixées ("Kowloon,Hong Kong").
    by_region: dict[str, str] = {}
    for it in items:
        iso = it.get("country_iso_code")
        if (
            it.get("location_type") == "Region"
            and iso
            and iso not in by_region
            and "," not in it["location_name"]
        ):
            by_region[iso] = it["location_name"]

    resolved, missing = {}, []
    for code in countries:
        iso = ISO_ALIASES.get(code, code)
        name = by_country.get(iso) or by_region.get(iso)
        if name:
            resolved[code] = name
        else:
            missing.append(code)
    return dict(sorted(resolved.items())), missing


def catalog_countries(catalog_path: Optional[Path] = None) -> list[str]:
    catalog = json.loads((catalog_path or CATALOG_PATH).read_text())
    entries = catalog.get("blogs", []) + catalog.get("ressources_sites", [])
    return sorted({e["country"] for e in entries if e.get("country")})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="N'écrit rien.")
    args = parser.parse_args()

    countries = catalog_countries()
    resolved, missing = build_map(fetch_locations(), countries)

    print(f"Résolus : {len(resolved)}/{len(countries)}")
    if missing:
        print(f"NON RÉSOLUS : {missing}")
        print("Ces pays n'auront pas de serp_location pré-rempli à l'onboarding.")

    doc = {
        "_comment": (
            "country ISO (superprof_blogs_catalog.json) -> location_name DataForSEO. "
            "Généré et validé contre /v3/serp/google/locations ; ne pas éditer à la main. "
            "Régénérer : python3 scripts/utils/build_dataforseo_locations.py. "
            "UK (catalogue) -> GB (ISO). HK/TW/PR n'existent pas en 'Country' chez "
            "DataForSEO : repli sur la Region homonyme."
        ),
        "locations": resolved,
    }
    if args.dry_run:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return 0

    OUTPUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Écrit : {OUTPUT_PATH.relative_to(_PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
