"""
Quick test script for anti-cannibalization system.

Tests the cannibalization detector on:
"Quel budget prévoir pour apprendre l'anglais en Angleterre en 2026 ?"
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scripts.cocon import CannibalizationDetector, SimilarityEngine
from scripts.scraping import WebScraper
from scripts.audit import HTMLAnalyzer

# Test URL
url = "https://enseigna.fr/avis-superprof/"
blog_id = "enseigna"

print("=" * 80)
print("ANTI-CANNIBALIZATION SYSTEM TEST")
print("=" * 80)
print(f"URL: {url}")
print(f"Blog: {blog_id}\n")

# Step 1: Fetch HTML
print("[1/5] Fetching HTML...")
scraper = WebScraper(rate_limit_rpm=20, timeout=30)
html = scraper.fetch_html(url)

if not html:
    print("[ERROR] Failed to fetch HTML")
    sys.exit(1)

print(f"[OK] Fetched {len(html)} characters")

# Step 2: Analyze HTML to extract H2s and cocon structure
print("\n[2/5] Analyzing HTML...")
analyzer = HTMLAnalyzer(domain="enseigna.fr")
html_result = analyzer.analyze(html, url)

h2_list = html_result.headings.h2_list
cocon_structure = html_result.cocon_structure

print(f"[OK] Found {len(h2_list)} H2 headings:")
for i, h2 in enumerate(h2_list, 1):
    print(f"   {i}. {h2}")

print(f"\n[OK] Cocon structure:")
print(f"   Parent: {cocon_structure.parent_url or 'None'}")
print(f"   Siblings: {len(cocon_structure.sibling_urls)}")
for i, sibling in enumerate(cocon_structure.sibling_urls[:5], 1):
    sibling_title = sibling.get('title', '') if isinstance(sibling, dict) else ''
    sibling_url = sibling.get('url', sibling) if isinstance(sibling, dict) else sibling
    print(f"   {i}. {sibling_title[:60]} ({sibling_url})")

# Step 3: Initialize cannibalization detector
print("\n[3/5] Initializing cannibalization detector...")
detector = CannibalizationDetector(
    sheets_client=None,  # No spreadsheet for this test
    web_scraper=scraper
)
print("[OK] Detector initialized")

# Step 4: Detect cannibalization
print("\n[4/5] Detecting cannibalization...")

# Prepare cocon structure dict
cocon_structure_dict = {
    'parent_url': cocon_structure.parent_url,
    'parent_title': cocon_structure.parent_title,
    'sibling_urls': cocon_structure.sibling_urls,
}

report = detector.detect(
    url=url,
    blog_id=blog_id,
    current_h2_list=h2_list,
    cocon_structure=cocon_structure_dict
)

print(f"[OK] Detection complete")
print(f"   H2s analyzed: {report.h2_analyzed_count}")
print(f"   Matches found: {len(report.matches)}")
print(f"   Blacklisted topics: {len(report.blacklist_h2_topics)}")

# Step 5: Display results
print("\n[5/5] RESULTS")
print("=" * 80)

if report.matches:
    print(f"\n[WARNING] CANNIBALIZATION DETECTED ({len(report.matches)} matches):\n")

    for i, match in enumerate(report.matches, 1):
        print(f"{i}. H2: \"{match.current_h2}\"")
        print(f"   ↔ Sibling: \"{match.sibling_h1}\"")
        print(f"   URL: {match.sibling_url}")
        print(f"   Score: {match.similarity_score:.2f} ({match.match_type})")
        print()

    print("\n[BLACKLIST] BLACKLIST FOR PROMPT:")
    print("-" * 80)
    for topic in report.blacklist_h2_topics:
        print(f"  • {topic}")

    print("\n[OK] These H2 sections should be replaced with:")
    print("   → 1-2 sentence mention + internal link to sibling article")

else:
    print("\n[OK] NO CANNIBALIZATION DETECTED")
    print("   All H2 sections are unique and don't overlap with siblings.")

# Test similarity engine manually
print("\n" + "=" * 80)
print("SIMILARITY ENGINE TEST (Manual)")
print("=" * 80)

engine = SimilarityEngine()

test_pairs = [
    ("Quel budget prévoir pour apprendre l'anglais en Angleterre",
     "Quel budget prévoir pour apprendre l'anglais en Angleterre"),  # Exact
    ("Où aller en Angleterre pour apprendre l'anglais",
     "Les meilleures villes où apprendre l'anglais en Angleterre"),  # Keyword overlap
    ("Combien de temps pour progresser en anglais",
     "Durée optimale séjour linguistique Angleterre"),  # Low similarity
]

for text1, text2 in test_pairs:
    score, match_type = engine.compute_similarity(text1, text2)
    print(f"\nText 1: {text1}")
    print(f"Text 2: {text2}")
    print(f"Score:  {score:.2f} ({match_type})")
    print(f"Status: {'[ALERT] CANNIBALIZING' if score >= 0.75 else '[OK] OK'}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
