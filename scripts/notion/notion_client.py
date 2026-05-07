"""
Notion API Client Module

Client pour l'API Notion v1 — lecture des tables de commandes (articles
déjà écrits depuis 2024) et gestion des nouveaux sujets à traiter.

Usages principaux :
    1. Anti-cannibalisation par titre : vérifier qu'un article similaire
       n'a pas déjà été commandé/publié sur un blog.
    2. Découverte de sujets : lister les topics non encore traités.
    3. Création de sujets : enregistrer un nouveau sujet détecté par le pipeline.

Credentials : token d'intégration Notion via NOTION_TOKEN dans .env
ou fichier JSON à NOTION_CREDENTIALS_PATH.

Graceful degradation : si le token est absent, toutes les méthodes
retournent des listes vides / None avec un warning (non-bloquant).
"""

import json
import logging
import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemin des credentials (même pattern que les autres analyzers)
# ---------------------------------------------------------------------------
NOTION_CREDENTIALS_PATH = Path(
    os.environ.get("NOTION_CREDENTIALS_PATH", "~/.credentials/notion/credentials.json")
).expanduser()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

# Mapping domaine Notion (NDD) → blog_id interne
_DOMAIN_TO_BLOG_ID: dict[str, str] = {
    "enseigna.fr": "enseigna",
    "superprof.fr": "superprof-ressources",
}

# Mapping inverse blog_id → domaine Notion (pour les filtres API)
_BLOG_ID_TO_DOMAIN: dict[str, str] = {v: k for k, v in _DOMAIN_TO_BLOG_ID.items()}


@dataclass
class NotionCommande:
    """Un article commandé/publié, lu depuis la base Notion."""
    notion_page_id: str
    title: str
    url: str = ""
    blog_id: str = ""
    status: str = ""
    date: str = ""
    subject: str = ""
    ytg_keyword: str = ""


@dataclass
class NotionSujet:
    """Un sujet à traiter, lu depuis la base Notion."""
    notion_page_id: str
    title: str
    blog_id: str = ""
    category: str = ""
    priority: str = ""
    status: str = ""


# ---------------------------------------------------------------------------
# Client principal
# ---------------------------------------------------------------------------

class NotionClient:
    """
    Client API Notion v1.

    Credentials : NOTION_TOKEN dans .env ou
    ~/.credentials/notion/credentials.json → {"token": "secret_xxx"}

    Toutes les méthodes de lecture retournent des listes vides si le token
    est absent (non-bloquant).
    """

    API_BASE_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"
    PAGE_SIZE = 100  # Max par requête Notion

    def __init__(self):
        self._token: str = ""
        self._init_credentials()

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def _init_credentials(self):
        """Charge le token depuis l'env ou le fichier de credentials."""
        # 1) Variable d'environnement directe
        self._token = os.environ.get("NOTION_TOKEN", "")

        # 2) Fichier JSON (fallback)
        if not self._token and NOTION_CREDENTIALS_PATH.exists():
            try:
                with open(NOTION_CREDENTIALS_PATH) as f:
                    creds = json.load(f)
                    if "notion" in creds:
                        creds = creds["notion"]
                    token = creds.get("token", creds.get("integration_token", ""))
                    if token and token != "YOUR_NOTION_TOKEN":
                        self._token = token
            except Exception as e:
                logger.warning(f"[Notion] Erreur chargement credentials: {e}")

        if not self._token:
            logger.warning(
                "[Notion] Token d'intégration manquant. Définir NOTION_TOKEN dans .env "
                "ou créer ~/.credentials/notion/credentials.json. "
                "Le module Notion sera désactivé."
            )

    @property
    def is_configured(self) -> bool:
        return bool(self._token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # API low-level
    # ------------------------------------------------------------------

    def query_database(
        self,
        database_id: str,
        filter_dict: Optional[dict] = None,
        sorts: Optional[list] = None,
    ) -> list[dict]:
        """
        Requête une base de données Notion avec pagination automatique.

        Args:
            database_id: ID de la base Notion (32 chars hex ou UUID)
            filter_dict: Filtre Notion (format API v1)
            sorts: Liste de tris Notion

        Returns:
            Liste complète des pages (résultats de toutes les pages).
            Retourne [] si non configuré.
        """
        if not self.is_configured:
            return []

        url = f"{self.API_BASE_URL}/databases/{database_id}/query"
        all_results = []
        payload: dict = {"page_size": self.PAGE_SIZE}
        if filter_dict:
            payload["filter"] = filter_dict
        if sorts:
            payload["sorts"] = sorts

        cursor = None
        while True:
            if cursor:
                payload["start_cursor"] = cursor

            try:
                response = requests.post(
                    url, headers=self._headers(), json=payload, timeout=30
                )
                if response.status_code == 401:
                    logger.error("[Notion] Token invalide (401)")
                    break
                if response.status_code == 404:
                    logger.error(f"[Notion] Base introuvable: {database_id}")
                    break
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"[Notion] Erreur query_database({database_id}): {e}")
                break

            results = data.get("results", [])
            all_results.extend(results)

            if not data.get("has_more", False):
                break
            cursor = data.get("next_cursor")

        return all_results

    def get_page(self, page_id: str) -> Optional[dict]:
        """Récupère une page Notion par son ID."""
        if not self.is_configured:
            return None

        url = f"{self.API_BASE_URL}/pages/{page_id}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[Notion] Erreur get_page({page_id}): {e}")
            return None

    def create_page(self, database_id: str, properties: dict) -> Optional[dict]:
        """
        Crée une nouvelle page dans une base Notion.

        Args:
            database_id: ID de la base cible
            properties: Dict des propriétés Notion (format API v1)

        Returns:
            Page créée (dict) ou None si erreur.
        """
        if not self.is_configured:
            return None

        url = f"{self.API_BASE_URL}/pages"
        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }

        try:
            response = requests.post(
                url, headers=self._headers(), json=payload, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[Notion] Erreur create_page: {e}")
            return None

    def update_page(self, page_id: str, properties: dict) -> Optional[dict]:
        """
        Met à jour les propriétés d'une page Notion.

        Args:
            page_id: ID de la page
            properties: Dict des propriétés à modifier (format API v1)

        Returns:
            Page mise à jour (dict) ou None si erreur.
        """
        if not self.is_configured:
            return None

        url = f"{self.API_BASE_URL}/pages/{page_id}"
        payload = {"properties": properties}

        try:
            response = requests.patch(
                url, headers=self._headers(), json=payload, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[Notion] Erreur update_page({page_id}): {e}")
            return None

    # ------------------------------------------------------------------
    # Commandes (articles commandés/publiés)
    # ------------------------------------------------------------------

    def get_commandes(
        self,
        database_id: str,
        blog_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[NotionCommande]:
        """
        Récupère les commandes d'articles depuis la base Notion "📕 Commandes".

        Schéma réel de la base :
          - "Blog Catégorie" (title)  → titre de l'article
          - "Permalink" (rich_text)   → URL de l'article
          - "NDD" (select)            → domaine du site (ex: "enseigna.fr")
          - "Statut" (status)         → statut de traitement
          - "Mois" (select)           → mois de publication (ex: "Mars 2026")
          - "Sujet" (rich_text)       → résumé du sujet
          - "Requête YTG" (rich_text) → mot-clé principal pour YTG

        Args:
            database_id: ID de la base "Commandes" Notion
            blog_id: blog ID interne (ex: "enseigna") — converti en domaine pour le filtre
            status: Filtre sur le statut (optionnel)

        Returns:
            Liste de NotionCommande. Retourne [] si non configuré.
        """
        filter_dict = None

        # Convertir blog_id → domaine pour le filtre "NDD"
        domain = _BLOG_ID_TO_DOMAIN.get(blog_id, blog_id) if blog_id else None

        conditions = []
        if domain:
            conditions.append({"property": "NDD", "select": {"equals": domain}})
        if status:
            conditions.append({"property": "Statut", "status": {"equals": status}})

        if len(conditions) == 2:
            filter_dict = {"and": conditions}
        elif len(conditions) == 1:
            filter_dict = conditions[0]

        pages = self.query_database(database_id, filter_dict=filter_dict)
        return [self._parse_commande(p) for p in pages]

    def _parse_commande(self, page: dict) -> NotionCommande:
        """Parse une page Notion en NotionCommande (schéma réel '📕 Commandes').

        Champs clés :
          - "Sujet"          → title  (titre de l'article, utilisé pour l'anti-cannibalisation)
          - "Blog Catégorie" → subject (catégorie editoriale, ex: "Postures de yoga")
          - "NDD"            → blog_id (domaine → id interne)
          - "Permalink"      → url
          - "Statut"         → status (type Notion natif "status")
          - "Mois"           → date (select, ex: "Mars 2026")
          - "Requête YTG"    → ytg_keyword
        """
        props = page.get("properties", {})

        # "NDD" contient le domaine (ex: "enseigna.fr") → convertir en blog_id
        ndd = self._extract_select(props, ["NDD"])
        blog_id = _DOMAIN_TO_BLOG_ID.get(ndd, ndd)

        # "Mois" est un select (pas un champ date) → ex: "Mars 2026"
        mois = self._extract_select(props, ["Mois"])

        return NotionCommande(
            notion_page_id=page.get("id", ""),
            title=self._extract_text(props, ["Sujet"]),         # titre réel de l'article
            url=self._extract_text(props, ["Permalink"]),
            blog_id=blog_id,
            status=self._extract_status(props, "Statut"),
            date=mois,
            subject=self._extract_title(props),                 # "Blog Catégorie" = catégorie
            ytg_keyword=self._extract_text(props, ["Requête YTG"]),
        )

    # ------------------------------------------------------------------
    # Sujets (topics à traiter)
    # ------------------------------------------------------------------

    def get_sujets(
        self,
        database_id: str,
        blog_id: Optional[str] = None,
    ) -> list[NotionSujet]:
        """
        Récupère les sujets à traiter depuis une base Notion.

        Args:
            database_id: ID de la base "Sujets" Notion
            blog_id: Filtre sur le blog (optionnel)

        Returns:
            Liste de NotionSujet.
        """
        filter_dict = None
        if blog_id:
            filter_dict = {"property": "Blog", "select": {"equals": blog_id}}

        pages = self.query_database(database_id, filter_dict=filter_dict)
        return [self._parse_sujet(p) for p in pages]

    def _parse_sujet(self, page: dict) -> NotionSujet:
        """Parse une page Notion en NotionSujet."""
        props = page.get("properties", {})
        return NotionSujet(
            notion_page_id=page.get("id", ""),
            title=self._extract_title(props),
            blog_id=self._extract_select(props, ["Blog", "Site", "blog"]),
            category=self._extract_select(props, ["Catégorie", "Category", "Thème"]),
            priority=self._extract_select(props, ["Priorité", "Priority"]),
            status=self._extract_select(props, ["Statut", "Status"]),
        )

    def create_sujet(
        self,
        database_id: str,
        title: str,
        blog_id: str = "",
        category: str = "",
        priority: str = "medium",
    ) -> Optional[dict]:
        """
        Crée un nouveau sujet dans la base Notion.

        Args:
            database_id: ID de la base "Sujets"
            title: Titre du sujet
            blog_id: Identifiant du blog
            category: Catégorie thématique
            priority: Priorité ("high", "medium", "low")

        Returns:
            Page Notion créée, ou None si erreur.
        """
        properties = {
            "Nom": {"title": [{"text": {"content": title}}]},
        }
        if blog_id:
            properties["Blog"] = {"select": {"name": blog_id}}
        if category:
            properties["Catégorie"] = {"select": {"name": category}}
        if priority:
            properties["Priorité"] = {"select": {"name": priority}}

        return self.create_page(database_id, properties)

    # ID du data source principal de la base multi-source "Publications"
    REFRESH_TRACKER_DATA_SOURCE_ID = "36cf1b15-1385-46fd-86d0-f379cf6d2a71"
    # Version API requise pour les bases multi-source
    MULTI_SOURCE_API_VERSION = "2025-09-03"

    def log_refresh(
        self,
        database_id: str,
        title: str,
        url: str,
        strategy: str,
        blog_id: str,
        impressions: int = 0,
        clicks: int = 0,
        indexed: str = "",
    ) -> Optional[dict]:
        """
        Log un refresh réussi dans la base Notion de suivi des publications.

        Utilise l'API version 2025-09-03 car la base a des data sources multiples.

        Args:
            database_id: ID de la base refresh tracker
            title: Titre de l'article (nouveau H1 ou original)
            url: URL de l'article
            strategy: Stratégie appliquée (ex: FULL_REFRESH)
            blog_id: Identifiant du blog (ex: enseigna)
            impressions: Impressions GSC 30j au moment du refresh
            clicks: Clics GSC 30j au moment du refresh
            indexed: Statut d'indexation ("YES" ou "NO")

        Returns:
            Page Notion créée, ou None si erreur/non configuré.
        """
        if not self.is_configured:
            return None

        from datetime import date

        properties = {
            "Sujet": {
                "title": [{"text": {"content": (title or "Sans titre")[:2000]}}]
            },
            "URL": {
                "url": url
            },
            "Date": {
                "date": {"start": date.today().isoformat()}
            },
            "Auteur": {
                "multi_select": [{"name": "Samuel"}]
            },
            "Commentaires": {
                "rich_text": [{"text": {"content": f"{strategy} — {blog_id}"}}]
            },
            "Impressions": {
                "number": impressions
            },
            "Clics": {
                "number": clicks
            },
            "Indexed": {
                "select": {"name": indexed or "NO"}
            },
        }

        payload = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": self.REFRESH_TRACKER_DATA_SOURCE_ID,
            },
            "properties": properties,
        }

        headers = self._headers()
        headers["Notion-Version"] = self.MULTI_SOURCE_API_VERSION

        try:
            response = requests.post(
                f"{self.API_BASE_URL}/pages",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[Notion] Erreur log_refresh: {e}")
            return None

    def mark_sujet_en_cours(self, page_id: str) -> Optional[dict]:
        """Marque un sujet comme 'En cours' dans Notion."""
        return self.update_page(
            page_id,
            {"Statut": {"select": {"name": "En cours"}}},
        )

    # ------------------------------------------------------------------
    # Anti-cannibalisation
    # ------------------------------------------------------------------

    def find_title_match(
        self,
        commandes: list[NotionCommande],
        title: str,
        threshold: float = 0.85,
    ) -> Optional[NotionCommande]:
        """
        Vérifie si un titre correspond à un article déjà commandé/publié.

        Algorithme :
        1. Match exact (insensible à la casse)
        2. Match normalisé (sans accents, sans ponctuation)
        3. Jaccard sur les mots (seuil configurable)

        Args:
            commandes: Liste retournée par get_commandes()
            title: Titre à vérifier
            threshold: Seuil de similarité Jaccard (défaut 0.85)

        Returns:
            NotionCommande matchée ou None.
        """
        if not title or not commandes:
            return None

        title_norm = self._normalize(title)
        title_words = set(title_norm.split())

        for commande in commandes:
            if not commande.title:
                continue

            # 1) Match exact (casse insensible)
            if commande.title.lower() == title.lower():
                return commande

            # 2) Match normalisé
            cand_norm = self._normalize(commande.title)
            if cand_norm == title_norm:
                return commande

            # 3) Similarité Jaccard sur les mots
            if title_words:
                cand_words = set(cand_norm.split())
                intersection = title_words & cand_words
                union = title_words | cand_words
                jaccard = len(intersection) / len(union) if union else 0.0
                if jaccard >= threshold:
                    return commande

        return None

    # ------------------------------------------------------------------
    # Parsers de propriétés Notion
    # ------------------------------------------------------------------

    def _extract_title(self, props: dict) -> str:
        """Extrait le titre d'une page Notion (propriété de type 'title')."""
        # Cherche la propriété title — inclut "Blog Catégorie" (schéma réel)
        for key in ("Blog Catégorie", "Nom", "Name", "Titre", "Title", "titre", "name"):
            prop = props.get(key)
            if prop and prop.get("type") == "title":
                rich_text = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in rich_text)

        # Fallback: première propriété de type title
        for prop in props.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                rich_text = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in rich_text)

        return ""

    def _extract_status(self, props: dict, key: str) -> str:
        """
        Extrait la valeur d'un champ de type 'status' (distinct du type 'select').
        Notion utilise le type "status" pour les propriétés Status natives.
        """
        prop = props.get(key)
        if not prop:
            return ""
        ptype = prop.get("type", "")
        if ptype == "status":
            status_obj = prop.get("status")
            return status_obj.get("name", "") if status_obj else ""
        # Fallback si c'est un select standard
        if ptype == "select":
            sel = prop.get("select")
            return sel.get("name", "") if sel else ""
        return ""

    def _extract_text(self, props: dict, keys: list[str]) -> str:
        """Extrait un champ rich_text ou url depuis plusieurs clés possibles."""
        for key in keys:
            prop = props.get(key)
            if not prop:
                continue
            ptype = prop.get("type", "")
            if ptype == "url":
                return prop.get("url", "") or ""
            if ptype in ("rich_text", "text"):
                rich_text = prop.get("rich_text", [])
                return "".join(t.get("plain_text", "") for t in rich_text)
        return ""

    def _extract_select(self, props: dict, keys: list[str]) -> str:
        """Extrait la valeur d'un champ select ou multi_select."""
        for key in keys:
            prop = props.get(key)
            if not prop:
                continue
            ptype = prop.get("type", "")
            if ptype == "select":
                sel = prop.get("select")
                return sel.get("name", "") if sel else ""
            if ptype == "multi_select":
                items = prop.get("multi_select", [])
                return ", ".join(i.get("name", "") for i in items)
        return ""

    def _extract_date(self, props: dict, keys: list[str]) -> str:
        """Extrait la date de début d'un champ date."""
        for key in keys:
            prop = props.get(key)
            if not prop:
                continue
            if prop.get("type") == "date":
                date_obj = prop.get("date")
                if date_obj:
                    return date_obj.get("start", "") or ""
        return ""

    # ------------------------------------------------------------------
    # Utilitaire
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalise un texte pour la comparaison :
        - minuscules
        - suppression des accents
        - suppression de la ponctuation non-alphanumérique
        """
        # Minuscules
        text = text.lower()
        # Supprimer les accents (NFD → filtrer les combining chars)
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        # Garder uniquement lettres, chiffres, espaces
        text = "".join(c if c.isalnum() or c.isspace() else " " for c in text)
        # Normaliser les espaces multiples
        return " ".join(text.split())
