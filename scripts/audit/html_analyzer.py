"""
HTML Analyzer Module

Extraction et analyse du contenu HTML des articles.
"""

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from _shared.core.models import (
    ImageAsset,
    CTABlock,
    LinkAsset,
    HeadingStructure,
    HTMLAnalysisResult,
)
from _shared.core.constants import BLACKLIST_DOMAINS, SUPERPROF_DOMAIN


class HTMLAnalyzer:
    """
    Analyseur de contenu HTML pour l'extraction d'articles.

    Extrait:
    - Structure des titres (H1, H2, H3)
    - Contenu textuel
    - Images avec contexte
    - Liens (internes, externes, Superprof)
    - Métriques de qualité
    """

    def __init__(self, domain: str):
        """
        Initialise l'analyseur pour un domaine spécifique.

        Args:
            domain: Domaine du blog (ex: 'enseigna.fr')
        """
        self.domain = domain

    def analyze(self, html: str, url: str) -> HTMLAnalysisResult:
        """
        Analyse complète du contenu HTML.

        Args:
            html: Contenu HTML brut
            url: URL de la page

        Returns:
            HTMLAnalysisResult avec toutes les données extraites
        """
        # Extraction du titre et meta
        title = self._extract_title(html)
        meta_description = self._extract_meta_description(html)

        # Extraction de la structure des titres
        headings = self._extract_headings(html)

        # Extraction du contenu textuel
        text_content = self._extract_text_content(html)
        word_count = len(text_content.split())
        reading_time = max(1, word_count // 200)  # 200 mots/minute

        # Extraction des images (incluant l'identification de la featured image)
        all_images = self._extract_images(html, url, headings.h2_list)
        featured_image = self._identify_featured_image(all_images, html)
        # Exclure la featured image des images contextuelles
        images = [img for img in all_images if not img.is_featured_image]

        # Extraction des liens
        all_links = self._extract_links(html, url, headings.h2_list)
        internal_links = [l for l in all_links if l.link_type == "internal"]
        external_links = [l for l in all_links if l.link_type == "external"]
        superprof_links = [l for l in all_links if l.link_type == "superprof"]
        superprof_link = superprof_links[0] if superprof_links else None

        # Extraction des blocs CTA stylés
        cta_blocks = self._extract_cta_blocks(html, headings.h2_list)

        # Métriques de qualité
        has_faq = bool(re.search(r'<h[23][^>]*>\s*(FAQ|Questions?\s+fréquentes?|Foire\s+aux\s+questions?)', html, re.I))
        has_table = '<table' in html.lower()
        has_list = bool(re.search(r'<[ou]l[^>]*>', html, re.I))
        paragraph_count = len(re.findall(r'<p[^>]*>', html, re.I))

        return HTMLAnalysisResult(
            url=url,
            title=title,
            meta_description=meta_description,
            headings=headings,
            word_count=word_count,
            reading_time_minutes=reading_time,
            images=images,
            internal_links=internal_links,
            external_links=external_links,
            superprof_link=superprof_link,
            text_content=text_content,
            raw_html=html,
            has_faq_section=has_faq,
            has_table=has_table,
            has_list=has_list,
            paragraph_count=paragraph_count,
            featured_image=featured_image,
            cta_blocks=cta_blocks,
        )

    def _extract_title(self, html: str) -> str:
        """Extrait le titre H1 de la page."""
        match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        if match:
            return self._clean_html_text(match.group(1))

        # Fallback sur la balise title
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
        return self._clean_html_text(match.group(1)) if match else ""

    def _extract_meta_description(self, html: str) -> str:
        """Extrait la meta description."""
        match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        if not match:
            match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', html, re.I)
        return match.group(1) if match else ""

    def _extract_headings(self, html: str) -> HeadingStructure:
        """Extrait la structure des titres."""
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        h1 = self._clean_html_text(h1_match.group(1)) if h1_match else ""

        h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.I | re.S)
        h2_list = [self._clean_html_text(h) for h in h2_matches]

        h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.I | re.S)
        h3_list = [self._clean_html_text(h) for h in h3_matches]

        return HeadingStructure(h1=h1, h2_list=h2_list, h3_list=h3_list)

    def _extract_text_content(self, html: str) -> str:
        """Extrait le contenu textuel sans balises HTML."""
        # Supprimer les scripts et styles
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.I | re.S)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.I | re.S)

        # Supprimer les balises HTML
        text = re.sub(r'<[^>]+>', ' ', text)

        # Nettoyer les espaces
        text = re.sub(r'\s+', ' ', text).strip()

        # Décoder les entités HTML basiques
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')

        return text

    def _extract_images(self, html: str, base_url: str, h2_list: list[str]) -> list[ImageAsset]:
        """Extrait toutes les images avec leur contexte."""
        images = []

        # Pattern pour les balises img
        img_pattern = r'<img[^>]+>'

        for match in re.finditer(img_pattern, html, re.I):
            img_tag = match.group(0)

            # Extraire src
            src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.I)
            if not src_match:
                continue
            src = urljoin(base_url, src_match.group(1))

            # Extraire alt
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag, re.I)
            alt = alt_match.group(1) if alt_match else ""

            # Extraire dimensions
            width_match = re.search(r'width=["\']?(\d+)', img_tag, re.I)
            height_match = re.search(r'height=["\']?(\d+)', img_tag, re.I)

            # Trouver le H2 de contexte
            context_h2 = self._find_context_h2(html, match.start(), h2_list)

            images.append(ImageAsset(
                src=src,
                alt=alt,
                html=img_tag,
                context_h2=context_h2,
                width=int(width_match.group(1)) if width_match else None,
                height=int(height_match.group(1)) if height_match else None,
            ))

        return images

    def _extract_links(self, html: str, base_url: str, h2_list: list[str]) -> list[LinkAsset]:
        """Extrait tous les liens avec classification."""
        links = []

        # Pattern pour les balises a
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'

        for match in re.finditer(link_pattern, html, re.I | re.S):
            href = match.group(1)
            anchor = self._clean_html_text(match.group(2))
            full_tag = match.group(0)

            # Ignorer les ancres internes et javascript
            if href.startswith('#') or href.startswith('javascript:'):
                continue

            # Résoudre l'URL
            full_href = urljoin(base_url, href)
            parsed = urlparse(full_href)

            # Classifier le lien
            link_type = self._classify_link(parsed.netloc)

            # Vérifier blacklist
            is_blacklisted = any(bl in parsed.netloc for bl in BLACKLIST_DOMAINS)

            # Trouver le H2 de contexte
            context_h2 = self._find_context_h2(html, match.start(), h2_list)

            links.append(LinkAsset(
                href=full_href,
                anchor=anchor,
                html=full_tag,
                link_type=link_type,
                context_h2=context_h2,
                is_blacklisted=is_blacklisted,
            ))

        return links

    def _classify_link(self, netloc: str) -> str:
        """Classifie un lien selon son domaine."""
        netloc = netloc.lower()

        if SUPERPROF_DOMAIN in netloc:
            return "superprof"
        elif self.domain in netloc:
            return "internal"
        else:
            return "external"

    def _find_context_h2(self, html: str, position: int, h2_list: list[str]) -> Optional[str]:
        """Trouve le H2 précédant une position donnée dans le HTML."""
        # Chercher le dernier H2 avant cette position
        html_before = html[:position]
        h2_matches = list(re.finditer(r'<h2[^>]*>(.*?)</h2>', html_before, re.I | re.S))

        if h2_matches:
            last_h2 = self._clean_html_text(h2_matches[-1].group(1))
            return last_h2 if last_h2 in h2_list else None

        return None

    def _clean_html_text(self, text: str) -> str:
        """Nettoie le texte HTML (supprime balises, espaces multiples)."""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _identify_featured_image(self, images: list[ImageAsset], html: str) -> Optional[ImageAsset]:
        """
        Identifie l'image à la Une parmi les images extraites.

        L'image à la Une est généralement :
        - La première image après le H1
        - Ou la première image de grande taille (width >= 800)

        Args:
            images: Liste des images extraites
            html: HTML brut pour analyse de position

        Returns:
            L'image identifiée comme featured, ou None
        """
        if not images:
            return None

        # Trouver la position du H1
        h1_match = re.search(r'<h1[^>]*>', html, re.I)
        h1_position = h1_match.end() if h1_match else 0

        # La première image est probablement la featured image si :
        # 1. Elle est proche du H1 (dans les 500 premiers caractères après H1)
        # 2. Ou elle a une grande taille (width >= 800)
        first_img = images[0]

        # Trouver la position de la première image
        first_img_match = re.search(re.escape(first_img.html[:50]), html)
        if first_img_match:
            img_position = first_img_match.start()

            # Si l'image est dans les 1000 caractères après le H1
            if img_position <= h1_position + 1000:
                first_img.is_featured_image = True
                return first_img

        # Fallback : si la première image est grande (>= 800px de large)
        if first_img.width and first_img.width >= 800:
            first_img.is_featured_image = True
            return first_img

        return None

    def _extract_cta_blocks(self, html: str, h2_list: list[str]) -> list[CTABlock]:
        """
        Extrait les blocs CTA stylés de l'article.

        Détecte :
        - Boutons Superprof (style avec background-color)
        - Blocs définition/info (div avec border-left)

        Args:
            html: HTML brut
            h2_list: Liste des H2 pour contexte

        Returns:
            Liste des CTABlock extraits
        """
        cta_blocks = []

        # Pattern 1 : CTA bouton Superprof (paragraphe centré avec lien stylé)
        superprof_cta_pattern = r'(<p[^>]*style="[^"]*text-align:\s*center[^"]*"[^>]*>.*?<a[^>]*style="[^"]*background-color[^"]*"[^>]*>.*?</a>.*?</p>)'
        for match in re.finditer(superprof_cta_pattern, html, re.I | re.S):
            context_h2 = self._find_context_h2(html, match.start(), h2_list)
            cta_blocks.append(CTABlock(
                html=match.group(1),
                cta_type="superprof_button",
                context_h2=context_h2,
                required=True  # Le CTA Superprof est obligatoire
            ))

        # Pattern 2 : Bloc définition/info (div avec border-left stylé)
        definition_pattern = r'(<div[^>]*style="[^"]*border-left[^"]*"[^>]*>.*?</div>)'
        for match in re.finditer(definition_pattern, html, re.I | re.S):
            context_h2 = self._find_context_h2(html, match.start(), h2_list)
            cta_blocks.append(CTABlock(
                html=match.group(1),
                cta_type="definition_box",
                context_h2=context_h2,
                required=False  # Les blocs définition sont optionnels
            ))

        # Pattern 3 : Bloc info avec background stylé
        info_pattern = r'(<div[^>]*style="[^"]*background-color:\s*#f[0-9a-f]{5}[^"]*"[^>]*>.*?</div>)'
        for match in re.finditer(info_pattern, html, re.I | re.S):
            # Éviter les doublons avec definition_box
            if any(match.group(1) in cta.html for cta in cta_blocks):
                continue
            context_h2 = self._find_context_h2(html, match.start(), h2_list)
            cta_blocks.append(CTABlock(
                html=match.group(1),
                cta_type="info_box",
                context_h2=context_h2,
                required=False
            ))

        return cta_blocks

    def extract_assets_dict(self, result: HTMLAnalysisResult) -> dict:
        """
        Extrait les assets dans un dictionnaire pour préservation.

        Args:
            result: Résultat de l'analyse HTML

        Returns:
            Dictionnaire des assets à préserver
        """
        return {
            # Image à la Une (séparée, gérée par WordPress)
            "featured_image": {
                "html": result.featured_image.html,
                "src": result.featured_image.src,
                "alt": result.featured_image.alt,
            } if result.featured_image else None,

            # Images contextuelles (à inclure dans le corps)
            "images": [
                {
                    "html": img.html,
                    "src": img.src,
                    "alt": img.alt,
                    "context_h2": img.context_h2,
                }
                for img in result.images  # Exclut déjà la featured_image
            ],

            # Liens internes
            "internal_links": [
                {
                    "html": link.html,
                    "href": link.href,
                    "anchor": link.anchor,
                    "context_h2": link.context_h2,
                }
                for link in result.internal_links
            ],

            # Liens externes
            "external_links": [
                {
                    "html": link.html,
                    "href": link.href,
                    "anchor": link.anchor,
                    "context_h2": link.context_h2,
                }
                for link in result.external_links
                if not link.is_blacklisted
            ],

            # Lien Superprof
            "superprof_link": {
                "html": result.superprof_link.html,
                "href": result.superprof_link.href,
                "anchor": result.superprof_link.anchor,
            } if result.superprof_link else None,

            # Blocs CTA stylés
            "cta_blocks": [
                {
                    "html": cta.html,
                    "type": cta.cta_type,
                    "context_h2": cta.context_h2,
                    "required": cta.required,
                }
                for cta in result.cta_blocks
            ],

            # Comptages (sans featured_image)
            "counts": {
                "images": len(result.images),  # Images contextuelles uniquement
                "internal_links": len(result.internal_links),
                "external_links": len(result.external_links),
                "superprof_links": 1 if result.superprof_link else 0,
                "cta_blocks": len(result.cta_blocks),
            }
        }
