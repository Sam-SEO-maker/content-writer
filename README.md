# SEO Refresh Agent

Agent autonome de rafraîchissement de contenus SEO, piloté par Google Sheets, avec détection de cannibalisation, audit qualité, et mode Ghostwriter.

---

## Fonctionnalités

- **Audit Automatique** : Analyse GSC, DataforSEO, structure HTML
- **Détection Cannibalisation** : Identification des URLs concurrentes
- **Shift d'Intention** : Détection des changements d'intention de recherche
- **Decision Engine** : Règles configurables pour choisir la stratégie
- **Mode Ghostwriter** : Réécriture différentielle (économie de tokens)
- **Préservation Assets** : Images et liens jamais supprimés
- **Multi-Blog** : Support de N blogs avec configuration individuelle
- **Pilotage Sheets** : Workflow complet via Google Sheets

---

## Installation

```bash
# Cloner le projet
cd "Content Writer"

# Installer les dépendances
pip install -r requirements.txt

# Créer les dossiers de données
mkdir -p data/cache data/logs
```

---

## Configuration

### 1. Google Sheets

Configuration Google Sheets disponible dans la documentation partagée.

### 2. Configuration Blog

Éditer les fichiers dans `config/blogs/` :

```json
{
  "blog_id": "mon-blog",
  "domain": "mon-blog.fr",
  "gsc_property": "sc-domain:mon-blog.fr",
  "subject_category": "education_reviews",
  "sheets_config": {
    "spreadsheet_id": "VOTRE_ID"
  }
}
```

### 3. Règles de Décision

Personnaliser `config/decision_rules.json` si nécessaire.

---

## Usage

### Traiter une URL unique

```bash
python main.py --mode single \
  --url "https://enseigna.fr/avis-acadomia" \
  --blog enseigna
```

### Audit rapide (sans réécriture)

```bash
python main.py --mode audit \
  --url "https://enseigna.fr/avis-acadomia" \
  --blog enseigna \
  --verbose
```

### Traiter un batch depuis Sheets

```bash
python main.py --mode batch \
  --spreadsheet-id "1AbCdEfGhIjKlMnOpQrStUvWxYz" \
  --limit 10
```

### Mode schedulé (automatique)

```bash
python main.py --mode scheduled \
  --spreadsheet-id "1AbCdEfGhIjKlMnOpQrStUvWxYz" \
  --interval 3600
```

### Forcer une action spécifique

```bash
python main.py --mode single \
  --url "https://example.com/article" \
  --blog enseigna \
  --force-action TITLE_OPTIMIZATION
```

**Actions disponibles :**
- `NO_ACTION`
- `TITLE_OPTIMIZATION`
- `PARTIAL_REFRESH`
- `FULL_REFRESH`
- `SEMANTIC_REORIENTATION`
- `FORMAT_ADAPTATION`
- `EEAT_REWRITE`

---

## Architecture

```
Content Writer/
├── _shared/                # Ressources partagées centralisées
│   ├── cache/              # Futures fonctionnalités de cache
│   ├── config/             # Configuration blogs et règles
│   │   ├── blogs/          # Configuration par blog
│   │   ├── decision_rules.json
│   │   └── prompts_dispatch.json
│   ├── core/               # Core Python (modèles, utils, constantes)
│   │   ├── models/         # Dataclasses et Enums partagés
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   ├── audit_models.py
│   │   │   ├── decision_models.py
│   │   │   ├── sheets_models.py
│   │   │   └── workflow_models.py
│   │   ├── utils/          # Fonctions utilitaires partagées
│   │   │   ├── __init__.py
│   │   │   ├── html_utils.py
│   │   │   ├── text_utils.py
│   │   │   └── scoring_utils.py
│   │   └── constants.py    # Constantes globales
│   ├── docs/               # Documentation SEO
│   │   ├── GEO_2026_GUIDELINES.md
│   │   ├── EEAT_2026_GUIDELINES.md
│   │   ├── CONTENT_REFRESH_GUIDE.md
│   │   ├── SEO_GUIDELINES.md
│   │   └── GOOGLE_SHEETS_SETUP.md
│   ├── modules/            # Modules de détection
│   │   ├── deindexation_detector.md
│   │   └── topic_discovery_refresh.md
│   └── prompts/            # Prompts par matière/stratégie
│       ├── subjects/
│       └── strategies/
│
├── scripts/                # Logique métier Python
│   ├── agent/              # Orchestrateur principal
│   ├── audit/              # Moteur d'audit
│   ├── decision/           # Logique de décision
│   ├── ghostwriter/        # Mode réécriture
│   ├── assets/             # Préservation assets
│   ├── sheets/             # Client Google Sheets
│   └── cache/              # Cache documentation
│
├── data/                   # Données runtime (gitignored)
│   ├── cache/
│   └── logs/
│
├── outputs/                # Résultats générés
├── tests/                  # Tests unitaires
├── main.py                 # Point d'entrée CLI
├── requirements.txt
└── .gitignore
```

---

## Imports depuis _shared/core/

Le projet utilise une architecture centralisée où tous les modèles, utilitaires et constantes partagés sont regroupés dans `_shared/core/`.

### Modèles

```python
from _shared.core.models import (
    # Enums
    TaskStatus, RefreshStrategy, ContentFormat, SearchIntent,
    CannibalizationSeverity, ResolutionStrategy,

    # Audit Models
    ImageAsset, LinkAsset, CTABlock, HeadingStructure, CoconStructure,
    HTMLAnalysisResult, KeywordPerformance, URLPerformance, QuickWin,
    GSCAnalysisResult, SERPResult, SERPFeature, SERPAnalysisResult,
    CannibalizingURL, CannibalizationIssue, CannibalizationResult,
    IntentSignal, IntentShift, IntentAnalysisResult, AuditReport,

    # Decision Models
    RuleMatch, DecisionResult, StrategyConfig,

    # Sheets Models
    URLTask, AuditResultRow, RefreshResultRow,

    # Workflow Models
    RefreshWorkflowResult, WorkflowProgress, ScheduledTask,

    # Asset Models
    AssetValidationResult,
)
```

### Utilitaires

```python
from _shared.core.utils import (
    # HTML Utils
    extract_images, extract_links, extract_cta_blocks,

    # Text Utils
    clean_text, calculate_word_count, calculate_reading_time,

    # Scoring Utils
    calculate_similarity, calculate_trends, calculate_overlap_score,
)
```

### Constantes

```python
from _shared.core.constants import (
    # Domaines
    BLACKLIST_DOMAINS,
    SUPERPROF_DOMAIN,

    # Thresholds GSC
    CTR_LOW_THRESHOLD,
    CTR_GOOD_THRESHOLD,
    IMPRESSIONS_SIGNIFICANT,
    POSITION_DECLINE_ALERT,
    TRAFFIC_DECLINE_MODERATE,
    TRAFFIC_DECLINE_SEVERE,

    # Thresholds Cannibalization
    OVERLAP_VERY_LOW,
    OVERLAP_LOW,
    OVERLAP_MEDIUM,
    OVERLAP_HIGH,

    # Thresholds Intent
    INTENT_SHIFT_THRESHOLD,
    VARIANT_TREND_THRESHOLD,

    # Autres
    SIMILARITY_THRESHOLD,
    WORDS_PER_MINUTE,
)
```

---

## Workflow en 7 Étapes

| # | Étape | Description |
|---|-------|-------------|
| 0 | **Selection** | Identifier articles à rafraîchir (GSC, Sheets) |
| 1 | **Ingest** | Récupérer HTML + données SERP |
| 2 | **Audit** | Analyser performance, cannibalisation, intention |
| 3 | **Decision** | Déterminer stratégie (règles configurables) |
| 4 | **Writing** | Préparer contexte Ghostwriter |
| 5 | **Linking** | Valider et restaurer assets |
| 6 | **Sync** | Mettre à jour Google Sheets |

---

## Stratégies de Réécriture

| Stratégie | Déclencheur | Scope |
|-----------|-------------|-------|
| `TITLE_OPTIMIZATION` | CTR < 2%, impressions > 500 | Titre + Meta |
| `PARTIAL_REFRESH` | Contenu > 12 mois | Sections ciblées |
| `FULL_REFRESH` | Score < 50 | Article complet |
| `SEMANTIC_REORIENTATION` | Shift d'intention | Restructuration |
| `FORMAT_ADAPTATION` | Format ≠ SERP | Changement structure |
| `EEAT_REWRITE` | Contenu YMYL faible | E-E-A-T maximal |
| `REDIRECT_301` | Cannibalisation sévère | Alerte manuelle |

---

## Blogs Supportés

| Blog | ID | Catégorie |
|------|-----|-----------|
| Enseigna.fr | `enseigna` | Reviews éducation |
| Superprof.fr/ressources | `superprof-ressources` | Blog éducatif |

### Ajouter un nouveau blog

1. Créer `config/blogs/nouveau-blog.json`
2. Définir `blog_id`, `domain`, `gsc_property`
3. Choisir `subject_category` existant ou créer nouveau prompt

---

## Préservation des Assets

**Règle d'Or** : Ne jamais réduire les assets.

```
count(images après) >= count(images avant)
count(liens après)  >= count(liens avant)
superprof_links     == 1 (exactement)
```

### Liens Blacklistés (interdits)

- acadomia.fr
- kelprof.com
- apprentus.fr
- voscours.fr
- completude.com

---

## Tests

```bash
# Tous les tests
pytest tests/ -v

# Avec couverture
pytest tests/ -v --cov=scripts

# Test spécifique
pytest tests/test_decision_engine.py -v
```

---

## APIs & Serveurs MCP

### Serveurs MCP Intégrés

Le projet utilise le **Model Context Protocol (MCP)** pour accéder aux APIs externes et à la documentation technique.

| Service | Mode d'accès | Configuration | Statut |
|---------|--------------|---------------|--------|
| **DataforSEO** | MCP Server | `.env`: DATAFORSEO_LOGIN + PASSWORD | ✅ Actif |
| **Google Search Console** | API directe (service account) | Service account JSON | ✅ Actif |
| **Context7** | MCP Server | `.env`: CONTEXT7_API_KEY (optionnel) | ✅ Actif |

**Note** : Google Search Console utilise actuellement l'API directe via service account OAuth2. Un serveur MCP GSC est prévu pour une future version.

### Configuration Google Search Console

GSC fonctionne via l'**API Search Console** avec un service account.

**Prérequis** :
1. Créer un service account dans Google Cloud Console
2. Activer l'API Search Console
3. Télécharger le fichier JSON du service account
4. Placer le fichier dans : `C:/Users/[USER]/.credentials/google/google-service-account.json`
5. Ajouter le service account comme propriétaire dans GSC

**Installation dépendances** :
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

**Utilisation** :
```python
from scripts.audit.gsc_analyzer import GSCAnalyzer

# Créer l'analyseur
analyzer = GSCAnalyzer(gsc_property="sc-domain:mon-blog.fr")

# Analyser une URL
result = analyzer.analyze("https://mon-blog.fr/article")
```

### Configuration Context7

Context7 fournit de la **documentation technique à jour** directement dans le contexte des prompts, réduisant les hallucinations API et améliorant la qualité du code généré.

**Installation** :
```bash
cd mcp-server-context7
npm install
```

**Configuration (optionnel)** :
```bash
# .env
CONTEXT7_API_KEY=your_api_key_here  # Obtenez-la sur https://context7.com/dashboard
```

**Test** :
```bash
python test_context7_client.py
```

**Utilisation** :
```python
from scripts.mcp.mcp_client import MCPClient

# Client Context7
client = MCPClient(server_type="context7")

# Résoudre une bibliothèque
library = client.call_tool("resolve-library-id", {
    "query": "Python"
})

# Récupérer la documentation
docs = client.call_tool("query-docs", {
    "libraryId": "/python/docs",
    "query": "How to use decorators in Python?"
})
```

**Voir** : [`mcp-server-context7/README.md`](mcp-server-context7/README.md) pour plus de détails.

---

## Structure Google Sheets

### Feuille `URLs_Input`
- `url`, `blog_id`, `priority`, `status`, `triggered_by`

### Feuille `Audit_Results`
- Métriques GSC, cannibalisation, intention, alertes

### Feuille `Refresh_Results`
- Actions, assets avant/après, validation, publication

Détails : Voir configuration dans `config/blogs/`

---

## Documentation

Consultez les guides dans `_shared/docs/` :

| Document | Description |
|----------|-------------|
| [GEO_2026_GUIDELINES.md](_shared/docs/GEO_2026_GUIDELINES.md) | Guide GEO (Generative Engine Optimization) |
| [EEAT_2026_GUIDELINES.md](_shared/docs/EEAT_2026_GUIDELINES.md) | Guide E-E-A-T complet |
| [CONTENT_REFRESH_GUIDE.md](_shared/docs/CONTENT_REFRESH_GUIDE.md) | Workflow de rafraîchissement |

---

## Dépannage

### Erreur "Spreadsheet not found"
- Vérifier l'ID du spreadsheet
- Vérifier les permissions du compte de service

### Erreur "Rate limit exceeded"
- Le scheduler gère automatiquement le rate limiting
- Attendre 1 minute entre les batches si manuel

### Assets manquants après réécriture
- L'Asset Manager restaure automatiquement
- Vérifier `validation_passed` dans Refresh_Results

---

## Licence

Projet interne - Tous droits réservés.
