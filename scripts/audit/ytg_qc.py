"""
Cœur du QC sémantique YourTextGuru (YTG), factorisé et multi-blog.

Ce module analyse un contenu HTML généré contre son guide YTG (récupéré via le
mot-clé principal résolu), compare les scores SOSEO/DSEO aux cibles TOP3 des
concurrents, et produit un verdict actionnable AVANT l'intégration dans WordPress.

Il est appelé par trois call-sites :
    - la commande CLI `cw ytg qc` (batch par blog),
    - le chemin single-URL `cw refresh`,
    - l'étape post-génération de l'orchestrateur (STEP 5.6).

Verdicts :
    OPTIMAL     — SOSEO ≥ cible TOP3 ET DSEO ≤ cible TOP3.
    A_CORRIGER  — SOSEO ou DSEO hors cible (contenu publiable mais sous-optimisé).
    BLOQUE      — impossible d'analyser (guide introuvable, API KO) OU asset check KO.
    SKIP        — YTG désactivé/non configuré pour ce blog (non-bloquant).

Persistance : le résultat est écrit dans `_shared/context/{url_slug}/audit_data.json`
sous la clé `ytg_qc`, réutilisant le hook de traçabilité existant.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Verdicts (constantes exportées)
VERDICT_OPTIMAL = "OPTIMAL"
VERDICT_A_CORRIGER = "A_CORRIGER"
VERDICT_BLOQUE = "BLOQUE"
VERDICT_SKIP = "SKIP"


def url_to_context_slug(url: str) -> str:
    """Reproduit exactement le slug de contexte de l'orchestrateur."""
    return re.sub(r"[^a-z0-9]+", "_", (url or "").lower()).strip("_")


@dataclass
class YTGQCResult:
    """Résultat d'un QC sémantique YTG sur un article."""
    url: str
    blog_id: str
    main_keyword: str = ""
    keyword_source: str = ""
    guide_id: str = ""
    verdict: str = VERDICT_SKIP
    our_soseo: Optional[float] = None
    our_dseo: Optional[float] = None
    target_soseo: Optional[float] = None
    target_dseo: Optional[float] = None
    soseo_ok: Optional[bool] = None
    dseo_ok: Optional[bool] = None
    under_optimized_terms: list[str] = field(default_factory=list)  # bleu/absent
    over_optimized_terms: list[str] = field(default_factory=list)   # rouge
    message: str = ""
    html_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class YTGQualityCheck:
    """
    Orchestre le QC sémantique : résolution KW → guide → analyse → verdict.

    Réutilise YTGAnalyzer (API), KeywordResolver (mot-clé) et le RateLimiter.
    Graceful : renvoie un verdict SKIP si YTG non configuré ou blog désactivé.
    """

    def __init__(
        self,
        analyzer=None,
        keyword_resolver=None,
        rate_limiter=None,
    ):
        self._analyzer = analyzer
        self._resolver = keyword_resolver
        self._rate_limiter = rate_limiter
        self._guide_index: Optional[dict] = None

    # ------------------------------------------------------------------
    # Lazy getters
    # ------------------------------------------------------------------

    def _get_analyzer(self):
        if self._analyzer is None:
            from scripts.audit.ytg_analyzer import YTGAnalyzer
            self._analyzer = YTGAnalyzer()
        return self._analyzer

    def _get_resolver(self):
        if self._resolver is None:
            from scripts.audit.keyword_resolver import KeywordResolver
            self._resolver = KeywordResolver()
        return self._resolver

    def _rate_wait(self):
        if self._rate_limiter is not None:
            self._rate_limiter.wait_if_needed()

    # ------------------------------------------------------------------
    # Guide resolution (keyword → guide_id, avec cache d'index)
    # ------------------------------------------------------------------

    def _resolve_guide_id(
        self, keyword: str, group_id: Optional[int] = None, lang: str = "fr"
    ) -> str:
        """Trouve le guide_id d'un mot-clé (index local), sinon crée le guide."""
        analyzer = self._get_analyzer()
        if not keyword:
            return ""

        if self._guide_index is None:
            guides = analyzer.list_guides_all(group_id=group_id)
            self._guide_index = analyzer.build_query_index(guides)

        guide = self._guide_index.get(keyword.lower().strip())
        if guide and guide.get("id"):
            return str(guide["id"])

        # Pas de guide existant → création (peut être lente : polling)
        logger.info(f"[YTG QC] Aucun guide pour '{keyword}', création…")
        self._rate_wait()
        result = analyzer.create_and_wait(keyword, language=lang)
        if result and result.guide_id:
            # Rafraîchir l'index pour les prochains lookups
            if self._guide_index is not None:
                self._guide_index[keyword.lower().strip()] = {"id": result.guide_id}
            return str(result.guide_id)
        return ""

    # ------------------------------------------------------------------
    # QC principal
    # ------------------------------------------------------------------

    def check_html(
        self,
        blog_id: str,
        url: str,
        html: str,
        *,
        main_keyword: str = "",
        keyword_source: str = "",
        guide_id: str = "",
        ytg_config: Optional[dict] = None,
        keyword_sources: Optional[list[str]] = None,
    ) -> YTGQCResult:
        """
        Analyse un HTML généré contre son guide YTG et rend un verdict.

        Args:
            blog_id: identifiant du blog (enseigna, superprof-ressources, …).
            url: URL de l'article (pour résoudre le mot-clé et le slug de contexte).
            html: contenu HTML généré à analyser.
            main_keyword: mot-clé déjà connu (sinon résolu via KeywordResolver).
            guide_id: guide déjà connu (sinon résolu via le mot-clé).
            ytg_config: bloc `ytg` de la config blog ({enabled, group_id, lang, …}).
            keyword_sources: ordre de priorité des sources de mot-clé (optionnel).
        """
        cfg = ytg_config or {}
        result = YTGQCResult(url=url, blog_id=blog_id)

        # 1. YTG activé pour ce blog ?
        if cfg.get("enabled") is False:
            result.verdict = VERDICT_SKIP
            result.message = "YTG désactivé pour ce blog (ytg.enabled=false)"
            return result

        analyzer = self._get_analyzer()
        if not analyzer.is_configured:
            result.verdict = VERDICT_SKIP
            result.message = "YTG non configuré (YTG_API_KEY absente)"
            return result

        group_id = cfg.get("group_id")
        lang = cfg.get("lang", "fr")

        # 2. Mot-clé principal
        if not main_keyword:
            resolver = self._get_resolver()
            main_keyword, keyword_source = resolver.resolve(
                blog_id, url=url, sources=keyword_sources or cfg.get("keyword_sources")
            )
        result.main_keyword = main_keyword
        result.keyword_source = keyword_source
        if not main_keyword:
            result.verdict = VERDICT_BLOQUE
            result.message = "Mot-clé principal introuvable (aucune source)"
            return result

        # 3. Guide YTG
        if not guide_id:
            guide_id = self._resolve_guide_id(main_keyword, group_id=group_id, lang=lang)
        result.guide_id = guide_id
        if not guide_id:
            result.verdict = VERDICT_BLOQUE
            result.message = f"Guide YTG introuvable/non créé pour '{main_keyword}'"
            return result

        # 4. Cibles concurrents (TOP3) — via le guide
        guide = analyzer.get_guide(guide_id, keyword=main_keyword)
        if guide:
            result.target_soseo = guide.top3_soseo
            result.target_dseo = guide.top3_dseo

        # 5. Analyse du contenu
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
        self._rate_wait()
        analysis = analyzer.analyze_content(guide_id, text)
        if not analysis:
            result.verdict = VERDICT_BLOQUE
            result.message = "Analyse YTG échouée (API)"
            return result

        result.our_soseo = analysis.get("our_soseo", 0)
        result.our_dseo = analysis.get("our_dseo", 0)

        # Termes sous/sur-optimisés (pour le rapport actionnable)
        colors = analysis.get("term_colors", {})
        result.under_optimized_terms = [
            t for t, c in colors.items() if c in ("blue", "absent")
        ]
        result.over_optimized_terms = [t for t, c in colors.items() if c == "red"]

        # 6. Verdict
        target_s = result.target_soseo or 0
        target_d = result.target_dseo or 0
        result.soseo_ok = (result.our_soseo >= target_s) if target_s else True
        result.dseo_ok = (result.our_dseo <= target_d) if target_d else True

        if result.soseo_ok and result.dseo_ok:
            result.verdict = VERDICT_OPTIMAL
            result.message = (
                f"SOSEO {result.our_soseo:.0f}% ≥ cible {target_s:.0f}% | "
                f"DSEO {result.our_dseo:.0f}% ≤ cible {target_d:.0f}%"
            )
        else:
            warnings = []
            if not result.soseo_ok:
                warnings.append(f"SOSEO {result.our_soseo:.0f}% < cible {target_s:.0f}%")
            if not result.dseo_ok:
                warnings.append(f"DSEO {result.our_dseo:.0f}% > cible {target_d:.0f}%")
            result.verdict = VERDICT_A_CORRIGER
            result.message = " | ".join(warnings)

        return result

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def persist(self, result: YTGQCResult, context_root: Optional[Path] = None) -> Optional[Path]:
        """Écrit le résultat sous `ytg_qc` dans _shared/context/{slug}/audit_data.json."""
        root = context_root or (PROJECT_ROOT / "_shared" / "context")
        slug = url_to_context_slug(result.url)
        audit_path = root / slug / "audit_data.json"

        data = {}
        if audit_path.exists():
            try:
                with open(audit_path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        elif not data:
            data = {"url": result.url, "blog_id": result.blog_id}

        data["ytg_qc"] = result.to_dict()

        try:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with open(audit_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return audit_path
        except Exception as e:
            logger.warning(f"[YTG QC] Persistance échouée ({audit_path}): {e}")
            return None


# ---------------------------------------------------------------------------
# Découverte des HTML générés par blog (structure réelle _shared/outputs)
# ---------------------------------------------------------------------------

def discover_generated_html(
    blog_id: str,
    slug_filter: str = "",
) -> list[Path]:
    """
    Liste les `*_refreshed.html` générés d'un blog sous `_shared/outputs/{blog_id}/html/**`.

    ⚠️ Structure réelle vérifiée : les HTML sont dans des sous-dossiers de batch
    (ex: html/articles_7_juillet_2026/), pas dans html_child_posts/html_parent_posts.

    Args:
        blog_id: identifiant du blog (dossier sous _shared/outputs/).
        slug_filter: si fourni, ne retient que les fichiers dont le nom contient ce slug.
    """
    from _shared.core.tenant_paths import TenantPaths
    html_root = TenantPaths(base_path=PROJECT_ROOT).output_dir(blog_id) / "html"
    if not html_root.exists():
        return []

    files = sorted(html_root.rglob("*_refreshed.html"))
    if slug_filter:
        needle = slug_filter.strip().lower().replace("_", "-")
        files = [f for f in files if needle in f.stem.lower().replace("_", "-")]
    return files
