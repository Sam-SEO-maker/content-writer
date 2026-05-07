"""
Audit Models Module

Tous les modèles de données pour les analyses d'audit (HTML, GSC, SERP, Cannibalization, Intent).
"""

from dataclasses import dataclass, field
from typing import Optional

from .enums import (
    SearchIntent,
    ContentFormat,
    CannibalizationSeverity,
    ResolutionStrategy
)


# =========================================================================
# Modèles HTML
# =========================================================================

@dataclass
class ImageAsset:
    """Représente une image extraite."""
    src: str
    alt: str
    html: str
    context_h2: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_featured_image: bool = False  # True si c'est l'image à la Une


@dataclass
class CTABlock:
    """Représente un bloc CTA stylé."""
    html: str
    cta_type: str  # 'superprof_button', 'definition_box', 'info_box'
    context_h2: Optional[str] = None
    required: bool = False  # True pour CTA Superprof obligatoire


@dataclass
class LinkAsset:
    """Représente un lien extrait."""
    href: str
    anchor: str
    html: str
    link_type: str  # 'internal', 'external', 'superprof'
    context_h2: Optional[str] = None
    is_blacklisted: bool = False


@dataclass
class HeadingStructure:
    """Structure des titres de l'article."""
    h1: str
    h2_list: list[str] = field(default_factory=list)
    h3_list: list[str] = field(default_factory=list)


@dataclass
class HTMLAnalysisResult:
    """Résultat de l'analyse HTML."""
    url: str
    title: str
    meta_description: str
    headings: HeadingStructure
    word_count: int
    reading_time_minutes: int
    images: list[ImageAsset]  # Images contextuelles (sans featured image)
    internal_links: list[LinkAsset]
    external_links: list[LinkAsset]
    superprof_link: Optional[LinkAsset]
    text_content: str
    raw_html: str

    # Métriques de qualité
    has_faq_section: bool = False
    has_table: bool = False
    has_list: bool = False
    paragraph_count: int = 0

    # Nouveaux champs pour amélioration du workflow
    featured_image: Optional[ImageAsset] = None  # Image à la Une (exclue du corps)
    cta_blocks: list = field(default_factory=list)  # Blocs CTA stylés


# =========================================================================
# Modèles GSC
# =========================================================================

@dataclass
class KeywordPerformance:
    """Performance d'un mot-clé spécifique."""
    query: str
    clicks: int
    impressions: int
    ctr: float  # Pourcentage
    position: float
    trend_clicks: Optional[float] = None  # Variation en %
    trend_position: Optional[float] = None  # Variation en positions


@dataclass
class URLPerformance:
    """Performance globale d'une URL."""
    url: str
    clicks_30d: int
    impressions_30d: int
    ctr_30d: float
    avg_position_30d: float

    clicks_90d: int = 0
    impressions_90d: int = 0

    # Tendances (comparaison période précédente)
    clicks_trend: float = 0.0  # Variation en %
    impressions_trend: float = 0.0
    position_trend: float = 0.0  # Positions gagnées/perdues

    # Mots-clés associés
    keywords: list[KeywordPerformance] = field(default_factory=list)
    main_keyword: Optional[str] = None


@dataclass
class QuickWin:
    """Opportunité d'optimisation rapide."""
    url: str
    query: str
    impressions: int
    ctr: float
    position: float
    potential: str  # 'high', 'medium', 'low'
    recommendation: str


@dataclass
class GSCAnalysisResult:
    """Résultat complet de l'analyse GSC."""
    url: str
    performance: URLPerformance
    quick_wins: list[QuickWin]
    indexation_status: str  # 'INDEXED', 'NOT_INDEXED', 'UNKNOWN'

    # Signaux d'alerte
    is_declining: bool = False
    decline_severity: str = "none"  # 'none', 'moderate', 'severe'
    alert_messages: list[str] = field(default_factory=list)


# =========================================================================
# Modèles SERP
# =========================================================================

@dataclass
class SERPResult:
    """Un résultat de la SERP."""
    position: int
    url: str
    title: str
    description: str
    domain: str
    format_type: str  # 'guide', 'listicle', 'faq', 'comparison', 'tool', 'other'
    keywords: list[str] = field(default_factory=list)  # Mots-clés extraits du titre/description


@dataclass
class SERPFeature:
    """Une feature SERP (PAA, Featured Snippet, etc.)."""
    feature_type: str  # 'featured_snippet', 'paa', 'local_pack', 'video', etc.
    content: Optional[str] = None
    questions: list[str] = field(default_factory=list)  # Pour PAA


@dataclass
class SERPAnalysisResult:
    """Résultat complet de l'analyse SERP."""
    keyword: str
    organic_results: list[SERPResult]
    features: list[SERPFeature]

    # Analyse du format dominant
    dominant_format: str
    format_distribution: dict[str, int]

    # PAA (People Also Ask)
    paa_questions: list[str]

    # Position de l'URL analysée (si présente)
    our_position: Optional[int] = None
    our_url_found: bool = False

    # Recommandations
    format_mismatch: bool = False
    recommended_format: Optional[str] = None


# =========================================================================
# Modèles Cannibalization
# =========================================================================

@dataclass
class CannibalizingURL:
    """Une URL en compétition pour le même mot-clé."""
    url: str
    position: float
    clicks: int
    impressions: int
    ctr: float
    overlap_score: float  # Score de chevauchement (0-100)


@dataclass
class CannibalizationIssue:
    """Un problème de cannibalisation détecté."""
    keyword: str
    primary_url: str
    competing_urls: list[CannibalizingURL]
    severity: CannibalizationSeverity
    max_overlap: float
    recommended_strategy: ResolutionStrategy
    action_message: str


@dataclass
class CannibalizationResult:
    """Résultat de l'analyse de cannibalisation."""
    url: str
    has_cannibalization: bool
    issues: list[CannibalizationIssue]
    total_competing_urls: int
    most_severe_issue: Optional[CannibalizationIssue] = None

    # Pour le Sheets
    requires_action: bool = False
    suggested_action: str = ""


# =========================================================================
# Modèles Intent
# =========================================================================

@dataclass
class IntentSignal:
    """Un signal d'intention détecté."""
    signal_type: str
    source: str  # 'keyword_variant', 'serp_feature', 'competitor_content'
    description: str
    weight: float  # Importance du signal (0-1)


@dataclass
class IntentShift:
    """Un changement d'intention détecté."""
    from_intent: SearchIntent
    to_intent: SearchIntent
    confidence: float  # 0-100
    signals: list[IntentSignal]
    recommendation: str


@dataclass
class IntentAnalysisResult:
    """Résultat de l'analyse d'intention."""
    keyword: str
    current_content_intent: SearchIntent
    current_content_format: ContentFormat
    detected_serp_intent: SearchIntent
    detected_serp_format: ContentFormat

    # Shifts détectés
    intent_shift_detected: bool
    format_shift_detected: bool
    shifts: list[IntentShift]

    # Variantes de mots-clés
    rising_variants: list[dict]
    declining_variants: list[dict]

    # Recommandations
    recommendations: list[str]


# =========================================================================
# Modèle Audit Complet
# =========================================================================

@dataclass
class AuditReport:
    """Rapport d'audit complet pour une URL."""
    url: str
    blog_id: str
    audit_date: str

    # Résultats des analyseurs
    html_analysis: HTMLAnalysisResult
    gsc_analysis: GSCAnalysisResult
    serp_analysis: Optional[SERPAnalysisResult]
    cannibalization: CannibalizationResult
    intent_analysis: Optional[IntentAnalysisResult]

    # Scores et métriques agrégés
    overall_score: int  # 0-100
    eeat_score: int  # 0-100
    freshness_score: int  # 0-100

    # Alertes et recommandations
    alerts: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Décisions suggérées
    suggested_action: str = ""  # 'TITLE_OPT', 'PARTIAL_REFRESH', 'FULL_REWRITE', etc.
    action_priority: int = 5  # 1-5 (1 = haute priorité)

    # Assets extraits (pour préservation)
    assets: dict = field(default_factory=dict)

    # Mot-clé fourni (optionnel, pour forcer analyse SERP)
    provided_keyword: str = ""  # Mot-clé fourni via spreadsheet


# =========================================================================
# Modèle Validation Assets
# =========================================================================

@dataclass
class AssetValidationResult:
    """Résultat de la validation des assets."""
    is_valid: bool
    images_original: int  # Images contextuelles uniquement (sans featured image)
    images_new: int
    images_valid: bool
    links_original: int
    links_new: int
    links_valid: bool
    superprof_count: int
    superprof_valid: bool
    blacklist_violations: list[str]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Nouveaux champs pour CTA
    cta_superprof_valid: bool = True  # CTA Superprof présent
    cta_blocks_preserved: int = 0  # Nombre de blocs CTA préservés


# =========================================================================
# Modèles Editorial Audit (Quality Gate)
# =========================================================================

@dataclass
class FactCheckResult:
    """Résultat de vérification factuelle (fact-checking)."""
    checked: bool
    is_valid: bool
    error_type: Optional[str] = None  # "date_mismatch", "obsolete_stat", "missing_entity"
    expected_value: Optional[str] = None
    found_value: Optional[str] = None
    context: Optional[str] = None
    severity: str = "medium"  # "critical", "high", "medium", "low"


@dataclass
class EEATDiagnosis:
    """Diagnostic E-E-A-T du contenu."""
    experience_score: int  # 0-100
    expertise_score: int  # 0-100
    authoritativeness_score: int  # 0-100
    trustworthiness_score: int  # 0-100
    overall_score: int  # 0-100 (moyenne pondérée)

    sources_count: int = 0
    sources_authoritative_count: int = 0
    disclaimers_present: bool = False
    disclaimers_required: bool = False

    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)


@dataclass
class EditorialAuditResult:
    """
    Résultat complet de l'audit éditorial (Quality Gate).

    Score final (1-10) basé sur:
    - Truth (40%): Vérifications factuelles
    - E-E-A-T (30%): Expertise, autorité, confiance
    - Freshness (20%): Fraîcheur des données
    - Genericness (10%): Éviter phrases génériques
    """
    url: str
    topic: Optional[str] = None  # Topic détecté (ex: "parcoursup_2026")
    ymyl_level: str = "low"  # "very_high", "high", "medium", "low"

    # Scores composants (0-100)
    truth_score: int = 0
    eeat_score: int = 0
    freshness_score: int = 0
    genericness_score: int = 0

    # Score final (1-10)
    overall_score: float = 0.0

    # Fact-checking results
    fact_checks: list[FactCheckResult] = field(default_factory=list)
    factual_errors_count: int = 0
    critical_errors_count: int = 0

    # E-E-A-T diagnosis
    eeat_diagnosis: Optional[EEATDiagnosis] = None

    # Freshness issues
    obsolete_stats_count: int = 0
    missing_dates_count: int = 0

    # Genericness issues
    generic_statements_count: int = 0
    forbidden_generics_found: list[str] = field(default_factory=list)

    # Quality gate decision
    should_proceed: bool = True  # False si score < threshold
    blocking_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Metadata
    audit_date: Optional[str] = None
    execution_time_ms: int = 0
