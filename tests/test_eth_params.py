
import requests
import re

urls = [
    "https://www.phys.ethz.ch/the-department/people/professors.html?letter=A",
    "https://www.phys.ethz.ch/the-department/people/professors.html?q=A",
    "https://www.phys.ethz.ch/the-department/people/professors.html?page=1"
]
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

for url in urls:
    print(f"Testing {url}...")
    r = requests.get(url, headers=headers)
    if "Abreu" in r.text:
        print(f"Found Abreu in {url}!")
    else:
        print(f"Abreu NOT found in {url}.")
