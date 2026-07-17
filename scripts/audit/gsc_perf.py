"""Perfs SEO d'un blog/tenant via le MCP GSC (totaux + top keywords).

Coup d'œil léger sur l'état d'un blog : totaux de trafic (clics, impressions,
CTR, position moyenne) + top requêtes, récupérés via le MCP gsc-remote pour
superprof.* (fallback service account), via le SA pour enseigna/tenants hors MCP.
Le routage est porté par `GSCAnalyzer` (voir `fetch_blog_performance`).

Complémentaire de `gsc_state` (qui, lui, catégorise + pousse vers Sheet) : ici on
affiche dans le chat et on dump un JSON local léger, sans dépendance Sheet.

Usage :
    python content_writer.py audit gsc-perf --market superprof-ressources
    python content_writer.py audit gsc-perf --market enseigna --days 90 --dry-run
"""

import json
from datetime import datetime, timezone
from typing import Optional

from scripts.audit.ahrefs_state import REPO_ROOT
from scripts.audit.gsc_analyzer import GSCAnalyzer
from scripts.audit.gsc_state import _site_gsc_property  # résolution gsc_property depuis sites.json


def _property_for_url(url: str) -> "tuple[str, str]":
    """Déduit (tenant_id, gsc_property) depuis une URL, sans argument tenant.

    On matche l'URL contre la `gsc_property` de chaque tenant (celle-ci peut être
    un préfixe de chemin, ex. `https://www.superprof.fr/ressources/`). Le tenant
    dont la property est un préfixe de l'URL, LE PLUS LONG, gagne — pour ne pas
    confondre `superprof.fr/ressources/` avec un futur `superprof.fr/blog/`.
    """
    import json
    sites_path = REPO_ROOT / "_shared" / "config" / "sites.json"
    with open(sites_path, encoding="utf-8") as f:
        data = json.load(f)
    best: "tuple[str, str]" = ()
    for s in data.get("sites", []):
        prop = s.get("gsc_property")
        if prop and url.startswith(prop):
            if not best or len(prop) > len(best[1]):
                best = (s["id"], prop)
    if not best:
        raise ValueError(f"Aucun tenant ne couvre cette URL dans sites.json : {url}")
    return best


def run_gsc_perf(
    blog: str,
    days: int = 28,
    top_kw: int = 20,
    dry_run: bool = False,
) -> dict:
    """Récupère les perfs blog et dump un JSON local. Retourne le dict de perfs.

    Args:
        blog: tenant id (résolu en gsc_property via sites.json).
        days: fenêtre en jours (défaut 28, unité native des tools MCP).
        top_kw: nombre de requêtes à ramener (plafonné ~20 côté MCP).
        dry_run: si True, n'écrit pas le dump local.
    """
    gsc_property = _site_gsc_property(blog)
    analyzer = GSCAnalyzer(gsc_property)
    perf = analyzer.fetch_blog_performance(days=days, top_kw=top_kw)

    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {"site_id": blog, "snapshot_date": snapshot, **perf}

    if not dry_run:
        result["output_path"] = _dump(blog, f"gsc_perf_{snapshot}", result)

    return result


def run_gsc_page(url: str, days: int = 28, dry_run: bool = False) -> dict:
    """Perfs GSC d'une **URL précise** : requêtes sur lesquelles elle ranke.

    Le tenant/property est déduit de l'URL (`_property_for_url`). Routage MCP
    (superprof.*) avec fallback service account, porté par `GSCAnalyzer`.

    Retourne {url, site_id, source, days, keywords:[...], totals:{...}}.
    """
    blog, gsc_property = _property_for_url(url)
    analyzer = GSCAnalyzer(gsc_property)

    rows = None
    source = "service_account"
    if analyzer.uses_mcp:
        try:
            from scripts.audit.gsc_mcp_client import GSCMCPClient
            rows = GSCMCPClient().search_by_page_query(gsc_property, url, days=days)
            source = "mcp"
        except Exception as e:  # GSCMCPError ou réseau → fallback SA
            print(f"[GSC] MCP indisponible ({str(e)[:80]}) — fallback service account.")
    if rows is None:
        rows = analyzer._fetch_current_period_rows_via_sa(url) or []

    total_clicks = sum(r["clicks"] for r in rows)
    total_impr = sum(r["impressions"] for r in rows)
    # Position moyenne pondérée par les impressions (méthode GSC), pas une
    # moyenne simple qui donnerait le même poids à une requête à 1 impression.
    avg_position = (
        sum(r["position"] * r["impressions"] for r in rows) / total_impr
        if total_impr else 0.0
    )
    ctr = (total_clicks / total_impr * 100) if total_impr else 0.0
    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {
        "url": url, "site_id": blog, "snapshot_date": snapshot,
        "source": source, "days": days,
        "totals": {
            "clicks": total_clicks,
            "impressions": total_impr,
            "ctr": round(ctr, 2),
            "position": round(avg_position, 1),
        },
        "keywords": rows,
    }

    if not dry_run:
        safe = url.rstrip("/").rsplit("/", 1)[-1].replace(".html", "") or "page"
        result["output_path"] = _dump(blog, f"gsc_page_{safe}_{snapshot}", result)

    return result


def _dump(blog: str, stem: str, payload: dict) -> str:
    """Écrit un dump JSON dans outputs/{tenant}/audit/. Retourne le chemin."""
    from _shared.core.tenant_paths import TenantPaths
    out_dir = TenantPaths(base_path=REPO_ROOT).output_dir(blog) / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stem}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return str(out_path)
