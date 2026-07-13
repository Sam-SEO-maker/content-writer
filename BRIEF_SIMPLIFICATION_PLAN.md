# Simplification du brief éditorial vers une architecture skill multi-tenant

**Statut** : proposition d'architecture (réflexion, non implémentée)
**Destinée à** : hébergement GitHub pour étude avant lancement
**Complément de** : `MULTI_MARKET_ORCHESTRATOR_PLAN.md` (ce document en précise le volet « composition de prompt »)

---

## Contexte

Question posée : *la génération de brief éditorial peut-elle être simplifiée sans perte de qualité ?*

Réponse : **oui, et une grande partie de la simplification consiste à supprimer une complexité qui n'existe déjà plus que sur le papier.** L'investigation du code révèle un écart majeur entre l'architecture décrite (5 strates de prompt) et l'architecture réelle (2 strates actives). Refondre, ici, c'est d'abord aligner la doc et le code sur ce qui fonctionne, puis déplacer la logique éditoriale dans une **skill partagée** pour la rendre scalable à un **nombre quelconque de tenants**.

> **Périmètre — pas seulement Superprof.** Un « tenant » est **n'importe quel site/marque/client** que l'utilisateur veut travailler : les blogs Superprof pays (≈ 91 actifs en juillet 2026, chiffre voué à augmenter), mais aussi `enseigna`, `apuntes`, `resources.com`, et tout futur client sans lien avec Superprof. L'architecture ne doit **jamais** être taillée pour « 91 blogs Superprof » : ce nombre est un instantané, pas une contrainte de conception. Le code actuel est d'ailleurs déjà **plat et générique** (`sites.json` liste `enseigna` et `superprof-ressources` au même niveau, sans notion de « client Superprof » au-dessus). La refonte préserve cette neutralité : un registre de tenants ouvert, pas un annuaire de pays Superprof.

Ce qui prompte la refonte :
- **Coût de contexte** : `CLAUDE.md` (668 lignes) est relu intégralement à chaque session même quand la tâche ne le nécessite pas.
- **Scalabilité N tenants** : chaque responsable de tenant doit disposer d'un dossier générique où charger ses propres fichiers (prompts, landings), sans dupliquer le moteur — quel que soit le type de client.
- **Complexité fictive** : la composition « 4-5 niveaux » du `PromptComposer` est en grande partie du code mort.

---

## Constats d'investigation (état réel du code)

### 1. La strate multi-niveaux est déjà fictive

`_shared/core/prompt_composer.py` compose 5 niveaux, mais 3 ne se chargent jamais faute de fichiers/dossiers :

| Niveau | Source attendue | État réel |
|---|---|---|
| 1 — base/callouts | `templates/callouts.md` | **Dossier `templates/` absent** → jamais chargé |
| 2 — catégorie | `categories/{group}/{subject}.md` | **Dossier `categories/` absent** → jamais injecté |
| 3 — stratégie | `strategies/{strategy}.md` | ✅ actif |
| 4 — site override | `sites/{site_id}.md` | ✅ actif |
| 5 — template | `templates/{content_type}_template.md` | **Absent** → jamais chargé |

**Seuls 2 niveaux produisent du contenu : Strategy + Site.** `MULTI_MARKET_ORCHESTRATOR_PLAN.md` décrit pourtant `categories/{group}/{subject}.md` comme réel — la doc est désynchronisée du disque.

### 2. Catégorie et Site pointent déjà vers le même fichier

Dans `_shared/config/prompts_dispatch.json`, `subject_prompts.education_reviews.file` **=** `site_overrides.enseigna` **=** `sites/enseigna.md`. La strate « catégorie » et la strate « site » sont donc **déjà fusionnées** dans les faits. Confirme qu'il n'y a pas 3 axes à séparer, mais 2 : *ce qui est commun aux pays* vs *ce qui est propre à un pays*.

### 3. Le bug « toujours FULL_REFRESH »

`scripts/ghostwriter/ghostwriter.py:594` : `audit_data.get("decision", {}).get("strategy", "FULL_REFRESH")`. Le fallback non défensif fait retomber toute décision non propagée sur FULL_REFRESH. Le mapping `prompts_dispatch.json` aggrave : `partial_refresh` pointe déjà vers `full_refresh.md`. Ironie : la réduction à 2 stratégies est presque déjà en place *par bug*.

### 4. Aucune skill / slash command n'existe encore

`.claude/` ne contient que `settings.json` + `settings.local.json`. Pas de `.claude/skills/`, pas de `.claude/commands/`. Terrain vierge — rien à défaire.

---

## Décisions tranchées

| Question | Décision | Justification |
|---|---|---|
| Où vit la composition ? | **Skill = workflow 7 étapes + 2 fichiers strategy (partagés). Site = donnée du tenant.** | Sépare par axe de variation : commun à tous les tenants dans la skill, spécifique-tenant dans son dossier. Le dispatch prouve que catégorie⊂site, donc pas de 3e axe. |
| Combien de stratégies de rédaction ? | **2 : `full_refresh.md` + `eeat_rewrite.md`.** partial/semantic/format se replient sur full_refresh. TITLE_OPTIMIZATION reste géré par `TitleOptimizer` (chemin de code séparé, sans fichier strategy). | Réduit la surface de bug ; le mapping actuel est déjà incohérent. |
| Garde-t-on le decision engine ? | **Oui, intact.** | La décision (data-driven GSC/DataForSEO) est un pilier. On ne réduit que les *fichiers de rédaction*, pas la granularité de décision. |
| Source des blogs Superprof pays actifs ? | **WebFetch de la page publique `superprof.fr/blog/superprof-dans-le-monde/`, réconciliée avec Notion (`NOTION_TOKEN` en curl) si écart.** | *(Concerne uniquement le type de tenant « blog Superprof pays ».)* La page publique reflète les blogs réellement affichés ; Notion sert de contrôle structuré. Le connecteur Notion claude.ai n'est pas auth en session non-interactive, mais le token `.env` l'est. |
| Hébergement / distribution multi-tenant ? | **Monorepo unique privé** (`github.com/Sam-SEO-maker/content-writer.git`) : moteur central + dossiers tenants `tenants/{tenant}/`. Accès collaborateur via `CODEOWNERS`. Pas de repo template cloné, pas de repo de données séparé. | Le template cloné ne scale pas (autant de forks figés que de tenants, MAJ skill impossible à propager). Le moteur central lit les configs de **tous les tenants** (Superprof pays, enseigna, apuntes, resources.com, futurs clients) et se met à jour d'un seul push. Confirmé par le code (dispatch déjà id-keyé, registre plat) et `MULTI_MARKET_ORCHESTRATOR_PLAN.md` §4. |

---

## Architecture cible

### Séparation par axe de variation

Un seul monorepo privé. Deux zones dans le même repo, séparées par axe de variation :

```
MOTEUR CENTRAL (commun, versionné 1×)        DOSSIER TENANT  tenants/{tenant}/
─────────────────────────────────           ──────────────────────────────
.claude/skills/…/SKILL.md : workflow 7 ét.   prompts/site.md   (ton, blacklist, format WP)
references/full_refresh.md                   config/tenant.json + config/landings.csv
references/eeat_rewrite.md                   linking_maps/
references/seo_geo_eeat.md  (ex-CLAUDE.md)   outputs/
_shared/config/sites.json (index global mince : 1 entrée/tenant, type quelconque)
```

`{tenant}` = **n'importe quel client** : `enseigna`, `apuntes`, `resources-com`, `superprof-fr-ressources`, `superprof-es-blog`… La skill charge dynamiquement `references/{strategy}.md` (partagé) + le `site.md` du tenant résolu par son id. Le responsable d'un tenant ne touche que `tenants/{tenant}/` ; il hérite du moteur sans jamais le cloner. Zéro coût de contexte tant que la skill n'est pas invoquée.

### CLAUDE.md réduit

- **Reste** : les 7 étapes du workflow + un index de pointeurs (vers skill, dossiers tenant). Le « quoi faire ».
- **Part dans la skill** (`references/seo_geo_eeat.md`) : règles SEO/GEO/E-E-A-T, formats HTML, cocons. Le « comment rédiger ».

Le composer le documente déjà (`prompt_composer.py:10` : « règles E-E-A-T de base dans CLAUDE.md »). La refonte inverse : règles → skill, CLAUDE.md → index (~150 lignes cible vs 668).

---

## Plan d'exécution

> **Principe de séquencement (retour ingénieur IA) : séparer le nettoyage de la refonte.** Le rangement (code mort, dossiers fantômes, archivage, `.claudeignore`) est un **chantier distinct, à faire d'abord**, dans des commits/PR séparés de la refonte structurelle (skills + monorepo). On ne mélange pas « je range » et « je restructure » : diffs plus lisibles, review et revert plus sûrs, base propre avant de bâtir. La refonte assume par ailleurs de **refactoriser le code là où c'est nécessaire** (dé-hardcode, racines de chemins, composer) — pas seulement du cosmétique.

### Étape 0 — Nettoyage préalable (chantier séparé, AVANT la refonte)
Purge du code mort déjà identifié aux Constats d'investigation, en PR autonomes :
- Supprimer/archiver les niveaux morts du composer : dossiers fantômes `categories/`, `templates/`, `subjects/`, et les `prompts/formats/*.md` référencés mais absents (Constat #1).
- Archiver les 3 stratégies non retenues (`format_adaptation.md`, `semantic_reorientation.md`, `title_optimization.md` → `_archive/`) — le fichier, pas encore la logique (celle-ci en Étape B).
- Ajouter `.claudeignore` (données générées : `_shared/context/`, `_shared/outputs/`, `_shared/temp/`, `_local/`, `Images/`, `__pycache__/`, `.venv/`, `_archive/`) — pour **cibler les recherches**, pas pour économiser des tokens (un fichier non lu n'en consomme pas).
- Isoler `_local/` (données machine) du reste.
> Aucune modification de comportement à cette étape : que du rangement. Les corrections de logique (bug fallback, réduction composer) restent en Étapes B/D.

### Étape A — Créer la skill de génération éditoriale
- `.claude/skills/edito-refresh/SKILL.md` : workflow 7 étapes + logique d'assemblage (ordre, override Site > Strategy).
- `references/full_refresh.md`, `references/eeat_rewrite.md` : copiés depuis `_shared/prompts/strategies/` (garder ces 2, archiver les 3 autres).
- `references/seo_geo_eeat.md` : extraction des règles SEO/GEO/E-E-A-T de `CLAUDE.md`.

### Étape B — Réduire les stratégies à 2
- Archiver `format_adaptation.md`, `semantic_reorientation.md`, `title_optimization.md` (→ `_archive/`).
- Corriger `prompts_dispatch.json` : `strategy_prompts` ne garde que `full_refresh` + `eeat_rewrite`.
- **Corriger le bug** `ghostwriter.py:594` : propager réellement `DecisionResult.primary_action` vers `audit_data["decision"]["strategy"]` et enlever le fallback silencieux `"FULL_REFRESH"`.

### Étape C — Réduire CLAUDE.md
- Réécrire en index : 7 étapes + pointeurs. Déplacer le corps règles dans la skill (Étape A).

### Étape D — Nettoyer le PromptComposer
- Simplifier `compose()` à 2 niveaux (`strategy + site`), supprimer les niveaux morts (categories/templates) pour aligner code et réalité.

### Étape E — Config des pays dans Notion → sync vers `sites.json`
**Décision : la config des pays *vit* dans Notion.** Notion est l'**interface humaine de saisie** de la liste des tenants « blog Superprof pays » (une page/base : pays, structure `/blog` vs `/ressources`, statut actif, domaine, propriété GSC…). Ce n'est **que de la config**, pas du pilotage : Notion ne déclenche aucun refresh, ne porte aucun statut de workflow.

Modèle de flux (unidirectionnel, sans lecture Notion au runtime) :
```
Notion (page config pays, éditée par un humain)
   │  sync explicite  (script cw, NOTION_TOKEN en curl)
   ▼
_shared/config/sites.json   ← SOURCE DE VÉRITÉ lue par le moteur
```
- **Pourquoi ne pas lire Notion au runtime** : le connecteur Notion claude.ai n'est pas authentifié en session non-interactive (seul le token `.env` marche en curl), et le moteur ne doit pas dépendre d'un appel réseau Notion à chaque run. Le Google Sheet **reste le pilote de statut** (`WorkflowTracker`), inchangé — Notion et Sheet ne se recouvrent pas. `NotionClient` a déjà les primitives (`query_database`) pour bâtir le sync.
- **Source primaire de recensement** : `WebFetch` de `superprof.fr/blog/superprof-dans-le-monde/` (~91 blogs pays en juillet 2026, amené à croître), la page Notion servant de base structurée éditable : https://app.notion.com/p/superprof/b4f6b521eeb14e29a56a527febd9d278?v=2301f405403544ae9abf5e84fefa95bf&source=copy_link
- **Portée** : ce mécanisme Notion→`sites.json` concerne le type de tenant « blog Superprof pays ». Les autres tenants (enseigna, apuntes, resources.com, futurs clients) sont ajoutés à la main, un dossier `tenants/{tenant}/` + entrée `sites.json` chacun — pas de recensement Notion automatique pour eux.

### Étape F — Monorepo « moteur central + dossiers tenants »
Ne **PAS** créer de repo template cloné (anti-pattern : autant de forks figés que de tenants, un `git pull` par tenant à chaque MAJ de skill, forks qui divergent). Le repo de prod privé **devient le moteur unique qui lit les configs de tous les tenants**. Un seul endroit à mettre à jour → tous les tenants servis instantanément, quel que soit leur nombre.

- **Moteur central (versionné une fois, hérité par tous)** : code Python (orchestrateur, `PromptComposer`, decision engine), skill(s) `.claude/skills/`, règles universelles (`references/seo_geo_eeat.md`, `references/full_refresh.md`, `references/eeat_rewrite.md`).
- **Dossiers tenants** : `tenants/{tenant}/` regroupant tout ce qui est propre au client (`prompts/site.md`, `config/`, `linking_maps/`, `outputs/`). Un `{tenant}` peut être un blog Superprof pays, `enseigna`, `apuntes`, `resources.com` ou tout futur client. Un responsable ne touche **que** son dossier.
- **Registre ouvert, pas Superprof-centré** : l'index `sites.json` liste des tenants hétérogènes au même niveau (aucune hiérarchie « Superprof » au-dessus). Ajouter un client non-Superprof = même geste qu'ajouter un blog pays.
- **Accès** : repo **privé** + `CODEOWNERS` par dossier `tenants/{tenant}/` + protection de branche. Les collaborateurs externes voient le code mais ne modifient que leur tenant (pas de repo public, pas de submodule séparé).
  - **Privé ≠ non clonable.** `git clone <url>` fonctionne sur un repo privé dès lors que le terminal est authentifié avec un compte **invité comme collaborateur** (ou membre de l'organisation GitHub). Le geste du responsable est identique à un repo public — `git clone` puis `git pull` pour recevoir les MAJ moteur/skill ; seule s'ajoute une auth SSH/token une fois. Sans invitation, le clone échoue (`repository not found`), ce qui est précisément le filtre voulu. Public exposerait le code SEO à tous, inutilement. À grande échelle, préférer une **organisation GitHub + équipes** aux invitations individuelles.
  - Modèle de travail : le clone est un **checkout de travail** (clone une fois, `git pull` régulier), pas une copie qu'on emporte et fait diverger. C'est ce qui garantit que les MAJ du moteur atteignent tous les tenants.
- **Onboarding d'un tenant = créer 1 dossier `tenants/{tenant}/`** (site.md + config + entrée dans l'index `sites.json`), **zéro ligne de code**. La skill et le moteur sont hérités automatiquement, jamais copiés.

> Cohérent avec `MULTI_MARKET_ORCHESTRATOR_PLAN.md` §4 (« ne pas créer un nouveau repo — étendre les conventions existantes »). Le code clé déjà tout sur `blog_id` avec un **registre plat et générique** (`enseigna` et `superprof-ressources` cohabitent sans notion de client au-dessus) : aucune instance de moteur par tenant, le monorepo est la direction naturelle. Le layout regroupé `tenants/{tenant}/` remplace l'éclatement actuel (4 arbres plats) pour rendre chaque tenant self-service — indépendamment de la marque.

---

## Fichiers critiques (référence)

| Fichier | Rôle dans la refonte |
|---|---|
| `_shared/core/prompt_composer.py` | À simplifier (2 niveaux) — l.10, l.60-108 |
| `_shared/config/prompts_dispatch.json` | À réduire (strategy_prompts) + fusion catégorie/site à acter |
| `scripts/ghostwriter/ghostwriter.py:594` | **Bug fallback FULL_REFRESH à corriger** |
| `scripts/decision/decision_engine.py` | Intact (granularité de décision conservée) |
| `_shared/prompts/strategies/*.md` | Garder 2, archiver 3 |
| `CLAUDE.md` (668 l.) | À réduire en index |
| `.env` | `NOTION_TOKEN` présent (source pays) |

---

## Vérification

1. **Skill fonctionnelle** : invoquer la skill sur une URL test, vérifier que le prompt composé contient bien strategy + site sans les 3 niveaux morts.
2. **Bug stratégie** : forcer une décision TITLE_OPTIMIZATION, vérifier que le ghostwriter ne compose pas full_refresh (log de la stratégie effective).
3. **Contexte réduit** : mesurer les tokens de session avant/après réduction CLAUDE.md.
4. **Non-régression qualité** : générer un article sur Enseigna + un sur Superprof-ressources, comparer aux sorties actuelles (assets préservés, ton, format Gutenberg).
5. **Liste blogs Superprof pays** : `markets.json` contient toutes les entrées cohérentes avec la page publique (~91 en juillet 2026). Ce test ne couvre que ce type de tenant ; les tenants non-Superprof sont vérifiés séparément (§ onboarding manuel).
6. **Neutralité multi-client** : ajouter un tenant factice non-Superprof (ex. `resources-com`) via un seul dossier `tenants/{tenant}/` + entrée `sites.json`, et vérifier que le moteur le charge sans aucune modification de code ni référence Superprof.

---

## Réponse synthétique à la réflexion initiale

- **Simplifier sans perdre en qualité ?** Oui — la moitié de la complexité est déjà morte. On passe de 5 strates affichées à 2 réelles.
- **Déplacer les strates dans une skill ?** Oui, mais en séparant : workflow + strategy → skill partagée ; site → donnée du tenant. Pas tout dans une seule skill.
- **Moins de stratégies (full_refresh + eeat_rewrite) ?** Oui, sans toucher au moteur de décision. Corriger d'abord le bug fallback.
- **Notion pour recenser les blogs Superprof pays ?** Faisable via `NOTION_TOKEN`, mais la page publique est la source primaire ; Notion = contrôle. Ne concerne que ce type de tenant.
- **Distribuer à N tenants (tout type de client) ?** Monorepo unique privé (moteur central + dossiers tenants `tenants/{tenant}/`, accès `CODEOWNERS`), pas un repo template cloné : le clone crée autant de forks figés que de tenants, impossibles à mettre à jour. Le moteur central lit les configs de tous les tenants — Superprof pays, enseigna, apuntes, resources.com, futurs clients — et se met à jour d'un seul push. Le nombre de tenants (91 ou 500) n'est pas une contrainte de conception.
