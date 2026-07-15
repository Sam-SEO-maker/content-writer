"""
Config Adapter Module

Adapte les nouveaux fichiers de configuration blog JSON vers le format SiteConfig
utilisé par le module sitemap.
"""

import json
from pathlib import Path
from typing import Optional

from _shared.core.models import SiteConfig


def load_blog_config_as_site_config(blog_id: str, base_path: Optional[Path] = None) -> SiteConfig:
    """
    Charge un fichier de configuration blog et le convertit en SiteConfig.

    Args:
        blog_id: Identifiant du blog (sans .fr/.com)
        base_path: Chemin racine du projet

    Returns:
        SiteConfig compatible avec le module sitemap

    Raises:
        FileNotFoundError: Si le fichier config n'existe pas
        ValueError: Si des champs requis sont manquants
    """
    if base_path is None:
        base_path = Path(__file__).parent.parent.parent

    # Config tenant unique (layout monorepo) : tenants/{id}/config/tenant.json
    from _shared.core.tenant_paths import TenantPaths
    config_paths = [TenantPaths(base_path=base_path).blog_config(blog_id)]

    config_file = None
    for path in config_paths:
        if path.exists():
            config_file = path
            break

    if not config_file:
        raise FileNotFoundError(f"Configuration non trouvée pour blog_id: {blog_id}")

    # Charger le JSON
    with open(config_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extraire les champs nécessaires pour SiteConfig
    blog_id_clean = data.get("blog_id", blog_id)
    display_name = data.get("display_name", blog_id)
    domain = data.get("domain")
    gsc_property = data.get("gsc_property", f"https://{domain}/")

    # Récupérer spreadsheet_id depuis sheets_config
    sheets_config = data.get("sheets_config", {})
    sheet_id = sheets_config.get("spreadsheet_id", "")

    # Sitemap URL (vide = auto-découverte)
    sitemap_url = data.get("sitemap_url", "")

    # Credentials (nom du fichier, par défaut vide)
    credentials = data.get("credentials", "")

    # Validation
    if not domain:
        raise ValueError(f"Champ 'domain' manquant dans la config de {blog_id}")

    # Créer le SiteConfig
    return SiteConfig(
        id=blog_id_clean,
        name=display_name,
        domain=domain,
        gsc_property=gsc_property,
        sheet_id=sheet_id,
        credentials=credentials,
        active=True,  # Tous les blogs avec config sont considérés actifs
        sitemap_url=sitemap_url
    )


def load_fetcher_from_blog_config(blog_id: str, base_path: Optional[Path] = None):
    """
    Charge un SitemapFetcher depuis la configuration blog.

    Args:
        blog_id: Identifiant du blog
        base_path: Chemin racine du projet

    Returns:
        SitemapFetcher configuré

    Usage:
        fetcher = load_fetcher_from_blog_config("enseigna")
        result = fetcher.fetch_and_detect_new()
    """
    from .fetcher import SitemapFetcher

    site_config = load_blog_config_as_site_config(blog_id, base_path)
    return SitemapFetcher(site_config, base_path=base_path)


def load_analyzer_from_blog_config(blog_id: str, base_path: Optional[Path] = None):
    """
    Charge un SitemapAnalyzer depuis la configuration blog.

    Args:
        blog_id: Identifiant du blog
        base_path: Chemin racine du projet

    Returns:
        SitemapAnalyzer configuré

    Usage:
        analyzer = load_analyzer_from_blog_config("enseigna")
        stale = analyzer.find_stale_content(months=6)
    """
    from .analyzer import SitemapAnalyzer

    fetcher = load_fetcher_from_blog_config(blog_id, base_path)
    return SitemapAnalyzer(fetcher)
