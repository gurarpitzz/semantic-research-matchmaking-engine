
import os
os.environ['HOME'] = 'C:\\Users\\HP'
from playwright.sync_api import sync_playwright
import json

def capture_ajax():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        request_captured = []

        def handle_request(request):
            if "/views/ajax" in request.url and request.method == "POST":
                print(f"Captured AJAX POST to {request.url}")
                request_captured.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": request.headers,
                    "post_data": request.post_data
                })

        page.on("request", handle_request)
        
        print("Navigating to Oxford Physics...")
        page.goto("https://www.physics.ox.ac.uk/our-people", wait_until="networkidle")
        
        print("Scrolling to bottom to trigger AJAX...")
        # Scroll in increments to trigger lazy load or infinite scroll
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

        if request_captured:
            with open("captured_ajax.json", "w") as f:
                json.dump(request_captured, f, indent=2)
            print("Successfully captured AJAX request(s).")
        else:
            print("No AJAX request captured. Maybe it's not infinite scroll or already loaded?")
            # Take a screenshot to see what's happening
            page.screenshot(path="oxford_state.png")

        browser.close()

if __name__ == "__main__":
    capture_ajax()
