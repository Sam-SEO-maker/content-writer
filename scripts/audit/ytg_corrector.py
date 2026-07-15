"""
YTG Semantic Corrector Module

Corrects articles based on YourTextGuru analysis:
- OVER-OPTIMIZED: reduces stuffed terms (red) using synonyms
- UNDER-OPTIMIZED: enriches missing terms (blue) naturally

Usage:
    corrector = YTGCorrector(site_id="enseigna.fr")
    results = corrector.run_batch()
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from scripts.audit.ytg_analyzer import YTGAnalyzer, YTGAPIError

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple sliding-window rate limiter for YTG API (15 req/min)."""

    def __init__(self, max_calls: int = 13, window: float = 60.0):
        self.timestamps: list[float] = []
        self.max_calls = max_calls
        self.window = window

    def wait_if_needed(self):
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < self.window]
        if len(self.timestamps) >= self.max_calls:
            sleep_time = self.window - (now - self.timestamps[0]) + 1.0
            logger.info(f"[RateLimit] Sleeping {sleep_time:.0f}s")
            time.sleep(sleep_time)
        self.timestamps.append(time.time())


# ---------------------------------------------------------------------------
# Corrector
# ---------------------------------------------------------------------------

class YTGCorrector:
    """
    Corrects articles based on YTG semantic analysis.

    For each article needing correction:
    1. Gets per-term analysis (colors + scores + targets)
    2. Builds a focused correction prompt
    3. Returns the prompt (caller handles Claude call)
    4. Validates corrected HTML via YTG re-analysis
    """

    MAX_RETRIES = 1

    def __init__(self, site_id: str = "enseigna.fr"):
        self.site_id = site_id
        from _shared.core.tenant_paths import TenantPaths
        self.base_path = TenantPaths(base_path=PROJECT_ROOT).output_dir(site_id)
        self.analyzer = YTGAnalyzer()
        self.rate_limiter = RateLimiter()
        self._guide_index: Optional[dict] = None

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def load_batch_results(self) -> list[dict]:
        """Load ytg_batch_results.json."""
        path = self.base_path / "ytg_batch_results.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def filter_needing_correction(self, results: list[dict]) -> list[dict]:
        """Filter articles that need correction (OVER or UNDER optimized)."""
        to_fix = []
        for r in results:
            if "status" in r:
                # NO_HTML entries: try to resolve anyway
                if r["status"] == "NO_HTML":
                    html_path = self.resolve_html_path(r["url"])
                    if html_path:
                        r.pop("status")  # fixable
                    else:
                        continue
                else:
                    continue

            s, d = r.get("soseo", 0), r.get("dseo", 0)
            tmin, dmax = r.get("target_min", 0), r.get("dseo_max", 0)

            if s >= tmin and d <= dmax:
                continue  # Already OK

            to_fix.append(r)

        # Sort: OVER-OPT first (higher risk), then UNDER-OPT
        to_fix.sort(key=lambda x: (-x.get("dseo", 0), x.get("soseo", 0)))
        return to_fix

    # ------------------------------------------------------------------
    # File Resolution
    # ------------------------------------------------------------------

    def resolve_html_path(self, url: str) -> Optional[Path]:
        """Resolve URL to HTML file path with multiple fallback strategies."""
        slug = url.strip("/").split("/")[-1]
        slug_u = slug.replace("-", "_")

        # Strategy 1: Direct URL-based match
        for folder in ["html_child_posts", "html_parent_posts"]:
            folder_path = self.base_path / folder
            if not folder_path.exists():
                continue

            # Try exact match with prefix
            candidate = folder_path / f"https_{self.site_id.replace('.', '_')}_{slug_u}_refreshed.html"
            if candidate.exists():
                return candidate

            # Strategy 2: Scan for slug in filenames
            for f in folder_path.glob("*_refreshed.html"):
                fname = f.stem.replace("_refreshed", "")
                fname_clean = fname.replace(f"https_{self.site_id.replace('.', '_')}_", "")
                if slug_u == fname_clean or slug in fname_clean.replace("_", "-"):
                    return f

            # Strategy 3: Partial slug match (for title-based filenames)
            slug_parts = slug.split("-")
            if len(slug_parts) >= 3:
                key_parts = slug_parts[:3]
                for f in folder_path.glob("*_refreshed.html"):
                    fname_lower = f.stem.lower().replace("_", "-")
                    if all(p in fname_lower for p in key_parts):
                        return f

        return None

    # ------------------------------------------------------------------
    # Guide Index
    # ------------------------------------------------------------------

    def get_guide_index(self) -> dict:
        """Build keyword->guide_id index (cached, one API call)."""
        if self._guide_index is not None:
            return self._guide_index

        all_guides = self.analyzer.list_guides_all()
        self._guide_index = {}
        for g in all_guides:
            query = g.get("query", g.get("keyword", ""))
            gid = g.get("id", "")
            if query and gid:
                self._guide_index[query.lower().strip()] = str(gid)

        logger.info(f"[YTGCorrector] Guide index: {len(self._guide_index)} entries")
        return self._guide_index

    def find_guide_id(self, keyword: str) -> Optional[str]:
        """Find guide_id for a keyword."""
        index = self.get_guide_index()
        return index.get(keyword.lower().strip())

    # ------------------------------------------------------------------
    # Term Analysis
    # ------------------------------------------------------------------

    def get_term_analysis(self, guide_id: str, html_text: str) -> Optional[dict]:
        """Get detailed per-term analysis from YTG API."""
        self.rate_limiter.wait_if_needed()
        try:
            result = self.analyzer.analyze_content(guide_id, html_text)
            return result
        except YTGAPIError as e:
            logger.error(f"[YTGCorrector] analyze_content failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Correction Prompt
    # ------------------------------------------------------------------

    def build_correction_prompt(
        self,
        html: str,
        term_analysis: dict,
        article_meta: dict,
        retry_info: Optional[dict] = None,
    ) -> str:
        """Build a focused correction prompt for Claude."""
        colors = term_analysis.get("term_colors", {})
        scores = term_analysis.get("term_scores", {})
        targets = term_analysis.get("term_targets", {})

        # Classify terms
        red_terms = []
        blue_terms = []
        absent_terms = []

        for term, color in colors.items():
            score = scores.get(term, 0)
            target = targets.get(term, {})
            green_min = target.get("green_min", 0)
            green_max = target.get("green_max", 0)

            if color == "red":
                red_terms.append({
                    "term": term,
                    "current": score,
                    "target_max": green_max,
                    "reduce_by": max(0, score - green_max) if green_max else score // 2,
                })
            elif color == "blue":
                blue_terms.append({
                    "term": term,
                    "current": score,
                    "target_min": green_min,
                    "add": max(0, green_min - score) if green_min else 1,
                })
            elif color == "absent" and green_min > 0:
                absent_terms.append({
                    "term": term,
                    "target_min": green_min,
                })

        # Sort by impact
        red_terms.sort(key=lambda x: -x["reduce_by"])
        blue_terms.sort(key=lambda x: -x["add"])

        # Build prompt
        kw = article_meta.get("kw", "")
        soseo = article_meta.get("soseo", 0)
        dseo = article_meta.get("dseo", 0)
        target_min = article_meta.get("target_min", 0)
        dseo_max = article_meta.get("dseo_max", 0)

        prompt_parts = [
            "# TACHE : Correction semantique YTG (patch cible)",
            "",
            f"Article : {kw}",
            f"SOSEO actuel : {soseo:.0f}% (cible >= {target_min:.0f}%)",
            f"DSEO actuel : {dseo:.0f}% (cible <= {dseo_max:.0f}%)",
            "",
            "## REGLES ABSOLUES",
            "- NE PAS modifier la structure HTML (H2, H3, sections)",
            "- NE PAS ajouter ou supprimer d'images, tableaux, videos, figcaption",
            "- NE PAS modifier les liens internes (href ET textes d'ancre EXACTS)",
            "- NE PAS modifier les callouts (disclaimers, CTA, bon reflexe, info highlight)",
            "- NE PAS modifier le tableau recapitulatif apres l'intro",
            "- NE PAS modifier les balises <figure>, <figcaption>, <table>, <img>, <a>",
            "- Conserver le vouvoiement et le ton dynamique/technique",
            "- Accents francais obligatoires",
            "- NE PAS utiliser le tiret cadratin",
            "- NE PAS ajouter de commentaires HTML",
            "",
        ]

        if red_terms:
            prompt_parts.append("## TERMES A REDUIRE (surdose rouge YTG)")
            prompt_parts.append("Remplacer des occurrences par un synonyme ou une periphrase :")
            for t in red_terms[:15]:
                prompt_parts.append(
                    f"- \"{t['term']}\" : score {t['current']}, cible max {t['target_max']}. "
                    f"Reduire d'environ {t['reduce_by']} occurrences."
                )
            prompt_parts.append("")

        if blue_terms:
            prompt_parts.append("## TERMES A ENRICHIR (sous-optimises bleu YTG)")
            prompt_parts.append("Ajouter naturellement dans le texte existant :")
            for t in blue_terms[:15]:
                prompt_parts.append(
                    f"- \"{t['term']}\" : score {t['current']}, cible min {t['target_min']}. "
                    f"Ajouter environ {t['add']} occurrences."
                )
            prompt_parts.append("")

        if absent_terms:
            prompt_parts.append("## TERMES ABSENTS (a integrer)")
            for t in absent_terms[:10]:
                prompt_parts.append(
                    f"- \"{t['term']}\" : absent, integrer {t['target_min']} fois."
                )
            prompt_parts.append("")

        if retry_info:
            prompt_parts.append("## NOTE : DEUXIEME TENTATIVE")
            prompt_parts.append(
                f"La premiere correction a atteint SOSEO={retry_info['soseo']:.0f}% "
                f"DSEO={retry_info['dseo']:.0f}%. "
                "Intensifier les corrections ci-dessus."
            )
            prompt_parts.append("")

        prompt_parts.extend([
            "## METHODE",
            "- Pour les termes a REDUIRE : remplacer par un synonyme contextuel dans les phrases existantes",
            "- Pour les termes a ENRICHIR : inserer dans des phrases existantes ou ajouter une courte phrase",
            "- Distribuer les ajouts uniformement (pas tous dans la meme section)",
            "- Les modifications doivent etre imperceptibles a la lecture",
            "",
            "## HTML A CORRIGER",
            "Retourne UNIQUEMENT le HTML corrige, sans commentaires, sans blocs de code markdown.",
            "",
            html,
        ])

        return "\n".join(prompt_parts)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_correction(
        self,
        original_html: str,
        corrected_html: str,
        guide_id: str,
        article_meta: dict,
    ) -> dict:
        """Validate a corrected article."""
        # 1. Asset count check
        def count_assets(html):
            soup = BeautifulSoup(html, "html.parser")
            return {
                "images": len(soup.find_all("img")),
                "tables": len(soup.find_all("table")),
                "links": len(soup.find_all("a", href=True)),
                "figures": len(soup.find_all("figure")),
            }

        orig_assets = count_assets(original_html)
        new_assets = count_assets(corrected_html)

        asset_ok = all(
            new_assets.get(k, 0) >= orig_assets.get(k, 0)
            for k in orig_assets
        )

        # 2. YTG re-analysis
        text = BeautifulSoup(corrected_html, "html.parser").get_text(" ", strip=True)
        self.rate_limiter.wait_if_needed()
        try:
            analysis = self.analyzer.analyze_content(guide_id, text)
        except Exception:
            analysis = None

        if not analysis:
            return {
                "status": "ANALYZE_FAILED",
                "asset_ok": asset_ok,
                "assets_before": orig_assets,
                "assets_after": new_assets,
            }

        new_soseo = analysis["our_soseo"]
        new_dseo = analysis["our_dseo"]
        tmin = article_meta.get("target_min", 0)
        dmax = article_meta.get("dseo_max", 0)

        # 3. Improvement check
        old_soseo = article_meta.get("soseo", 0)
        old_dseo = article_meta.get("dseo", 0)

        soseo_improved = new_soseo >= old_soseo or new_soseo >= tmin * 0.9
        dseo_improved = new_dseo <= old_dseo or new_dseo <= dmax

        in_target = new_soseo >= tmin * 0.9 and new_dseo <= dmax * 1.1

        if in_target and asset_ok:
            status = "IMPROVED"
        elif (soseo_improved or dseo_improved) and asset_ok:
            status = "PARTIAL"
        elif not asset_ok:
            status = "ASSET_VIOLATION"
        else:
            status = "NO_IMPROVEMENT"

        return {
            "status": status,
            "before": {"soseo": old_soseo, "dseo": old_dseo},
            "after": {"soseo": new_soseo, "dseo": new_dseo},
            "target": {"soseo_min": tmin, "dseo_max": dmax},
            "asset_ok": asset_ok,
            "assets_before": orig_assets,
            "assets_after": new_assets,
            "analysis": analysis,
        }

    # ------------------------------------------------------------------
    # Batch Processing (prompt generation only)
    # ------------------------------------------------------------------

    def prepare_batch(self) -> list[dict]:
        """
        Prepare all correction prompts for the batch.

        Returns a list of dicts with:
        - kw, url, html_path, guide_id
        - correction_prompt (ready to send to Claude)
        - article_meta (for validation)
        """
        results = self.load_batch_results()
        to_fix = self.filter_needing_correction(results)
        logger.info(f"[YTGCorrector] {len(to_fix)} articles to correct")

        batch = []
        for article in to_fix:
            kw = article["kw"]
            url = article["url"]

            # Resolve HTML
            html_path = self.resolve_html_path(url)
            if not html_path:
                logger.warning(f"[YTGCorrector] No HTML for: {kw}")
                continue

            # Find guide
            guide_id = self.find_guide_id(kw)
            if not guide_id:
                logger.warning(f"[YTGCorrector] No guide for: {kw}")
                continue

            # Get term analysis
            html = html_path.read_text(encoding="utf-8")
            text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
            analysis = self.get_term_analysis(guide_id, text)
            if not analysis:
                logger.warning(f"[YTGCorrector] Analysis failed for: {kw}")
                continue

            # Build prompt
            prompt = self.build_correction_prompt(html, analysis, article)

            batch.append({
                "kw": kw,
                "url": url,
                "html_path": str(html_path),
                "guide_id": guide_id,
                "correction_prompt": prompt,
                "article_meta": article,
                "original_html": html,
            })

        logger.info(f"[YTGCorrector] {len(batch)} prompts prepared")
        return batch

    def save_corrected(self, html_path: str, corrected_html: str) -> Path:
        """Save corrected HTML alongside original."""
        original = Path(html_path)
        corrected_path = original.parent / original.name.replace(
            "_refreshed.html", "_corrected.html"
        )
        corrected_path.write_text(corrected_html, encoding="utf-8")
        return corrected_path
