"""
Tenant Paths — point de résolution UNIQUE des chemins par tenant.

Depuis la Phase 4.1, chaque tenant est regroupé sous `tenants/{id}/` :

    tenants/{id}/
    ├── prompts/site.md          (prompt override ; ex _shared/prompts/sites/{id}.md)
    ├── prompts/…                (assets : blocks/, guides/, reference.md, vs_concurrent.md)
    ├── config/tenant.json       (config runtime ; ex _shared/config/blogs/{id}.json)
    ├── linking_maps/            (ex _shared/config/linking_maps/{id}.*)
    └── outputs/                 (ex _shared/outputs/{id}/)

Ce module est le SEUL endroit qui connaît ce layout : les ~40 sites d'appel
passent par lui (Phase 4.0/4.0c), donc la bascule `_shared/…` → `tenants/{id}/`
ne se fait qu'ici.

Clés :
- `tenant_id` = identifiant logique (`enseigna`, `superprof-ressources`) — la clé
  UNIQUE des configs (`sites.json`) ET du dossier tenant. Les sorties sont
  indexées par `tenant_id` (Phase 4.0b), plus par domaine.
"""

from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class TenantPaths:
    """Résout les chemins par tenant sous `tenants/{id}/` depuis un point unique."""

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or _project_root()
        self.tenants_root = self.base_path / "tenants"

    def tenant_dir(self, tenant_id: str) -> Path:
        """Racine du tenant : `tenants/{id}/`."""
        return self.tenants_root / tenant_id

    # --- Prompt site override -------------------------------------------------
    def site_prompt(self, tenant_id: str) -> Path:
        """`tenants/{id}/prompts/site.md` — prompt override du tenant."""
        return self.tenant_dir(tenant_id) / "prompts" / "site.md"

    def vs_concurrent_prompt(self, tenant_id: str) -> Path:
        """`tenants/{id}/prompts/vs_concurrent.md` — prompt du type versus.

        Prompt principal des articles comparatifs (A vs B) ; complète site.md
        pour ce sous-type. Absent chez les tenants sans articles versus.
        """
        return self.tenant_dir(tenant_id) / "prompts" / "vs_concurrent.md"

    def prompts_dir(self, tenant_id: str) -> Path:
        """`tenants/{id}/prompts/` — dossier des assets prompt (blocks/, guides/…)."""
        return self.tenant_dir(tenant_id) / "prompts"

    # --- Config tenant --------------------------------------------------------
    def blog_config(self, tenant_id: str) -> Path:
        """`tenants/{id}/config/tenant.json` — config runtime du tenant."""
        return self.tenant_dir(tenant_id) / "config" / "tenant.json"

    def blog_config_files(self) -> list[tuple[str, Path]]:
        """Liste (tenant_id, chemin config) en parcourant `tenants/*/config/tenant.json`.

        Remplace l'ancien glob plat `config/blogs/*.json` : le layout monorepo
        éclate les configs par dossier tenant.
        """
        if not self.tenants_root.exists():
            return []
        out = []
        for tenant_dir in sorted(self.tenants_root.iterdir()):
            if not tenant_dir.is_dir():
                continue
            cfg = tenant_dir / "config" / "tenant.json"
            if cfg.exists():
                out.append((tenant_dir.name, cfg))
        return out

    # --- Linking maps ---------------------------------------------------------
    def linking_maps_dir(self, tenant_id: str) -> Path:
        """`tenants/{id}/linking_maps/` — cartes de maillage du tenant."""
        return self.tenant_dir(tenant_id) / "linking_maps"

    # --- Outputs --------------------------------------------------------------
    def output_dir(self, tenant_id: str) -> Path:
        """`tenants/{id}/outputs/` — dossier de sortie du tenant."""
        return self.tenant_dir(tenant_id) / "outputs"

    def output_dirs(self) -> list[tuple[str, Path]]:
        """Liste (tenant_id, dossier outputs) pour tous les tenants ayant un outputs/."""
        if not self.tenants_root.exists():
            return []
        out = []
        for tenant_dir in sorted(self.tenants_root.iterdir()):
            if not tenant_dir.is_dir():
                continue
            odir = tenant_dir / "outputs"
            if odir.exists():
                out.append((tenant_dir.name, odir))
        return out
