
import requests
import sys
import certifi

url = "https://www.damtp.cam.ac.uk/people"
print(f"Testing SSL connection to: {url}")
print(f"Using CA Bundle: {certifi.where()}")

try:
    response = requests.get(url, timeout=10, verify=certifi.where())
    print(f"✅ Success! Status Code: {response.status_code}")
    print(f"Content length: {len(response.text)}")
except requests.exceptions.SSLError as e:
    print(f"❌ SSL Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
