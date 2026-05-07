"""
Similarity Engine Module

Computes text similarity between strings using multiple algorithms.
"""

import re
import unicodedata
from typing import Tuple


class SimilarityEngine:
    """
    Engine for computing semantic similarity between text strings.

    Uses multiple algorithms:
    1. Exact match (after normalization)
    2. Jaccard similarity (keyword overlap)
    3. Levenshtein distance (edit distance)
    """

    # French stopwords to remove during normalization
    STOPWORDS = {
        'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'à', 'au', 'aux',
        'pour', 'par', 'sur', 'dans', 'avec', 'en', 'et', 'ou', 'que', 'qui',
        'quoi', 'dont', 'où', 'comment', 'combien', 'quel', 'quelle', 'quels', 'quelles',
        'ce', 'cet', 'cette', 'ces', 'son', 'sa', 'ses', 'leur', 'leurs',
        'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'notre', 'nos', 'votre', 'vos',
        'est', 'sont', 'être', 'avoir', 'fait', 'faire', 'très', 'plus', 'moins'
    }

    def compute_similarity(self, text1: str, text2: str) -> Tuple[float, str]:
        """
        Compute similarity score between two texts.

        Algorithms (in order of priority):
        1. Exact match (after normalization) → score 1.0, type 'exact'
        2. Keyword overlap (Jaccard) → score 0.6-1.0, type 'keyword'
        3. Levenshtein distance → score 0.5-0.9, type 'semantic'

        Args:
            text1: First text (e.g., H2 heading)
            text2: Second text (e.g., sibling H1)

        Returns:
            Tuple of (similarity_score, match_type)
            - similarity_score: 0.0-1.0 (0 = no match, 1.0 = identical)
            - match_type: 'exact', 'keyword', or 'semantic'
        """
        # Normalize both texts
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)

        # 1. Exact match (after normalization)
        if norm1 == norm2:
            return (1.0, 'exact')

        # Extract keywords
        keywords1 = self.extract_keywords(norm1)
        keywords2 = self.extract_keywords(norm2)

        # 2. Jaccard similarity (keyword overlap)
        jaccard_score = self.jaccard_similarity(keywords1, keywords2)
        if jaccard_score >= 0.6:
            return (jaccard_score, 'keyword')

        # 3. Levenshtein distance (edit distance)
        lev_score = self.levenshtein_similarity(norm1, norm2)
        if lev_score >= 0.5:
            return (lev_score, 'semantic')

        # No significant similarity
        return (max(jaccard_score, lev_score), 'none')

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.

        Normalization steps:
        1. Lowercase
        2. Remove accents (é → e, à → a)
        3. Remove punctuation (: ? !)
        4. Remove stopwords
        5. Trim extra whitespace

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        # Lowercase
        text = text.lower()

        # Remove accents (NFD decomposition + ASCII filter)
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

        # Remove punctuation (keep letters, numbers, spaces)
        text = re.sub(r'[^\w\s]', ' ', text)

        # Remove stopwords
        words = text.split()
        words = [w for w in words if w not in self.STOPWORDS]

        # Trim whitespace
        return ' '.join(words).strip()

    def extract_keywords(self, normalized_text: str) -> set[str]:
        """
        Extract significant keywords from normalized text.

        Filters:
        - Length > 3 characters
        - Not stopwords (already filtered during normalization)

        Args:
            normalized_text: Pre-normalized text

        Returns:
            Set of keywords
        """
        words = normalized_text.split()
        # Filter short words (< 3 chars)
        keywords = {word for word in words if len(word) > 3}
        return keywords

    def jaccard_similarity(self, set1: set[str], set2: set[str]) -> float:
        """
        Compute Jaccard similarity coefficient.

        Formula: |A ∩ B| / |A ∪ B|

        Args:
            set1: First set of keywords
            set2: Second set of keywords

        Returns:
            Jaccard score (0.0-1.0)
        """
        if not set1 or not set2:
            return 0.0

        intersection = set1 & set2
        union = set1 | set2

        if len(union) == 0:
            return 0.0

        return len(intersection) / len(union)

    def levenshtein_similarity(self, text1: str, text2: str) -> float:
        """
        Compute normalized Levenshtein similarity.

        Levenshtein distance = minimum number of single-character edits
        (insertions, deletions, substitutions) to change text1 into text2.

        Normalized score = 1 - (distance / max_length)

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0-1.0)
        """
        if text1 == text2:
            return 1.0

        len1, len2 = len(text1), len(text2)

        if len1 == 0 or len2 == 0:
            return 0.0

        # Create distance matrix
        # dp[i][j] = distance between text1[:i] and text2[:j]
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        # Initialize base cases
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j

        # Fill matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if text1[i - 1] == text2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],      # deletion
                        dp[i][j - 1],      # insertion
                        dp[i - 1][j - 1]   # substitution
                    )

        distance = dp[len1][len2]
        max_len = max(len1, len2)

        # Normalize: 1 - (distance / max_length)
        similarity = 1 - (distance / max_len)

        return max(0.0, similarity)
