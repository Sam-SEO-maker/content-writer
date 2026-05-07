"""
Enums Module

Tous les Enums partagés du projet centralisés ici.
"""

from enum import Enum


# =========================================================================
# Enums pour Sheets et Workflow
# =========================================================================

class TaskStatus(Enum):
    """Statuts possibles d'une tâche."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AUDITING = "AUDITING"
    DECIDING = "DECIDING"
    WRITING = "WRITING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TriggerType(Enum):
    """Types de déclenchement."""
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    GSC_ALERT = "GSC_ALERT"
    STALE_DETECTION = "STALE_DETECTION"


class TaskPriority(Enum):
    """Niveaux de priorité des tâches."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


# =========================================================================
# Enums pour Stratégies de Refresh
# =========================================================================

class RefreshStrategy(Enum):
    """Stratégies de refresh disponibles."""
    NO_ACTION = "NO_ACTION"
    TITLE_OPTIMIZATION = "TITLE_OPTIMIZATION"
    PARTIAL_REFRESH = "PARTIAL_REFRESH"
    FULL_REFRESH = "FULL_REFRESH"
    SEMANTIC_REORIENTATION = "SEMANTIC_REORIENTATION"
    FORMAT_ADAPTATION = "FORMAT_ADAPTATION"
    EEAT_REWRITE = "EEAT_REWRITE"
    REDIRECT_301 = "REDIRECT_301"
    LONG_TAIL_SPECIALIZATION = "LONG_TAIL_SPECIALIZATION"


# =========================================================================
# Enums pour Analyse d'Intention
# =========================================================================

class SearchIntent(Enum):
    """Types d'intention de recherche."""
    INFORMATIONAL = "informational"  # Cherche de l'information
    NAVIGATIONAL = "navigational"  # Cherche un site spécifique
    TRANSACTIONAL = "transactional"  # Prêt à acheter/agir
    COMMERCIAL = "commercial"  # Compare avant d'acheter


class ContentFormat(Enum):
    """Formats de contenu."""
    GUIDE = "guide"
    LISTICLE = "listicle"
    COMPARISON = "comparison"
    FAQ = "faq"
    TUTORIAL = "tutorial"
    TOOL = "tool"
    OTHER = "other"


# =========================================================================
# Enums pour Cannibalisation
# =========================================================================

class CannibalizationSeverity(Enum):
    """Niveaux de sévérité de la cannibalisation."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResolutionStrategy(Enum):
    """Stratégies de résolution de la cannibalisation."""
    MERGE = "merge"  # Fusionner les contenus
    DIFFERENTIATE = "differentiate"  # Différencier avec longue traîne
    REDIRECT_301 = "redirect_301"  # Rediriger vers l'URL principale
    NOINDEX = "noindex"  # Désindexer la page secondaire
    CANONICAL = "canonical"  # Ajouter une balise canonical
