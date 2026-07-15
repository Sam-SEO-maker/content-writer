"""Sync Notion « config pays » → sites.json (Phase 6d).

Vérifie la SÛRETÉ du merge (aucune perte de champ ni de clé top-level) et le
parsing des propriétés Notion — sans accès réseau.
"""

from scripts.notion.sync_sites_from_notion import (
    merge_into_sites,
    row_to_site,
    _plain_value,
)


def test_merge_preserves_existing_fields_and_toplevel():
    existing = {
        "notion_refresh_tracker_db_id": "KEEP",
        "sites": [
            {"id": "enseigna", "name": "Enseigna", "blacklist": ["a.fr"],
             "acf_fields": 15, "active": True},
        ],
    }
    notion = [{"id": "enseigna", "registre": "vouvoiement"}]
    merged, changes = merge_into_sites(existing, notion)

    # clé top-level jamais perdue
    assert merged["notion_refresh_tracker_db_id"] == "KEEP"
    ens = next(s for s in merged["sites"] if s["id"] == "enseigna")
    # champs riches préservés
    assert ens["blacklist"] == ["a.fr"] and ens["acf_fields"] == 15
    # champ Notion appliqué
    assert ens["registre"] == "vouvoiement"
    assert any("registre" in c for c in changes)


def test_merge_adds_new_tenant():
    existing = {"sites": [{"id": "enseigna"}]}
    notion = [{"id": "es-es-ressources", "domain": "superprof.es", "active": True}]
    merged, changes = merge_into_sites(existing, notion)
    ids = {s["id"] for s in merged["sites"]}
    assert ids == {"enseigna", "es-es-ressources"}
    assert any("nouveau tenant" in c for c in changes)


def test_merge_no_change_returns_empty_changelog():
    existing = {"sites": [{"id": "x", "domain": "d"}]}
    _, changes = merge_into_sites(existing, [{"id": "x", "domain": "d"}])
    assert changes == []


def test_row_to_site_requires_id():
    assert row_to_site({"properties": {"domain": {"type": "url", "url": "x"}}}) is None


def test_row_to_site_maps_types_and_ignores_unmapped():
    row = {"properties": {
        "tenant_id": {"type": "title", "title": [{"plain_text": "es-es-ressources"}]},
        "domain": {"type": "url", "url": "https://superprof.es"},
        "active": {"type": "checkbox", "checkbox": True},
        "ymyl_level": {"type": "select", "select": {"name": "low"}},
        "unmapped": {"type": "rich_text", "rich_text": [{"plain_text": "x"}]},
    }}
    site = row_to_site(row)
    assert site == {
        "id": "es-es-ressources",
        "domain": "https://superprof.es",
        "active": True,
        "ymyl_level": "low",
    }


def test_plain_value_types():
    assert _plain_value({"type": "checkbox", "checkbox": False}) is False
    assert _plain_value({"type": "number", "number": 3}) == 3
    assert _plain_value(
        {"type": "multi_select", "multi_select": [{"name": "a"}, {"name": "b"}]}
    ) == ["a", "b"]
    assert _plain_value(
        {"type": "rich_text", "rich_text": [{"plain_text": "Héllo"}]}
    ) == "Héllo"
