"""
Injection Planner Module

Determines WHERE to inject internal links based on relationship type and HTML structure.
"""

import re
import logging
from typing import Optional

from bs4 import BeautifulSoup, Tag

from _shared.core.models.linking_models import LinkMapping, InjectionPoint
from scripts.linking.similarity_engine import SimilarityEngine

logger = logging.getLogger(__name__)


class InjectionPlanner:
    """
    Plans optimal injection points for internal links.

    Rules (from CLAUDE.md):
    - Enfant -> Parent: Introduction (1st or 2nd paragraph, before first H2)
    - Parent -> Enfant: After the matching H2 section
    - Soeur: Body content with 150+ word spacing between links
    - Never inject into callout <div> blocks
    - Never inject into paragraphs < 20 words
    """

    MIN_WORDS_BETWEEN_LINKS = 150
    MIN_PARAGRAPH_WORDS = 20

    def __init__(self, domain: str):
        self.domain = domain
        self.similarity_engine = SimilarityEngine()

    def plan_injection(
        self,
        soup: BeautifulSoup,
        mapping: LinkMapping,
    ) -> Optional[InjectionPoint]:
        """
        Determine the optimal injection point for a link.

        Args:
            soup: Parsed HTML (BeautifulSoup)
            mapping: LinkMapping with relation type and keyword

        Returns:
            InjectionPoint or None if no valid position found
        """
        if mapping.type_relation == "Enfant":
            return self._plan_enfant_to_parent(soup)
        elif mapping.type_relation == "Parent":
            return self._plan_parent_to_enfant(soup, mapping)
        elif mapping.type_relation == "Soeur":
            return self._plan_soeur(soup)
        else:
            logger.warning(f"[InjectionPlanner] Unknown relation type: {mapping.type_relation}")
            return None

    def _plan_enfant_to_parent(self, soup: BeautifulSoup) -> Optional[InjectionPoint]:
        """
        CHILD -> PARENT: Inject in the introduction (before first H2).

        Strategy:
        1. Find all <p> tags before the first <h2>
        2. Select one that doesn't already have an internal link
        3. Prefer the 1st or 2nd paragraph
        """
        intro_paragraphs = self._get_intro_paragraphs(soup)

        if not intro_paragraphs:
            logger.warning("[InjectionPlanner] No intro paragraphs found for Enfant->Parent")
            return None

        # Find a paragraph without an existing internal link
        all_p_tags = self._get_eligible_paragraphs(soup)
        for idx, (p_tag, global_idx) in enumerate(intro_paragraphs):
            if not self._paragraph_has_internal_link(p_tag):
                logger.info(f"[InjectionPlanner] Enfant->Parent: paragraph {global_idx} (intro)")
                return InjectionPoint(
                    paragraph_index=global_idx,
                    context_h2=None,
                    insertion_type="intro",
                )

        # Fallback: use last intro paragraph even if it has a link
        p_tag, global_idx = intro_paragraphs[-1]
        logger.info(f"[InjectionPlanner] Enfant->Parent: fallback to paragraph {global_idx}")
        return InjectionPoint(
            paragraph_index=global_idx,
            context_h2=None,
            insertion_type="intro",
        )

    def _plan_parent_to_enfant(
        self,
        soup: BeautifulSoup,
        mapping: LinkMapping,
    ) -> Optional[InjectionPoint]:
        """
        PARENT -> CHILD: Inject after the matching H2 section.

        Strategy:
        1. Find the H2 that best matches the target keyword/H1
        2. Select the first <p> after that H2
        """
        h2_tags = soup.find_all("h2")
        if not h2_tags:
            logger.warning("[InjectionPlanner] No H2 tags found for Parent->Enfant")
            return self._plan_soeur(soup)  # Fallback to sibling strategy

        # Find best matching H2 using SimilarityEngine
        target_text = mapping.h1_cible or mapping.mot_cle_principal
        best_h2 = None
        best_score = 0.0

        for h2 in h2_tags:
            h2_text = h2.get_text(strip=True)
            score, _ = self.similarity_engine.compute_similarity(h2_text, target_text)
            if score > best_score:
                best_score = score
                best_h2 = h2

        if best_score < 0.3:
            # No good match - use the first H2 as fallback
            logger.warning(
                f"[InjectionPlanner] No H2 matches '{target_text[:40]}' (best score: {best_score:.2f}), "
                f"using first H2"
            )
            best_h2 = h2_tags[0]

        h2_text = best_h2.get_text(strip=True)
        logger.info(
            f"[InjectionPlanner] Parent->Enfant: matched H2 '{h2_text[:50]}' "
            f"(score: {best_score:.2f})"
        )

        # Find the first eligible <p> after this H2
        all_p_tags = list(soup.find_all("p"))
        h2_index = self._find_element_index_in_tree(soup, best_h2)

        for i, p_tag in enumerate(all_p_tags):
            p_index = self._find_element_index_in_tree(soup, p_tag)
            if p_index > h2_index and self._is_eligible_paragraph(p_tag):
                return InjectionPoint(
                    paragraph_index=i,
                    context_h2=h2_text,
                    insertion_type="after_h2",
                )

        logger.warning("[InjectionPlanner] No eligible paragraph after matching H2")
        return None

    def _plan_soeur(self, soup: BeautifulSoup) -> Optional[InjectionPoint]:
        """
        SIBLING -> SIBLING: Inject in body content with word spacing enforcement.

        Strategy:
        1. Find all existing <a> tag positions (word offsets)
        2. Find paragraphs with the largest gaps (150+ words) from any link
        3. Prefer middle-to-end of article, avoid intro and conclusion
        """
        all_p_tags = list(soup.find_all("p"))
        if len(all_p_tags) < 3:
            logger.warning("[InjectionPlanner] Too few paragraphs for Soeur injection")
            return None

        # Build list of eligible paragraphs with their word positions
        eligible = []
        cumulative_words = 0

        for i, p_tag in enumerate(all_p_tags):
            text = p_tag.get_text(strip=True)
            word_count = len(text.split())

            if self._is_eligible_paragraph(p_tag) and word_count >= self.MIN_PARAGRAPH_WORDS:
                # Calculate minimum distance to any existing link
                min_distance = self._min_word_distance_to_link(
                    soup, all_p_tags, i, cumulative_words
                )
                eligible.append((i, min_distance, cumulative_words))

            cumulative_words += word_count

        if not eligible:
            logger.warning("[InjectionPlanner] No eligible paragraphs for Soeur injection")
            return None

        # Filter: only paragraphs with 150+ word distance from nearest link
        spaced = [(idx, dist, pos) for idx, dist, pos in eligible
                   if dist >= self.MIN_WORDS_BETWEEN_LINKS]

        if not spaced:
            # Relaxed: pick the paragraph with the maximum distance
            spaced = eligible

        # Prefer middle-to-end of article (skip first 20% and last paragraph)
        total = len(all_p_tags)
        start_threshold = max(2, total // 5)
        end_threshold = total - 1

        middle_candidates = [
            (idx, dist) for idx, dist, pos in spaced
            if start_threshold <= idx < end_threshold
        ]

        if middle_candidates:
            # Pick the one with the largest gap
            best = max(middle_candidates, key=lambda x: x[1])
            chosen_idx = best[0]
        else:
            # Fallback: pick the largest gap overall
            best = max(spaced, key=lambda x: x[1])
            chosen_idx = best[0]

        # Find context H2
        context_h2 = self._find_context_h2_for_paragraph(soup, all_p_tags[chosen_idx])

        logger.info(
            f"[InjectionPlanner] Soeur: paragraph {chosen_idx} "
            f"(H2: {context_h2[:40] if context_h2 else 'None'})"
        )

        return InjectionPoint(
            paragraph_index=chosen_idx,
            context_h2=context_h2,
            insertion_type="body",
        )

    def _get_intro_paragraphs(self, soup: BeautifulSoup) -> list[tuple[Tag, int]]:
        """
        Get <p> tags in the introduction (before the first <h2>).

        Returns:
            List of (p_tag, global_index) tuples
        """
        all_p_tags = list(soup.find_all("p"))
        first_h2 = soup.find("h2")

        if not first_h2:
            return [(p, i) for i, p in enumerate(all_p_tags[:3])]

        h2_pos = self._find_element_index_in_tree(soup, first_h2)
        intro = []

        for i, p_tag in enumerate(all_p_tags):
            p_pos = self._find_element_index_in_tree(soup, p_tag)
            if p_pos < h2_pos and self._is_eligible_paragraph(p_tag):
                intro.append((p_tag, i))

        return intro

    def _get_eligible_paragraphs(self, soup: BeautifulSoup) -> list[tuple[Tag, int]]:
        """Get all eligible paragraphs (not inside callouts, not too short)."""
        result = []
        for i, p_tag in enumerate(soup.find_all("p")):
            if self._is_eligible_paragraph(p_tag):
                result.append((p_tag, i))
        return result

    def _is_eligible_paragraph(self, p_tag: Tag) -> bool:
        """
        Check if a paragraph is eligible for link injection.

        Excludes:
        - Paragraphs inside styled callout divs (background-color, border-left)
        - Paragraphs with fewer than MIN_PARAGRAPH_WORDS words
        - Paragraphs inside CTA blocks (green background)
        """
        # Check word count
        text = p_tag.get_text(strip=True)
        if len(text.split()) < self.MIN_PARAGRAPH_WORDS:
            return False

        # Check if inside a callout/CTA div
        parent = p_tag.parent
        while parent and parent.name:
            if parent.name == "div":
                style = parent.get("style", "")
                if "background-color" in style or "border-left" in style:
                    return False
            parent = parent.parent

        return True

    def _paragraph_has_internal_link(self, p_tag: Tag) -> bool:
        """Check if a paragraph already contains an internal link."""
        links = p_tag.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            if self.domain in href:
                return True
        return False

    def _find_element_index_in_tree(self, soup: BeautifulSoup, element: Tag) -> int:
        """
        Find the character-level position of an element in the HTML string.

        Uses sourceline and sourcepos if available, otherwise uses string search.
        """
        # Use the element's string representation to find its position
        all_elements = list(soup.descendants)
        try:
            return all_elements.index(element)
        except ValueError:
            return 0

    def _min_word_distance_to_link(
        self,
        soup: BeautifulSoup,
        all_p_tags: list[Tag],
        target_p_index: int,
        target_cumulative_words: int,
    ) -> int:
        """
        Calculate the minimum word distance from a paragraph to any existing <a> tag.

        Args:
            soup: Parsed HTML
            all_p_tags: List of all <p> tags
            target_p_index: Index of the target paragraph
            target_cumulative_words: Cumulative word count up to this paragraph

        Returns:
            Minimum word distance (large number if no links found)
        """
        min_dist = 999999
        cumulative = 0

        for i, p_tag in enumerate(all_p_tags):
            text = p_tag.get_text(strip=True)
            word_count = len(text.split())

            # Check if this paragraph has any links
            if p_tag.find("a", href=True):
                distance = abs(target_cumulative_words - cumulative)
                if distance < min_dist:
                    min_dist = distance

            cumulative += word_count

        return min_dist

    def _find_context_h2_for_paragraph(self, soup: BeautifulSoup, p_tag: Tag) -> Optional[str]:
        """Find the H2 heading that precedes a given paragraph."""
        # Walk backwards through previous siblings and parents
        current = p_tag
        while current:
            prev = current.find_previous_sibling("h2")
            if prev:
                return prev.get_text(strip=True)
            current = current.parent
            if current and current.name == "[document]":
                break

        # Broader search: find all H2s and pick the last one before this <p>
        all_elements = list(soup.descendants)
        try:
            p_pos = all_elements.index(p_tag)
        except ValueError:
            return None

        last_h2 = None
        for elem in all_elements[:p_pos]:
            if hasattr(elem, "name") and elem.name == "h2":
                last_h2 = elem.get_text(strip=True)

        return last_h2
