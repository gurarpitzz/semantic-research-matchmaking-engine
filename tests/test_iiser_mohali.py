import sys
import os
# Add the project root to sys.path
sys.path.append(os.getcwd())

from backend.core.scraper import scraper

def test_iiser_mohali():
    url = "https://web.iisermohali.ac.in/dept/physics/Faculty.html"
    print(f"🚀 Testing SRME Scraper on: {url}")
    faculty = scraper.get_faculty_list(url)
    print(f"✅ Harvested {len(faculty)} faculty members.")
    
    for f in faculty[:5]:
        print(f" - {f['name']} ({f['email'] or 'No Email'}) -> {f['url']}")
    
    if len(faculty) > 25:
        print("🎉 SUCCESS: IISER Mohali fully discovered!")
    else:
        print(f"❌ FAILURE: Only found {len(faculty)} faculty.")

if __name__ == "__main__":
    test_iiser_mohali()
