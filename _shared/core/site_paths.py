"""
Site Paths — point de résolution UNIQUE des chemins par site.

Depuis la Phase 4.1, chaque site est regroupé sous `sites/{id}/` :

    sites/{id}/
    ├── prompts/site.md          (prompt override ; ex _shared/prompts/sites/{id}.md)
    ├── prompts/…                (assets : blocks/, guides/, reference.md, vs_concurrent.md)
    ├── config/site.json       (config runtime ; ex _shared/config/blogs/{id}.json)
    ├── linking_maps/            (ex _shared/config/linking_maps/{id}.*)
    └── outputs/                 (ex _shared/outputs/{id}/)

Ce module est le SEUL endroit qui connaît ce layout : les ~40 sites d'appel
passent par lui (Phase 4.0/4.0c), donc la bascule `_shared/…` → `sites/{id}/`
ne se fait qu'ici.

Clés :
- `site_slug` = identifiant logique (`enseigna`, `superprof.fr-ressources`) — la clé
  UNIQUE des configs (`sites.json`) ET du dossier site. Les sorties sont
  indexées par `site_slug` (Phase 4.0b), plus par domaine.
"""

from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class SitePaths:
    """Résout les chemins par site sous `sites/{id}/` depuis un point unique."""

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or _project_root()
        self.sites_root = self.base_path / "sites"

    def site_dir(self, site_slug: str) -> Path:
        """Racine du site : `sites/{id}/`."""
        return self.sites_root / site_slug

    # --- Prompt site override -------------------------------------------------
    def site_prompt(self, site_slug: str) -> Path:
        """`sites/{id}/prompts/site.md` — prompt override du site."""
        return self.site_dir(site_slug) / "prompts" / "site.md"

    def vs_concurrent_prompt(self, site_slug: str) -> Path:
        """`sites/{id}/prompts/vs_concurrent.md` — prompt du type versus.

        Prompt principal des articles comparatifs (A vs B) ; complète site.md
        pour ce sous-type. Absent chez les sites sans articles versus.
        """
        return self.site_dir(site_slug) / "prompts" / "vs_concurrent.md"

    def prompts_dir(self, site_slug: str) -> Path:
        """`sites/{id}/prompts/` — dossier des assets prompt (blocks/, guides/…)."""
        return self.site_dir(site_slug) / "prompts"

    # --- Config site --------------------------------------------------------
    def site_config(self, site_slug: str) -> Path:
        """`sites/{id}/config/site.json` — config runtime du site."""
        return self.site_dir(site_slug) / "config" / "site.json"

    def site_config_files(self) -> list[tuple[str, Path]]:
        """Liste (site_slug, chemin config) en parcourant `sites/*/config/site.json`.

        Remplace l'ancien glob plat `config/blogs/*.json` : le layout monorepo
        éclate les configs par dossier site.
        """
        if not self.sites_root.exists():
            return []
        out = []
        for site_dir in sorted(self.sites_root.iterdir()):
            if not site_dir.is_dir():
                continue
            cfg = site_dir / "config" / "site.json"
            if cfg.exists():
                out.append((site_dir.name, cfg))
        return out

    # --- Linking maps ---------------------------------------------------------
    def linking_maps_dir(self, site_slug: str) -> Path:
        """`sites/{id}/linking_maps/` — cartes de maillage du site."""
        return self.site_dir(site_slug) / "linking_maps"

    # --- Sources (annuaire d'autorité, tier 1 de source-research) ----------
    def sources_dir(self, site_slug: str) -> Path:
        """`sites/{id}/sources/` — annuaire des domaines d'autorité du site.

        Alimente le tier 1 de la skill `source-research` (ex. `authority-map.md`,
        mapping matière → domaines d'autorité). Absent chez les sites sans annuaire.
        """
        return self.site_dir(site_slug) / "sources"

    # --- Outputs --------------------------------------------------------------
    def output_dir(self, site_slug: str) -> Path:
        """`sites/{id}/outputs/` — dossier de sortie du site."""
        return self.site_dir(site_slug) / "outputs"

    def scrape_cache_dir(self, site_slug: str) -> Path:
        """`sites/{id}/outputs/_scrape_cache/` — cache de HTML scrapé (comparaison avant/après refresh)."""
        return self.output_dir(site_slug) / "_scrape_cache"

    def output_dirs(self) -> list[tuple[str, Path]]:
        """Liste (site_slug, dossier outputs) pour tous les sites ayant un outputs/."""
        if not self.sites_root.exists():
            return []
        out = []
        for site_dir in sorted(self.sites_root.iterdir()):
            if not site_dir.is_dir():
                continue
            odir = site_dir / "outputs"
            if odir.exists():
                out.append((site_dir.name, odir))
        return out
