
import requests
import sys
# pip-system-certs patches requests at runtime automatically; no import needed here usually, 
# but simply importing it ensures the hook runs if not auto-loaded.
try:
    import pip_system_certs.wrapt_requests
except ImportError:
    pass

url = "https://www.damtp.cam.ac.uk/people"
print(f"Testing SSL connection to: {url}")

try:
    response = requests.get(url, timeout=10)
    print(f"✅ Success! Status Code: {response.status_code}")
    print(f"Content length: {len(response.text)}")
except requests.exceptions.SSLError as e:
    print(f"❌ SSL Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
