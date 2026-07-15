"""
Tenant Paths — point de résolution UNIQUE des chemins par tenant.

Avant la refonte monorepo (Phase 4), les racines de chemins par tenant étaient
construites à la main dans ~40 fichiers (prompts, config blog, linking maps,
outputs). Ce module centralise ces 4 racines pour qu'un futur déplacement vers
`tenants/{id}/` ne change qu'UN endroit (la constante `TENANTS_LAYOUT` + les
méthodes ci-dessous), au lieu de 40 sites d'appel.

État actuel (Phase 4.0) : les chemins pointent ENCORE vers les emplacements
historiques `_shared/…` — aucun changement de comportement. La bascule vers
`tenants/{id}/` se fera en Phase 4.1 en modifiant ces méthodes seules.

Clés :
- `tenant_id` = identifiant logique (`enseigna`, `superprof-ressources`) — la clé
  UNIQUE des configs (`sites.json`, `blogs/{id}.json`, `sites/{id}.md`) ET du
  dossier de sortie. Depuis la Phase 4.0b, les sorties sont indexées par
  `tenant_id`, plus par domaine (le mapping domaine historique a été retiré : il
  divergeait du contenu de prod, de push_to_wp et de ytg_qc).
"""

from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class TenantPaths:
    """Résout les 4 racines de chemins par tenant depuis un point unique."""

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or _project_root()
        # Racines historiques (Phase 4.0). En 4.1 : self.tenants_root = base/"tenants".
        self._prompts_sites = self.base_path / "_shared" / "prompts" / "sites"
        self._config_blogs = self.base_path / "_shared" / "config" / "blogs"
        self._linking_maps = self.base_path / "_shared" / "config" / "linking_maps"
        self._outputs_root = self.base_path / "_shared" / "outputs"

    # --- Prompt site override -------------------------------------------------
    def site_prompt(self, tenant_id: str) -> Path:
        """`sites/{id}.md` — prompt override du tenant."""
        return self._prompts_sites / f"{tenant_id}.md"

    def site_prompt_dir(self, tenant_id: str) -> Path:
        """`sites/{id}/` — dossier d'assets prompt (templates HTML enseigna…)."""
        return self._prompts_sites / tenant_id

    # --- Config blog ----------------------------------------------------------
    def blog_config(self, tenant_id: str) -> Path:
        """`config/blogs/{id}.json` — config runtime du tenant."""
        return self._config_blogs / f"{tenant_id}.json"

    def blog_configs_dir(self) -> Path:
        """Dossier de découverte des configs blog (glob *.json)."""
        return self._config_blogs

    # --- Linking maps ---------------------------------------------------------
    def linking_maps_dir(self) -> Path:
        """`config/linking_maps/` — racine des cartes de maillage."""
        return self._linking_maps

    def linking_map(self, tenant_id: str, suffix: str = "csv") -> Path:
        """`config/linking_maps/{id}.{suffix}`."""
        return self._linking_maps / f"{tenant_id}.{suffix}"

    # --- Outputs --------------------------------------------------------------
    def outputs_root(self) -> Path:
        return self._outputs_root

    def output_dir(self, tenant_id: str) -> Path:
        """Dossier de sortie du tenant, indexé par `tenant_id` (Phase 4.0b)."""
        return self._outputs_root / tenant_id
