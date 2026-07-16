"""
YourTextGuru (YTG) Analyzer Module

Client API pour YourTextGuru — création de guides sémantiques, récupération
des termes à optimiser et calibration des scores SOSEO/DSEO sur les vraies
données concurrentes (TOP 3 / TOP 10 SERP).

Utilisation typique :
    analyzer = YTGAnalyzer()
    result = analyzer.create_and_wait("bienfaits yoga")
    # result.semantic_terms   → list[str] pour semantic_field_override
    # result.term_colors      → dict {terme: "blue"|"green"|"orange"|"red"}
    # result.top3_soseo       → float (cible SOSEO > cette valeur)
    # result.top3_dseo        → float (cible DSEO < cette valeur)
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemin des credentials (même pattern que serp_analyzer.py)
# ---------------------------------------------------------------------------
YTG_CREDENTIALS_PATH = Path(
    os.environ.get("YTG_CREDENTIALS_PATH", "~/.credentials/ytg/credentials.json")
).expanduser()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class YTGAPIError(Exception):
    """Erreur renvoyée par l'API YTG."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"YTG API {status_code}: {message}")


class YTGGuideTimeoutError(Exception):
    """Délai dépassé en attendant qu'un guide soit prêt."""
    def __init__(self, guide_id: str, attempts: int):
        self.guide_id = guide_id
        self.attempts = attempts
        super().__init__(
            f"Guide YTG '{guide_id}' non prêt après {attempts} tentatives"
        )


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class YTGTerm:
    """Un terme du guide YTG avec son statut d'optimisation."""
    term: str
    color: str          # "blue" | "green" | "orange" | "red"
    min_count: int = 0  # occurrences minimales recommandées
    max_count: int = 0  # occurrences maximales recommandées
    current_count: int = 0  # occurrences dans le document analysé


@dataclass
class YTGGuideResult:
    """Résultat complet d'un guide YourTextGuru."""
    guide_id: str
    keyword: str
    status: str              # "ready" | "pending"
    top3_soseo: float        # SOSEO moyen TOP 3 (%)
    top3_dseo: float         # DSEO moyen TOP 3 (%)
    top10_soseo: float       # SOSEO moyen TOP 10 (%)
    top10_dseo: float        # DSEO moyen TOP 10 (%)
    our_soseo: Optional[float] = None   # SOSEO de notre contenu (si analysé)
    our_dseo: Optional[float] = None    # DSEO de notre contenu (si analysé)
    terms: list[YTGTerm] = field(default_factory=list)
    semantic_terms: list[str] = field(default_factory=list)    # flat list
    term_colors: dict[str, str] = field(default_factory=dict)  # term → couleur
    raw_data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Analyst principal
# ---------------------------------------------------------------------------

class YTGAnalyzer:
    """
    Client API YourTextGuru.

    Credentials : clé API via variable d'environnement YTG_API_KEY
    ou fichier JSON à YTG_CREDENTIALS_PATH.

    Graceful degradation : si la clé est absente, toutes les méthodes
    retournent None avec un warning (non-bloquant, même comportement que
    SERPAnalyzer sans credentials DataForSEO).
    """

    API_BASE_URL = "https://yourtext.guru/api/v2"
    GUIDE_ENDPOINT = "/guides"
    ANALYZE_ENDPOINT = "/guides/{guide_id}/check"

    # Projet/groupe par défaut pour les guides Content Writer (thematic-websites)
    DEFAULT_PROJECT_ID = 106774
    DEFAULT_GROUP_ID = 82174

    # Polling : 15 s × 20 tentatives = 5 min max
    POLL_INTERVAL_SECONDS = 15
    POLL_MAX_ATTEMPTS = 20

    def __init__(self):
        self._api_key: str = ""
        self._init_credentials()

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def _init_credentials(self):
        """Charge la clé API depuis l'env ou le fichier de credentials."""
        # 1) Variable d'environnement directe
        # YTG_NEW_API_KEY prioritaire (rotation de clé) ; YTG_API_KEY = legacy.
        self._api_key = os.environ.get("YTG_NEW_API_KEY", "") or os.environ.get(
            "YTG_API_KEY", ""
        )

        # 2) Fichier JSON (fallback)
        if not self._api_key and YTG_CREDENTIALS_PATH.exists():
            try:
                with open(YTG_CREDENTIALS_PATH) as f:
                    creds = json.load(f)
                    if "ytg" in creds:
                        creds = creds["ytg"]
                    key = creds.get("api_key", "")
                    if key and key != "YOUR_YTG_API_KEY":
                        self._api_key = key
            except Exception as e:
                logger.warning(f"[YTG] Erreur chargement credentials: {e}")

        if not self._api_key:
            logger.warning(
                "[YTG] Clé API manquante. Définir YTG_API_KEY dans .env "
                "ou créer ~/.credentials/ytg/credentials.json. "
                "Le module YTG sera désactivé."
            )

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict:
        """Headers pour les requêtes GET (pas de Content-Type)."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    def _post_headers(self) -> dict:
        """Headers pour les requêtes POST sans body (ex: POST /guides)."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    def list_guides(
        self,
        group_id: Optional[int] = None,
        lang: Optional[str] = None,
        status: Optional[str] = None,
        last_id: int = 0,
    ) -> list[dict]:
        """
        Liste une page de guides YTG (GET /guides, 50 items max).

        Returns:
            list[dict] — une page de GuideInfo bruts.
        """
        if not self.is_configured:
            return []

        url = f"{self.API_BASE_URL}{self.GUIDE_ENDPOINT}"
        params: dict = {}
        if group_id is not None:
            params["groupId"] = group_id
        if lang:
            params["lang"] = lang
        if status:
            params["status"] = status
        if last_id:
            params["lastId"] = last_id

        try:
            response = requests.get(url, headers=self._headers(), params=params, timeout=30)
            if response.status_code in (401, 403):
                raise YTGAPIError(response.status_code, "Clé API invalide")
            response.raise_for_status()
            data = response.json()
            items = data if isinstance(data, list) else data.get("data", data.get("guides", []))
            return items if isinstance(items, list) else []
        except YTGAPIError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[YTG] Erreur list_guides: {e}")
            return []

    def list_guides_all(
        self,
        group_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """
        Télécharge TOUS les guides du groupe (pagination automatique via lastId).

        L'API retourne 50 items par page. On pagine jusqu'à page vide.

        Returns:
            list[dict] — tous les guides du groupe.
        """
        all_guides: list[dict] = []
        last_id = 0

        while True:
            page = self.list_guides(
                group_id=group_id or self.DEFAULT_GROUP_ID,
                status=status,
                last_id=last_id,
            )
            if not page:
                break
            all_guides.extend(page)
            if len(page) < 50:
                break  # Dernière page
            last_id = page[-1].get("id", 0)
            if not last_id:
                break

        logger.info(f"[YTG] {len(all_guides)} guides téléchargés (groupId={group_id or self.DEFAULT_GROUP_ID})")
        return all_guides

    def build_query_index(self, guides: list[dict]) -> dict[str, dict]:
        """
        Construit un index {query_normalisée: guide_dict} depuis une liste de guides.

        Permet le matching local O(1) au lieu de N appels API.
        """
        index: dict[str, dict] = {}
        for g in guides:
            query = g.get("query", g.get("keyword", ""))
            if query:
                index[query.lower().strip()] = g
        return index

    def find_guide_by_keyword(
        self,
        keyword: str,
        group_id: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Cherche un guide existant pour ce mot-clé exact dans le groupe.

        Comparaison normalisée (minuscules, espaces réduits).

        Returns:
            dict brut du guide si trouvé, None sinon.
        """
        target = keyword.lower().strip()
        guides = self.list_guides_all(group_id=group_id or self.DEFAULT_GROUP_ID)
        for g in guides:
            query = g.get("query", g.get("keyword", ""))
            if query and query.lower().strip() == target:
                ready = g.get("ready", False)
                in_progress = g.get("inProgress", False)
                logger.info(
                    f"[YTG] Guide existant trouvé pour '{keyword}' "
                    f"(id={g.get('id')}, ready={ready}, inProgress={in_progress})"
                )
                return g
        return None

    # Map short language codes to YTG locale format
    LANG_MAP = {
        "fr": "fr_FR", "en": "en_GB", "es": "es_ES", "de": "de_DE",
        "it": "it_IT", "pt": "pt_PT", "nl": "nl_NL",
    }

    def create_guide(
        self,
        keyword: str,
        language: str = "fr_FR",
        country: str = "fr",
        deduplicate: bool = True,
    ) -> Optional[str]:
        """
        Crée un guide YTG pour le mot-clé donné.

        Si `deduplicate=True` (défaut), vérifie d'abord si un guide existe
        déjà pour ce mot-clé dans le groupe et retourne son ID sans recréer.

        Returns:
            guide_id (str) si succès, None si non configuré.
        Raises:
            YTGAPIError: si l'API retourne une erreur HTTP.
        """
        if not self.is_configured:
            return None

        # Normalize short lang codes (fr → fr_FR)
        lang_normalized = self.LANG_MAP.get(language, language)

        # Déduplication (uniquement pour usage CLI standalone, pas pour batch)
        # Pour les batches, utiliser batch-prefetch qui télécharge les guides en une passe.
        if deduplicate:
            existing = self.find_guide_by_keyword(keyword)
            if existing:
                guide_id = str(existing.get("id", ""))
                logger.info(f"[YTG] Réutilisation guide existant: {guide_id} pour '{keyword}'")
                return guide_id

        url = f"{self.API_BASE_URL}{self.GUIDE_ENDPOINT}"
        params = {
            "query": keyword,
            "lang": lang_normalized,
            "projectId": self.DEFAULT_PROJECT_ID,
            "groupId": self.DEFAULT_GROUP_ID,
        }

        try:
            # POST sans body : pas de Content-Type (l'API attend des query params)
            response = requests.post(
                url, headers=self._post_headers(), params=params, timeout=30
            )
            if response.status_code in (401, 403):
                raise YTGAPIError(response.status_code, "Clé API invalide ou crédits épuisés")
            if response.status_code not in (200, 201):
                content_type = response.headers.get("Content-Type", "")
                snippet = response.text[:200] if response.text else ""
                raise YTGAPIError(
                    response.status_code,
                    f"Réponse inattendue (Content-Type={content_type}): {snippet}"
                )
            data = response.json()
            guide_id = data.get("id") or data.get("guide_id") or data.get("data", {}).get("id")
            if not guide_id:
                raise YTGAPIError(0, f"guide_id absent dans la réponse: {data}")
            logger.info(f"[YTG] Guide créé: {guide_id} pour '{keyword}'")
            return str(guide_id)
        except YTGAPIError:
            raise
        except requests.exceptions.JSONDecodeError as e:
            raise YTGAPIError(0, f"Réponse non-JSON: {response.text[:200]}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[YTG] Erreur réseau create_guide: {e}")
            raise YTGAPIError(0, str(e))

    def get_guide_status(self, guide_id: str) -> Optional[dict]:
        """
        Récupère le statut et les données d'un guide existant.

        Returns:
            dict brut de l'API, ou None si non configuré.
        """
        if not self.is_configured:
            return None

        url = f"{self.API_BASE_URL}{self.GUIDE_ENDPOINT}/{guide_id}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
            if response.status_code in (401, 403):
                raise YTGAPIError(response.status_code, "Clé API invalide")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[YTG] Erreur get_guide_status({guide_id}): {e}")
            raise YTGAPIError(0, str(e))

    @staticmethod
    def _is_ready(raw: dict) -> bool:
        """
        Vérifie si un guide est prêt.

        L'API YTG utilise des booleans plutôt qu'un champ status :
        - Liste GET /guides : {"ready": true, "inProgress": false, "error": false}
        - Détail GET /guides/{id} : {"data": {"ready": true, ...}, ...}
        """
        # Format liste (pas de wrapping "data")
        if "ready" in raw:
            return bool(raw.get("ready")) and not bool(raw.get("error"))
        # Format détail (wrapping dans "data")
        d = raw.get("data", {})
        if "ready" in d:
            return bool(d.get("ready")) and not bool(d.get("error"))
        # Fallback legacy (string status)
        return raw.get("status") == "ready"

    @staticmethod
    def _is_error(raw: dict) -> bool:
        """Vérifie si un guide est en erreur."""
        if "error" in raw:
            return bool(raw.get("error"))
        d = raw.get("data", {})
        if "error" in d:
            return bool(d.get("error"))
        return raw.get("status") == "error"

    def wait_for_guide(
        self,
        guide_id: str,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        max_attempts: int = POLL_MAX_ATTEMPTS,
    ) -> dict:
        """
        Attend qu'un guide soit prêt en pollingant jusqu'à max_attempts fois.

        Returns:
            dict brut de l'API quand ready == true.
        Raises:
            YTGGuideTimeoutError: si le guide n'est pas prêt après max_attempts.
        """
        for attempt in range(1, max_attempts + 1):
            data = self.get_guide_status(guide_id)
            if data is None:
                raise YTGAPIError(0, "YTG non configuré")

            if self._is_error(data):
                raise YTGAPIError(0, f"Guide {guide_id} en erreur")

            is_ready = self._is_ready(data)
            logger.info(
                f"[YTG] Guide {guide_id} — ready={is_ready} "
                f"({attempt}/{max_attempts})"
            )

            if is_ready:
                return data

            if attempt < max_attempts:
                time.sleep(poll_interval)

        raise YTGGuideTimeoutError(guide_id, max_attempts)

    def create_and_wait(
        self,
        keyword: str,
        language: str = "fr",
        country: str = "fr",
    ) -> Optional["YTGGuideResult"]:
        """
        Crée un guide et attend qu'il soit prêt.

        Pas de déduplication ici : pour éviter un download de tous les guides.
        La déduplication doit être gérée en amont :
        - Via batch-prefetch (bulk, 1 seul download)
        - Via orchestrateur STEP 2.5 (vérifie audit_data["ytg_guide_id"] d'abord)

        Returns:
            YTGGuideResult parsé, ou None si non configuré.
        """
        if not self.is_configured:
            return None

        guide_id = self.create_guide(keyword, language, country, deduplicate=False)
        if not guide_id:
            return None

        raw = self.wait_for_guide(guide_id)
        return self._parse_guide_result(guide_id, keyword, raw)

    def get_or_create_guide(
        self,
        guide_id: str,
        keyword: str,
        language: str = "fr",
    ) -> Optional["YTGGuideResult"]:
        """
        Récupère un guide existant par ID (cache hit), ou le crée si absent.

        Appelé par l'orchestrateur STEP 2.5 :
        - guide_id présent dans audit_data → 1 seul GET /guides/{id}
        - guide_id absent → create_and_wait() (crée + attend)

        Args:
            guide_id: ID connu du guide (depuis audit_data), ou "" si inconnu.
            keyword: Mot-clé pour créer le guide si nécessaire.
        """
        if not self.is_configured:
            return None

        if guide_id:
            # Cache hit : fetch direct, pas de recherche
            raw = self.get_guide_status(guide_id)
            if raw and self._is_ready(raw):
                logger.info(f"[YTG] Cache hit guide {guide_id}")
                return self._parse_guide_result(guide_id, keyword, raw)
            if raw and not self._is_ready(raw):
                # Guide pas encore prêt → polling
                raw = self.wait_for_guide(guide_id)
                return self._parse_guide_result(guide_id, keyword, raw)

        # Pas de guide_id → créer
        return self.create_and_wait(keyword, language)

    def get_guide(self, guide_id: str, keyword: str = "") -> Optional["YTGGuideResult"]:
        """
        Récupère un guide existant (cache hit).

        Returns:
            YTGGuideResult ou None si non configuré / guide non prêt.
        """
        if not self.is_configured:
            return None

        raw = self.get_guide_status(guide_id)
        if not raw:
            return None

        if not self._is_ready(raw):
            logger.info(f"[YTG] Guide {guide_id} pas encore prêt")
            return None

        return self._parse_guide_result(guide_id, keyword, raw)

    def analyze_content(
        self,
        guide_id: str,
        content_text: str,
    ) -> Optional[dict]:
        """
        Analyse un contenu texte contre un guide YTG (étape optionnelle post-génération).

        Returns:
            dict avec {our_soseo, our_dseo, term_colors} ou None si non configuré.
        """
        if not self.is_configured:
            return None

        url = f"{self.API_BASE_URL}{self.ANALYZE_ENDPOINT.format(guide_id=guide_id)}"
        payload = {"text": content_text}

        try:
            response = requests.post(
                url, headers=self._headers(), json=payload, timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_analysis_result(data)
        except requests.exceptions.RequestException as e:
            logger.error(f"[YTG] Erreur analyze_content({guide_id}): {e}")
            return None

    # ------------------------------------------------------------------
    # SERP competitor scores
    # ------------------------------------------------------------------

    def fetch_serp_scores(self, guide_id: str) -> dict:
        """
        Récupère les SOSEO/DSEO réels des concurrents via GET /guides/{id}/serp.

        Returns:
            dict with top3_soseo, top3_dseo, top10_soseo, top10_dseo
            (moyennes calculées depuis serps[].scores.soseo/dseo)
        """
        if not self.is_configured:
            return {}

        url = f"{self.API_BASE_URL}{self.GUIDE_ENDPOINT}/{guide_id}/serp"
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"[YTG] Erreur fetch_serp_scores({guide_id}): {e}")
            return {}

        serps = data.get("serps", [])
        if not serps:
            return {}

        def avg(values):
            return sum(values) / len(values) if values else 0

        top3_s = [s.get("scores", {}).get("soseo", 0) for s in serps[:3]]
        top3_d = [s.get("scores", {}).get("dseo", 0) for s in serps[:3]]
        top10_s = [s.get("scores", {}).get("soseo", 0) for s in serps[:10]]
        top10_d = [s.get("scores", {}).get("dseo", 0) for s in serps[:10]]

        return {
            "top3_soseo": round(avg(top3_s), 1),
            "top3_dseo": round(avg(top3_d), 1),
            "top10_soseo": round(avg(top10_s), 1),
            "top10_dseo": round(avg(top10_d), 1),
        }

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_guide_result(
        self, guide_id: str, keyword: str, raw: dict
    ) -> "YTGGuideResult":
        """
        Parse la réponse brute de GET /guides/{id} en YTGGuideResult.

        Les champs target_SOSEO_min/max et target_DSEO_min/max sont les
        plages cibles recommandées par YTG (PAS les moyennes concurrents).

        Les vrais scores concurrents (TOP 3 / TOP 10) sont récupérés via
        fetch_serp_scores() qui appelle GET /guides/{id}/serp.
        """
        # Plages cibles YTG (pour référence)
        target_soseo_min = float(raw.get("target_SOSEO_min") or 0)
        target_soseo_max = float(raw.get("target_SOSEO_max") or 0)
        target_dseo_max = float(raw.get("target_DSEO_max") or 0)

        # Récupérer les vrais scores concurrents depuis /serp
        serp_scores = self.fetch_serp_scores(guide_id)

        top3_soseo = serp_scores.get("top3_soseo", target_soseo_min)
        top3_dseo = serp_scores.get("top3_dseo", target_dseo_max)
        top10_soseo = serp_scores.get("top10_soseo", target_soseo_min)
        top10_dseo = serp_scores.get("top10_dseo", target_dseo_max)

        # Les termes sont dans "data" sous forme de ngrams
        d = raw.get("data", raw)
        keyword_from_guide = d.get("query", keyword)

        # Combiner 1grams + 2grams + 3grams
        terms_raw: list[str] = []
        terms_raw.extend(d.get("1grams", []))
        terms_raw.extend(d.get("2grams", []))
        terms_raw.extend(d.get("3grams", []))

        # Ajouter les entités nommées si présentes
        terms_raw.extend(d.get("entities", []))

        # Supprimer les doublons en conservant l'ordre
        seen: set[str] = set()
        unique_terms: list[str] = []
        for t in terms_raw:
            if t and isinstance(t, str) and t not in seen:
                seen.add(t)
                unique_terms.append(t)

        # Créer des YTGTerm sans couleur (les couleurs viennent de analyze_content)
        terms = [YTGTerm(term=t, color="green") for t in unique_terms]

        semantic_terms = self.extract_semantic_terms_from_list(terms)
        term_colors = self.extract_term_colors_from_list(terms)

        return YTGGuideResult(
            guide_id=guide_id,
            keyword=keyword_from_guide or keyword,
            status="ready",
            top3_soseo=top3_soseo,
            top3_dseo=top3_dseo,
            top10_soseo=top10_soseo,
            top10_dseo=top10_dseo,
            terms=terms,
            semantic_terms=semantic_terms,
            term_colors=term_colors,
            raw_data=raw,
        )

    def _parse_analysis_result(self, raw: dict) -> dict:
        """Parse le résultat d'une analyse de contenu.

        L'API retourne les scores en MAJUSCULES au niveau racine :
        {"SOSEO": 109, "DSEO": 33, "areas": {"subOptimization": {...}, ...}}
        """
        # Scores: try uppercase first (actual API), then lowercase (legacy)
        our_soseo = float(raw.get("SOSEO", raw.get("soseo", 0)) or 0)
        our_dseo = float(raw.get("DSEO", raw.get("dseo", 0)) or 0)

        # Targets
        target_soseo_min = float(raw.get("target_SOSEO_min", 0) or 0)
        target_soseo_max = float(raw.get("target_SOSEO_max", 0) or 0)
        target_dseo_max = float(raw.get("target_DSEO_max", 0) or 0)

        # Term colors from areas + scores
        # Each area has {term: [min_level, max_level]} boundaries.
        # The term's actual score is in raw["scores"][term].
        # Color = which area boundary the score falls into.
        term_colors = {}
        areas = raw.get("areas", {})
        scores_map = raw.get("scores", {})
        if scores_map and areas:
            sub = areas.get("subOptimization", {})
            std = areas.get("standardOptimization", {})
            strong = areas.get("strongOptimization", {})
            over = areas.get("overOptimization", {})
            all_terms = set(sub) | set(std) | set(strong) | set(over)
            for term in all_terms:
                score = scores_map.get(term, 0)
                if score == 0:
                    term_colors[term] = "absent"
                    continue
                sub_hi = sub.get(term, [0, 0])[1] if term in sub else 0
                std_hi = std.get(term, [0, 0])[1] if term in std else 0
                strong_hi = strong.get(term, [0, 0])[1] if term in strong else 0
                if score <= sub_hi:
                    term_colors[term] = "blue"
                elif score <= std_hi:
                    term_colors[term] = "green"
                elif score <= strong_hi:
                    term_colors[term] = "orange"
                else:
                    term_colors[term] = "red"

        # Fallback to legacy format
        if not term_colors:
            d = raw.get("data", raw)
            term_colors = self._extract_color_map(
                d.get("keywords", d.get("terms", []))
            )

        # Build term_scores (actual occurrence score per term)
        # and term_targets (green zone boundaries per term)
        term_scores = {}
        term_targets = {}
        if scores_map and areas:
            std = areas.get("standardOptimization", {})
            for term in set(sub) | set(std) | set(strong) | set(over):
                term_scores[term] = scores_map.get(term, 0)
                if term in std:
                    bounds = std[term]
                    term_targets[term] = {
                        "green_min": bounds[0] if len(bounds) > 0 else 0,
                        "green_max": bounds[1] if len(bounds) > 1 else 0,
                    }
                else:
                    term_targets[term] = {"green_min": 0, "green_max": 0}

        return {
            "our_soseo": our_soseo,
            "our_dseo": our_dseo,
            "target_soseo_min": target_soseo_min,
            "target_soseo_max": target_soseo_max,
            "target_dseo_max": target_dseo_max,
            "term_colors": term_colors,
            "term_scores": term_scores,
            "term_targets": term_targets,
        }

    def _parse_terms(self, terms_raw) -> list[YTGTerm]:
        """Parse une liste de termes bruts en YTGTerm."""
        if not terms_raw or not isinstance(terms_raw, list):
            return []

        result = []
        for item in terms_raw:
            if isinstance(item, str):
                # Format simplifié: juste le terme
                result.append(YTGTerm(term=item, color="green"))
            elif isinstance(item, dict):
                term = item.get("word", item.get("term", item.get("keyword", "")))
                if not term:
                    continue
                color = self._map_color(item)
                result.append(YTGTerm(
                    term=term,
                    color=color,
                    min_count=int(item.get("min", item.get("min_count", 0)) or 0),
                    max_count=int(item.get("max", item.get("max_count", 0)) or 0),
                    current_count=int(item.get("count", item.get("current", 0)) or 0),
                ))
        return result

    def _map_color(self, item: dict) -> str:
        """
        Mappe les données d'un terme vers une couleur YTG.

        Conventions possibles selon la version API :
        - champ "color": "blue" | "green" | "orange" | "red"
        - champ "status": "sub_optimization" | "normal" | "strong" | "over_optimization"
        - champ "level": int (0=blue, 1-2=green, 3=orange, 4+=red)
        """
        # 1) Couleur explicite
        color = item.get("color", "")
        if color in ("blue", "green", "orange", "red"):
            return color

        # 2) Statut textuel
        status = item.get("status", item.get("optimization_status", ""))
        status_map = {
            "sub_optimization": "blue",
            "sub-optimization": "blue",
            "under_optimized": "blue",
            "normal": "green",
            "ok": "green",
            "strong": "orange",
            "strong_optimization": "orange",
            "over_optimization": "red",
            "over_optimized": "red",
            "suroptimisation": "red",
        }
        if status in status_map:
            return status_map[status]

        # 3) Niveau numérique
        level = item.get("level", item.get("optimization_level", -1))
        if isinstance(level, (int, float)):
            if level == 0:
                return "blue"
            elif level <= 2:
                return "green"
            elif level == 3:
                return "orange"
            elif level >= 4:
                return "red"

        # 4) Inférence depuis min/max/count
        count = int(item.get("count", item.get("current", 0)) or 0)
        min_c = int(item.get("min", 0) or 0)
        max_c = int(item.get("max", 0) or 0)
        if min_c > 0 and count == 0:
            return "blue"
        if max_c > 0 and count > max_c:
            return "red"

        return "green"

    def _extract_color_map(self, terms_raw) -> dict[str, str]:
        """Retourne un dict {term: color} depuis une liste brute."""
        terms = self._parse_terms(terms_raw)
        return self.extract_term_colors_from_list(terms)

    def _safe_float(self, d: dict, keys: list, default: float) -> float:
        """Cherche une valeur float dans d selon plusieurs clés possibles."""
        for key in keys:
            val = d.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue
        return default

    # ------------------------------------------------------------------
    # Helpers publics pour l'orchestrateur
    # ------------------------------------------------------------------

    def extract_semantic_terms(self, guide_data: dict) -> list[str]:
        """
        Extrait la liste plate des termes à optimiser depuis des données brutes.

        Args:
            guide_data: dict brut retourné par get_guide_status()
        Returns:
            list[str] — pour semantic_field_override dans audit_data
        """
        d = guide_data.get("data", guide_data)
        terms_raw = d.get("keywords", d.get("terms", d.get("words", [])))
        terms = self._parse_terms(terms_raw)
        return self.extract_semantic_terms_from_list(terms)

    def extract_term_colors(self, guide_data: dict) -> dict[str, str]:
        """
        Extrait le mapping {terme: couleur} depuis des données brutes.

        Args:
            guide_data: dict brut retourné par get_guide_status()
        Returns:
            dict[str, str] — pour ytg_term_colors dans audit_data
        """
        d = guide_data.get("data", guide_data)
        terms_raw = d.get("keywords", d.get("terms", d.get("words", [])))
        terms = self._parse_terms(terms_raw)
        return self.extract_term_colors_from_list(terms)

    @staticmethod
    def extract_semantic_terms_from_list(terms: list[YTGTerm]) -> list[str]:
        """Retourne la liste plate des termes (toutes couleurs confondues)."""
        return [t.term for t in terms if t.term]

    @staticmethod
    def extract_term_colors_from_list(terms: list[YTGTerm]) -> dict[str, str]:
        """Retourne le dict {terme: couleur}."""
        return {t.term: t.color for t in terms if t.term}

    def extract_competitor_targets(self, guide_data: dict) -> dict:
        """
        Extrait les cibles concurrentes depuis des données brutes.

        Returns:
            dict avec top3_soseo, top3_dseo, top10_soseo, top10_dseo
        """
        result = self._parse_guide_result("", "", guide_data)
        return {
            "top3_soseo": result.top3_soseo,
            "top3_dseo": result.top3_dseo,
            "top10_soseo": result.top10_soseo,
            "top10_dseo": result.top10_dseo,
        }
