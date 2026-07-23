"""
Shared Models Package

Centralises all the project's data models (dataclasses and enums).
Allows simplified imports: from _shared.core.models import ImageAsset, TaskStatus
"""

# Enums
from .enums import (
    TaskStatus,
    TriggerType,
    TaskPriority,
    RefreshStrategy,
    SearchIntent,
    ContentFormat,
    CannibalizationSeverity,
    ResolutionStrategy
)

# Audit Models
from .audit_models import (
    ImageAsset,
    CTABlock,
    LinkAsset,
    HeadingStructure,
    HTMLAnalysisResult,
    KeywordPerformance,
    URLPerformance,
    QuickWin,
    GSCAnalysisResult,
    SERPResult,
    SERPFeature,
    SERPAnalysisResult,
    CannibalizingURL,
    CannibalizationIssue,
    CannibalizationResult,
    IntentSignal,
    IntentShift,
    IntentAnalysisResult,
    AuditReport,
    AssetValidationResult
)

# Decision Models
from .decision_models import (
    RuleMatch,
    DecisionResult,
    StrategyConfig
)

# Sheets Models
from .sheets_models import (
    EnseignaAvisRow,
    URLTask,
    AuditResultRow,
    RefreshResultRow,
    RefreshAuditRow
)

# Workflow Models
from .workflow_models import (
    RefreshWorkflowResult,
    WorkflowProgress,
    ScheduledTask
)

# Ghostwriter Models
from .ghostwriter_models import (
    SectionDiff,
    ContentDiff,
    RewriteResult
)

# Site Models
from .site_models import SiteConfig

# Sitemap Models
from .sitemap_models import (
    SitemapType,
    SitemapURL,
    SitemapCache,
    FetchResult,
    StaleContent
)

# Linking Models
from .linking_models import (
    LinkMapping,
    InjectionPoint,
    InjectionResult,
    InjectionReport
)

__all__ = [
    # Enums
    "TaskStatus",
    "TriggerType",
    "TaskPriority",
    "RefreshStrategy",
    "SearchIntent",
    "ContentFormat",
    "CannibalizationSeverity",
    "ResolutionStrategy",
    # Audit Models
    "ImageAsset",
    "CTABlock",
    "LinkAsset",
    "HeadingStructure",
    "HTMLAnalysisResult",
    "KeywordPerformance",
    "URLPerformance",
    "QuickWin",
    "GSCAnalysisResult",
    "SERPResult",
    "SERPFeature",
    "SERPAnalysisResult",
    "CannibalizingURL",
    "CannibalizationIssue",
    "CannibalizationResult",
    "IntentSignal",
    "IntentShift",
    "IntentAnalysisResult",
    "AuditReport",
    "AssetValidationResult",
    # Decision Models
    "RuleMatch",
    "DecisionResult",
    "StrategyConfig",
    # Sheets Models
    "EnseignaAvisRow",
    "URLTask",
    "AuditResultRow",
    "RefreshResultRow",
    "RefreshAuditRow",
    # Workflow Models
    "RefreshWorkflowResult",
    "WorkflowProgress",
    "ScheduledTask",
    # Ghostwriter Models
    "SectionDiff",
    "ContentDiff",
    "RewriteResult",
    # Site Models
    "SiteConfig",
    # Sitemap Models
    "SitemapType",
    "SitemapURL",
    "SitemapCache",
    "FetchResult",
    "StaleContent",
    # Linking Models
    "LinkMapping",
    "InjectionPoint",
    "InjectionResult",
    "InjectionReport",
]
