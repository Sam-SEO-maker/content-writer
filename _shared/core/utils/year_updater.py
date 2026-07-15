"""
Year Updater Module

Gère la détection et le remplacement automatique des années obsolètes
dans les contenus textes et HTML, avec exclusion intelligente des contextes
qui ne doivent pas être modifiés (URLs, citations, références).
"""

import re
from datetime import datetime
from typing import Optional, Tuple, List, Dict


class YearUpdater:
    """
    Gestionnaire de mise à jour automatique des années obsolètes.

    Détecte et remplace les années 2024/2025 par l'année cible (2026),
    tout en préservant les contextes qui ne doivent pas être modifiés.
    """

    # Patterns d'exclusion - contextes à préserver intacts
    EXCLUSION_PATTERNS = {
        'url': r'https?://[^\s]*20(24|25)',  # URLs HTTP(S)
        'citation': r'\([^)]*20(24|25)[^)]*\)',  # Citations: (Author, 2025)
        'reference': r'\[[^\]]*20(24|25)[^\]]*\]',  # Références: [1] Year 2025
        'link_href': r'<a[^>]*href=["\'][^"\']*20(24|25)[^"\']*["\'][^>]*>',  # Attributs href
        'historical': r'\d{4}\s*(→|vs|par rapport à)\s*\d{4}',  # Comparaisons: 2024 vs 2025
    }

    # Fenêtre d'années passées considérées obsolètes (à remplacer).
    _OBSOLETE_WINDOW = 3

    def __init__(self, target_year: Optional[int] = None):
        """
        Initialise le YearUpdater.

        Args:
            target_year: Année cible pour remplacement (None = année courante)
        """
        self.target_year = target_year or datetime.now().year
        # Années obsolètes = les N années précédant la cible (dynamique, ne se
        # périme pas). Avant : liste statique [2024, 2025] qui aurait manqué les
        # années > 2025 à mesure que le temps passe.
        self.YEARS_TO_REPLACE = [
            self.target_year - i for i in range(1, self._OBSOLETE_WINDOW + 1)
        ]
        self.changes: List[Dict] = []

    def detect_obsolete_years(self, text: str) -> List[Dict]:
        """
        Détecte toutes les années obsolètes dans un texte.

        Args:
            text: Texte à analyser

        Returns:
            Liste de dictionnaires avec détails des années détectées:
            [{
                'match': '2025',
                'position': 45,
                'context': '...contexte avant et après...',
                'should_exclude': False
            }]
        """
        matches = []

        for year_to_find in self.YEARS_TO_REPLACE:
            pattern = rf'\b{year_to_find}\b'

            for match in re.finditer(pattern, text):
                pos = match.start()
                # Extraire le contexte (50 chars avant/après)
                context_start = max(0, pos - 50)
                context_end = min(len(text), pos + len(str(year_to_find)) + 50)
                context = text[context_start:context_end]

                matches.append({
                    'match': str(year_to_find),
                    'position': pos,
                    'context': context,
                    'should_exclude': self._should_exclude_at_position(text, pos)
                })

        return matches

    def replace_years(
        self,
        text: str,
        exclude_patterns: Optional[List[str]] = None
    ) -> Tuple[str, List[Dict]]:
        """
        Remplace les années obsolètes par l'année cible.

        Args:
            text: Texte à traiter
            exclude_patterns: Noms des patterns d'exclusion à utiliser
                            (ex: ['url', 'citation'])

        Returns:
            Tuple (texte_modifié, liste_changements)
        """
        self.changes = []
        modified_text = text
        offset = 0  # Décalage pour gérer les changements de longueur

        # Détecter toutes les années
        matches = self.detect_obsolete_years(text)

        # Trier par position (ascendante) pour éviter les chevauchements
        matches_to_replace = []
        for match in sorted(matches, key=lambda m: m['position']):
            # Vérifier les exclusions demandées
            should_exclude = False
            if exclude_patterns:
                for pattern_name in exclude_patterns:
                    if self._matches_exclusion_pattern(match['context'], pattern_name):
                        should_exclude = True
                        break
            else:
                should_exclude = match['should_exclude']

            if not should_exclude:
                matches_to_replace.append(match)

        # Remplacer en ordre inverse pour ne pas affecter les positions
        for match in reversed(matches_to_replace):
            old_year = match['match']
            new_year = str(self.target_year)

            # Calculer les positions ajustées
            adjusted_pos = match['position'] + offset
            start = adjusted_pos
            end = adjusted_pos + len(old_year)

            # Effectuer le remplacement
            modified_text = modified_text[:start] + new_year + modified_text[end:]

            # Enregistrer le changement
            self.changes.insert(0, {
                'original': old_year,
                'replacement': new_year,
                'context': match['context'],
                'position': match['position']
            })

            # Mettre à jour l'offset
            offset += len(new_year) - len(old_year)

        return modified_text, self.changes

    def should_exclude(self, context: str) -> bool:
        """
        Détermine si un contexte doit être exclu de la modification.

        Args:
            context: Contexte texte à vérifier

        Returns:
            True si le contexte doit être préservé
        """
        for pattern_name, pattern in self.EXCLUSION_PATTERNS.items():
            if re.search(pattern, context):
                return True
        return False

    def _should_exclude_at_position(self, text: str, position: int) -> bool:
        """
        Vérifie si une position donnée doit être exclue.

        Args:
            text: Texte complet
            position: Position dans le texte

        Returns:
            True si la position doit être exclue
        """
        # Extraire le contexte autour de la position
        context_start = max(0, position - 200)
        context_end = min(len(text), position + 200)
        context = text[context_start:context_end]

        return self.should_exclude(context)

    def _matches_exclusion_pattern(self, context: str, pattern_name: str) -> bool:
        """
        Vérifie si un contexte correspond à un pattern d'exclusion spécifique.

        Args:
            context: Contexte à vérifier
            pattern_name: Nom du pattern ('url', 'citation', etc.)

        Returns:
            True si le contexte correspond au pattern
        """
        if pattern_name not in self.EXCLUSION_PATTERNS:
            return False

        pattern = self.EXCLUSION_PATTERNS[pattern_name]
        return bool(re.search(pattern, context))

    def get_changes_summary(self) -> str:
        """
        Retourne un résumé des changements effectués.

        Returns:
            Texte descriptif des modifications
        """
        if not self.changes:
            return "Aucune année mise à jour"

        count = len(self.changes)
        return f"{count} année(s) mise(s) à jour (→{self.target_year})"

    def get_statistics(self) -> Dict:
        """
        Retourne des statistiques sur les changements.

        Returns:
            Dictionnaire avec statistiques:
            {
                'total_changes': 5,
                'years_replaced': {2025: 4, 2024: 1},
                'summary': "5 année(s) mise(s) à jour (→2026)"
            }
        """
        years_replaced = {}
        for change in self.changes:
            year = change['original']
            years_replaced[year] = years_replaced.get(year, 0) + 1

        return {
            'total_changes': len(self.changes),
            'years_replaced': years_replaced,
            'summary': self.get_changes_summary()
        }


# Utilisation simple
if __name__ == "__main__":
    # Exemple d'utilisation
    updater = YearUpdater(target_year=2026)

    sample_text = """
    <h1>Guide complet 2025 pour apprendre l'anglais</h1>
    <p>En 2025, les méthodes d'apprentissage ont évolué.</p>
    <p>Selon Smith (2025), 70% des étudiants réussissent.</p>
    <p><a href="https://example.com/study-2025">Voir l'étude</a></p>
    """

    modified, changes = updater.replace_years(
        sample_text,
        exclude_patterns=['citation', 'url']
    )

    print("Texte modifié:")
    print(modified)
    print("\nChangements:")
    for change in changes:
        print(f"  {change['original']} → {change['replacement']}")
    print(f"\nRésumé: {updater.get_changes_summary()}")
