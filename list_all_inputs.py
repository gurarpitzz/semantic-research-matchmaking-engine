
import requests
from bs4 import BeautifulSoup

url = "https://www.physics.ox.ac.uk/our-people"
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(r.text, 'html.parser')

print("--- All Hidden Inputs ---")
for inp in soup.find_all("input", type="hidden"):
    print(f"Name: {inp.get('name')}, Value: {inp.get('value')}")

print("\n--- All Forms ---")
for f in soup.find_all("form"):
    print(f"Form Class: {f.get('class')}, ID: {f.get('id')}")
