"""
Résolveur du mot-clé principal (main_keyword) multi-source.

Le guide YourTextGuru (YTG) doit être créé/résolu avec le mot-clé principal de
la requête. Ce mot-clé peut provenir de plusieurs sources, cloisonnées par blog
dans l'état actuel du projet. Ce module unifie la résolution en une seule
fonction, avec un ordre de priorité configurable par blog.

Sources supportées (dans l'ordre de priorité par défaut) :
    1. notion  — propriété "Requête YTG" de la base "📕 Commandes"
                 (source de vérité pour les NOUVEAUX articles ; enseigna surtout).
    2. sheet   — mot-clé lu dans l'onglet réel du blog (service account) :
                   * enseigna              → onglets "Avis"/"Versus" (col B top_keyword)
                                             + "A ajouter" (col D main_keyword)
                   * superprof-ressources  → onglet "New Growing List" (col B main_keyword)
    3. gsc     — top query par impressions/clicks sur 12 mois (API GSC directe).
    4. slug    — slug de l'URL normalisé (dernier recours, jamais None).

⚠️ IMPORTANT — onglets réels : l'ancien onglet "Refreshs_Audit" n'existe plus
dans les Google Sheets réels (il provoque un HTTP 400). Ce module lit donc
directement les onglets réels par blog, il ne dépend PAS de RefreshAuditRow.

Utilisation :
    resolver = KeywordResolver()
    kw, source = resolver.resolve("enseigna", url="https://enseigna.fr/acadomia-avis/")
    # kw = "acadomia avis", source = "sheet" (ou "notion"/"gsc"/"slug")
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# Ordre de priorité par défaut si la config blog ne le précise pas.
DEFAULT_KEYWORD_SOURCES = ["notion", "sheet", "gsc", "slug"]

# Mapping blog_id → (env var du spreadsheet, onglets à scanner, index colonne du mot-clé)
# Les onglets et index sont ceux VÉRIFIÉS EN LIVE (juillet 2026).
_SHEET_LAYOUT = {
    "enseigna": {
        "spreadsheet_env": "SPREADSHEET_ID_ENSEIGNA",
        # (onglet, index_url, index_keyword)
        "tabs": [
            ("Avis", 0, 1),        # A=url, B=top_keyword
            ("Versus", 0, 1),      # A=url, B=top_keyword (pas de kw dédié → fallback col B si présent)
            ("A ajouter", 0, 3),   # A=url, D=main_keyword (nouveaux articles)
        ],
    },
    "superprof-ressources": {
        "spreadsheet_env": "SPREADSHEET_ID_SUPERPROF",
        "tabs": [
            ("New Growing List", 0, 1),  # A=url, B=main_keyword
        ],
    },
}


def _resolve_sheet_layout(blog_id: str) -> dict | None:
    """Layout des onglets Sheet d'un tenant.

    Source de vérité : le bloc `sheets` de tenants/{id}/config/tenant.json
    (externalisé en Phase 4bis-A). Repli sur la constante _SHEET_LAYOUT si la
    config est absente/incomplète, pour ne pas casser un tenant non encore migré.
    """
    try:
        from _shared.core.tenant_paths import TenantPaths
        import json
        cfg_path = TenantPaths().blog_config(blog_id)
        if cfg_path.exists():
            sheets = json.loads(cfg_path.read_text(encoding="utf-8")).get("sheets", {})
            tabs = sheets.get("tabs")
            env = sheets.get("spreadsheet_env")
            if tabs and env:
                return {
                    "spreadsheet_env": env,
                    "tabs": [
                        (t["name"], t.get("col_url", 0), t.get("col_keyword", 1))
                        for t in tabs
                    ],
                }
    except Exception as e:
        logger.warning(f"[KeywordResolver] lecture sheets config '{blog_id}' échouée: {e}")
    return _SHEET_LAYOUT.get(blog_id)


def _norm_url(url: str) -> str:
    """Normalise une URL pour comparaison (minuscules, sans slash final)."""
    return (url or "").strip().rstrip("/").lower()


def slug_to_keyword(url_or_slug: str) -> str:
    """
    Dérive un mot-clé lisible depuis un slug d'URL (dernier recours).

    Ex: "https://enseigna.fr/acadomia-avis/" → "acadomia avis"
    """
    if not url_or_slug:
        return ""
    slug = url_or_slug.strip().rstrip("/").split("/")[-1]
    slug = re.sub(r"\.(html?|php)$", "", slug)
    return slug.replace("-", " ").replace("_", " ").strip()


class KeywordResolver:
    """
    Résout le mot-clé principal d'une URL en interrogeant plusieurs sources.

    Les clients (Notion, Sheets, GSC) sont lazy-init et graceful : si une source
    n'est pas configurée, elle est silencieusement sautée et on passe à la suivante.
    """

    def __init__(
        self,
        notion_client=None,
        sheets_client_factory=None,
        gsc_analyzer=None,
        notion_db_resolver=None,
    ):
        """
        Args:
            notion_client: instance NotionClient (optionnel, lazy sinon).
            sheets_client_factory: callable(spreadsheet_id) -> SheetsClient (lazy sinon).
            gsc_analyzer: instance GSCAnalyzer (optionnel, lazy sinon).
            notion_db_resolver: callable(blog_id) -> notion_commandes_db_id | None.
        """
        self._notion = notion_client
        self._sheets_factory = sheets_client_factory
        self._gsc = gsc_analyzer
        self._notion_db_resolver = notion_db_resolver
        # Cache par blog pour éviter de relire un onglet à chaque URL.
        self._sheet_index_cache: dict[str, dict] = {}
        self._notion_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Point d'entrée
    # ------------------------------------------------------------------

    def resolve(
        self,
        blog_id: str,
        url: str = "",
        slug: str = "",
        sources: Optional[list[str]] = None,
    ) -> tuple[str, str]:
        """
        Retourne (main_keyword, source) pour cette URL/blog.

        source ∈ {"notion", "sheet", "gsc", "slug", "none"}.
        Le mot-clé n'est jamais None : au pire slug, au pire-pire "".
        """
        order = sources or DEFAULT_KEYWORD_SOURCES

        for src in order:
            try:
                if src == "notion":
                    kw = self._from_notion(blog_id, url)
                elif src == "sheet":
                    kw = self._from_sheet(blog_id, url)
                elif src == "gsc":
                    kw = self._from_gsc(blog_id, url)
                elif src == "slug":
                    kw = slug_to_keyword(url or slug)
                else:
                    logger.warning(f"[KeywordResolver] Source inconnue ignorée: {src}")
                    continue
            except Exception as e:
                logger.warning(f"[KeywordResolver] Source '{src}' en erreur (ignorée): {e}")
                continue

            if kw:
                logger.info(f"[KeywordResolver] {blog_id} '{url}' → '{kw}' (source={src})")
                return kw, src

        # Aucun résultat même via slug
        return "", "none"

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def _from_notion(self, blog_id: str, url: str) -> str:
        """Cherche la 'Requête YTG' d'une commande Notion matchant l'URL."""
        db_id = self._resolve_notion_db(blog_id)
        if not db_id:
            return ""

        index = self._notion_cache.get(blog_id)
        if index is None:
            notion = self._get_notion()
            if notion is None:
                return ""
            commandes = notion.get_commandes(db_id, blog_id=blog_id)
            index = {}
            for c in commandes:
                if c.ytg_keyword:
                    if c.url:
                        index[_norm_url(c.url)] = c.ytg_keyword.strip()
            self._notion_cache[blog_id] = index

        return index.get(_norm_url(url), "")

    def _from_sheet(self, blog_id: str, url: str) -> str:
        """Cherche le mot-clé dans l'onglet réel du blog (service account)."""
        layout = _resolve_sheet_layout(blog_id)
        if not layout:
            return ""

        index = self._sheet_index_cache.get(blog_id)
        if index is None:
            index = self._build_sheet_index(blog_id, layout)
            self._sheet_index_cache[blog_id] = index

        return index.get(_norm_url(url), "")

    def _from_gsc(self, blog_id: str, url: str) -> str:
        """Top query GSC 12 mois pour cette URL."""
        if not url:
            return ""
        gsc = self._get_gsc(blog_id)
        if gsc is None:
            return ""
        kw = gsc.fetch_top_keyword_12m(url)
        return (kw or "").strip()

    # ------------------------------------------------------------------
    # Construction d'index (avec cache)
    # ------------------------------------------------------------------

    def _build_sheet_index(self, blog_id: str, layout: dict) -> dict:
        """Construit {url_norm: keyword} depuis les onglets réels du blog."""
        import os

        sid = os.environ.get(layout["spreadsheet_env"], "")
        if not sid:
            logger.warning(
                f"[KeywordResolver] {layout['spreadsheet_env']} absent — source sheet sautée pour {blog_id}"
            )
            return {}

        sheets = self._get_sheets(sid)
        if sheets is None:
            return {}

        index: dict[str, str] = {}
        for tab, url_idx, kw_idx in layout["tabs"]:
            try:
                data = sheets._read_sheet(tab)
            except Exception as e:
                logger.warning(f"[KeywordResolver] lecture onglet '{tab}' échouée: {e}")
                continue
            if not data:
                continue
            for row in data[1:]:  # skip header
                if len(row) <= url_idx:
                    continue
                u = _norm_url(row[url_idx])
                if not u:
                    continue
                kw = row[kw_idx].strip() if len(row) > kw_idx and row[kw_idx] else ""
                # Ne pas écraser un mot-clé déjà trouvé dans un onglet prioritaire
                if kw and u not in index:
                    index[u] = kw
        logger.info(f"[KeywordResolver] index sheet {blog_id}: {len(index)} URLs")
        return index

    def _resolve_notion_db(self, blog_id: str) -> Optional[str]:
        if self._notion_db_resolver is not None:
            try:
                return self._notion_db_resolver(blog_id)
            except Exception:
                return None
        # Fallback : lire sites.json
        return self._notion_db_from_sites_json(blog_id)

    @staticmethod
    def _notion_db_from_sites_json(blog_id: str) -> Optional[str]:
        import json
        from pathlib import Path

        try:
            base = Path(__file__).resolve().parent.parent.parent
            sites_path = base / "_shared" / "config" / "sites.json"
            if not sites_path.exists():
                return None
            with open(sites_path) as f:
                data = json.load(f)
            for site in data.get("sites", []):
                if site.get("id") == blog_id:
                    return site.get("notion_commandes_db_id") or None
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # Lazy getters
    # ------------------------------------------------------------------

    def _get_notion(self):
        if self._notion is None:
            try:
                from scripts.notion.notion_client import NotionClient
                self._notion = NotionClient()
            except Exception as e:
                logger.warning(f"[KeywordResolver] NotionClient indisponible: {e}")
                self._notion = None
        return self._notion

    def _get_sheets(self, spreadsheet_id: str):
        try:
            if self._sheets_factory is not None:
                return self._sheets_factory(spreadsheet_id)
            from scripts.sheets.sheets_client import SheetsClient
            return SheetsClient(spreadsheet_id=spreadsheet_id)
        except Exception as e:
            logger.warning(f"[KeywordResolver] SheetsClient indisponible: {e}")
            return None

    # GSC analyzers sont par-blog (une gsc_property chacun) → cache par blog_id.
    def _get_gsc(self, blog_id: str):
        if self._gsc is not None:
            return self._gsc  # instance injectée explicitement
        cached = getattr(self, "_gsc_by_blog", None)
        if cached is None:
            cached = {}
            self._gsc_by_blog = cached
        if blog_id not in cached:
            prop = self._gsc_property_for_blog(blog_id)
            if not prop:
                cached[blog_id] = None
            else:
                try:
                    from scripts.audit.gsc_analyzer import GSCAnalyzer
                    cached[blog_id] = GSCAnalyzer(prop)
                except Exception as e:
                    logger.warning(f"[KeywordResolver] GSCAnalyzer indisponible: {e}")
                    cached[blog_id] = None
        return cached[blog_id]

    @staticmethod
    def _gsc_property_for_blog(blog_id: str) -> str:
        """Lit gsc_property depuis _shared/config/blogs/{blog_id}.json."""
        import json
        from pathlib import Path

        try:
            base = Path(__file__).resolve().parent.parent.parent
            from _shared.core.tenant_paths import TenantPaths
            cfg_path = TenantPaths(base_path=base).blog_config(blog_id)
            if not cfg_path.exists():
                return ""
            with open(cfg_path) as f:
                return json.load(f).get("gsc_property", "") or ""
        except Exception:
            return ""
