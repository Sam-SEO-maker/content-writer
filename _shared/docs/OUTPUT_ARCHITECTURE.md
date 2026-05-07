# Output Architecture

**Version**: 2.0
**Last Updated**: 2026-02-13

---

## Règle d'Or

**AUCUN fichier ne doit être écrit en dehors de cette structure.**

```
_shared/
├── temp/           # Cache temporaire (éphémère, peut être purgé)
└── outputs/        # Sorties validées (permanent, tracking git)
```

---

## 1. Cache Temporaire (`_shared/temp/`)

**Objectif**: Stocker temporairement le HTML scrapé pour comparaison lors de l'audit éditorial.

**Caractéristiques**:
- ❌ **Non versionné** (dans `.gitignore`)
- ⏱️ **Éphémère** - Peut être purgé à tout moment via `OutputManager.init_workspace(purge_temp=True)`
- 🔄 **Usage unique** - HTML brut scrapé depuis URL, utilisé pour editorial_audit.md, puis jetable

**Structure**:
```
_shared/temp/
├── enseigna.fr/
│   ├── avis-acadomia.html
│   └── cours-maths-primaire.html
├── enseigna-vs-concurrent/
└── superprof-ressources/
```

**Méthodes OutputManager**:
- `save_temp_html(site_id, url_slug, html)` - Sauvegarder HTML scrapé
- `get_temp_html(site_id, url_slug)` - Récupérer HTML scrapé
- `clear_temp_cache(site_id=None)` - Purger cache (1 site ou tous)

---

## 2. Sorties Permanentes (`_shared/outputs/`)

**Objectif**: Stocker les résultats validés du workflow (HTML optimisé, metadata, audits).

**Caractéristiques**:
- ✅ **Versionné** (tracking git)
- 📦 **Permanent** - Représente le livrable final
- 🔒 **Validé** - Passe par quality gate (editorial audit, asset validation)

**Structure par site**:
```
_shared/outputs/{site_id}/
├── html/                          # HTML WordPress-ready (après refresh)
│   ├── {slug}_refreshed.html
│   └── {slug}_refreshed.gutenberg.html
├── metadata/                      # Métadonnées et rapports d'audit JSON
│   ├── {slug}_metadata.json       # Title, meta, keywords, assets counts
│   ├── {slug}_audit.json          # Audit report (GSC + SERP + HTML analysis)
│   ├── {slug}_serp.json           # SERP analysis (TOP 3, PAA, intent)
│   └── {slug}_gsc.json            # GSC metrics (CTR, impressions, position)
├── csv/                           # Tableaux d'articles extraits (TablePress-ready)
└── editorial_audits/              # Audits éditoriaux quality gate
    └── {slug}_editorial_audit.md  # Quality gate report (1-10 score)
```

**Exemple concret**:
```
_shared/outputs/enseigna/
├── html/
│   └── preply-avis_refreshed.gutenberg.html
├── metadata/
│   └── preply-avis_metadata.json
└── editorial_audits/
    └── preply-avis_editorial_audit.md

_shared/outputs/superprof-ressources/
├── html/
│   └── apprendre-piano_refreshed.html
├── metadata/
│   └── apprendre-piano_metadata.json
├── csv/
│   └── tableau-comparaison-cours.csv
└── editorial_audits/
    └── apprendre-piano_editorial_audit.md
```

**Méthodes OutputManager**:
- `save_refreshed_html(site_id, url_slug, html)` - HTML optimisé
- `save_metadata(site_id, url_slug, metadata)` - Metadata JSON
- `save_audit_report(site_id, url_slug, data, report_type)` - Rapports d'audit
- `save_editorial_audit(site_id, url_slug, markdown)` - Audit éditorial (quality gate)

---

## 3. Multi-Tenant Isolation

**Sites autorisés** (définis dans `OutputManager.VALID_SITE_IDS`):

| Site ID | Domain | Type |
|---------|--------|------|
| `enseigna.fr` | enseigna.fr | Reviews soutien scolaire |
| `enseigna-vs-concurrent` | enseigna.fr | Comparatifs Enseigna vs concurrents |
| `superprof-ressources` | superprof.fr/ressources/ | Blog éducatif Superprof FR |

**Validation stricte**:
```python
output_mgr._validate_site_id("enseigna.fr")  # ✅ OK
output_mgr._validate_site_id("invalid.com")  # ❌ ValueError
```

---

## 4. Workflow Intégration

### Étape 1: Scrape (Temp Cache)
```python
scraper.fetch_html(url)
  → output_mgr.save_temp_html(site_id, url_slug, html)
  → _shared/temp/{site_id}/{slug}.html
```

### Étape 1.5: Editorial Audit (Lecture Temp + Écriture Outputs)
```python
html_temp = output_mgr.get_temp_html(site_id, url_slug)  # Lecture temp
editorial_result = auditor.audit(html_temp)
  → output_mgr.save_editorial_audit(site_id, url_slug, report_md)
  → _shared/outputs/{site_id}/editorial_audits/{slug}_editorial_audit.md
```

### Étape 4: Refresh (Écriture Outputs)
```python
refreshed_html = ghostwriter.refresh(html, audit)
  → output_mgr.save_refreshed_html(site_id, url_slug, html)
  → _shared/outputs/{site_id}/{slug}_refreshed.html

  → output_mgr.save_metadata(site_id, url_slug, metadata)
  → _shared/outputs/{site_id}/{slug}_metadata.json
```

---

## 5. Initialisation Workspace

**Au démarrage du workflow autonome**:
```python
output_mgr = OutputManager()
stats = output_mgr.init_workspace(purge_temp=True)

# Garantit:
# - _shared/temp/ est vide (purgé)
# - _shared/outputs/{site_id}/ existe pour chaque site
# - _shared/outputs/{site_id}/editorial_audits/ existe
```

**Résultat**:
```python
{
  "temp_files_removed": 42,           # Fichiers purgés
  "output_dirs_created": 6,           # 1 par site
  "editorial_audit_dirs_created": 6   # 1 par site
}
```

---

## 6. Validation & Sécurité

### Validation Outputs Existent
```python
all_exist, missing = output_mgr.validate_outputs_exist(
    site_id="enseigna.fr",
    url_slug="avis-acadomia",
    required=["refreshed_html", "metadata", "editorial_audit"]
)

if not all_exist:
    print(f"Missing: {missing}")  # ["refreshed_html", "metadata"]
```

### Statistiques Workspace
```python
stats = output_mgr.get_workspace_stats()
# {
#   "temp_cache": {"enseigna.fr": 12, "superprof-ressources": 8},
#   "outputs": {"enseigna.fr": 45, "superprof-ressources": 32},
#   "total_temp_size_mb": 2.4,
#   "total_output_size_mb": 18.7
# }
```

---

## 7. Distinction Cache vs Outputs

| Aspect | `_shared/temp/` | `_shared/outputs/` |
|--------|-----------------|-------------------|
| **Versionné** | ❌ Non (.gitignore) | ✅ Oui (tracking git) |
| **Durée de vie** | Éphémère (session) | Permanent |
| **Contenu** | HTML brut scrapé | HTML optimisé + metadata + audits |
| **Usage** | Comparaison audit | Livrable final |
| **Purge** | Fréquente (init_workspace) | Jamais (archive si besoin) |
| **Validation** | Aucune | Quality gate + asset validation |

**Exemple de cycle de vie**:
```
URL → Scraper → temp/{slug}.html (éphémère)
                     ↓
              Editorial Audit (lecture)
                     ↓
            Quality Gate (score ≥ 4?)
                     ↓
              Ghostwriter Refresh
                     ↓
        outputs/{slug}_refreshed.html (permanent)
                     ↓
              temp/{slug}.html (peut être purgé)
```

---

## 8. API OutputManager (Référence)

### Initialisation
```python
from scripts.utils.output_manager import OutputManager
mgr = OutputManager()  # Auto-detect base_path
mgr.init_workspace(purge_temp=True)
```

### Cache Temporaire
```python
mgr.save_temp_html("enseigna.fr", "avis-acadomia", "<html>...")
html = mgr.get_temp_html("enseigna.fr", "avis-acadomia")
mgr.clear_temp_cache("enseigna.fr")  # Purger 1 site
mgr.clear_temp_cache()  # Purger tous les sites
```

### Outputs Permanents
```python
mgr.save_refreshed_html("enseigna.fr", "avis-acadomia", "<html>...")
mgr.save_metadata("enseigna.fr", "avis-acadomia", {"title": "..."})
mgr.save_audit_report("enseigna.fr", "avis-acadomia", {...}, "audit")
mgr.save_editorial_audit("enseigna.fr", "avis-acadomia", "# Report...")
```

### Validation
```python
outputs = mgr.get_output_files("enseigna.fr", "avis-acadomia")
all_ok, missing = mgr.validate_outputs_exist("enseigna.fr", "avis-acadomia")
stats = mgr.get_workspace_stats()
```

---

**Fin de la documentation technique**
