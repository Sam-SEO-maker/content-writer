"""Catalogue Superprof + onboarding tenant (Phase 6d) — sans réseau.

Vérifie le générateur de catalogue (filtrage blog/ressources) et la sûreté de
l'onboarding (squelette, merge sites.json sans perte, guards).
"""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.utils.build_superprof_catalog import build_catalog, parse_properties
from scripts.utils import tenant_onboard as T


# --- Catalogue --------------------------------------------------------------

_SAMPLE = """
- https://www.superprof.fr/ressources/ (siteFullUser)
- https://www.superprof.fr/blog/ (siteFullUser)
- https://www.superprof.es/apuntes/ (siteFullUser)
- https://www.superprof.es/diccionario/ (siteFullUser)
- https://www.superprof.co.uk/resources/ (siteFullUser)
- https://www.superprof.se/laromedel/ (siteFullUser)
- https://www.superprof.de/ (siteFullUser)
- https://www.superprof.com.br/blog/ (siteFullUser)
"""


def test_catalog_keeps_only_blog_and_known_ressources():
    urls = parse_properties(_SAMPLE)
    cat = build_catalog(urls)
    res_ids = {r["tenant_id"] for r in cat["ressources_sites"]}
    blog_props = {b["gsc_property"] for b in cat["blogs"]}

    # 3 ressources connus présents
    assert res_ids == {"superprof-ressources", "es-es-ressources", "en-uk-ressources"}
    # diccionario / laromedel / homepage nue écartés
    assert not any("diccionario" in b or "laromedel" in b for b in blog_props)
    assert "https://www.superprof.de/" not in blog_props  # homepage nue
    # blogs /blog/ gardés
    assert "https://www.superprof.fr/blog/" in blog_props
    assert "https://www.superprof.com.br/blog/" in blog_props


def test_catalog_blog_id_convention():
    cat = build_catalog(parse_properties(_SAMPLE))
    by_prop = {b["gsc_property"]: b for b in cat["blogs"]}
    assert by_prop["https://www.superprof.fr/blog/"]["tenant_id"] == "fr-fr-blog"
    assert by_prop["https://www.superprof.com.br/blog/"]["tenant_id"] == "pt-br-blog"


def test_language_overrides_verified_on_real_content():
    """Golfe/Maghreb : langue arabe vérifiée sur le contenu réel (pas l'heuristique).

    EAU reste en anglais (vérifié). Cf. _LANG_OVERRIDES.
    """
    from scripts.utils.build_superprof_catalog import resolve_meta
    assert resolve_meta("https://www.superprof.qa/blog/")[1] == "ar"
    assert resolve_meta("https://www.superprof.com.om/blog/")[1] == "ar"
    assert resolve_meta("https://www.superprof.com.tn/blog/")[1] == "ar"
    # EAU NON overridé → reste anglais
    assert resolve_meta("https://www.superprof.ae/blog/")[1] == "en"
    # Maroc/Sénégal francophones confirmés
    assert resolve_meta("https://www.superprof.ma/blog/")[1] == "fr"
    assert resolve_meta("https://www.superprof.com.sn/blog/")[1] == "fr"
    # Islande/Maurice : blogs en anglais (balayage 90 blogs 2026-07-15)
    assert resolve_meta("https://www.superprof.is/blog/")[1] == "en"
    assert resolve_meta("https://www.superprof.mu/blog/")[1] == "en"
    # Corée : reste coréen (indéterminé au fetch, défaut sûr)
    assert resolve_meta("https://www.superprof.co.kr/blog/")[1] == "ko"


# --- Onboarding -------------------------------------------------------------

@pytest.fixture
def fake_root(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "_shared" / "config").mkdir(parents=True)
        catalog = {
            "ressources_sites": [
                {"tenant_id": "es-es-ressources", "type": "ressources", "country": "ES",
                 "language": "es", "gsc_property": "https://www.superprof.es/apuntes/",
                 "url_base": "/apuntes/", "onboardable": True},
            ],
            "blogs": [],
        }
        (root / "_shared" / "config" / "superprof_blogs_catalog.json").write_text(
            json.dumps(catalog), encoding="utf-8")
        (root / "_shared" / "config" / "sites.json").write_text(json.dumps({
            "notion_refresh_tracker_db_id": "KEEP",
            "sites": [{"id": "enseigna", "name": "Enseigna", "blacklist": ["a.fr"]}],
        }), encoding="utf-8")
        monkeypatch.setattr(T, "CATALOG_PATH",
                            root / "_shared" / "config" / "superprof_blogs_catalog.json")
        monkeypatch.setattr(T, "SITES_JSON", root / "_shared" / "config" / "sites.json")
        yield root


def test_onboard_creates_skeleton_and_prefills(fake_root):
    rep = T.onboard_tenant("es-es-ressources", base_path=fake_root)
    cfg = json.loads((fake_root / "tenants" / "es-es-ressources" / "config" / "tenant.json").read_text())
    assert cfg["gsc_property"] == "https://www.superprof.es/apuntes/"
    assert cfg["domain"] == "superprof.es"
    assert cfg["language"] == "es"
    assert "_TODO" in cfg
    assert (fake_root / "tenants" / "es-es-ressources" / "prompts" / "site.md").exists()
    assert (fake_root / "tenants" / "es-es-ressources" / "outputs").is_dir()
    assert rep["registry_updated"] is True


def test_onboard_merges_sites_json_without_loss(fake_root):
    T.onboard_tenant("es-es-ressources", base_path=fake_root)
    sites = json.loads((fake_root / "_shared" / "config" / "sites.json").read_text())
    assert sites["notion_refresh_tracker_db_id"] == "KEEP"
    ens = next(s for s in sites["sites"] if s["id"] == "enseigna")
    assert ens["blacklist"] == ["a.fr"]
    assert {s["id"] for s in sites["sites"]} == {"enseigna", "es-es-ressources"}


def test_onboard_refuses_existing_without_force(fake_root):
    T.onboard_tenant("es-es-ressources", base_path=fake_root)
    with pytest.raises(ValueError):
        T.onboard_tenant("es-es-ressources", base_path=fake_root)


def test_onboard_force_no_duplicate_registry(fake_root):
    T.onboard_tenant("es-es-ressources", base_path=fake_root)
    rep2 = T.onboard_tenant("es-es-ressources", base_path=fake_root, force=True)
    assert rep2["registry_updated"] is False
    sites = json.loads((fake_root / "_shared" / "config" / "sites.json").read_text())
    assert sum(1 for s in sites["sites"] if s["id"] == "es-es-ressources") == 1


def test_onboard_rejects_unknown_id(fake_root):
    with pytest.raises(ValueError):
        T.onboard_tenant("xx-zz-blog", base_path=fake_root)
