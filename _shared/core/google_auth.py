"""
Google auth — credentials par tenant selon `auth_mode` (Phase 4bis-B).

Deux modes, choisis par tenant (champ `auth_mode` de sa config, défaut service_account) :

- `service_account` (défaut) : compte de service partagé (GOOGLE_SA_PATH). Zéro
  friction pour le mainteneur — fonctionne déjà sur ses propriétés GSC/Sheets.
- `oauth_user` : le collaborateur lance une fois le flow Chrome existant
  (scripts/setup/generate_gsc_token.py → token.json), consent, et l'app utilise
  SES accès — sans clé de service partagée.

Point d'entrée unique `get_credentials(scopes, auth_mode=...)` : les helpers d'auth
(sheets_client, gsc_analyzer) passent par lui au lieu de dupliquer le branchement.
"""

import os
from pathlib import Path
from typing import Optional


_SA_PATH = Path(
    os.environ.get("GOOGLE_SA_PATH", "~/.credentials/google/google-service-account.json")
).expanduser()
_TOKEN_PATH = Path(
    os.environ.get("GOOGLE_OAUTH_TOKEN", "~/.credentials/google/token.json")
).expanduser()


def resolve_auth_mode(tenant_id: Optional[str] = None) -> str:
    """Lit `auth_mode` de la config du tenant. Défaut: 'service_account'."""
    if not tenant_id:
        return "service_account"
    try:
        from _shared.core.tenant_paths import TenantPaths
        import json
        cfg_path = TenantPaths().blog_config(tenant_id)
        if cfg_path.exists():
            mode = json.loads(cfg_path.read_text(encoding="utf-8")).get("auth_mode")
            if mode in ("service_account", "oauth_user"):
                return mode
    except Exception:
        pass
    return "service_account"


def get_credentials(scopes: list[str], auth_mode: str = "service_account"):
    """Retourne des credentials Google selon le mode, ou None si indisponible.

    - oauth_user : token.json (from_authorized_user_file, avec refresh auto).
    - service_account (défaut ou fallback) : GOOGLE_SA_PATH.
    """
    if auth_mode == "oauth_user":
        creds = _oauth_user_credentials(scopes)
        if creds is not None:
            return creds
        # Pas de token utilisateur exploitable → repli service account.

    return _service_account_credentials(scopes)


def _service_account_credentials(scopes: list[str]):
    if not _SA_PATH.exists():
        return None
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_file(str(_SA_PATH), scopes=scopes)


def _oauth_user_credentials(scopes: list[str]):
    if not _TOKEN_PATH.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), scopes)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds
    except Exception:
        return None
