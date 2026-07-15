"""
Boucle de correction sémantique automatique YTG.

Enchaîne, pour un article dont le QC a rendu le verdict A_CORRIGER :
    1. analyse par terme (couleurs YTG) → prompt de correction ciblée,
    2. réécriture du HTML par un SUB-AGENT Claude Code (plan Max),
    3. re-validation (assets préservés + SOSEO/DSEO re-mesurés),
    4. retry (borné) si toujours hors cible.

⚠️ RÈGLES D'EXÉCUTION (imposées) :
  - La correction passe TOUJOURS par les sub-agents Claude Code (plan Max 20x),
    JAMAIS par l'API Anthropic payante.
  - Le HTML corrigé n'est JAMAIS écrit dans la conversation/session : le sub-agent
    écrit directement le fichier `_corrected.html` sur le disque, et cette boucle
    ne fait que préparer les prompts puis re-valider les fichiers produits.

Ce module produit donc un "plan de correction" (prompts + manifest JSON) que la
couche appelante (l'agent orchestrateur) exécute en lançant un sub-agent par
article, chacun ayant pour consigne d'écrire le `_corrected.html` sur disque.
La re-validation (assets + scores YTG) est ensuite automatique via revalidate().

Réutilise YTGCorrector.build_correction_prompt() et validate_correction()
(assets préservés, blocs Gutenberg/callouts explicitement non modifiés).
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from scripts.audit.ytg_corrector import YTGCorrector, RateLimiter

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

MAX_CORRECTION_RETRIES = 1

# Consigne système ajoutée à chaque prompt de correction destiné au sub-agent.
# Elle impose l'écriture sur disque et interdit tout retour du HTML dans le chat.
SUBAGENT_INSTRUCTIONS = (
    "Tu es un sous-agent de correction sémantique. Applique les corrections "
    "ci-dessous au HTML puis ÉCRIS le résultat dans le fichier indiqué "
    "(chemin `output_path`) avec l'outil Write. N'affiche JAMAIS le HTML dans "
    "ta réponse : écris-le uniquement dans le fichier. Ta réponse finale doit "
    "se limiter à une ligne de confirmation (chemin écrit + nb de modifications)."
)


@dataclass
class CorrectionTask:
    """Un item de correction à confier à un sub-agent (mode plan Max)."""
    url: str
    blog_id: str
    guide_id: str
    html_path: str          # _refreshed.html source
    output_path: str        # _corrected.html à écrire par le sub-agent
    prompt_path: str        # fichier .txt contenant le prompt complet
    targets: dict = field(default_factory=dict)
    current_scores: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RevalidationResult:
    """Résultat de la re-validation d'un `_corrected.html` produit par le sub-agent."""
    url: str
    blog_id: str
    status: str = ""        # IMPROVED / PARTIAL / NO_IMPROVEMENT / ASSET_VIOLATION / MISSING / ERROR
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    asset_ok: Optional[bool] = None
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class YTGAutoCorrector:
    """
    Prépare les tâches de correction (mode sub-agent plan Max) et re-valide.

    Le flux d'exécution :
        tasks = corrector.prepare(items)        # écrit prompts + manifest
        # → l'agent lance 1 sub-agent par task (Task tool), qui écrit output_path
        results = [corrector.revalidate(t) for t in tasks]   # assets + scores
    """

    def __init__(
        self,
        blog_id: str,
        analyzer=None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.blog_id = blog_id
        self._corrector = YTGCorrector(site_id=blog_id)
        if analyzer is not None:
            self._corrector.analyzer = analyzer
        if rate_limiter is not None:
            self._corrector.rate_limiter = rate_limiter

    # ------------------------------------------------------------------
    # Préparation des tâches de correction
    # ------------------------------------------------------------------

    def prepare_one(
        self,
        url: str,
        html_path: Path,
        guide_id: str,
        targets: dict,
        current_scores: Optional[dict] = None,
    ) -> Optional[CorrectionTask]:
        """
        Analyse un article A_CORRIGER et écrit son prompt de correction ciblée.

        Retourne un CorrectionTask (à confier à un sub-agent), ou None si l'analyse
        par terme échoue.
        """
        html_path = Path(html_path)
        if not html_path.exists():
            logger.warning(f"[YTG AutoCorrect] HTML introuvable: {html_path}")
            return None

        html = html_path.read_text(encoding="utf-8")
        article_meta = {
            "kw": "",
            "url": url,
            "soseo": (current_scores or {}).get("soseo", 0),
            "dseo": (current_scores or {}).get("dseo", 0),
            "target_min": targets.get("top3_soseo", 0),
            "dseo_max": targets.get("top3_dseo", 0),
        }

        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        self._corrector.rate_limiter.wait_if_needed()
        term_analysis = self._corrector.analyzer.analyze_content(guide_id, text)
        if not term_analysis:
            logger.warning(f"[YTG AutoCorrect] analyse par terme échouée: {url}")
            return None

        base_prompt = self._corrector.build_correction_prompt(html, term_analysis, article_meta)

        output_path = html_path.parent / html_path.name.replace(
            "_refreshed.html", "_corrected.html"
        )
        prompt_path = html_path.parent / f"{html_path.stem.replace('_refreshed', '')}_ytg_fix_prompt.txt"

        full_prompt = (
            f"{SUBAGENT_INSTRUCTIONS}\n\n"
            f"output_path: {output_path}\n\n"
            f"{base_prompt}"
        )
        prompt_path.write_text(full_prompt, encoding="utf-8")

        return CorrectionTask(
            url=url,
            blog_id=self.blog_id,
            guide_id=guide_id,
            html_path=str(html_path),
            output_path=str(output_path),
            prompt_path=str(prompt_path),
            targets=targets,
            current_scores=current_scores or {},
        )

    def prepare(self, items: list[dict]) -> list[CorrectionTask]:
        """
        Prépare toutes les tâches de correction et écrit un manifest JSON.

        items : liste de dicts {url, html_path, guide_id, targets, current_scores}.
        """
        tasks = []
        for it in items:
            task = self.prepare_one(
                url=it["url"],
                html_path=it["html_path"],
                guide_id=it["guide_id"],
                targets=it.get("targets", {}),
                current_scores=it.get("current_scores"),
            )
            if task:
                tasks.append(task)

        if tasks:
            from _shared.core.tenant_paths import TenantPaths
            manifest = TenantPaths(base_path=PROJECT_ROOT).output_dir(self.blog_id) / "ytg_fix_manifest.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"[YTG AutoCorrect] {len(tasks)} tâche(s) préparée(s) — manifest: {manifest}")
        return tasks

    # ------------------------------------------------------------------
    # Re-validation d'un HTML corrigé produit par le sub-agent
    # ------------------------------------------------------------------

    def revalidate(self, task: CorrectionTask) -> RevalidationResult:
        """
        Re-valide le `_corrected.html` écrit par le sub-agent (assets + scores YTG).

        À appeler APRÈS que le sub-agent a écrit output_path.
        """
        res = RevalidationResult(url=task.url, blog_id=task.blog_id)
        original_path = Path(task.html_path)
        corrected_path = Path(task.output_path)

        if not corrected_path.exists():
            res.status = "MISSING"
            res.message = f"HTML corrigé absent: {corrected_path} (sub-agent non exécuté ?)"
            return res

        original_html = original_path.read_text(encoding="utf-8")
        corrected_html = corrected_path.read_text(encoding="utf-8")
        article_meta = {
            "soseo": task.current_scores.get("soseo", 0),
            "dseo": task.current_scores.get("dseo", 0),
            "target_min": task.targets.get("top3_soseo", 0),
            "dseo_max": task.targets.get("top3_dseo", 0),
        }

        try:
            validation = self._corrector.validate_correction(
                original_html, corrected_html, task.guide_id, article_meta
            )
        except Exception as e:
            res.status = "ERROR"
            res.message = f"validate_correction a échoué: {e}"
            return res

        res.status = validation.get("status", "ERROR")
        res.before = validation.get("before", {})
        res.after = validation.get("after", {})
        res.asset_ok = validation.get("asset_ok")
        res.message = (
            f"assets_ok={res.asset_ok} "
            f"SOSEO {res.before.get('soseo', 0):.0f}%→{res.after.get('soseo', 0):.0f}% "
            f"DSEO {res.before.get('dseo', 0):.0f}%→{res.after.get('dseo', 0):.0f}%"
        )
        return res
