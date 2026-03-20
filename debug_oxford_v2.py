
import requests
from bs4 import BeautifulSoup
import json
import re

url = "https://www.physics.ox.ac.uk/our-people"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

print("--- Form State Extraction ---")
form = soup.select_one("form.views-exposed-form")
if form:
    for inp in form.find_all("input"):
        print(f"Name: {inp.get('name')}, Value: {inp.get('value')}")
else:
    print("Form NOT found via select_one('form.views-exposed-form')")
    # Try finding any form with 'exposed' in class
    for f in soup.find_all('form'):
        if 'exposed' in str(f.get('class')):
            print(f"Found Alternative Exposed Form: {f.get('class')}")

print("\n--- Drupal Settings Search ---")
settings_script = soup.find('script', {'data-drupal-selector': 'drupal-settings-json'})
if settings_script:
    stxt = settings_script.get_text()
    settings = json.loads(stxt)
    print("ajaxPageState:", settings.get("ajaxPageState", {}).keys())
    print("theme_token:", settings.get("ajaxPageState", {}).get("theme_token"))
else:
    print("Settings script not found")

print("\n--- CSRF Tokens in HTML ---")
# Sometimes Drupal 8/9 puts it in a script or meta
matches = re.findall(r'"form_build_id"\s*:\s*"([^"]+)"', r.text)
print("form_build_id matches in whole HTML:", matches)
