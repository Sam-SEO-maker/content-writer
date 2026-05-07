"""
Test STEP 6: Post-Refresh Cannibalization Validation

Simulates the post-refresh validation by:
1. Loading a refreshed HTML file
2. Extracting H2s
3. Re-running cannibalization detection
4. Checking if any new cannibalization was introduced
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scripts.cocon import CannibalizationDetector
from scripts.scraping import WebScraper
from scripts.audit import HTMLAnalyzer
from bs4 import BeautifulSoup

print("=" * 80)
print("STEP 6: POST-REFRESH CANNIBALIZATION VALIDATION")
print("=" * 80)

# Path to refreshed HTML file
refreshed_file = Path("_shared/outputs/enseigna.fr/html/https_enseigna_fr_avis-superprof_refreshed.html")

if not refreshed_file.exists():
    print(f"[ERROR] File not found: {refreshed_file}")
    sys.exit(1)

# Load refreshed HTML
with open(refreshed_file, 'r', encoding='utf-8') as f:
    refreshed_html = f.read()

print(f"[OK] Loaded refreshed HTML ({len(refreshed_html)} characters)")

# Extract H2s from refreshed HTML
soup = BeautifulSoup(refreshed_html, 'html.parser')
new_h2_list = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]

print(f"\n[OK] Extracted {len(new_h2_list)} H2 headings:")
for i, h2 in enumerate(new_h2_list, 1):
    print(f"   {i}. {h2}")

# Re-analyze HTML to extract cocon structure
print("\n[STEP 6.1] Re-analyzing HTML for cocon structure...")
url = "https://enseigna.fr/avis-superprof/"
blog_id = "enseigna"

analyzer = HTMLAnalyzer(domain="enseigna.fr")
html_result = analyzer.analyze(refreshed_html, url)

cocon_structure_dict = {
    'parent_url': html_result.cocon_structure.parent_url,
    'parent_title': html_result.cocon_structure.parent_title,
    'sibling_urls': html_result.cocon_structure.sibling_urls,
}

print(f"[OK] Cocon structure extracted:")
print(f"   Parent: {cocon_structure_dict['parent_url'] or 'None'}")
print(f"   Siblings: {len(cocon_structure_dict['sibling_urls'])}")

# Initialize cannibalization detector
print("\n[STEP 6.2] Running cannibalization detection...")
scraper = WebScraper(rate_limit_rpm=20, timeout=30)
detector = CannibalizationDetector(
    sheets_client=None,
    web_scraper=scraper
)

# Run detection
cannibalization_report = detector.detect(
    url=url,
    blog_id=blog_id,
    current_h2_list=new_h2_list,
    cocon_structure=cocon_structure_dict
)

# Display results
print("\n" + "=" * 80)
print("VALIDATION RESULTS")
print("=" * 80)

if cannibalization_report.matches:
    print(f"\n[WARNING] POST-REFRESH CANNIBALIZATION DETECTED ({len(cannibalization_report.matches)} matches):\n")

    for i, match in enumerate(cannibalization_report.matches, 1):
        print(f"{i}. H2: \"{match.current_h2}\"")
        print(f"   <-> Sibling: \"{match.sibling_h1}\"")
        print(f"   URL: {match.sibling_url}")
        print(f"   Score: {match.similarity_score:.3f} ({match.match_type})")
        print()

    print("[ERROR] Validation FAILED: Cannibalization still present after refresh!")
    print("   -> The Ghostwriter did NOT respect the blacklist")
    print("   -> These H2 sections should be shortened to 1-2 sentences + internal link")

else:
    print("\n[OK] POST-REFRESH VALIDATION PASSED")
    print("   No H2 cannibalization detected in refreshed content")
    print("   All H2 sections are unique and don't overlap with siblings")
    print("\n   -> The Ghostwriter successfully respected the anti-cannibalization rules!")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
