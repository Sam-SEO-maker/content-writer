"""Table country -> location_name DataForSEO + pré-remplissage à l'onboarding.

Sans réseau : la table livrée (`_shared/config/dataforseo_locations.json`) est
lue telle quelle, la résolution contre l'API vit dans
`scripts/utils/build_dataforseo_locations.py`.
"""

import json
from pathlib import Path

import pytest

from scripts.utils.build_dataforseo_locations import build_map
from scripts.utils.tenant_onboard import (
    LOCATIONS_PATH,
    build_tenant_config,
    resolve_serp_location,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CATALOG = _PROJECT_ROOT / "_shared" / "config" / "superprof_blogs_catalog.json"


def _catalog_countries() -> set[str]:
    cat = json.loads(_CATALOG.read_text(encoding="utf-8"))
    return {e["country"] for e in cat.get("blogs", []) + cat.get("ressources_sites", [])}


def _table() -> dict:
    return json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))["locations"]


# --- Table livrée -----------------------------------------------------------

def test_tous_les_pays_du_catalogue_sont_resolus():
    """Un pays non résolu = tenant onboardé sans locale SERP."""
    manquants = _catalog_countries() - set(_table())

    assert not manquants, f"pays sans location_name : {sorted(manquants)}"


def test_aucune_location_vide():
    assert not [c for c, name in _table().items() if not name.strip()]


@pytest.mark.parametrize(
    "country,expected",
    [
        ("FR", "France"),
        ("US", "United States"),
        ("JP", "Japan"),
        ("ES", "Spain"),
        ("UK", "United Kingdom"),  # catalogue UK -> ISO GB
        ("HK", "Hong Kong"),       # pas de "Country" chez DFS -> Region
        ("TW", "Taiwan"),
        ("PR", "Puerto Rico"),
    ],
)
def test_locations_de_reference(country, expected):
    assert _table()[country] == expected


# --- Résolveur --------------------------------------------------------------

def test_resolve_pays_inconnu_renvoie_vide():
    """Vide plutôt que deviner : l'orchestrateur retombera sur France."""
    assert resolve_serp_location("ZZ") == ""
    assert resolve_serp_location("") == ""


# --- build_map (logique de résolution, items simulés) -----------------------

def test_build_map_alias_uk_vers_gb():
    items = [{"location_type": "Country", "country_iso_code": "GB",
              "location_name": "United Kingdom"}]

    resolved, missing = build_map(items, ["UK"])

    assert resolved == {"UK": "United Kingdom"}
    assert missing == []


def test_build_map_repli_sur_region_racine():
    """HK n'a pas de Country : prendre "Hong Kong", pas une subdivision."""
    items = [
        {"location_type": "Region", "country_iso_code": "HK",
         "location_name": "Kowloon,Hong Kong"},
        {"location_type": "Region", "country_iso_code": "HK",
         "location_name": "Hong Kong"},
    ]

    resolved, _ = build_map(items, ["HK"])

    assert resolved == {"HK": "Hong Kong"}


def test_build_map_signale_les_non_resolus():
    resolved, missing = build_map([], ["ZZ"])

    assert resolved == {}
    assert missing == ["ZZ"]


# --- Scaffold ---------------------------------------------------------------

def test_scaffold_pre_remplit_la_locale():
    entry = {
        "tenant_id": "ja-jp-blog",
        "gsc_property": "https://www.superprof.jp/blog/",
        "country": "JP",
        "language": "ja",
        "type": "blog",
    }

    cfg = build_tenant_config(entry)

    assert cfg["serp_location"] == "Japan"
    assert cfg["language"] == "ja"


def test_suisse_deux_langues_meme_location():
    """CH sert un blog fr (www) et un blog de (de.) : même location, langues distinctes."""
    from scripts.utils.tenant_onboard import load_catalog_entry

    fr = build_tenant_config(load_catalog_entry("fr-ch-blog"))
    de = build_tenant_config(load_catalog_entry("de-ch-blog"))

    assert fr["serp_location"] == de["serp_location"] == "Switzerland"
    assert (fr["language"], de["language"]) == ("fr", "de")


def test_scaffold_pays_inconnu_laisse_la_locale_vide():
    entry = {
        "tenant_id": "xx-zz-blog",
        "gsc_property": "https://example.test/blog/",
        "country": "ZZ",
        "language": "xx",
        "type": "blog",
    }

    cfg = build_tenant_config(entry)

    assert cfg["serp_location"] == ""
