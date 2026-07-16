"""
Workflow Models Module

Modèles pour l'orchestration et le suivi des workflows.
"""

from dataclasses import dataclass, field
from typing import Optional

from .enums import TaskPriority


@dataclass
class RefreshWorkflowResult:
    """Résultat complet d'un workflow de refresh."""
    url: str
    blog_id: str
    success: bool
    action_taken: str
    audit_score: int
    rewrite_type: Optional[str]
    new_title: Optional[str]
    new_meta: Optional[str]
    assets_valid: bool
    errors: list[str]
    execution_time_seconds: float
    main_keyword: str = field(default="")
    # PAA + secondary keywords issus de la SERP (audit live) — permettent au CLI
    # refresh unitaire de peupler le contexte de génération sans passer par le Sheet.
    people_also_ask: str = field(default="")
    secondary_keywords: str = field(default="")
    # Guide sémantique YTG calculé au STEP 2.5 de process_url — propagé au CLI
    # refresh pour (a) injecter les termes dans le prompt de génération et
    # (b) réutiliser le guide au QC post-génération sans le recréer.
    ytg_guide_id: str = field(default="")
    ytg_semantic_field: list[str] = field(default_factory=list)
    ytg_competitor_targets: dict = field(default_factory=dict)
    ytg_term_colors: dict = field(default_factory=dict)


@dataclass
class WorkflowProgress:
    """Suivi de la progression d'un workflow."""
    url: str
    current_step: str
    steps_completed: list[str]
    steps_remaining: list[str]
    progress_percent: int
    started_at: str
    last_update: str
    errors: list[str]


@dataclass(order=True)
class ScheduledTask:
    """Tâche planifiée avec priorité."""
    priority: int
    url: str = field(compare=False)
    blog_id: str = field(compare=False)
    action: str = field(compare=False)
    scheduled_at: str = field(compare=False)
    metadata: dict = field(default_factory=dict, compare=False)
    main_keyword: str = field(default="", compare=False)  # Mot-clé fourni optionnel
