
import requests
from bs4 import BeautifulSoup
import re
import sys
import os

# Mock the scraper logic
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

BLACKLIST = {
    "Calendar", "Events", "News", "Contact", "Give", "Social", "Mission", 
    "Values", "Diversity", "Search", "Login", "Resources", "Safety", "COVID",
    "History", "Map", "Jobs", "Career", "Colloquia", "Seminars", "About", "Home"
}

def get_faculty(url):
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    faculty = []
    seen_urls = set()
    
    for container in soup.find_all(['div', 'tr', 'li', 'p']):
        link = container.find('a', href=True)
        if not link: continue
        text = link.get_text().strip()
        href = link['href']
        if not text or len(text) < 3 or len(text) > 50: continue
        if any(word in text for word in BLACKLIST): continue
        is_name_like = re.search(r'^[A-Z\u00C0-\u017F][A-Za-z\u00C0-\u017F\-\.\s\',]+$', text)
        is_prof = any(kw in text for kw in ["Professor", "Prof.", "Dr."])
        if (is_name_like or is_prof) and 2 < len(text) < 50 and ' ' in text:
            if href not in seen_urls:
                seen_urls.add(href)
                faculty.append(text)
    return faculty

url = "https://www.phys.ethz.ch/the-department/people/professors.html"
found = get_faculty(url)
print(f"Found {len(found)} faculty at directory URL.")
for f in found[:20]:
    print(f" - {f}")

homepage = "https://www.phys.ethz.ch/"
found_home = get_faculty(homepage)
print(f"\nFound {len(found_home)} faculty at homepage.")
for f in found_home[:20]:
    print(f" - {f}")
