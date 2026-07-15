# Orchestrateur Multi-Tenant — Plan d'architecture

**Statut** : proposition, non implémentée
**Objectif** : auditer le workflow pour le rendre scalable à un **nombre quelconque de tenants de tout type** (refaire from scratch ou refactoriser ?)

> **Périmètre — pas seulement Superprof.** Ce plan a été rédigé autour du cas Superprof (les blogs pays sont le volume dominant, ~91 en juillet 2026), mais la cible est **tout client** : blogs Superprof pays, `enseigna`, `apuntes`, `resources.com`, futurs clients. Là où le texte dit « marché » / « pays », lire « tenant » (client quelconque). Le code est déjà plat et générique (registre `sites.json` sans hiérarchie « Superprof »), l'architecture ne doit jamais être taillée pour un nombre fixe de blogs Superprof.

---

## Contexte

Ce que fait le workflow.

- **CLI Click** (`content_writer.py` + `cli/commands/*.py`) exposant des commandes typées : `python content_writer.py refresh <url> --blog X`, `cw workflow run`, `cw batch keyword-discovery/audit-gsc/decision/refresh` (+ 5 autres sous-commandes batch), `cw audit editorial/serp` (+ `ahrefs-state`/`enseigna-refresh-list`/`gsc-state`), etc. (voir `README_CLI.md`, à la racine du projet).
  ⚠️ Vérifié directement dans le code (2026-07-08, re-vérifié 2026-07-13) : `cw audit cannibalization` et `cw cocon identify/validate` **n'existent pas** dans le CLI actuel, bien qu'ils soient documentés dans `README_CLI.md` — le README est désynchronisé du code sur ces deux points. Le groupe `linking` expose **une seule sous-commande réelle : `avis`** (`cw linking avis [--apply] [--url ...]`), un outil de maillage complet (pas un stub) branché sur `EnseignaAvisLinker` — **pas** `preview`/`run`, et **pas** de gestion automatisée de cocons sémantiques.
- **`RefreshOrchestrator`** (`scripts/agent/orchestrator.py`, 2700+ lignes) qui enchaîne déjà les 7 étapes GSC → audit → décision → contexte de génération → sync Sheets, avec cache (`DocumentCache`), lazy init des clients GSC/SERP/WP, et intégrations DataForSEO/GSC/Notion/YTG déjà câblées.

  **Les 7 étapes du workflow de refresh** (l'ossature commune à tous les tenants, qui migre vers la skill partagée du plan de simplification) :

  1. **Identification de l'URL** — récupération de l'URL à traiter et de son tenant depuis le Google Sheet de pilotage (`SheetsClient` / `WorkflowTracker`), avec les signaux de priorisation déjà calculés (CTR, impressions, position, âge, statut). Détermine *quoi* rafraîchir et pour quel tenant. En amont : ingestion du HTML existant via `ContentExtractor` (sélecteurs site → WP REST → heuristiques) et snapshot pour comparaison avant/après.
  2. **Diagnostic GSC** — `GSCAnalyzer` interroge Search Console (3/6/12 mois) : CTR, impressions, position, clics, tendances, KW principal vs variants, SERP features. Produit un score de dégradation qui alimente la décision. Passe désormais par le MCP `gsc-remote` pour les accès ad hoc.
  3. **Diagnostic DataForSEO (TOP 3) + guide sémantique YTG** — `SERPAnalyzer` analyse les 3 concurrents en tête (word count, asset count, structure H2/H3, signaux E-E-A-T, format dominant) et `HTMLAnalyzer` parse l'article actuel → *gap analysis* actuel vs TOP 3. En parallèle, **`YTGAnalyzer` crée/récupère le guide YourTextGuru** (`get_or_create_guide`) et cible les scores SOSEO/DSEO du TOP3/TOP10 (`fetch_serp_scores`) — c'est le guide qui servira de barème au **contrôle sémantique post-génération** (étape 6bis). Non-bloquant à ce stade.
  4. **Analyse SERP & intention** — `IntentDetector` établit l'intention dominante (informationnel / transactionnel / navigationnel), le format cible (guide / listicle / review / FAQ) et les SERP features (PAA, featured snippet). C'est aussi ici que joue la quality gate bloquante `EditorialAuditor` (score < 4/10 = refresh refusé) et l'anti-cannibalisation (`CannibalizationChecker` / `NotionClient`).
  5. **Décision de stratégie** — `DecisionEngine` évalue les règles déclaratives de `decision_rules.json` contre les données d'audit et retourne une stratégie ; `StrategySelector` la combine avec les prompts matière et l'override tenant. Data-driven, pas d'intuition. *(La refonte réduit les fichiers de rédaction à 2 — `full_refresh` + `eeat_rewrite` — sans toucher à cette granularité de décision.)*
  5bis. **Recherche documentaire (sources & faits) — ÉTAPE À CONSTRUIRE, manquante aujourd'hui** — avant de composer le brief, collecter de la **matière factuelle autoritative** : études, statistiques récentes (2024-2026), citations d'experts, sources institutionnelles à jour. But : que la rédaction s'appuie sur du **vérifié**, pas sur des sources inventées. ⚠️ **Trou actuel confirmé (investigation 2026-07-13)** : aucune étape ne va chercher de sources ; le champ `eeat_sources` est **inventé par le LLM à la génération** (le prompt dit juste « ajoute N sources autoritaires »), le seul crochet prévu est un `TODO` jamais implémenté (`fact_checker.py:295`), et le fichier de stats/experts pré-curées (`categories/{subject}.md`) **n'existe pas** (dossier fantôme). **Modèle retenu (décision tranchée, mode autonome) : bibliothèque curée thématisée + recherche en complément (cascade).** Le volume de matières à couvrir est large → deux niveaux :
     - **Socle : une bibliothèque de sources fiables PAR MATIÈRE**, constituée à l'avance — `tenants/{tenant}/sources/{matière}.md` (ou partagée si transverse) : sources institutionnelles/autoritatives de référence (ex. INSERM/santé, Éduscol·Onisep/éducation), avec url + année. **C'est précisément la ressource que l'architecture d'origine prévoyait sous `categories/{subject}.md` (« stats, experts, sources ») et qui n'a jamais été créée** — la construire comble ce dossier fantôme. Embryon existant à formaliser : la liste de domaines recommandés déjà en dur dans `claude_client.py:249` (`education.gouv.fr`, `eduscol.fr`, `onisep.fr`).
     - **Complément : recherche à la volée** via la skill `deep-research` + `WebSearch`/`WebFetch` — comble seulement les lacunes du socle (fait récent absent) et **enrichit la bibliothèque au passage**. L'article pioche d'abord dans le référentiel de sa matière (fiable, rapide), la recherche ne fait que compléter.
     - **Constitution de la bibliothèque : semi-automatique** — un agent (`deep-research`) **propose** les sources autoritatives par matière, **un humain valide/élague** avant de figer le référentiel. À l'échelle de nombreuses matières, le tout-manuel ne scale pas ; l'auto-sans-validation contredit l'exigence E-E-A-T (sources non filtrées = risque). Le semi-auto est le seul qui tient l'échelle sans sacrifier la fiabilité.

     Sortie : un bloc de sources vérifiées (source, url, année) injecté dans le brief de l'étape 6.
  6. **Composition du prompt de génération** — `Ghostwriter.generate_from_context()` compose le prompt final via `PromptComposer` (strategy + site) et prépare le contexte de réécriture (assets, guidelines, diff) **+ les sources vérifiées de l'étape 5bis** ; `DiffEngine` cible les changements (ex : mise à jour d'années) ; `TitleOptimizer` gère le cas TITLE_OPTIMIZATION seul. **Sortie : `generation_prompt.txt` — le contexte est prêt, le texte n'est pas encore écrit.** (État actuel du code : `orchestrator.py:812` s'arrête ici, `# la réécriture effective par LLM est à faire par l'appelant`.)
  6bis. **Génération du contenu (subagent Claude Code, PAS l'API payante)** — un **subagent générateur** (`.claude/agents/content-generator`, à créer) lit `generation_prompt.txt` et **produit le HTML + metadata** sous l'abonnement Max, jamais via un appel API facturé depuis le CLI. `AssetManager` **valide et restaure les assets** (Règle d'Or `assets_after ≥ assets_before`) ; `gutenberg_formatter.py` met en forme. Le contenu final est **écrit dans `_shared/outputs/{tenant}/`** via `OutputManager.save_refreshed_html()` (`html/`, `.gutenberg.html`, `csv/`, `acf/`). ⚠️ *Chaînon manquant aujourd'hui : génération stubbée (`claude_client.py` en `simulation_mode`), et `save_refreshed_html()` sans appelant. Voir « Bout-en-bout » ci-dessous et le séquencement (phase dédiée).*
  6ter. **Contrôle sémantique YTG (post-génération)** — `YTGQualityCheck.check_html()` (`cw ytg qc`) score le HTML fraîchement généré contre le guide de l'étape 3 : SOSEO/DSEO + verdict `OPTIMAL` / `A_CORRIGER` / `BLOQUE` (termes sous/sur-optimisés), persisté dans `audit_data.json`. **Boucle de correction** : sur `A_CORRIGER`, le subagent re-corrige (plafond d'itérations, ex. 2-3, sous abonnement Max) ; sur `BLOQUE`, **arrêt + alerte humaine** (sur-optimisation grave = problème de fond, pas corrigeable par simple régénération). `SemanticChecker` complète l'anti-suroptimisation.
  6quater. **Maillage interne & liens Superprof (automatique, selon le type de tenant)** — étape aujourd'hui manuelle/hors-pipeline, à **brancher dans la chaîne**. La logique dépend du tenant :
     - **Article Superprof (blog pays)** — insérer un/des **liens de landing Superprof** du bon pays, au format `superprof.{tld-pays}/cours/{matière}/{ville}/` (forme réelle vérifiée : `https://www.superprof.fr/cours/yoga/paris/`). Sélection intelligente par `SuperprofRotator` : filtre par sujet, bonus si le KW ranke P2-P10, anti-répétition d'ancres, ancre puisée dans le pool de la landing. Le rotator injecte déjà sa directive dans le prompt de génération (`get_prompt_directive`) — à généraliser par pays (dé-hardcode `superprof_landings.json`).
     - **Article d'avis Enseigna** — `EnseignaAvisLinker` insère deux catégories de liens **cloisonnées** (pour ne jamais pointer deux fois la même page) : (1) jusqu'à **2 liens internes vers d'autres avis de la même famille thématique — avis de concurrents uniquement, JAMAIS l'avis Superprof** ; et (2) **exactement 1 lien vers l'article « Superprof avis »**, distinct et compté à part (via le rotator / retargeting d'un `superprof.fr/` nu). ⚠️ **Anti-doublon obligatoire** : l'article « Superprof avis » appartient à la famille « plateformes en ligne » — il doit donc être **exclu du pool des 2 liens internes**, sinon la règle (1) et la règle (2) le sélectionneraient toutes deux → 2 liens vers la même page. Total garanti : 2 avis concurrents + 1 Superprof avis = 3 cibles **distinctes**. Règle d'or du linker : l'ancre est **du texte déjà présent** dans l'article (jamais une phrase robotisée), jamais un concurrent en anchor money-KW, jamais un doublon d'URL ; si aucune ancre naturelle → skip + rapport.
     - **Garde-fous communs** : respect des règles cocons/anti-patterns de `CLAUDE.md` (liens espacés ≥150-200 mots, pas de section « articles connexes », pas d'ancre en `<strong>`, pas de lien dans un H2/H3) ; validation `InjectionValidator` ; préservation Règle d'Or (jamais moins de liens qu'avant, exactement 1 lien Superprof).
  7. **Mise à jour du Sheet & livraison** — `WorkflowTracker` inscrit les colonnes post-refresh (`status` → DONE, `strategy_applied`, `word_count_before/after`, `assets_before/after`, `tokens_used`, `refresh_date`…) et `action_formatter.py` génère les colonnes « To Do » / « Recommended Actions ». Validations finales : slug unique, cocons PARENT/CHILD, sources E-E-A-T, ton du tenant. Publication WP réelle (`push_to_wp.py`) reste une étape séparée à fort blast radius (`--publish`).

  > La décision (étape 5) est un pilier conservé intact ; la refonte ne simplifie que le *nombre de fichiers de rédaction* de l'étape 6, pas la logique des étapes. **Frontière de coût** : le CLI Python va jusqu'au prompt (étape 6) et écrit les sorties/QC (étapes 6bis-fin) ; **la rédaction elle-même (6bis) est déléguée à un subagent Claude Code** — jamais un appel API Anthropic facturé depuis le CLI. Le chef d'orchestre du bout-en-bout est donc la **skill/commande Claude Code**, pas `python content_writer.py` seul (un subagent ne s'invoque que depuis une session Claude Code).
- **Moteur de décision data-driven** : `decision_rules.json` (règles déclaratives, pas de logique câblée en dur) + `DecisionEngine`/`StrategySelector`.
- **Prompt Composer 4 niveaux** déjà codé (`_shared/core/prompt_composer.py`) : Category → Strategy → Site → Template, avec override `Site > Strategy > Category`, piloté par `prompts_dispatch.json` (mapping blog→subject, blog→category, content_type_mapping, eeat_levels).
- **`SitesRegistry`** (`_shared/core/sites_registry.py`) : déjà un registre multi-tenant JSON (`sites.json`) conçu pour accueillir N sites — get/add/remove/deactivate. Actuellement 2 entrées (enseigna, superprof-ressources FR), mais l'abstraction pour en ajouter un 3e existe déjà.
- **MCP DataForSEO** déjà connecté (`.mcp.json`), plus GSC/Ahrefs/Notion via connecteurs claude.ai, WordPress REST API et YourTextGuru via clients Python (`scripts/scraping/wordpress_api_client.py`, `scripts/audit/ytg_analyzer.py`).

**Le vrai problème** : Claude Code (l'agent, dans les sessions interactives) n'invoque pas ce CLI existant. À chaque session il retape la logique métier en texte libre en français, relit des fichiers `.md` volumineux (`superprof-ressources.md` = 982 lignes, `CLAUDE.md` = 700+ lignes) même quand la tâche ne les nécessite pas, et perd le contexte multi-marchés d'une session à l'autre. Résultat : tokens gaspillés, lenteur, pas de scalabilité vers 65 pays.

**Conclusion architecturale** : ne pas construire un nouveau repo/CLI parallèle (ce serait dupliquer 2700 lignes d'orchestrateur, un decision engine, un prompt composer et des clients API déjà testés). Le levier est de **construire l'interface manquante entre Claude Code et le CLI existant**, plus une structure de config qui généralise proprement `sites.json` à N pays × 2 structures (`/blog`, `/ressources`) sans toucher au moteur.

---

## Cartographie de l'architecture actuelle

Cette section documente le repo tel qu'il existe aujourd'hui, pour qu'un lecteur sans accès au code puisse suivre le reste du plan.

### Point d'entrée

Tout passe par un seul CLI Click : `python content_writer.py <groupe> <commande> [options]` (alias `cw` dans la doc). Le fichier racine `content_writer.py` ne fait qu'enregistrer les groupes de commandes définis dans `cli/commands/*.py` :

| Groupe | Fichier | Rôle |
|---|---|---|
| `refresh` | `cli/commands/refresh.py` | Refresh d'une URL unique : scraping → audit éditorial → audit GSC/SERP → décision de stratégie → composition du prompt de génération. S'arrête à "contexte prêt", ne rédige pas lui-même. |
| `workflow` | `cli/commands/workflow.py` | Même pipeline que `refresh` mais avec mise à jour du Google Sheet de pilotage à chaque étape (statuts, scores). |
| `audit` | `cli/commands/audit.py` | Audits ponctuels : `editorial` (quality gate), `serp` (PAA, mots-clés secondaires), `ahrefs-state`, `enseigna-refresh-list`, `gsc-state`. Pas de sous-commande `cannibalization` malgré la mention dans `README_CLI.md` — vérifié absente du code. |
| `batch` | `cli/commands/batch.py` | Traitement en masse depuis Google Sheets : `keyword-discovery`, `keyword-refresh`, `audit-gsc`, `audit-serp`, `decision`, `refresh`, `workflow-auto`, `benchmark`, `extract-tables` (9 sous-commandes). C'est la commande utilisée pour traiter des dizaines d'URLs en une passe. |
| `linking` | `cli/commands/linking.py` | Une seule sous-commande réelle : **`avis`** (`cw linking avis [--apply]`), outil de maillage complet branché sur `EnseignaAvisLinker` (2 liens avis concurrents même famille, hors Superprof, + 1 lien Superprof avis distinct) — **pas** `preview`/`run`. Outil **manuel, hors pipeline** de refresh. Pas de gestion automatisée de cocons ; `cw cocon identify/validate` (README) n'existent pas. Un 2e moteur générique `LinkInjector` (CSV) existe mais est **orphelin** (aucune commande ne l'appelle). |
| `ytg` | `cli/commands/ytg.py` | Interactions avec YourTextGuru : `create-guide`, `check-guide`, `list-guides`, `batch-prefetch`, `analyze` (5 sous-commandes). |
| `notion_cmd` (`notion`) | `cli/commands/notion_cmd.py` | Intégration Notion : `sync` (résumé des commandes par blog/statut), `check-title` (anti-cannibalisation par titre), `list-sujets`, `create-sujet` (4 sous-commandes). |
| `report` | `cli/commands/report.py` | Génération de rapports GSC mensuels/tendances. |
| `statuts` | `cli/commands/statuts.py` | Mise à jour manuelle du statut d'une ligne dans le Sheet. |
| `ngl_status` | `cli/commands/ngl_status.py` | Statut du pipeline "New Growing List" (Superprof Ressources). |
| `indexing` | `cli/commands/indexing.py` | Requêtes d'indexation Google (Search Console). |
| `debug` | `cli/commands/debug.py` | Commandes de diagnostic (ex: extraction de structures HTML). |

### Le cœur du moteur : `scripts/agent/orchestrator.py` (`RefreshOrchestrator`)

C'est la classe qui orchestre les 7 étapes du workflow (Ingest → Editorial Audit → Audit GSC/SERP → Decision → Writing/contexte → Linking → Sync Sheets). Chaque commande CLI ci-dessus instancie cet orchestrateur et appelle une de ses méthodes (`process_url`, `batch_editorial_audit`, `batch_keyword_discovery`, etc.). Il gère aussi, en interne et de façon paresseuse (lazy init), les clients vers GSC, DataForSEO/SERP, WordPress REST API, YourTextGuru et Notion — un collaborateur n'a jamais à instancier ces clients lui-même.

Modules internes que l'orchestrateur assemble (tous sous `scripts/`) :

- **`audit/`** — `AuditEngine` (orchestre l'audit complet), `GSCAnalyzer` (performance Search Console), `SERPAnalyzer` (analyse concurrentielle DataForSEO), `HTMLAnalyzer` (parsing structure/assets), `EditorialAuditor` (quality gate bloquant : score < 4/10 = refresh refusé), `CannibalizationChecker`, `IntentDetector`, `SemanticChecker` (anti-suroptimisation post-génération), `YTGAnalyzer` (guides sémantiques YourTextGuru).
- **`decision/`** — `DecisionEngine` : évalue les règles déclaratives de `_shared/config/decision_rules.json` contre les données d'audit et retourne une stratégie. `StrategySelector` : combine cette décision avec les prompts par matière et les overrides par blog pour produire une config de stratégie prête à l'emploi.
- **`ghostwriter/`** — `Ghostwriter` : prépare le contexte de réécriture (assets, guidelines, diff) et compose le prompt final via `PromptComposer` ; ne génère pas de texte lui-même, prépare uniquement l'input pour un LLM externe. `DiffEngine` calcule les changements ciblés (ex: mise à jour d'années). `TitleOptimizer` gère la stratégie TITLE_OPTIMIZATION seule.
- **`assets/`** — `AssetManager` : extrait, préserve et restaure les assets (images, tableaux, vidéos, liens internes) pour garantir la Règle d'Or (`assets_after ≥ assets_before`).
- **`sheets/`** — `SheetsClient` (API Google Sheets directe, pas MCP) et `WorkflowTracker` (avancement du workflow ligne par ligne dans le Sheet de pilotage).
- **`cache/`** — `DocumentCache` : cache singleton qui charge une seule fois par process les guidelines SEO et configs de blog, pour éviter de relire les fichiers à chaque appel interne.
- **`scraping/`** — `ContentExtractor` (extraction multi-niveaux : sélecteurs spécifiques au site → WordPress → heuristiques → nettoyage) et `WordPressAPIClient` (lecture directe via REST API WP quand disponible, avec fallback scraping HTTP sinon).
- **`notion/`** — `NotionClient` : anti-cannibalisation par titre (vérifie qu'un article similaire n'est pas déjà en commande) et découverte de sujets.
- **`cta/`** — `SuperprofRotator` : rotation des call-to-action Superprof.
- **`utils/`** — `OutputManager` (chemins de sortie centralisés : `_shared/outputs/{site}/html|json|editorial_audits/`), `gutenberg_formatter.py` (conversion HTML → blocs Gutenberg WordPress), `action_formatter.py` (génère les colonnes "To Do"/"Recommended Actions" du Sheet), plus divers scripts ponctuels de QC (`sp_qc_check.py`, `lint_gutenberg.py`, etc.).
- **`indexing/`**, **`sitemap/`**, **`seo/`** (client Ahrefs), **`reports/`** — modules support pour l'indexation Google, la découverte de sitemap et les rapports GSC périodiques.

### Configuration et prompts (`_shared/`)

- **`_shared/core/`** — la couche d'abstraction réutilisable : `sites_registry.py` (`SitesRegistry`, lit/écrit `sites.json`), `prompt_composer.py` (`PromptComposer`, compose le prompt final en 4 niveaux), `constants.py`, `models/` (dataclasses partagées : `SiteConfig`, `AuditReport`, `RefreshWorkflowResult`, etc.), `utils/` (timing, mise à jour d'années dans le texte).
- **`_shared/config/`** :
  - `sites.json` — registre central des sites/marchés (id, domaine, propriété GSC, sheet_id, ton éditorial, blacklist concurrents, etc.). Aujourd'hui 2 entrées : `enseigna` et `superprof-ressources`.
  - `blogs/{id}.json` — config technique par blog (ex: `wp_api_config` pour la connexion WordPress REST).
  - `decision_rules.json` — règles déclaratives du moteur de décision (conditions GSC/SERP → action à prendre).
  - `prompts_dispatch.json` — mapping blog→subject, blog→category, mapping content_type→template, niveaux E-E-A-T.
  - `editorial_rules.json`, `year_update_config.json`, `superprof_landings.json`, `linking_maps/` — configs annexes.
- **`_shared/prompts/`** :
  - `categories/{group}/{subject}.md` — Niveau 1 : stats, experts, PAA, vocabulaire par thématique (ex: `education/education_reviews.md`).
  - `strategies/{strategy}.md` — Niveau 2 : instructions de réécriture par stratégie (`full_refresh.md`, `title_optimization.md`, `semantic_reorientation.md`, `format_adaptation.md`, `eeat_rewrite.md`).
  - `sites/{site_id}.md` — Niveau 3 : règles spécifiques au site (blacklist, ton, format). Pour superprof-ressources, éclaté en plusieurs guides (`superprof-ressources/guide-1/2/3-*.md`) référencés depuis `sites.json`.
  - `templates/{content_type}_template.md` — Niveau 4 (optionnel) : structure imposée par type de contenu, plus `callouts.md` (templates HTML des encadrés/CTA, chargé systématiquement).
  - `refresh_article.md` — template de référence historique du processus de refresh (antérieur au moteur actuel, gardé comme documentation du processus).
- **`_shared/docs/`** — documentation de référence : `SEO_GUIDELINES.md`, `STYLE_GUIDE.md`, `EEAT_GUIDE.md` / `EEAT_2026_GUIDELINES.md`, `GEO_2026_GUIDELINES.md`, `COCONS_GUIDE.md`, `OUTPUT_ARCHITECTURE.md`, `CONTENT_REFRESH_GUIDE.md`.
- **`README_CLI.md`** (racine du projet) — référence complète des commandes CLI, à côté de `content_writer.py`.
- **`_shared/outputs/{site_id}/`** — sorties permanentes : `html/` (articles rafraîchis), `json/` (métadonnées), `editorial_audits/` (rapports d'audit qualité).
- **`_shared/temp/{site_id}/`** — cache temporaire du HTML scrapé, pour comparaison avant/après.
- **`_shared/context/`** — snapshots d'articles utilisés pour analyse/contexte ponctuel (pas partie du pipeline automatisé).
- **`_shared/cache/`** — caches applicatifs (`sitemap_cache.json`, état Ahrefs).

### Autres dossiers racine

- **`tests/`** — suite pytest couvrant asset manager, decision engine, ghostwriter, gutenberg formatter, cannibalisation, etc.
- **`scripts/setup/`** — génération de tokens OAuth GSC pour l'onboarding d'un nouveau service account.
- **`workflows/`** — scripts d'analyse ponctuels (ex: découverte de sitemap).
- **`.mcp.json`** — déclare le serveur MCP DataForSEO (`dataforseo-remote`, via `supergateway`) ; les autres intégrations (GSC, Ahrefs, Notion) passent par des connecteurs claude.ai déjà configurés côté IDE, pas par ce fichier.
- **`.claude/settings.json`** — permissions Claude Code : liste blanche de commandes Bash, WebFetch domains, outils MCP autorisés sans prompt.
- **`CLAUDE.md`** — actuellement le document de règles éditoriales complet (workflow 7 étapes, règles E-E-A-T, formats HTML, cocons) lu intégralement par Claude Code à chaque session ; c'est ce fichier que ce plan propose de réduire à un simple index (section 2a).

---

## 0. Arrêter de rescanner l'architecture à chaque session

Constat direct : construire ce plan a nécessité de relire `content_writer.py`, l'orchestrateur (2700 lignes), le prompt composer, `sites.json`, `decision_rules.json`, etc. — alors que cette cartographie ne change presque jamais d'une session à l'autre. C'est le symptôme concret du problème : ni `CLAUDE.md` ni la mémoire persistante actuelle ne contiennent de **carte d'architecture** (quels fichiers existent, quelles commandes CLI sont disponibles, quel est le point d'entrée unique). La mémoire actuelle ne stocke que des règles éditoriales et des pièges ponctuels, jamais la structure du repo elle-même.

**Action** : écrire une mémoire persistante (`project_architecture_map`, dans le système de mémoire Claude Code) qui liste une fois pour toutes :
- Le point d'entrée unique (`python content_writer.py <group> <command>`) et la liste des groupes de commandes déjà disponibles (`refresh`, `workflow`, `audit`, `batch`, `linking`, `ytg`, `notion`, `report`, `statuts`, `ngl_status`, `indexing`, `debug`).
- Ce qui définit un site/marché dans le layout cible : le dossier tenant `tenants/{tenant}/` (`prompts/site.md`, `config/blog.json`, `config/landings.csv`, `linking_maps/`) + son entrée dans l'index global `sites.json` ; et où vit le decision engine (`decision_rules.json`) / dispatch prompt (`prompts_dispatch.json`). *(Avant le regroupement Étape F, ces fichiers sont encore éclatés en `_shared/config/blogs/{id}.json` + `_shared/prompts/sites/{id}.md` + `_shared/config/linking_maps/{id}.*` — la mémoire ne doit être écrite qu'une fois la migration `tenants/{tenant}/` faite.)*
- Un renvoi explicite : "avant de relire le code, consulter cette mémoire — ne re-explorer que si un fichier référencé n'existe plus".

Cette mémoire doit être écrite **à la fin de ce chantier** (une fois les slash commands et le subagent en place), pour qu'elle documente l'état cible, pas l'état actuel en friche.

---

## 1. Interface de commandes : Slash Commands Claude Code qui wrappent `cw`

Créer des commandes Claude Code custom dans `.claude/commands/` (chargées uniquement à l'invocation, donc zéro coût de contexte tant qu'elles ne sont pas utilisées). Chaque commande est un fichier `.md` avec frontmatter qui documente les arguments attendus et appelle directement `cw` via Bash — pas de texte libre.

```
.claude/commands/
├── refresh.md              # /refresh <url> --market=fr --blog=enseigna
├── batch.md                # /batch <step> --market=es --type=ressources
├── audit.md                # /audit <editorial|serp|cannibalization> <url> --market=X
├── decide.md               # /decide <url> --market=X   (expose la décision sans écrire)
└── market-status.md        # /market-status --market=X  (health check config/API)
```

Exemple de commande (`refresh.md`) :

```markdown
---
description: Refresh une URL via le CLI cw (aucune relecture de CLAUDE.md nécessaire)
argument-hint: <url> --market=<code> [--strategy=FULL_REFRESH]
---
Exécute directement, sans reformuler la tâche en langage naturel :

    python content_writer.py refresh $ARGUMENTS

Le marché détermine automatiquement --blog, la config sites.json,
et le jeu de fichiers _shared/prompts/sites/{market}/ à charger.
Affiche le résultat brut de la commande, n'improvise pas de logique.
```

Effet concret : l'utilisateur (blog US, ES, FI, FR, BR, peu importe) tape `/refresh <url> --market=br-blog` au lieu d'un paragraphe en français. Claude Code n'a plus besoin de "comprendre" la stratégie — il exécute une commande déterministe et rapporte le résultat structuré déjà produit par l'orchestrateur (JSON/stdout).

### Éliminer les confirmations Y/N à chaque micro-étape

Problème constaté : aujourd'hui, une commande comme `cw refresh` s'exécute déjà en un seul process Python non-interactif (elle n'attend aucun Y/N en interne) — mais **la session Claude Code, elle**, redemande une confirmation de permission à chaque `Bash`/`Edit` séparé si ces actions ne sont pas pré-autorisées. Le ressenti "validation manuelle à chaque micro-étape" vient de là, pas du CLI Python lui-même. Trois corrections :

1. **Pré-autoriser les slash commands dans `.claude/settings.json`** : ajouter des règles `allow` couvrant explicitement `Bash(python content_writer.py refresh:*)`, `Bash(python content_writer.py batch:*)`, `Bash(python content_writer.py audit:*)`, etc. (le pattern `Bash(python content_writer.py:*)` existe déjà — vérifier qu'il couvre bien tous les sous-groupes, sinon l'étendre). Une fois fait, `/refresh <url> --market=X` doit s'exécuter de bout en bout sans aucune invite.
2. **Une commande = un seul appel Bash**, pas une séquence de plusieurs appels nécessitant chacun sa propre validation. Les slash commands doivent invoquer `cw` une fois avec tous les flags nécessaires (`--publish`, `--strategy`, etc.) plutôt que d'enchaîner plusieurs commandes séparées.
3. Le seul Y/N qui doit subsister est la confirmation finale humaine avant publication WordPress réelle (`--publish`), qui reste un acte à fort blast radius (site public).

**Argument `--market` unique** (au lieu de `--blog` + langue implicite) : un identifiant marché du type `fr-enseigna`, `es-apuntes`, `br-blog` qui résout en une seule clé vers l'entrée `sites.json` correspondante — un collaborateur n'a qu'un seul paramètre à connaître.

---

## 2. Gestion du contexte et économie de tokens

Deux leviers distincts, à ne pas confondre.

### a) Contexte agent Claude Code (le vrai poste de coût)

- **Ne plus laisser `CLAUDE.md` documenter les règles éditoriales en détail** — il doit devenir un index de commandes ("pour refresh : `/refresh`, pour audit : `/audit`, jamais de texte libre") pointant vers les fichiers `.md` de règles, sans les inliner.
- Les fichiers `.md` de règles (SEO, GEO, tone par site) restent chargés **uniquement par le moteur Python** (`PromptComposer`), pas par Claude Code lui-même. Claude Code n'a jamais besoin de lire `superprof-ressources.md` (982 lignes) en contexte : c'est `RefreshOrchestrator`/`PromptComposer` qui compose le prompt final et l'écrit dans `generation_prompt.txt`.
- **Génération = agents Claude Code, pas API facturée à la clé.** L'abonnement Max Plan 20x d'Anthropic couvre l'usage de Claude Code (y compris ses subagents via le SDK), pas des appels séparés à l'API Claude classique. Concrètement : la commande `/refresh` doit lancer `cw refresh` pour préparer `generation_prompt.txt` (audit + décision + composition prompt, aucun LLM impliqué à ce stade), puis **déléguer la rédaction à un subagent Claude Code** (via l'`Agent` tool, `subagent_type` dédié type `content-generator`) qui lit ce fichier déjà composé et produit le HTML + JSON de sortie. Ce subagent tourne sous l'abonnement Max, pas en pay-per-token API. Le CLI Python ne doit donc jamais appeler l'API Anthropic lui-même pour la génération — son rôle s'arrête à préparer un prompt propre et minimal ; c'est la couche Claude Code (agent/subagent) qui l'exécute et consomme le quota d'abonnement.
- Ce découplage évite aussi le vrai problème de fond : aujourd'hui c'est la session interactive principale qui lit `generation_prompt.txt` et rédige dans son propre contexte (donc pollue la conversation avec tout le corps d'article généré). En passant par un subagent dédié, seul le résumé/résultat final remonte dans la conversation principale — économie de tokens supplémentaire.

### b) Cache applicatif (déjà existant, à généraliser)

- `DocumentCache` (`scripts/cache/doc_cache.py`) et `_shared/cache/sitemap_cache.json` existent déjà pour éviter de relire les configs blog à chaque appel — bon pattern à répliquer pour le cache multi-marché.
- Ajouter un **cache de guide marché résolu** : au premier appel `--market=X`, résoudre une fois `sites.json` + fichiers de règles associés vers un objet marché immuable, réutilisé pour tous les appels suivants dans le même run batch (pertinent surtout pour `cw batch`, qui traite déjà des dizaines d'URLs par run).

### c) Accès GSC via le MCP `gsc-remote`

Le repo dispose désormais de `.mcp.json` avec un serveur **`gsc-remote`** (`http://mcp.superprof.cloud:3001/sse`, en plus de `dataforseo-remote`). C'est la bonne réponse au problème « relire GSC à chaque étape » : Claude Code **récupère la data GSC directement via les tools MCP `gsc-remote`** (`get_performance_overview`, `get_search_analytics`, `check_indexing_issues`, `compare_search_periods`, etc.), sans scraping ni relecture de fichiers, et sans dupliquer cet état localement. **Décision** : la donnée GSC se récupère à la demande via le MCP `gsc-remote` — c'est la source vivante, interrogée quand on en a besoin, pas un état à synchroniser ou à stocker en local. Le Google Sheets (`SheetsClient`, `WorkflowTracker`) reste l'interface humaine de pilotage/suivi de statut, un sujet distinct qui n'a pas besoin d'accélération pour l'instant.

**Pourquoi le MCP plutôt que l'API Google directe.** L'accès historique via service account Python (`GSCAnalyzer`, `google.oauth2.service_account` + `build('searchconsole','v1')`) fait porter au repo les credentials, les quotas Search Console et la gestion d'erreurs/blocages — un canal fragile et à distribuer. Le MCP `gsc-remote` déporte tout ça sur le serveur `superprof.cloud` : un seul canal, pas de clé sensible à diffuser, et c'est ce qui rend possible le mode `oauth_user` par tenant (§4bis-B). Cible de migration : `GSCAnalyzer` devient un adaptateur fin qui appelle le MCP en interne en conservant son contrat (`analyze()`, `fetch_top_keyword_12m()`, etc.) pour ne pas casser ses appelants. Bascule progressive (PoC comparatif MCP vs API sur une URL → nouvelles features direct sur MCP → bascule méthode par méthode avec non-régression → suppression du service account en dernier), jamais en big-bang sur le cœur du pipeline de décision.

**Premier cas d'usage : détection automatique de candidats au refresh.** Croiser deux signaux déjà disponibles pour produire une liste triée d'URLs à rafraîchir, sans intervention manuelle :

```
compare_search_periods(dimensions="page")   →  URLs en perte de trafic, delta par page (MCP gsc-remote)
SitemapAnalyzer.find_stale_content()        →  URLs stale (days_since_update réel, parsing lastmod XML)
Jointure locale par URL normalisée          →  score = f(ampleur perte trafic, ancienneté)
                                             →  liste de candidats refresh, triée
```

- **Module** : `scripts/audit/refresh_candidates.py` ; **commande** : `cw audit refresh-candidates --blog X --months 3 --stale-threshold-days 180` (cohérente avec les sous-commandes de `cli/commands/audit.py`) ; exposable aussi en skill `/candidats-refresh` (backlog A, wrappe le MCP).
- Le `lastmod` par URL vient **uniquement** du parsing XML (`SitemapAnalyzer.find_stale_content()`, cf. `_shared/docs/SITEMAP_DISCOVERY.md`) : le MCP GSC n'expose que le statut de soumission du sitemap, pas l'ancienneté par article — ne pas chercher à remplacer `SitemapAnalyzer`.
- Exclure les URLs non-indexées (`check_indexing_issues` / `inspect_url_enhanced`) avant de les proposer.
- Point de friction à traiter tôt : normalisation d'URL entre sitemap (trailing slash, paramètres) et dimension `page` du MCP (`sc-domain:` vs URL-prefix, cf. `_shared/config/sites.json`). Score volontairement simple en v1 (perte trafic normalisée + ancienneté normalisée), pas de scoring complexe.

---

## 3. Flux end-to-end : ce qui change, ce qui ne change pas

Le flux GSC/DataForSEO → décision → **composition du prompt** existe déjà dans `RefreshOrchestrator.process_url()`. **En revanche la génération, l'écriture des sorties et le QC auto NE sont PAS branchés** — le pipeline s'arrête à `generation_prompt.txt` (`orchestrator.py:812`). Ce qui manque :

### Bout-en-bout : boucler URL → génération → score YTG → livraison dans `/outputs`

**Objectif** : une seule invocation (pilotée par la skill/commande Claude Code) qui va de l'identification de l'URL jusqu'au contenu final écrit dans `_shared/outputs/{tenant}/`, en passant par la génération et le contrôle sémantique YTG — sans reprise manuelle au milieu. **Contrainte de coût inviolable** : la rédaction passe par un **subagent Claude Code (abonnement Max)**, jamais un appel API Anthropic facturé depuis le CLI Python. Donc l'orchestration bout-en-bout vit dans la skill, pas dans un script Python autonome (un subagent ne s'invoque que depuis une session Claude Code).

Ce qui existe déjà (à réutiliser, ne pas réécrire) :
- `OutputManager.save_refreshed_html()` (`output_manager.py:311`) écrit `html/` + `.gutenberg.html` + `csv/` + `acf/` — **mais n'a aucun appelant** (infra prête, non branchée).
- `YTGQualityCheck.check_html()` (`ytg_qc.py:146`, `cw ytg qc`) score un HTML généré (SOSEO/DSEO, verdict `OPTIMAL`/`A_CORRIGER`/`BLOQUE`) — **mais ne tourne que si le HTML est déjà sur disque** (`refresh.py:214` affiche sinon « lancer APRÈS génération »).
- `AssetManager` (Règle d'Or), `gutenberg_formatter.py`, `SemanticChecker` — fonctionnels.

Les 4 chantiers manquants :
1. **Subagent générateur** — créer `.claude/agents/content-generator` qui lit `generation_prompt.txt` et produit le HTML + metadata sous abonnement Max. `scripts/llm/claude_client.py` est le point d'accroche prévu (`simulation_mode=True`, `# TODO: Lancer sub-agent` l.75) mais scopé *corrections* ; le chemin *génération complète* est entièrement absent.
2. **Brancher l'écriture** — appeler `OutputManager.save_refreshed_html()` avec le HTML généré, depuis `cli/commands/refresh.py` (qui s'arrête aujourd'hui l.175 sur « CONTEXTE PRÊT »).
3. **Auto-QC YTG + boucle** — après l'écriture, enchaîner `YTGQualityCheck.check_html()` dans le même run (au lieu d'un re-run manuel). **Boucle de correction** : `A_CORRIGER` → le subagent re-corrige (plafond 2-3 itérations) ; `BLOQUE` → **arrêt + alerte humaine** (garde-fou : sur-optimisation grave non corrigeable mécaniquement). *Décision tranchée (mode autonome) : compromis boucle-légère + stop-sur-BLOQUE, cohérent avec les 3 verdicts déjà distingués par le code et avec la mémoire « correction via sub-agents plan Max, jamais l'API payante ».*
4. **Brancher le maillage dans le pipeline (aujourd'hui manuel/hors-chaîne)** — l'étape 5 « linking » de `process_url` (`orchestrator.py:820`) ne fait qu'un `advance_step`, elle n'injecte rien. À câbler selon le type de tenant :
   - **tenant Superprof** → `SuperprofRotator` : liens de landing `superprof.{pays}/cours/{matière}/{ville}/` (dé-hardcode `superprof_landings.json` par pays) ;
   - **avis Enseigna** → `EnseignaAvisLinker` : 2 liens internes vers d'autres avis **concurrents** de la même famille (l'avis Superprof **exclu** de ce pool) + 1 lien « Superprof avis » distinct → 3 cibles distinctes, jamais 2 liens vers la même page.
   `EnseignaAvisLinker` est le bon moteur (ancre = texte réel) et est déjà exposé en `cw linking avis` ; le `LinkInjector` générique est orphelin (fabrique des phrases artificielles) → **ne pas le brancher tel quel**, préférer étendre le modèle `EnseignaAvisLinker` aux autres tenants. Prérequis : le binding fichier→URL (`enseigna_file_urls.json`) est **manuel** et doit rester la source de vérité (pas de rapprochement auto fiable). Respecter les règles cocons de `CLAUDE.md`.
5. **Refondre le tail de `process_url`** — remplacer le `return` « à faire par l'appelant » (`orchestrator.py:812-848`) pour que la chaîne génération→écriture→QC→**maillage** soit pilotée, `new_title`/`new_meta` peuplés, statut Sheet → DONE.

### Publication et batch (inchangés)

1. **Publication WP automatique** : `WordPressAPIClient` (lecture) + `scripts/utils/push_to_wp.py` existent — non branchés comme étape finale. **Action** : flag `--publish` optionnel sur `cw refresh` qui, après QC OK, appelle `push_to_wp.py` pour le tenant (mapping WP par tenant, pattern `wp_api_config`). Reste à fort blast radius → confirmation humaine.
2. **YourTextGuru** : `YTGAnalyzer` déjà intégré (guide en étape 3, QC en 6ter) — juste s'assurer que chaque tenant a ses credentials YTG dans `.env`.
3. **Un seul point d'entrée batch par tenant** : `cw batch workflow-auto --blog X` existe — il faut que `--blog`/`--market` résolve vers la bonne config, guides, credentials.

---

## 4. Structure config pour généraliser à N marchés × 2 structures (`/blog`, `/ressources`)

Ne pas créer un nouveau repo — monorepo unique privé, moteur central + **dossiers tenants regroupés** `tenants/{tenant}/`. Un `{tenant}` est **n'importe quel client** (blog Superprof pays, `enseigna`, `apuntes`, `resources.com`, futur client), pas seulement un marché Superprof. Le dispatch étant déjà id-keyé (`RefreshOrchestrator._normalize_blog_id()`, `doc_cache.get_blog_config(blog_id)`, `PromptComposer.compose(site_id=...)`, `link_mapping_loader.load_csv(site_id)`) sur un **registre plat**, le regroupement est mécanique : il ne déplace que des racines de chemins, sans toucher à la logique ni introduire de hiérarchie « client ».

```
tenants/
├── {tenant}/                       # tout le client au même endroit, self-service
│   ├── .claude/skills/             # ← skills de génération/QC PROPRES au tenant
│   │                               #   (ex: generate-enseigna-avis, sp-ressources-gutenberg)
│   │                               #   discovery scopée native de Claude Code : lancé depuis
│   │                               #   tenants/{tenant}/, seul ce dossier + les skills transverses
│   │                               #   racine sont chargés. PAS de symlink, PAS de dossier plat global.
│   ├── prompts/site.md             # ← ex _shared/prompts/sites/{id}.md
│   ├── config/tenant.json          # ← ex _shared/config/blogs/{id}.json (wp_api_config, tone…)
│   ├── config/landings.csv         # ← ex superprof_landings.json (dé-hardcodé)
│   ├── linking_maps/               # ← ex _shared/config/linking_maps/{id}.*
│   └── outputs/                    # ← ex _shared/outputs/{id}/
└── …                               # nouveau tenant (tout type) = 1 dossier

.claude/skills/                     # ← noyau TRANSVERSE UNIQUEMENT, vu par tous les tenants :
                                    #   format-wordpress + recherche-sources. Aucun skill de tenant ici.

_shared/config/
└── sites.json                      # index global MINCE — 1 entrée/tenant, types hétérogènes
                                    #   ("structure_type": "blog"|"ressources"|…, "language": …)
```

Un nouveau tenant (quel que soit le client) = **1 dossier `tenants/{tenant}/` à créer** (site.md + config + `.claude/skills/` propres + entrée dans l'index `sites.json`) + credentials `.env` — aucune ligne de code Python à toucher. **Isolement des skills confirmé natif** (vérifié 2026-07-15, doc « large codebases ») : un responsable pays lance `claude` depuis `tenants/{son-tenant}/` et ne voit QUE ses skills + les 2 transverses racine, jamais ceux des 99 autres tenants. Le `.claude/skills/` de son tenant, vide + README au départ, EST sa liste des skills à créer. `CODEOWNERS` par `tenants/{tenant}/` → chacun ne possède que son sous-arbre, zéro conflit git sur un dossier partagé. C'est ce qui rend le modèle tenable à ~100 tenants × ~100 utilisateurs.

> **Réconciliation avec `BRIEF_SIMPLIFICATION_PLAN.md` (Étape F)** : les deux plans convergent désormais sur le **layout regroupé `tenants/{tenant}/`** et le monorepo privé + `CODEOWNERS`. L'ancienne recommandation « garder l'éclatement en 4 arbres plats parallèles » créait la friction « toucher 4 dossiers » pour un responsable pays ; on la remplace par le regroupement. Prérequis à acter au passage : dé-hardcoder `superprof_landings.json` (`superprof_rotator.py:22`, `build_superprof_landings.py:28`) et `push_to_wp.py:22` (`BLOG_CFG` figé superprof-only), et purger les dossiers fantômes `categories/`/`templates/`/`prompts/formats/` résolus par le composer mais absents du disque.

**Ce qui reste à concevoir (pas à coder maintenant, juste cadrer)** :
- Convention de nommage `{tenant}` : un slug libre, non contraint à un schéma Superprof. Pour les blogs Superprof pays, `{lang}-{country}-{structure}` (ex: `es-es-blog`, `pt-br-ressources`) évite les collisions et permet un même pays avec 2 structures ; pour les autres clients, un slug parlant suffit (`enseigna`, `apuntes`, `resources-com`). Aucun tenant n'est privilégié dans l'index.
- Un `--market` catalogue (`cw market list`) pour qu'un collaborateur découvre les IDs valides sans lire de JSON.
- **Index unique des marchés = `sites.json`** (pas de second fichier `markets.json` — une seule source de vérité runtime, sinon on recrée une divergence type contradiction E-E-A-T §Brief). Chaîne amont→aval : **page Notion « config pays »** (source éditée par les humains — https://app.notion.com/p/superprof/b4f6b521eeb14e29a56a527febd9d278?v=2301f405403544ae9abf5e84fefa95bf ) →[sync unidirectionnel, Étape 6]→ `sites.json` (index machine) → `cw market list` (vue humaine) → moteur (runtime, lit `sites.json`, jamais Notion). La page Notion est le tableau de bord ; `sites.json` en est la projection synchronisée.

### 4bis. Trois verrous multi-tenant à lever (bloquants pour l'onboarding d'un collaborateur)

Investigation 2026-07-13 (points A/B) puis 2026-07-15 (point C) : le repo est aujourd'hui **mono-utilisateur déguisé en multi-tenant**. Trois points forcent une édition d'un fichier NOYAU (code Python, ou subagent partagé) à chaque nouveau collaborateur — à corriger pour que « déposer un dossier tenant » suffise réellement.

**A. Google Sheet : nom d'onglet, colonnes et ID à externaliser en config.**
Aujourd'hui hardcodés dans les scripts, pas lus depuis la config :
- **Nom d'onglet** en dur (avec casses incohérentes « New Growing List » / « New growing List ») : `prepare_weekly_batch.py:35` (`NGL_SHEET`), `keyword_resolver.py:54`, `keyword_discovery_growing_list.py:39`, `update_planning_sp_ressources.py:20`. Onglets d'autres tenants pareil : `ENSEIGNA_TABS = ["Avis","Versus"]` (`sheets_client.py:1374`).
- **Colonnes** en dur (url=A/0, kw=B/1, statut=F…).
- **sheet_id** ~70% config/env (`sites.json`, `SPREADSHEET_ID_*`) mais **dupliqué en dur** dans `superprof_gsc_audit.py:38`, `keyword_discovery_growing_list.py:38`, `update_planning_sp_ressources.py:19`.
- Un stub existe déjà mais n'est **pas lu** : `_shared/config/sheets_config.json` (`"main": "TODO_nom_onglet"`).
**Action** : câbler pour de vrai un bloc `sheets` par tenant (`tenants/{tenant}/config` ou `sites.json`) : `{spreadsheet_id, tab_name, columns:{url,keyword,status,...}}`. `SheetsClient.__init__(spreadsheet_id)` est déjà paramétré — le hardcode est dans les *appelants*, pas le client. Supprimer les littéraux dupliqués. **C'est le fichier de TON tenant (« New Growing List » = ta sheet), pas celui de tous les collaborateurs** : chacun a la sienne, d'où l'externalisation obligatoire.

**B. Authentification Google par utilisateur (option `auth_mode`).**
Aujourd'hui : **compte de service partagé unique** (`GOOGLE_SA_PATH`) pour GSC *et* Sheets — un collaborateur devrait recevoir une clé sensible et être ajouté à chaque propriété/sheet. Mais un **flow OAuth navigateur existe déjà**, débranché : `scripts/setup/generate_gsc_token.py` (`InstalledAppFlow` + `run_local_server`, scopes GSC+Sheets corrects → `token.json`). Rien ne lit ce `token.json` au runtime.
**Décision (tranchée, mode autonome) : supporter les DEUX via un flag `auth_mode: service_account | oauth_user` par tenant.** Le service account reste par défaut (il fonctionne déjà sur vos propriétés, zéro friction pour vous) ; un collaborateur externe passe en `oauth_user` : il lance une fois le flow Chrome existant, consent, et l'app utilise **ses** accès GSC/Sheets — sans clé partagée.
**Action** : les 3 helpers d'auth (`_init_direct_api` dans `sheets_client.py:140` et `gsc_analyzer.py:63`, `_build_clients` dans `superprof_gsc_audit.py:64`) tentent `Credentials.from_authorized_user_file(token.json)` (avec refresh) selon `auth_mode`, sinon retombent sur `from_service_account_file`. Distribuer un `credentials.json` (client OAuth desktop). La propriété GSC est déjà paramétrée (`GSCAnalyzer(gsc_property=...)`, `sites.json`). Scopes identiques entre les deux chemins → rien à ajuster côté scopes.

**C. Mapping blog→skill de génération/QC hardcodé dans le subagent noyau (identifié 2026-07-15).**
Aujourd'hui : `.claude/agents/content-generator.md` (L33-35) liste en dur `enseigna → generate-enseigna-avis` et `superprof-ressources → sp-ressources-gutenberg (+ qc-sp-ressources)`. C'est le **même mal que l'erreur du passé** (métier FR câblé dans le code), juste déplacé en Markdown : un collaborateur PT/US devrait éditer ce fichier NOYAU partagé pour brancher SON skill. Les skills typés par tenant sont légitimes (chaque tenant a besoin des siens, cf. §4 `.claude/skills/` par tenant) — le défaut est le **point de branchement en dur dans le subagent partagé**, pas leur existence.
**Action** : externaliser le mapping en config par tenant : ajouter `generation_skill` et `qc_skill` (nullable) à l'entrée du tenant (`tenants/{tenant}/config/tenant.json` ou `sites.json`). Réécrire `content-generator.md` pour qu'il **résolve le skill à invoquer depuis la config du tenant** (« utilise le skill nommé dans `generation_skill`, puis `qc_skill` s'il est non-null ») au lieu de lister enseigna/superprof. Résultat : ajouter un tenant = 1 dossier `.claude/skills/` + 2 champs config, **zéro édition du noyau**. Combiné à la discovery scopée (§4), c'est ce qui ferme complètement le couplage moteur↔tenant côté génération.

> Ces deux verrous sont la condition pour que la promesse « onboarding = 1 dossier `tenants/{tenant}/`, zéro code » soit vraie. À intégrer au séquencement (phase monorepo/config).

---

## Hors scope de ce plan

- Pas de nouveau repo, pas de duplication d'orchestrateur.
- Pas de base de données locale en remplacement de l'accès GSC : la data GSC se récupère à la demande via le MCP `gsc-remote` (§2c). Le Google Sheet reste l'interface de pilotage humaine.
- Pas d'onboarding d'un pays réel maintenant — le point 4 documente le layout cible et les fichiers à créer par tenant, pas la création d'un marché précis. ⚠️ **Correction** : contrairement à ce qui était supposé, l'architecture actuelle ne supporte **pas encore** l'ajout d'un tenant sans réécriture — les deux verrous de §4bis (onglet/colonnes hardcodés, auth service-account partagée) imposent aujourd'hui une édition du code Python. Les lever fait partie de la refonte (pas hors scope) ; c'est leur résolution qui rendra vraie la promesse « zéro code ».

---

## Prochaines étapes concrètes (ordre d'implémentation)

1. Vérifier/étendre les règles `allow` de `.claude/settings.json` pour que chaque sous-commande `cw` tourne sans prompt de confirmation (section 1).
2. Créer `.claude/commands/{refresh,batch,audit,decide,market-status}.md` qui wrappent `cw` en un seul appel Bash chacun (aucune modif Python).
3. Créer un subagent dédié à la génération (ex: `.claude/agents/content-generator.md`) dont l'unique rôle est : lire `generation_prompt.txt` composé par le CLI, produire le HTML/JSON de sortie, respecter la Règle d'Or (assets_before ≥ assets_after) — pas de logique métier dans le subagent, juste exécution du prompt déjà composé. Le brancher pour qu'il tourne sous l'abonnement Max (Agent tool), jamais via un appel API direct facturé séparément.
4. Réduire `CLAUDE.md` à un index de commandes + pointeurs vers les guides (ne plus inliner les règles détaillées qui sont déjà dans `_shared/docs/*.md` et `_shared/prompts/sites/*.md`).
5. Documenter/vérifier que `--market` peut déjà transiter comme `--blog` dans le CLI actuel (sinon ajouter un alias `--market` = `--blog` dans `cli/commands/*.py`, changement minime).
6. Brancher `push_to_wp.py` comme étape optionnelle `--publish` dans `cw refresh` / `cw workflow run`.
7. S'assurer que les appels GSC dans l'orchestrateur (et dans les slash commands `/audit`, `/market-status`) passent par le MCP `gsc-remote` plutôt que par un scraping/relecture de fichier local, pour tout accès ad hoc initié depuis Claude Code.
8. Écrire la mémoire `project_architecture_map` (section 0) une fois les étapes 1-7 stabilisées.

---

## Vérification

- Lancer `cw refresh <url_test> --blog enseigna` en CLI pur (sans Claude Code) pour confirmer que le moteur fonctionne indépendamment de l'agent — preuve que l'interface est bien découplée, et que le CLI ne fait aucun appel API Anthropic lui-même.
- Créer une commande `/refresh` de test, l'invoquer dans une session Claude Code fraîche, et vérifier dans les logs/transcript qu'aucun fichier `_shared/prompts/sites/*.md` volumineux n'a été lu par la session principale (seul `generation_prompt.txt` composé doit être lu, et seulement par le subagent de génération — pas par l'agent principal).
- Vérifier que la génération passe bien par le subagent (Agent tool / abonnement Max) et non par un appel API à la clé — inspecter qu'aucune clé API Anthropic n'est configurée/utilisée dans le chemin `cw refresh` → génération.
- Comparer le nombre de tokens consommés par un `/refresh` via slash command vs. l'ancien flux texte libre, sur la même URL.

---
---

# Volet 2 — Refonte CLAUDE.md vers Agent Skills natifs (allègement du contexte)

**Statut** : proposition, non implémentée (discussion du 10/07)
**Complémentaire au Volet 1** : le Volet 1 construit l'interface `/commande` autour du CLI `cw` ;
ce volet traite la deuxième source de gaspillage de tokens — `CLAUDE.md` lui-même, chargé
intégralement à chaque session alors que la majorité de son contenu ne sert que ponctuellement.
Les deux volets partagent le même objectif (industrialiser, économiser les tokens, éliminer le
texte libre) et doivent être lus ensemble.

> **Validation externe (call ingénieur IA).** Trois recommandations du call sont déjà portées
> par ces deux volets : (1) **« créer des skills »** = Volet 2 (`.claude/skills/`) ; (2) **« liste de
> commandes déterministes qui exécutent les skills »** = Volet 1 (slash commands `.claude/commands/`
> qui wrappent `cw`, cf. `/refresh` « commande déterministe ») ; (3) **« IA.md, lis le fichier / éviter
> que la conversation soit remplie de contexte »** = le même diagnostic, mais résolu **mieux** par le
> natif que par un unique `IA.md` qu'on demande de lire : le *progressive disclosure* des skills ne
> laisse que les `description` en contexte (~200 tokens) et charge le corps à la demande, là où un gros
> fichier lu en entier recharge tout à chaque fois. On garde l'approche skills. Le point « config pays
> dans Notion » est traité dans le `BRIEF_SIMPLIFICATION_PLAN.md` (Étape E), et « séparer le nettoyage
> de la refonte » y est acté en Étape 0.

## Contexte

Le projet Content Writer souffre d'un **CLAUDE.md monolithique de 668 lignes** chargé
intégralement à chaque session. ~60 % de ce fichier sont des **procédures spécifiques**
(Workflow 7 étapes, Formats & Métadonnées, Checklist Spreadsheet, Template refresh, détail
des 6 stratégies) qui ne servent que ponctuellement mais coûtent des tokens en permanence.
L'objectif : migrer ces workflows vers le **système natif de skills** (`.claude/skills/`)
pour bénéficier du *progressive disclosure* (seul le `description` d'un skill reste en
contexte, ~200 tokens ; le corps se charge à la demande), et réduire CLAUDE.md aux seules
règles universelles.

Le déclencheur était un prompt d'orchestration proposé par l'utilisateur. Après vérification
des faits, **ce prompt reposait sur 3 hypothèses fausses** qui invalidaient son approche telle
quelle. Ce volet corrige la trajectoire.

## Évaluation du prompt initial de l'utilisateur

### Ce qui était FAUX dans le prompt (à ne pas suivre)

1. **`.claudeignore` ≠ économie de tokens.** Vérifié : `.claudeignore` exclut les fichiers
   des recherches (Glob/Grep) — il n'existe PAS de "scan automatique" qui brûlerait le
   contexte. Un fichier non lu = 0 token. Donc « les dossiers ne brûleront pas mon contexte »
   est un malentendu. `.claudeignore` reste utile, mais pour **accélérer/cibler les
   recherches**, pas pour le budget tokens. Bonus : c'est un signal *bypassable*, pas une
   barrière (pour ça → `permissions.deny` dans `settings.json`).

2. **Mettre les skills dans `_shared/prompts/` = réinventer (mal) le natif.** Des `.md`
   dans un dossier custom restent des fichiers passifs que Claude doit être *invité* à lire
   (coût + friction). Le système natif `.claude/skills/<nom>/SKILL.md` fait automatiquement
   ce que le prompt tentait de forcer : index auto (les `description`), chargement à la demande,
   invocation `/nom`. **Pire encore** : mettre les skills dans un dossier *ignoré* les
   rendrait inutilisables.

3. **La commande de suivi n'est pas `/stats`.** Vérifié : c'est **`/context`** (décomposition
   de la fenêtre : system prompt, MCP tools, CLAUDE.md/MEMORY.md, skills, messages, etc.) et
   **`/usage`** (coût $ / attribution). `/mcp` montre le coût par serveur MCP.

### Ce qui était JUSTE (à garder)

- Le **diagnostic de fond** : CLAUDE.md trop lourd → skills. 100 % valide, et cohérent avec
  le Volet 1 (section « Gestion du contexte et économie de tokens »).
- **Réponses concises, formats structurés, rapports compacts.**
- **Séparer `_local/` (machine) et archives du reste** — bonne hygiène (et là `.claudeignore`
  a du sens, pour cibler les recherches).

### Découverte non anticipée par le prompt

L'architecture **« 4 niveaux » (Category + Strategy + Site + Template) décrite dans CLAUDE.md
n'existe pas réellement** : `_shared/prompts/categories/` et `.../templates/` sont vides/absents
dans les faits (le Volet 1 ci-dessus documente le composer tel que codé, mais la réalité des
fichiers sur disque est plus proche de 2 niveaux effectifs). Le réel est à ~2 niveaux
(`strategies/` = 5 fichiers, `sites/` = 15 fichiers, templates Enseigna imbriqués en `.html`
sous `sites/enseigna/`). La refonte doit **réaligner la doc sur le réel**, pas propager une
architecture fantôme. **À trancher avant implémentation** : soit documenter les 2 niveaux réels,
soit peupler `categories/`/`templates/` si l'intention est de les remplir plus tard.

### Verdict

On ne suit PAS la structure du prompt initial (`_shared/prompts/` comme couche d'orchestration
manuelle). On adopte l'approche **« migrer l'existant vers skills natifs »** : garder l'arbo
`_shared/` actuelle, extraire les workflows en `.claude/skills/`, alléger CLAUDE.md, et
ajouter un `.claudeignore` pour la *pertinence des recherches* (pas le budget tokens).

## Approche retenue

### A. Alléger CLAUDE.md (668 → cible ~150 lignes)

**Critère de tri (pas « est-ce important ? » — tout l'est).** Le bon test est : *est-ce nécessaire à **chaque** session pour que l'agent s'oriente, ou seulement quand il exécute une tâche précise ?* Ce qui n'est utile que ponctuellement descend en skill (chargé à la demande), même si c'est une règle importante. Principe : **`CLAUDE.md` = ce qu'il faut pour s'orienter** (qui je suis, quels tenants, quelles skills existent, quels invariants absolus) ; **les skills = ce qu'il faut pour exécuter une tâche donnée** (notamment tout le « comment rédiger »).

**Reste dans CLAUDE.md** (universel, toujours en contexte) :
- **Rôle & Mission** (condensé), **Architecture Multi-Tenant + règle d'override** (l'agent doit savoir en permanence qu'il y a N tenants et comment ils se résolvent), **Composition des prompts** en **pointeur** (savoir *que* le prompt = strategy + site, pas le détail), les **3 Piliers**.
- **La *carte* des étapes du workflow** — la liste des titres (Identification → GSC → DataForSEO → SERP → Décision → **Recherche sources** → Génération → QC YTG → Maillage → Sync), **une ligne par étape**. C'est de l'**orientation** : l'agent doit savoir en permanence quelle est la chaîne pour invoquer la bonne skill au bon moment. Seul le **détail procédural** de chaque étape descend en skill (voir ci-dessous). ⚠️ Ne pas confondre : la *carte* reste, le *mode d'emploi* descend.
- **Règle d'Or** en **une ligne** seulement (invariant de sécurité « jamais réduire les assets ») — le détail (JSON de validation avant/après, exemples) descend dans la skill `refresh`.
- CLAUDE.md devient aussi l'**index des skills** (une ligne par skill : quand l'invoquer) — même rôle d'index que le Volet 1 lui assignait pour les slash commands `/refresh`, `/audit`, etc. Les deux index (commandes + skills) cohabitent dans le même CLAUDE.md allégé, pas dans deux fichiers séparés.

**Descend vers les skills** (« comment rédiger » — utile seulement quand une skill de rédaction est active, donc du coût de contexte gaspillé à chaque session s'il reste dans CLAUDE.md) :
- **Règles Éditoriales** (anti-patterns, callouts interdits) → skills de rédaction (`format-wordpress`, `generate-enseigna-avis`, `sp-ressources-gutenberg`).
- **E-E-A-T (framework)** → skills de rédaction / génération (cadre de rédaction, pas d'orientation).
- **Détail de la Règle d'Or** → skill `refresh`.
- **Détail procédural de chaque étape du workflow** (comment auditer, quel score bloque, comment composer le prompt…), Formats & Métadonnées, Checklist Spreadsheet, Template Article Refresh, détail des 6 stratégies → skills correspondantes. *(La carte des étapes, elle, reste dans CLAUDE.md — cf. ci-dessus. Cohérent avec `BRIEF_SIMPLIFICATION_PLAN.md` : « Reste : les 7 étapes + un index de pointeurs ».)*

> Effet : CLAUDE.md ne porte plus que l'**orientation** + les **index**. Toute connaissance procédurale ou de rédaction est en skill, chargée à la demande. Cible ~150 lignes (vs 668), et le contexte permanent chute d'autant.

### B. Créer les skills natifs sous `.claude/skills/` — un TOOLKIT, pas un monolithe

**Principe (correction d'orientation).** La version initiale de ce plan faisait de `refresh-article` **le** cœur monolithique qui contient tout. L'investigation du code (2026-07-13) inverse ce constat : **8 des 12 capacités SEO sont déjà des modules autonomes adossés à une commande `cw`** — elles sont déjà invocables indépendamment. Le SEO doit donc être exposé comme un **toolkit de skills discrètes et réutilisables**, chacune faisant une chose (« maille cet article », « donne les perfs de cette URL », « audite la SERP »), et `/refresh` devient un **orchestrateur mince qui les séquence**, pas un contenant qui les ré-inline.

Deux axes de classement :
- **Lecture vs transformation** : les skills de *lecture* (perfs, indexation) sont sans effet de bord → **auto-déclenchables** (`disable-model-invocation: false`) ; les skills de *transformation* (refresh, netlinking, publish) sont lourdes/à blast radius → **déclenchées par l'utilisateur** (`disable-model-invocation: true`).
- **Coût de construction** : beaucoup wrappent juste un `cw` déterministe ou un tool MCP déjà branché → **quasi zéro code**.

#### Famille 1 — Performance / Reporting SEO (lecture seule, auto-déclenchable)

Répond à « récupère les perfs SEO de cette URL ». Sans effet de bord, donc sûre à auto-déclencher. Presque entièrement gratuite : wrappe le MCP `gsc-remote` déjà branché (`.mcp.json`).

| Skill | Wrappe | Effort |
|---|---|---|
| **`/performances-url <url>`** | MCP `gsc-remote get_search_by_page_query` **ou** `GSCAnalyzer.analyze(url)` (`gsc_analyzer.py:72`, sort clics/impressions/CTR/position + tendances + quick wins) | **~zéro code** (MCP) |
| **`/diagnostic-indexation <url>`** | MCP `inspect_url_enhanced` + `check_indexing_issues` ; batch multi-tenant déjà via `cw report monday-indexation` | **zéro code** (MCP) |
| **`/comparer-periodes <url\|site>`** | MCP `compare_search_periods` | **zéro code** (MCP) |
| **`/rapport-gsc [--site\|--mensuel]`** | `cw audit gsc-state --site` (état top-N) ; volet mensuel/tendance = scripts `scripts/reports/*monthly_report.py` **sans CLI** | **mixte** : état = wrappe `cw` ; mensuel = à exposer (`cw report gsc-monthly`) |

> Source complémentaire optionnelle : MCP Ahrefs (`site-explorer-organic-keywords`, `pages-by-traffic`) pour positions + trafic estimé, en regard des données réelles GSC.

#### Famille 2 — Capacités SEO discrètes (transformation, invocables seules)

Chacune wrappe une commande `cw` **déjà existante** (Tier A → quasi zéro code) :

| Skill | Wrappe `cw` | Invocable seule |
|---|---|---|
| **`/audit-serp <url>`** | `cw audit serp` (`audit.py:84`) | oui |
| **`/audit-editorial <url>`** | `cw audit editorial --blog` (quality gate, score<4 bloque) | oui |
| **`/keyword-discovery`** | `cw batch keyword-discovery --blog` | oui (batch) |
| **`/audit-gsc`** | `cw batch audit-gsc` | oui (batch) |
| **`/netlinking <url>`** | `cw linking avis [--apply]` (`EnseignaAvisLinker` + `SuperprofRotator`) | **oui** ← ex. canonique : « maille cet article » sans lancer un refresh entier |
| **`/ytg-guide`** | `cw ytg create-guide --keyword` (brief sémantique pré-génération) | oui |
| **`/ytg-qc`** | `cw ytg qc --blog --slug [--fix]` (gate post-génération) | oui |

À exposer (Tier B — module autonome mais pas de `cw`, ajouter un wrapper mince) : **`/wp-publish`** (`push_to_wp`), **`/gutenberg-format`** (`gutenberg_formatter`), **`/netlinking-internal`** (`LinkInjector` — mais préférer étendre `EnseignaAvisLinker`, cf. §3).

#### Famille 3 — Skills de rédaction / format (le contenu éditorial)

Les skills qui portent le *quoi dire* et le *comment rédiger* (chargées par le subagent générateur) :
1. **`recherche-sources <sujet\|url>`** — **recherche documentaire en cascade** : pioche d'abord dans la **bibliothèque curée par matière** (`tenants/{tenant}/sources/{matière}.md`), puis complète les lacunes via `deep-research` + `WebSearch`/`WebFetch` et enrichit la biblio au passage. Nourrit le brief E-E-A-T (sources vérifiées, pas inventées). **À construire**, avec deux livrables : (a) le socle bibliothèque (constitution semi-auto : agent propose → humain valide) ; (b) le câblage recherche+injection au brief. Cf. étape 5bis. Invocable seule (« documente-moi ce sujet ») **et** appelée par l'orchestrateur avant la génération.
2. **`qc-sp-ressources`** — checklist QC Superprof. Le plus autonome → **skill témoin à faire en 1er**.
3. **`generate-enseigna-avis`** — article avis (ACF JSON, verdict rapide en fin, pas de déclaration d'indépendance).
4. **`sp-ressources-gutenberg`** — format Gutenberg maison (5 blocs, AdvGB, infobox).
5. **`format-wordpress`** — Formats & Métadonnées (HTML clean, accents/tiret/ancres). Référençable par les autres.
6. *(le contenu généré lui-même est produit par le subagent `content-generator`, cf. §3 « Bout-en-bout ».)*

#### Famille 4 — Orchestrateur mince

**`refresh`** ne contient plus tout : il **séquence** les skills des familles 1-3 pour le flux complet (audit → décision → **recherche sources** → génération → QC YTG → netlinking → publish), comme documenté dans les étapes du workflow. Il invoque `cw refresh` (déterministe) puis délègue génération/correction au subagent. Trois pièces encore à **construire** avant d'être pleinement exposables : la **recherche de sources** (étape 5bis, aucune existante), la **génération** (stub `orchestrator.py:1852/1935`) et la **cannibalisation** (couplée dans `AuditEngine`, la commande `cw audit cannibalization` annoncée n'existe pas → extraire d'abord).

**Frontmatter type** (avec le flag clé découvert) :
```yaml
# Skill de transformation (lourde) → déclenchée par l'utilisateur
---
name: refresh
description: Orchestre le refresh SEO complet d'un article (audit → décision → génération →
  QC YTG → netlinking) pour un tenant, à partir de signaux GSC/DataForSEO. Invoquer via /refresh.
disable-model-invocation: true   # workflow lourd → déclenché par l'utilisateur, pas auto
---

# Skill de lecture (légère) → auto-déclenchable
---
name: performances-url
description: Récupère les performances SEO d'une URL (clics, impressions, CTR, position,
  tendances) via GSC. Lecture seule, aucun effet de bord.
disable-model-invocation: false   # sûre → Claude peut la charger quand on parle perfs
---
```
Règle du flag : **`true` pour les skills de transformation lourdes** (refresh, génération,
netlinking, publish) qu'on déclenche soi-même ; **`false` (défaut) pour les skills de lecture
et QC légères** (famille Performance, `qc-sp-ressources`) utilement auto-déclenchées quand le
sujet arrive dans la conversation.

Taille cible d'un SKILL.md : même ordre de grandeur que CLAUDE.md (~200 lignes), le détail
lourd part en fichiers annexes lus à la demande.

**Articulation avec le subagent de génération du Volet 1** : le subagent `content-generator`
(section « Prochaines étapes concrètes », point 3 du Volet 1) et les skills de rédaction
(`generate-enseigna-avis` / `sp-ressources-gutenberg` / `format-wordpress`) ne sont pas
redondants — le subagent est le *contexte d'exécution* (tourne sous l'abonnement Max, isole les
tokens de génération de la session principale), les skills sont la *documentation procédurale*
qu'il charge pour savoir comment rédiger. Le subagent lit le SKILL.md pertinent, pas l'inverse.

**Ordre de construction du toolkit** (valeur/coût) : commencer par les skills **~zéro code** à
plus fort levier — la Famille 1 (Performance, wrappe le MCP `gsc-remote`) et les 7 skills Tier A
de la Famille 2 (wrappent un `cw` existant) sont livrables presque immédiatement et prouvent le
modèle toolkit. Puis la Famille 3 (rédaction, dont `qc-sp-ressources` comme témoin). L'orchestrateur
`refresh` (Famille 4) vient **en dernier**, car il dépend des deux pièces à construire (génération,
cannibalisation) — inutile d'assembler un flux dont deux briques n'existent pas encore.

#### Backlog de skills SEO (futures) — liste, PAS des fichiers

> **Le SEO se skillifie bien plus loin que le refresh.** Investigation 2026-07-13 : ~15 skills
> supplémentaires sont possibles, la plupart à coût faible. **Important — ceci n'alourdit PAS le
> repo générique** : une skill non écrite ne coûte rien, et une skill invoquée ne charge son corps
> qu'à la demande (*progressive disclosure*, ~200 tokens d'index par skill). Ce backlog est de la
> **documentation de priorisation**, pas des `SKILL.md` à créer maintenant. Deux garde-fous : (1)
> ne créer un dossier de skill que quand on la construit vraiment ; (2) **ne skillifier que des
> capacités portables** — les modules client-spécifiques (`enseigna_*`, `superprof_*`) restent des
> *templates*, pas des skills du repo générique (cohérent avec les verrous §4bis).

**Backlog A — zéro code (wrappent un MCP déjà branché : `gsc-remote`, `dataforseo-remote`, Ahrefs).** Ouvre des familles SEO **absentes du projet aujourd'hui**, surtout l'off-page :
- **Off-page / Backlinks** (aucune ligne de code backlinks n'existe dans le repo) : `/backlinks-audit` (profil référents/ancres/spam/liens cassés), `/link-gap` (domaines liant les concurrents pas nous), `/rank-tracker` (positions dans le temps).
- **Recherche & concurrence** : `/content-gap` (KW où les concurrents rankent), `/search-intent` (intention à l'échelle), `/trends` (courbes de demande).
- **Technique** : `/audit-technique` (Lighthouse/on-page via `on_page_lighthouse`), `/sitemap` (`gsc-remote manage_sitemaps`).
- **GEO/AEO** : `/brand-radar` (visibilité de marque dans les réponses IA — Ahrefs `brand-radar-*`).

**Backlog B — wrappent du code déjà écrit (juste un `SKILL.md` à ajouter) :**
- `/optimiser-titre` (`TitleOptimizer`), `/extraire-paa` (`SERPAnalyzer`), `/detecter-intention` (`IntentDetector`), `/demander-indexation` (`cw indexing request`), `/scan-sitemap-obsolete` (`SitemapAnalyzer.find_stale_content`), `/audit-onpage` (`HTMLAnalyzer`).
- ⚠️ Dédupliquer avant de construire : `/scan-sitemap-obsolete` & `/demander-indexation` vs `/diagnostic-indexation` ; `/gsc-monthly` vs `/rapport-gsc`.

**Backlog C — à construire (vrais chantiers, pas des wrappers) :**
- `/cocon-validator` (construire/valider l'arbre PARENT/CHILD — substrat présent mais aucun code de graphe ; répond au besoin cocons de `CLAUDE.md`), `/schema-jsonld` (données structurées schema.org — greenfield), `/meta-description` (génération dédiée — aujourd'hui seulement extraite).

### C. Ajouter un `.claudeignore` (pertinence des recherches, PAS budget tokens)

Exclure les ~94 Mo / ~1700 fichiers de **données générées** des recherches Glob/Grep :
```
_shared/context/     # 17 Mo, 778 fichiers (scrapes/audits)
_shared/outputs/     # 5,7 Mo, 739 fichiers (articles générés)
_shared/temp/        # 1,5 Mo, 101 fichiers
_local/              # 70 Mo (données machine)
Images/
__pycache__/
.venv/
_shared/prompts/_archive/
```
Cadrer le message : ceci **accélère et cible** les recherches ; ça ne « sauve » pas de tokens
en soi (les fichiers non lus n'en consommaient déjà pas).

### D. Réaligner la doc sur l'architecture réelle

Corriger la section « Composition des prompts » de CLAUDE.md : décrire les 2 niveaux effectifs
(strategy + site, templates Enseigna en `.html`), retirer les niveaux `categories/` et
`templates/` fantômes — ou les créer si l'intention est de les remplir plus tard (décision
à confirmer au moment de l'implémentation).

## Fichiers concernés

- `CLAUDE.md` — allègement + transformation en index de skills **et** de slash commands
  (fusion avec l'index du Volet 1) + réalignement doc.
- `.claude/skills/<nom>/SKILL.md` (nouveaux, ~5 dossiers) — voir découpage B.
- `.claude/commands/{refresh,batch,audit,decide,market-status}.md` (nouveaux, voir Volet 1).
- `.claudeignore` (nouveau, racine) — voir C.
- Ressources déjà existantes à référencer (pas à dupliquer) :
  `_shared/prompts/strategies/*.md`, `_shared/prompts/sites/enseigna/acf-fields-template.md`,
  `_shared/prompts/sites/superprof-ressources-reference.md`,
  `_shared/prompts/sites/superprof-ressources/guide-*.md`.
- Source de vérité pour QC : mémoires `feedback_sp_ressources_qc_checklist`,
  `feedback_faq_question_emoji`, `feedback_advgb_block_format`, etc.

## Vérification (end-to-end)

1. **Avant** : lancer `/context` et noter les tokens de la ligne « Memory files » (CLAUDE.md).
2. Créer d'abord le **skill témoin `qc-sp-ressources`**, relancer une session, vérifier :
   - `/context` montre le skill (name+description seulement) dans la catégorie Skills ;
   - `/qc-sp-ressources` charge bien le corps à la demande.
3. Alléger CLAUDE.md, relancer `/context` : la ligne Memory files doit chuter nettement
   (cible ~200 lignes vs 668).
4. Exécuter un vrai QC via `/qc-sp-ressources` sur un article de `_shared/outputs/` et
   confirmer que le résultat est identique à l'ancien comportement (aucune règle perdue).
5. Vérifier qu'une recherche Grep ne fouille plus `_shared/context/` ni `_local/`
   (`.claudeignore` actif).

## Séquencement proposé (Volet 2, à enchaîner après ou en parallèle du Volet 1)

1. Skill témoin `qc-sp-ressources` (preuve de concept, risque minimal).
2. Validation `/context` + exécution réelle.
3. Extraction des 4 autres skills.
4. Allègement CLAUDE.md + réalignement doc + fusion de l'index skills/commandes.
5. Ajout `.claudeignore`.

---

## Volet doc : consolider `_shared/docs/` (sous-chantier de la phase 5)

**Constat vérifié en session.** Les 12 `.md` de `_shared/docs/` ne sont **pas** un problème de contexte : ils ne sont jamais chargés automatiquement. Deux canaux les consomment à la demande — `CLAUDE.md` (renvois « voir détails dans… », pour l'humain et l'agent) et `scripts/cache/doc_cache.py` (chargement runtime par l'orchestrateur). Le seul poids permanent réel est `CLAUDE.md` lui-même (668 lignes, injecté à chaque session) — traité en phase 5. Le vrai défaut de `_shared/docs/` n'est pas le volume, c'est l'**incohérence** : doublons, orphelins, docs d'implémentation pourris.

**Point critique — contradiction E-E-A-T câblée.** Deux fichiers quasi-identiques coexistent et sont chargés par **deux entry points différents** : `doc_cache.py:108` charge `EEAT_2026_GUIDELINES.md` (runtime, ce que voit l'orchestrateur), tandis que `CLAUDE.md` renvoie vers `EEAT_GUIDE.md` (ce que je lis en session). Or `EEAT_GUIDE.md` se déclare lui-même « Version 3.0 — fusion EEAT_GUIDE + EEAT_2026_GUIDELINES » : la fusion a été faite mais l'ancien fichier n'a jamais été supprimé ni le runtime repointé. Résultat : le workflow charge une version pendant que la doc en montre une autre. **Action** : faire de `EEAT_GUIDE.md` l'unique doc E-E-A-T (superset : exemples ❌/✅ + piliers + YMYL + scoring), repointer `doc_cache.py:108` dessus, supprimer `EEAT_2026_GUIDELINES.md`. Vérifier au passage que `EEAT_GUIDE.md` couvre bien les tenants voulus (l'ancien 2026 listait 6 blogs, le nouveau se limite à 2 — réaligner sur les 2 tenants réels de `sites.json`).

**Verdicts par fichier** (audit sous-agent, croisé au code) :

| Fichier | Verdict | Raison |
|---|---|---|
| `EEAT_GUIDE.md` | **GARDER (canonique E-E-A-T)** | Superset déclaré ; en faire l'unique doc, repointer `doc_cache.py`. |
| `EEAT_2026_GUIDELINES.md` | **SUPPRIMER** (après repointage runtime) | Doublon quasi-total absorbé par `EEAT_GUIDE.md`. |
| `STYLE_GUIDE.md` | **GARDER** | Doc le plus référencé (CLAUDE.md + prompts `full_refresh`/`semantic_reorientation`), anti-patterns uniques. |
| `SEO_GUIDELINES.md` | **GARDER (hub)** | Pivot câblé runtime ; nettoyer sa duplication GEO interne et ses deux sections « 9 ». |
| `GEO_2026_GUIDELINES.md` | **GARDER** | Traitement GEO approfondi, complémentaire de SEO_GUIDELINES (pas un doublon). |
| `COCONS_GUIDE.md` | **GARDER** | Guide maillage durable, chargé par CLAUDE.md. |
| `CONTENT_REFRESH_GUIDE.md` | **GARDER** | Guide stratégique câblé runtime ; rafraîchir stats datées (76.4%…). |
| `OUTPUT_ARCHITECTURE.md` | **VÉRIFIER FRAÎCHEUR** | `output_manager.py` existe mais le doc parle de 6 sites vs `VALID_SITE_IDS` réel (à recompter). |
| `PARENT_H2_WHITELIST_GUIDE.md` | **VÉRIFIER FRAÎCHEUR** | Code décrit existe, mais test cité manquant + doc orphelin ; garder si feature active. |
| `SITEMAP_DISCOVERY.md` | **RÉÉCRIRE ou SUPPRIMER** | Point d'entrée `sitemap_discovery.py`/`main.py` absents (exemples CLI non exécutables) + contenu corrompu (domaines placeholder, 6 blogs tous « enseigna »). |
| `YEAR_UPDATE_IMPLEMENTATION.md` | **ARCHIVER** | Log de livraison à n° de ligne périssables, orphelin ; sortir des guides actifs (→ `_shared/docs/archive/` ou git). |
| `ADD_COLUMNS_GUIDE.md` | **SUPPRIMER** | Procédure one-shot déjà appliquée ; script `add_sheet_columns.py` inexistant ; path Windows en dur ; orphelin. |

**Principe de tri** : distinguer les **guides conceptuels durables** (règles édito/SEO — restent des docs) des **docs d'implémentation** (décrivent du code, pourrissent avec les n° de ligne et les noms de fichiers — à archiver ou convertir). Ne supprimer un doc câblé (`doc_cache.py`) qu'après avoir repointé ou retiré le chargement correspondant, jamais l'inverse.

---

## Séquencement global recommandé (les DEUX fichiers de plan)

Cette section est **le point d'entrée unique pour exécuter la refonte**. Elle intègre les étapes
du `BRIEF_SIMPLIFICATION_PLAN.md` (Étape 0, A→F) **et** les deux volets de ce fichier. Règles
d'or à respecter par l'agent qui l'exécute :

- **Une phase à la fois**, avec **arrêt et vérification** après chacune (chaque plan a sa section
  *Vérification*). Ne pas enchaîner « tout d'un coup ».
- **`CLAUDE.md` n'est réécrit qu'UNE seule fois** (phase 5). Les phases antérieures ne font que
  produire les skills/commandes qu'il indexera — sinon on le réécrit deux fois.
- **Nettoyage ≠ refonte** : la phase 0 est en **PR séparées**, sans changement de comportement.

| Phase | Contenu | Source | Point d'arrêt / vérif |
|---|---|---|---|
| **0. Nettoyage** | Purge code mort (dossiers fantômes `categories/`/`templates/`/`formats/`), archivage des 3 stratégies, `.claudeignore`, isolation `_local/`. **PR séparées, aucun changement de comportement.** | Brief **Étape 0** | Grep ne fouille plus les données générées ; tests toujours verts. |
| **1. Skills** | Skill témoin `qc-sp-ressources` → validation `/context` → 4 autres skills. Crée aussi la skill de refresh (`edito-refresh`) + `references/{full_refresh,eeat_rewrite,seo_geo_eeat}.md`. | Volet 2 (1-3) + Brief **A** | `/qc-sp-ressources` charge à la demande ; QC identique à l'ancien. |
| **2. Réduction stratégies + bug** | `strategy_prompts` → 2 fichiers ; **corriger le bug fallback** `ghostwriter.py:594` ; simplifier `PromptComposer` à 2 niveaux. | Brief **B + D** | Forcer TITLE_OPTIMIZATION → le ghostwriter ne compose plus full_refresh. |
| **3. Slash commands + subagent** | Permissions `.claude/settings.json`, `.claude/commands/` (wrappers `cw`), subagent `content-generator` référençant les skills de la phase 1. | Volet 1 (1-3) | `/refresh` de bout en bout sans invite ; génération via subagent (abonnement Max). |
| **3bis. Bout-en-bout (génération → outputs → QC → maillage)** | Brancher la chaîne complète : subagent générateur lit `generation_prompt.txt` → écrit via `save_refreshed_html()` → auto `YTGQualityCheck.check_html()` → boucle correction (`A_CORRIGER` re-corrige, `BLOQUE` stop+alerte) → **maillage** (`SuperprofRotator` pour tenant Superprof / `EnseignaAvisLinker` pour avis Enseigna) ; refondre le tail `process_url`. **Rédaction sous abonnement Max, jamais API payante.** | §3 « Bout-en-bout » | Un `/refresh <url>` va de l'URL au contenu écrit dans `_shared/outputs/{tenant}/` + verdict YTG + liens injectés, sans reprise manuelle. |
| **4. Monorepo `tenants/{tenant}/`** | `git mv` des 4 arbres `{id}` → `tenants/{id}/` ; racines de chemins (composer, doc_cache, link loader, output dir) ; **dé-hardcode superprof-only** (`superprof_rotator`, `push_to_wp`, `build_superprof_landings`) ; **externaliser onglet/colonnes/sheet_id Sheet par tenant** (§4bis-A, virer `NGL_SHEET` & littéraux) ; **`auth_mode` service_account\|oauth_user** en rebranchant le flow Chrome existant (§4bis-B) ; `sites.json` → index mince ; `CODEOWNERS`. | Brief **F** + §4/§4bis | Refresh enseigna OK depuis `tenants/enseigna/` ; tenant factice non-Superprof chargé **sans modif code** (onglet/sheet en config) ; un collègue s'authentifie via Chrome (OAuth) sur SA propre sheet + GSC. |
| **5. Fusion `CLAUDE.md` (UNE fois) + consolidation `_shared/docs/`** | Allègement unique → index des skills **et** slash commands + réalignement doc. **Consolider `_shared/docs/`** (voir *Volet doc*) : fusion E-E-A-T sur `EEAT_GUIDE.md` + repointage `doc_cache.py:108` ; suppression `ADD_COLUMNS_GUIDE.md` ; archivage `YEAR_UPDATE_IMPLEMENTATION.md` ; décision `SITEMAP_DISCOVERY.md` ; vérif fraîcheur `OUTPUT_ARCHITECTURE`/`PARENT_H2_WHITELIST`. | Brief **C** + Volet 2 (4) + *Volet doc* | Ligne « Memory files » de `/context` chute nettement (~150-200 l. vs 668) ; un **seul** doc E-E-A-T, chargé par le même nom via CLAUDE.md **et** `doc_cache.py`. |
| **6. Multi-tenant runtime + Notion** | Alias `--market`, `--publish`, accès GSC via MCP `gsc-remote` ; **page Notion « config pays » → sync `sites.json`** (unidirectionnel, pas de lecture Notion au runtime) ; recensement blogs Superprof pays ; mémoire `project_architecture_map`. | Volet 1 (5-8) + Volet 2 (5) + Brief **E** | `sites.json` (index UNIQUE, pas de `markets.json` séparé) cohérent avec la page Notion ; le moteur ne lit pas Notion au run. |

> **Ordre des dépendances clés** : phase 0 (base propre) → phases 1-2 (skills + stratégies, sans
> toucher `CLAUDE.md`) → phase 3 (commandes qui s'appuient sur les skills) → phase 4 (déplacement
> physique des tenants) → phase 5 (**seule** réécriture de `CLAUDE.md`, qui indexe tout ce qui
> précède) → phase 6 (branchements runtime + Notion). La phase 4 (monorepo) et la phase 5
> (`CLAUDE.md`) peuvent être inversées si l'on préfère figer la doc avant le `git mv`, mais **jamais**
> réécrire `CLAUDE.md` avant que skills + commandes existent.
