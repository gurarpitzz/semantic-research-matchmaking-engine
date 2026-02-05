
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.scraper import FacultyScraper

scraper = FacultyScraper()

# Test 1: ETH Zurich (Anchor-based segments)
eth_url = "https://www.phys.ethz.ch/the-department/people/professors.html"
print(f"\n--- TESTING ETH ZURICH ---")
found_eth = scraper.get_faculty_list(eth_url)
print(f"Total Found: {len(found_eth)}")
if found_eth:
    # Check if we have someone beyond 'A'
    for f in found_eth:
        if f['name'].startswith('Z'):
            print(f"✅ Success: Found a professor starting with Z: {f['name']}")
            break
    print(f"First 5: {[f['name'] for f in found_eth[:5]]}")

# Test 2: University of Toronto CS (Should still work)
uoft_url = "https://web.cs.toronto.edu/people/faculty-directory"
print(f"\n--- TESTING UNIVERSITY OF TORONTO ---")
found_uoft = scraper.get_faculty_list(uoft_url)
print(f"Total Found: {len(found_uoft)}")
