
import requests
from bs4 import BeautifulSoup
import json

url = "https://www.physics.ox.ac.uk/our-people"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

print(f"Fetching {url}...")
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

print("\n--- Forms Found ---")
forms = soup.find_all('form')
for i, form in enumerate(forms):
    print(f"Form {i}: id={form.get('id')}, class={form.get('class')}")
    for inp in form.find_all('input'):
        print(f"  Input: name={inp.get('name')}, type={inp.get('type')}, value={inp.get('value')[:30] if inp.get('value') else None}")

print("\n--- Drupal Settings ---")
settings_script = soup.find('script', {'data-drupal-selector': 'drupal-settings-json'})
if settings_script:
    settings = json.loads(settings_script.get_text())
    print(json.dumps(settings.get('views', {}), indent=2))
else:
    print("Drupal settings not found!")
