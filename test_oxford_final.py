
import sys
import os
sys.path.append(os.getcwd())
from backend.core.scraper import FacultyScraper

def test_oxford_csrf():
    scraper = FacultyScraper()
    url = "https://www.physics.ox.ac.uk/our-people"
    print(f"🚀 Testing Oxford Physics AJAX with CSRF Injection: {url}")
    
    # Run scraper
    faculty = scraper.get_faculty_list(url)
    
    print(f"📊 Total Faculty Found: {len(faculty)}")
    
    if len(faculty) >= 200:
        print("✅ SUCCESS: CSRF token injection worked. Full list retrieved.")
        for f in faculty[:5]:
            print(f"  - {f['name']} ({f['email']})")
    elif len(faculty) == 0:
        print("❌ FAILURE: Zero faculty found. CSRF token likely failed.")
    else:
        print(f"⚠️ PARTIAL: Found {len(faculty)}. Maybe heuristic failed or CAP reached.")

if __name__ == "__main__":
    test_oxford_csrf()
