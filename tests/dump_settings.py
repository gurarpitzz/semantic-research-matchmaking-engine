
import requests
from bs4 import BeautifulSoup
import json

url = "https://www.physics.ox.ac.uk/our-people"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

settings_script = soup.find('script', {'data-drupal-selector': 'drupal-settings-json'})
if settings_script:
    with open("oxford_settings.json", "w") as f:
        f.write(settings_script.get_text())
    print("Dumped settings to oxford_settings.json")
else:
    print("Not found")
