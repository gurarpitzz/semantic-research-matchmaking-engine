
import sys
import os
sys.path.append(os.getcwd())
from backend.core.scraper import FacultyScraper

def test_oxford_final():
    scraper = FacultyScraper()
    url = "https://www.physics.ox.ac.uk/our-people"
    print(f"Final Verification: Oxford Physics (Drupal AJAX + CSRF + Session + Indent Fix)")
    
    # Run scraper
    faculty = scraper.get_faculty_list(url)
    
    print(f"Total Faculty Found: {len(faculty)}")
    
    if len(faculty) >= 400:
        print("✅ SUCCESS: The Oxford 'Final Boss' has been defeated.")
        print("Samples:")
        for f in faculty[:10]:
            print(f"  - {f['name']} ({f['email']})")
    elif len(faculty) > 30:
        print(f"⚠️ PARTIAL: Found {len(faculty)}. Better than 0, but check why it didnt hit full depth.")
    else:
        print("❌ FAILURE: Zero or low faculty found. Something is still blocking the harvest.")

if __name__ == "__main__":
    test_oxford_final()
