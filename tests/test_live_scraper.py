
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.scraper import FacultyScraper

scraper = FacultyScraper()

url = "https://www.phys.ethz.ch/the-department/people/professors.html"
print(f"Testing URL: {url}")
found = scraper.get_faculty_list(url)
print(f"Found {len(found)} faculty.")
for f in found[:30]:
    print(f" - {f['name']} ({f['url']})")

homepage = "https://www.phys.ethz.ch/"
print(f"\nTesting Homepage: {homepage}")
found_h = scraper.get_faculty_list(homepage)
print(f"Found {len(found_h)} faculty.")
for f in found_h[:10]:
    print(f" - {f['name']}")
