"""Résolution du bloc `sheets` d'un tenant (§4bis-A).

Point d'accès unique au layout Sheet externalisé (`tenants/{id}/config/tenant.json`
→ clé `sheets`). Évite de dupliquer des constantes single-tenant (ENSEIGNA_TABS,
NGL_SHEET, SPREADSHEET_ID hardcodés) dans les scripts.

Retourne toujours un dict (vide si absent) → l'appelant décide de son repli.
"""
from __future__ import annotations

import json
from typing import Optional


def get_sheets_config(blog_id: str) -> dict:
    """Bloc `sheets` de la config du tenant, ou {} si absent/illisible."""
    try:
        from _shared.core.tenant_paths import TenantPaths
        cfg_path = TenantPaths().blog_config(blog_id)
        if cfg_path.exists():
            return json.loads(cfg_path.read_text(encoding="utf-8")).get("sheets", {}) or {}
    except Exception:
        pass
    return {}


def get_tab_names(blog_id: str, default: Optional[list[str]] = None) -> list[str]:
    """Noms des onglets Sheet du tenant (col `name` du bloc `tabs`)."""
    tabs = get_sheets_config(blog_id).get("tabs") or []
    names = [t["name"] for t in tabs if t.get("name")]
    return names or (default or [])


def get_spreadsheet_id(blog_id: str, default: Optional[str] = None) -> Optional[str]:
    """spreadsheet_id du tenant (bloc `sheets`), avec repli optionnel."""
    return get_sheets_config(blog_id).get("spreadsheet_id") or default


def get_status_col(blog_id: str, default: str = "F") -> str:
    """Colonne de statut du tenant (bloc `sheets`)."""
    return get_sheets_config(blog_id).get("status_col") or default


def get_primary_tab_name(blog_id: str, default: Optional[str] = None) -> Optional[str]:
    """Premier onglet déclaré (usage single-tab type NGL Superprof)."""
    names = get_tab_names(blog_id)
    return names[0] if names else default
