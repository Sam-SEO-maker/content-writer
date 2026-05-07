"""
Test script for anti-cannibalization with MOCKED siblings.

This test simulates a realistic cocon scenario where an article has
sibling articles on related topics (cities, budget, duration).
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scripts.cocon import CannibalizationDetector, SimilarityEngine
from scripts.scraping import WebScraper
from _shared.core.models.cocon_models import CoconRegistryData, SiblingArticle

print("=" * 80)
print("ANTI-CANNIBALIZATION TEST WITH MOCKED SIBLINGS")
print("=" * 80)

# Simulated current article
current_url = "https://enseigna.fr/combien-de-temps-apprendre-anglais-angleterre/"
current_h1 = "Combien de temps pour apprendre l'anglais en Angleterre ?"

# Simulated H2s (some cannibalizing, some not)
current_h2_list = [
    "Combien de temps faut-il pour progresser en anglais ?",  # OK - specific to article
    "Les meilleures villes ou aller en Angleterre pour apprendre l'anglais",  # CANNIBALIZING
    "Quel budget prevoir pour un sejour linguistique en Angleterre",  # CANNIBALIZING
    "Les avantages d'un sejour linguistique longue duree",  # OK - specific
    "Comment maximiser ses progres pendant le sejour",  # OK - specific
]

# Simulated sibling articles (realistic cocon)
sibling_articles = [
    SiblingArticle(
        url="https://enseigna.fr/meilleures-villes-apprendre-anglais-angleterre/",
        h1="Les meilleures villes ou apprendre l'anglais en Angleterre",
        main_keyword="villes apprendre anglais angleterre",
        context_h2_from_parent=None
    ),
    SiblingArticle(
        url="https://enseigna.fr/budget-sejour-linguistique-angleterre/",
        h1="Quel budget prevoir pour un sejour linguistique en Angleterre",
        main_keyword="budget sejour linguistique angleterre",
        context_h2_from_parent=None
    ),
    SiblingArticle(
        url="https://enseigna.fr/meilleurs-ecoles-anglais-londres/",
        h1="Les meilleures ecoles d'anglais a Londres",
        main_keyword="ecoles anglais londres",
        context_h2_from_parent=None
    ),
]

# Create mocked cocon structure
cocon_structure = {
    'parent_url': 'https://enseigna.fr/apprendre-anglais-angleterre/',
    'parent_title': 'Guide complet pour apprendre l\'anglais en Angleterre',
    'sibling_urls': [s.url for s in sibling_articles]
}

print(f"\nCurrent Article: {current_h1}")
print(f"URL: {current_url}")
print(f"\nH2 headings to analyze ({len(current_h2_list)}):")
for i, h2 in enumerate(current_h2_list, 1):
    print(f"  {i}. {h2}")

print(f"\nSibling articles ({len(sibling_articles)}):")
for i, sibling in enumerate(sibling_articles, 1):
    print(f"  {i}. {sibling.h1}")
    print(f"     URL: {sibling.url}")

# Initialize detector with mocked data
print("\n" + "=" * 80)
print("DETECTION PROCESS")
print("=" * 80)

scraper = WebScraper(rate_limit_rpm=20, timeout=30)
detector = CannibalizationDetector(
    sheets_client=None,
    web_scraper=scraper
)

# Mock the cocon registry to inject our sibling data
# We'll directly inject the CoconRegistryData
cocon_data = CoconRegistryData(
    current_url=current_url,
    current_h1=current_h1,
    parent_url=cocon_structure['parent_url'],
    parent_h1=cocon_structure['parent_title'],
    siblings=sibling_articles
)

# Manually run detection loop (bypass load_cocon)
print("\nComparing H2s with sibling H1s...")
print("-" * 80)

matches = []
for h2 in current_h2_list:
    print(f"\nH2: \"{h2}\"")
    for sibling in sibling_articles:
        score, match_type = detector.similarity_engine.compute_similarity(h2, sibling.h1)
        print(f"  vs \"{sibling.h1[:50]}...\"")
        print(f"  -> Score: {score:.3f} ({match_type})")

        if score >= detector.CANNIBALIZATION_THRESHOLD:
            print(f"  -> [ALERT] CANNIBALIZATION DETECTED!")
            from _shared.core.models.cocon_models import CannibalizationMatch
            matches.append(CannibalizationMatch(
                current_h2=h2,
                sibling_h1=sibling.h1,
                sibling_url=sibling.url,
                similarity_score=score,
                match_type=match_type
            ))

# Generate blacklist
blacklist = detector.generate_blacklist(matches, cocon_data)

# Display results
print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

if matches:
    print(f"\n[WARNING] CANNIBALIZATION DETECTED ({len(matches)} matches):\n")

    for i, match in enumerate(matches, 1):
        print(f"{i}. H2: \"{match.current_h2}\"")
        print(f"   <-> Sibling: \"{match.sibling_h1}\"")
        print(f"   URL: {match.sibling_url}")
        print(f"   Score: {match.similarity_score:.3f} ({match.match_type})")
        print()

    print("\n[BLACKLIST] TOPICS TO EXCLUDE FROM PROMPT:")
    print("-" * 80)
    for topic in blacklist:
        print(f"  - {topic}")

    print("\n[OK] These H2 sections should be replaced with:")
    print("   -> 1-2 sentence mention + internal link to sibling article")

else:
    print("\n[OK] NO CANNIBALIZATION DETECTED")
    print("   All H2 sections are unique and don't overlap with siblings.")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
