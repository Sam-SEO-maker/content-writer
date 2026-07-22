"""
Blacklist de domaines — chargée depuis le markdown canonique.

Source de vérité : `.claude/skills/source-research/references/blacklisted-domains.md`
(~750 domaines : concurrents, agrégateurs, toutes les éditions Wikipédia). Le fichier
est livré dans tous les clones (`.claude` figure dans onboarding/engine-sparse-paths.txt).

Fallback : si le markdown est introuvable, on retombe sur la liste legacy
`constants.BLACKLIST_DOMAINS` (5 domaines historiques) avec un warning.

Matching par HOST uniquement (jamais de substring sur l'URL entière : avec ~750
domaines, `ef.com` matcherait `chef.com`). Règle des sous-domaines du markdown :
- domaine nu blacklisté ⇒ tous ses sous-domaines le sont (suffix match) ;
- entrée sous-domaine (`en.duolingo.com`) ⇒ le parent (`duolingo.com`) l'est aussi ;
- entrée avec chemin (`quipper.com/id`) ⇒ le domaine parent est blacklisté.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from .constants import BLACKLIST_DOMAINS as LEGACY_BLACKLIST_DOMAINS

logger = logging.getLogger(__name__)

BLACKLIST_MD_RELPATH = Path(".claude/skills/source-research/references/blacklisted-domains.md")

# Famille Wikipédia (toutes langues via suffix match) + projets sœurs — toujours
# blacklistée, même si le markdown évolue.
WIKIPEDIA_FAMILY = frozenset({
    "wikipedia.org", "wikimedia.org", "wiktionary.org", "wikisource.org",
    "wikiquote.org", "wikinews.org", "wikivoyage.org", "wikibooks.org",
    "wikiversity.org",
})

_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")

# Seconds-level génériques : ne jamais promouvoir `co.nz`, `com.br`… en entrée
# blacklistée quand on dérive le parent d'un sous-domaine.
_GENERIC_SLD = {"co", "com", "org", "net", "ac", "gov", "edu", "or", "ne"}


def _project_root() -> Path:
    # _shared/core/blacklist.py → _shared/core → _shared → racine projet
    return Path(__file__).resolve().parent.parent.parent


def _normalize_entry(raw: str) -> set[str]:
    """Normalise une ligne du markdown en 0..2 domaines blacklistés."""
    entry = raw.strip().lower().rstrip(".,;")
    if not entry or entry.startswith("#"):
        return set()
    entry = entry.split("/", 1)[0]          # entrée avec chemin → domaine parent
    entry = entry.removeprefix("*.")
    entry = entry.removeprefix("www.")
    if not _DOMAIN_RE.match(entry):
        return set()
    domains = {entry}
    labels = entry.split(".")
    # Entrée sous-domaine ⇒ le parent est blacklisté aussi (règle du markdown),
    # sauf si le "parent" serait un suffixe public générique (co.nz, com.br…).
    if len(labels) >= 3 and labels[-2] not in _GENERIC_SLD:
        domains.add(".".join(labels[-2:]))
    return domains


@lru_cache(maxsize=1)
def load_blacklist_domains() -> frozenset[str]:
    """Charge la liste canonique depuis le markdown (avec cache process-wide)."""
    md_path = _project_root() / BLACKLIST_MD_RELPATH
    legacy = {d.strip().lower() for d in LEGACY_BLACKLIST_DOMAINS}

    if not md_path.exists():
        logger.warning(
            "Blacklist markdown introuvable (%s) — fallback liste legacy "
            "(%d domaines). Le clone est-il complet ?", md_path, len(legacy)
        )
        return frozenset(legacy | WIKIPEDIA_FAMILY)

    domains: set[str] = set(WIKIPEDIA_FAMILY)
    in_fence = False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            domains |= _normalize_entry(line)

    if len(domains) < 50:
        logger.warning(
            "Blacklist markdown suspecte (%d domaines parsés depuis %s) — "
            "liste legacy fusionnée par sécurité.", len(domains), md_path
        )
        domains |= legacy

    return frozenset(domains)


def url_host(url: str) -> str:
    """Extrait le host d'une URL (ou d'un domaine nu), normalisé lowercase sans www."""
    if not url:
        return ""
    raw = url.strip()
    parsed = urlparse(raw if "//" in raw else "//" + raw)
    host = (parsed.netloc or "").lower()
    host = host.rsplit("@", 1)[-1].split(":", 1)[0]  # strip userinfo / port
    return host.removeprefix("www.")


def is_blacklisted_host(host: str) -> bool:
    """True si `host` est un domaine blacklisté ou un sous-domaine d'un blacklisté."""
    host = (host or "").lower().removeprefix("www.")
    if not host:
        return False
    domains = load_blacklist_domains()
    parts = host.split(".")
    return any(".".join(parts[i:]) in domains for i in range(len(parts) - 1))


def is_blacklisted_url(url: str) -> bool:
    """True si l'URL pointe vers un domaine blacklisté (liens relatifs → False)."""
    return is_blacklisted_host(url_host(url))
