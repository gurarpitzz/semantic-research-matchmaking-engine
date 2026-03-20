import requests
from bs4 import BeautifulSoup
import re
import time
import os
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

# Optional: Hook into system certs for corporate/Windows environments
try:
    import pip_system_certs.wrapt_requests
except ImportError:
    pass

class FacultyScraper:
    def __init__(self, rate_limit_seconds=0.5):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        self.rate_limit = rate_limit_seconds
        self.BLACKLIST = {
            "Calendar", "Events", "News", "Contact", "Give", "Social", "Mission", 
            "Values", "Diversity", "Search", "Login", "Resources", "Safety", "COVID",
            "History", "Map", "Jobs", "Career", "Colloquia", "Seminars", "About", "Home",
            "Student", "Alumni", "Portal", "Accessibility", "Privacy", "Statement", "Language",
            "Services", "Department", "Faculty Directory", "People Search", "Staff", "Overview"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _fetch(self, url):
        try:
            if self.rate_limit > 0:
                time.sleep(self.rate_limit)
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"⚠️ Fetch failed for {url}: {e}")
            return None

    def get_faculty_list(self, dept_url):
        """
        Universal Scraper for Faculty Directories.
        Autonomous Discovery Stage -> Traversal Stage -> Extraction Stage.
        """
        initial = []
        try:
            print(f"🌐 SRME: Analyzing directory at {dept_url}")
            response = self._fetch(dept_url)
            
            # Use Browser Fallback if requests fails OR content is JS-hydrated
            use_browser = False
            soup = None
            
            if not response:
                print("🧠 SRME: Fetch failed. Attempting Browser Fallback (Connection Reset / Bot Detection)...")
                use_browser = True
            else:
                soup = BeautifulSoup(response.text, 'html.parser')
                if self._looks_js_hydrated(soup):
                    print("🧠 SRME: JS-hydrated directory detected. Launching browser fallback...")
                    use_browser = True
            
            if use_browser:
                rendered = self._render_with_browser(dept_url)
                if rendered:
                    soup = BeautifulSoup(rendered, 'html.parser')
                    initial = self._parse_faculty_from_soup(soup, dept_url)
            elif soup:
                initial = self._parse_faculty_from_soup(soup, dept_url)

            if len(initial) > 40:
                print(f"✅ SRME: Full list present in base HTML. Found {len(initial)} profiles.")
                return initial[:500]

            # 0. Discovery Phase A: Drupal AJAX / Infinite Scroll
            # [-] Issue 1: Only trust Drupal when it yields real volume (>30)
            ajax_results = self._try_drupal_ajax_crawl(soup, dept_url)
            if ajax_results and len(ajax_results) > 30:
                print(f"⚡ SRME: Drupal AJAX harvested {len(ajax_results)} profiles")
                return ajax_results[:250]

            # 1. Discovery Phase B: Search for Traversal Patterns (A-Z, Pagination, Scripts)
            traversal_targets = self._discover_traversal_targets(soup, dept_url)
            
            # Combine base URL with targets
            urls_to_scrape = [dept_url]
            for target in traversal_targets:
                if target not in urls_to_scrape:
                    urls_to_scrape.append(target)
            
            if len(urls_to_scrape) > 1:
                print(f"📂 SRME: Detected segmented directory. Traversing {len(urls_to_scrape)} sections...")

            faculty = []
            seen_urls = set()
            
            # 2. Execution Phase: Crawl and Parse
            for current_url in urls_to_scrape:
                try:
                    if current_url != dept_url:
                        r = self._fetch(current_url)
                        if not r: continue
                        curr_soup = BeautifulSoup(r.text, 'html.parser')
                    else:
                        curr_soup = soup
                    
                    segment_results = self._parse_faculty_from_soup(curr_soup, current_url)
                    
                    for f in segment_results:
                        if f['url'] not in seen_urls:
                            faculty.append(f)
                            seen_urls.add(f['url'])
                    
                    if len(faculty) >= 250:
                        break
                except Exception as segment_e:
                    print(f"⚠️ SRME: Skipping segment {current_url} due to error: {segment_e}")
                    continue
            
            # 3. Fallback Phase: If results are very small, try brute-force A-Z params
            if len(faculty) < 20 and len(urls_to_scrape) == 1:
                print("🔍 SRME: Low yield. Attempting best-effort A-Z query trial...")
                from string import ascii_uppercase
                for char in ascii_uppercase:
                    # Common params: letter, initial, q, filter
                    for param in ['letter', 'initial', 'q']:
                        sep = '&' if '?' in dept_url else '?'
                        trial_url = f"{dept_url}{sep}{param}={char}"
                        r = self._fetch(trial_url)
                        if r and char in r.text: # Only parse if the letter is actually prominent
                            segment_results = self._parse_faculty_from_soup(BeautifulSoup(r.text, 'html.parser'), trial_url)
                            for f in segment_results:
                                if f['url'] not in seen_urls:
                                    faculty.append(f)
                                    seen_urls.add(f['url'])
                    if len(faculty) >= 100: break

            print(f"✅ SRME: Harvested {len(faculty)} faculty profiles.")
            return faculty[:250]
            
        except Exception as e:
            print(f"❌ SRME: Critical Scraper Error: {e}")
            return []

    def _try_drupal_ajax_crawl(self, soup, base_url):
        """
        Attempts to detect and crawl Drupal Views AJAX/Infinite Scroll.
        Returns a list of extracted faculty if successful, else None.
        """
        import json

        # 1. Detection: Find Drupal Settings
        settings_script = soup.find('script', {'data-drupal-selector': 'drupal-settings-json'})
        if not settings_script:
            return None
            
        try:
            settings = json.loads(settings_script.get_text())
            views_data = settings.get('views', {})
            ajax_views = views_data.get('ajaxViews', {})
            
            if not ajax_views:
                return None
            
            # Select the Best View (Heuristic: most links/content)
            view_config = self._select_best_view(soup, ajax_views)
            if not view_config:
                return None

            print(f"⚡ SRME: Detected Drupal AJAX View provided by '{view_config.get('view_name')}'")
            
        except Exception as e:
            print(f"⚠️ Drupal Detection Error: {e}")
            return None

        # 2. Setup Extraction Loop
        # Start with what we already have on Page 0
        faculty_accumulated = self._parse_faculty_from_soup(soup, base_url)
        seen_urls = {f['url'] for f in faculty_accumulated}
        
        page = 0 # Start at 0, duplicate check handles overlapping
        
        # Base Endpoint
        ajax_path = views_data.get('ajax_path', '/views/ajax')
        api_url = self._resolve_url(base_url, ajax_path)
        
        # Headers specifically for Drupal AJAX
        ajax_headers = self.headers.copy()
        ajax_headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Referer": base_url,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        })

        # 2a. Hardening: Extract Form State (CSRF tokens)
        # Oxford/Imperial/UCL require hidden fields: form_build_id, form_id, form_token
        form_inputs = {}
        try:
            form = soup.select_one("form.views-exposed-form")
            if form:
                for inp in form.find_all("input"):
                    name = inp.get("name")
                    value = inp.get("value", "")
                    if name:
                        form_inputs[name] = value

                for sel in form.find_all("select"):
                    name = sel.get("name")
                    if name:
                        # For select lists in filters, sending empty string usually means "All"
                        form_inputs[name] = "" 
            
            if form_inputs:
                print(f"🔒 SRME: Extracted {len(form_inputs)} form state tokens (CSRF protection bypass).")
                
        except Exception as e:
            print(f"⚠️ Form State Extraction Warning: {e}")

        while True:
            # 3. Construct Payload
            # We use both underscored and non-underscored keys to support various Drupal versions (Oxford fix)
            payload = {
                'view_name': view_config.get('view_name'),
                'view_display_id': view_config.get('view_display_id'),
                '_view_name': view_config.get('view_name'),
                '_view_display_id': view_config.get('view_display_id'),
                'view_args': view_config.get('view_args', ''),
                'view_path': view_config.get('view_path', ''),
                'view_dom_id': view_config.get('view_dom_id'),
                'pager_element': view_config.get('pager_element', 0),
                'page': page,
                '_drupal_ajax': '1',
                'ajax_page_state[theme]': settings.get('ajaxPageState', {}).get('theme', ''),
                'ajax_page_state[theme_token]': settings.get('ajaxPageState', {}).get('theme_token', '') or '',
                'ajax_page_state[libraries]': settings.get('ajaxPageState', {}).get('libraries', '')
            }
            
            # Manually inject form_id if missing from extraction (common for anonymous getters)
            if 'form_id' not in form_inputs:
                payload['form_id'] = 'views_exposed_form'
            
            # Merge extracted form tokens (overwrites defaults if conflict)
            if form_inputs:
                payload.update(form_inputs)

            try:
                if page == 0:
                    print(f"  🔍 SRME Payload Keys: {list(payload.keys())}")
                
                print(f"  ➡️ requesting generic Drupal page {page}...")
                if self.rate_limit > 0: time.sleep(self.rate_limit)
                
                # Try primary AJAX endpoint
                response = self.session.post(api_url, data=payload, headers=ajax_headers, timeout=10)
                
                # Check for "HTML rejected" state (Status 200 but Content-Type = text/html)
                is_json = "application/json" in response.headers.get("Content-Type", "").lower()
                
                # Fallback: Some Drupal 8/9 sites handle AJAX on the base page URL itself
                if not is_json or response.status_code != 200:
                    if page == 0:
                        print("  🔍 Primary AJAX failed/rejected. Attempting Fallback to Base URL...")
                        response = self.session.post(base_url, data=payload, headers=ajax_headers, timeout=10)
                        is_json = "application/json" in response.headers.get("Content-Type", "").lower()

                if not is_json:
                    print(f"  ⚠️ Drupal rejected AJAX (returned HTML). Headers: {response.headers.get('Content-Type')}")
                    break

                response_json = response.json()
                
                # 4. Extract HTML from JSON Commands
                new_content_found = False
                
                # Drupal returns a list of commands. We look for 'insert' commands with HTML data.
                for command in response_json:
                    if command.get('command') == 'insert' and 'data' in command:
                        html_fragment = command['data']
                        if not html_fragment or not isinstance(html_fragment, str) or not html_fragment.strip(): continue
                        
                        # Parse this fragment
                        frag_soup = BeautifulSoup(html_fragment, 'html.parser')
                        
                        # Reuse our existing robust extractor
                        extracted = self._parse_faculty_from_soup(frag_soup, base_url)
                        
                        if extracted:
                            for f in extracted:
                                if f['url'] not in seen_urls:
                                    faculty_accumulated.append(f)
                                    seen_urls.add(f['url'])
                                    new_content_found = True
                
                if not new_content_found:
                    # If page 0 gave no *new* results (because it was the initial page), try page 1.
                    # If page > 0 gave no new results, we are done.
                    if page > 0:
                        print("  🛑 No new faculty found in AJAX response. End of list.")
                        break
                
                # [-] Issue 4: Infinite Loop Protection
                # Some buggy Drupal sites repeat last page forever.
                frag_hash = hash(str(response.text))
                if hasattr(self, "_last_frag") and self._last_frag == frag_hash:
                    print("  ⚠️ Infinite loop detected (repeated content). Stopping.")
                    break
                self._last_frag = frag_hash
                    
                page += 1
                if page > 50: break
                
            except Exception as e:
                print(f"⚠️ AJAX Loop Error: {e}")
                break
                
        return faculty_accumulated

    def _looks_js_hydrated(self, soup):
        """Detection Rule: Container exists but yield is low (<15) + Drupal signal."""
        # Check global yield using the exhaustive parser
        count = len(self._parse_faculty_from_soup(soup, ""))
        
        # Check for common Drupal/Generic faculty container classes
        has_container = False
        for cls in ['view-content', 'views-view-grid', 'people-list', 'faculty-list', 'directory', 'grid', 'row']:
            if soup.select_one(f".{cls}"):
                has_container = True
                break
        
        if has_container and count < 15:
            # If yield is low but container exists, check for JS-gate signals
            has_settings = bool(soup.find('script', {'data-drupal-selector': 'drupal-settings-json'}))
            has_pager = bool(soup.find(attrs={"data-drupal-selector": re.compile(r"pager")}))
            if has_settings or has_pager:
                print(f"  🔍 Detection signal: Low yield ({count}) with Drupal JS/Pager detected.")
                return True
        return False

    def _render_with_browser(self, url) -> str:
        """Headless browser fallback to handle JS-hydration and cookie gates."""
        try:
            # Ensure HOME is set for Playwright (Windows environment fix)
            if 'HOME' not in os.environ:
                os.environ['HOME'] = os.path.expanduser("~")

            with sync_playwright() as p:
                print(f"  🌐 Launching headless browser for {url}...")
                browser = p.chromium.launch(headless=True)
                # Use a specific user agent to look like a real browser
                context = browser.new_context(user_agent=self.headers['User-Agent'])
                page = context.new_page()
                
                # Navigate and wait for network to settle
                page.goto(url, wait_until="networkidle", timeout=30000)
                
                # 1. Cookie Gate Handling: Heuristic button match
                try:
                    # Look for "Accept", "Agree", or "Allow" buttons
                    btn = page.locator("button:has-text('Accept'), button:has-text('I agree'), button:has-text('Agree'), button:has-text('Allow')").first
                    if btn.is_visible(timeout=3000):
                        print("  🍪 SRME: Clicking cookie consent button...")
                        btn.click()
                        # Brief wait for UI to update
                        page.wait_for_timeout(1000)
                except Exception:
                    pass # No obvious cookie button found or already accepted

                # 2. Wait for content hydration & Trigger "Load More" loop
                try:
                    # Initial wait for first cards
                    # Broaden selectors to handle non-article/views-row layouts (e.g., people-row, grid items)
                    page.wait_for_selector(".view-content article, .view-content .views-row, .people-row, .people-item, .inner-people-grid, table tr", timeout=10000)
                    
                    # 3. "Load More" Automation for Drupal Infinite Scroll / Pager Load More
                    load_more_count = 0
                    while load_more_count < 25: # Increased safety limit
                        load_more_btn = page.locator(".js-pager__items a:has-text('Load more'), .pager__item a:has-text('Load more')").first
                        if load_more_btn.is_visible(timeout=3000):
                            items_selector = ".view-content article, .view-content .views-row, .people-row, .people-item, .inner-people-grid"
                            current_count = page.locator(items_selector).count()
                            print(f"  👇 SRME: Found {current_count} cards. Clicking 'Load More' (Trial {load_more_count+1})...")
                            load_more_btn.click()
                            # Wait for card count to increase
                            try:
                                page.wait_for_function(f"document.querySelectorAll('{items_selector}').length > {current_count}", timeout=8000)
                                page.wait_for_timeout(1000)
                            except Exception:
                                print("  ⚠️ Load more timed out or reached end.")
                                break
                            load_more_count += 1
                        else:
                            break
                    
                    # Final scroll to ensure we catch everything
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                except Exception:
                    print("  ⚠️ Browser timeout during hydration loop. Capturing what's visible.")

                # DEBUG: Capture screenshot
                page.screenshot(path="oxford_render_final.png")
                
                content = page.content()
                browser.close()
                return content
        except Exception as e:
            print(f"  ❌ Browser Fallback Failed: {e}")
            return None

    def _select_best_view(self, soup, ajax_views):
        """Heuristic: Select the view config that likely corresponds to the main faculty list."""
        best_view = None
        best_score = 0

        for vid, cfg in ajax_views.items():
            dom_id = cfg.get("view_dom_id")
            if not dom_id:
                continue

            # Drupal views often have class .js-view-dom-id-{HASH}
            container = soup.select_one(f".js-view-dom-id-{dom_id}")
            if not container:
                continue

            # Heuristic: count links that look like internal pages (likely profiles)
            # We exclude common nav links
            links = container.find_all('a', href=True)
            score = 0
            for a in links:
                href = a['href']
                if len(href) > 5 and not href.startswith(('http', 'mailto', '#')):
                     score += 1

            if score > best_score:
                best_score = score
                best_view = cfg

        return best_view

    def _discover_traversal_targets(self, soup, base_url):
        """Discovers A-Z indices, numeric pagination, and script-based endpoints."""
        targets = []
        
        # Heuristic 1: Cluster of single-letter links (Alphabetical Index)
        all_links = soup.find_all('a', href=True)
        letter_links = []
        for a in all_links:
            text = a.get_text().strip()
            if len(text) == 1 and text.isalpha():
                letter_links.append(a)
        
        if len(letter_links) >= 15:
            for l in letter_links:
                targets.append(self._resolve_url(base_url, l['href']))
                    
        # Heuristic 2: Sequential Pagination (Pager divs)
        for pager in soup.find_all(class_=re.compile(r'page|pager|pagination|nav', re.I)):
            for a in pager.find_all('a', href=True):
                txt = a.get_text().strip()
                if txt.isdigit() or any(kw in txt.lower() for kw in ['next', '>', '»', '→']):
                    targets.append(self._resolve_url(base_url, a['href']))
        
        # Heuristic 3: Script-based endpoint discovery (XHR/AJAX links)
        for script in soup.find_all('script'):
            stxt = script.string or ""
            # Search for endpoints like "/people?letter=" or similar
            matches = re.finditer(r'(["\'])(/[^"\']*\?[^"\']*(?:letter|initial|alpha|filter)=[A-Z])\1', stxt, re.I)
            for m in matches:
                raw_endpoint = m.group(2)
                from string import ascii_uppercase
                for char in ascii_uppercase:
                    # Replace whatever letter was in the match with the full A-Z range
                    templated = re.sub(r'=[A-Z]', f'={char}', raw_endpoint, flags=re.I)
                    targets.append(self._resolve_url(base_url, templated))
            
            # [-] Issue 3: API pagination patterns in scripts (React/Node)
            api_matches = re.findall(r'["\'](/api/[^"\']+page=\d+[^"\']*)["\']', stxt)
            for api in api_matches:
                for p in range(1, 8):
                    targets.append(self._resolve_url(base_url, re.sub(r'page=\d+', f'page={p}', api)))
                
        return sorted(list(set(targets)))[:50] # Dedup and cap

    def _parse_faculty_from_soup(self, soup, current_url):
        """Generic card extraction with high-precision name heuristics."""
        faculty = []
        
        priority_classes = [
            'view-content', 'people-list', 'faculty-list', 'directory', 
            'staff-list', 'profiles', 'people-row', 'people-item',
            'inner-people-grid', 'views-view-grid', 'grid', 'row'
        ]
        candidate_blocks = []
        
        # Collect all blocks that aren't navigation
        for cls in priority_classes:
            for block in soup.select(f".{cls}"):
                # Skip blocks inside nav/header/footer to avoid menus
                if block.find_parent(['nav', 'header', 'footer']):
                    continue
                candidate_blocks.append(block)
        
        if not candidate_blocks:
            candidate_blocks = [soup]
            
        seen_urls = set()
        # We look for repeat-blocks (divs, list items, rows)
        for block in candidate_blocks:
            # We search specifically for containers that likely hold a name and link
            containers = block.find_all(['div', 'li', 'tr', 'article', 'section', 'fieldset'], recursive=True)
            # If the block itself is a small container, include it
            if block.name in ['div', 'li', 'tr', 'article', 'section', 'fieldset']:
                containers = [block] + list(containers)
                
            for container in containers:
                # 1. Identify Profile Link
                link = container.find('a', href=True)
                if not link: continue
                
                href = link['href']
                # Skip common non-profile links
                if any(k in href.lower() for k in ['facebook', 'twitter', 'linkedin', 'mailto:', 'tel:', 'vcard', 'google', 'twitter']): 
                    continue
                if href == '#' or 'javascript:' in href: continue
                if href.endswith(('.jpg', '.png', '.pdf', '.docx', '.zip')): continue

                full_url = self._resolve_url(current_url, href)
                if full_url in seen_urls: continue
                
                # 2. Identify Potential Name
                potential_name = None
                # Priority: Header within container
                header = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if header:
                    potential_name = header.get_text().strip()
                
                # Sub-priority: Elements with name-like classes
                if not self._is_valid_name_format(potential_name):
                    name_elem = container.select_one('[class*="name"], [class*="title"]')
                    if name_elem:
                        potential_name = name_elem.get_text().strip()

                # Final priority: Strong/Bold/Link text
                if not self._is_valid_name_format(potential_name):
                    for elem in container.find_all(['strong', 'b', 'a'], recursive=False):
                        txt = elem.get_text().strip()
                        if self._is_valid_name_format(txt):
                            potential_name = txt
                            break
                    if not self._is_valid_name_format(potential_name):
                        txt = link.get_text().strip()
                        if self._is_valid_name_format(txt):
                            potential_name = txt
                
                if not self._is_valid_name_format(potential_name):
                    continue
                    
                # Clean Name
                name = self._clean_name(potential_name)
                
                # 3. Email Detection
                email = None
                mailto = container.find('a', href=re.compile(r'^mailto:'))
                if mailto:
                    email = mailto['href'].replace('mailto:', '').split('?')[0].strip()
                if not email:
                    txt = container.get_text()
                    match = re.search(r'[a-zA-Z0-9._%+-]+@[\w.-]+\.[a-zA-Z]{2,}', txt)
                    if match: 
                        email = match.group(0)
                    else:
                        match = re.search(r'[a-zA-Z0-9._%+-]+\s*(\[at\]|@)\s*[\w.-]+\s*(\[dot\]|\.)\s*[a-zA-Z]{2,}', txt)
                        if match:
                            email = match.group(0).replace('[at]', '@').replace('[dot]', '.').replace(' ', '')

                faculty.append({
                    "name": name,
                    "url": full_url,
                    "email": email
                })
                seen_urls.add(full_url)
            
        return faculty

    def _is_valid_name_format(self, text):
        if not text or len(text) < 5 or len(text) > 60: return False
        if any(word in text for word in self.BLACKLIST): return False
        # Must have a space or a comma (suggests multiple name components)
        if ' ' not in text and ',' not in text: return False
        # Must contain at least some alphabetic characters
        if not any(c.isalpha() for c in text): return False
        
        # [-] Issue 5: Reject long titles that look like departments
        if len(text.split()) > 4:
            return False
            
        return True

    def _clean_name(self, text):
        # Remove common academic prefixes/suffixes
        text = re.sub(r'(Prof\.|Professor|Dr\.|Dr-Ing\.|MD|PhD|M\.Sc\.|Associate|Assistant|Emeritus|Visiting|Junior|Senior)', '', text, flags=re.IGNORECASE)
        # Remove trailing/leading punctuation
        text = text.strip().strip(',').strip()
        # Handle "Last, First" -> "First Last" normalization if desired, but here we keep it clean
        return text

    def _resolve_url(self, base, path):
        return urljoin(base, path)

    def extract_email_from_url(self, url):
        """Deep scrape profile with obfuscation support."""
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code != 200: return None
            
            text = r.text
            # Basic de-obfuscation
            text = re.sub(r'[\(\[]at[\)\]]', '@', text, flags=re.IGNORECASE)
            text = re.sub(r'[\(\[]dot[\)\]]', '.', text, flags=re.IGNORECASE)
            
            match = re.search(r'[a-zA-Z0-9._%+-]+@[\w.-]+\.[a-zA-Z]{2,}', text)
            if match: return match.group(0).lower()
            
            # Link check
            soup = BeautifulSoup(r.text, 'html.parser')
            mailto = soup.find('a', href=re.compile(r'^mailto:'))
            if mailto:
                return mailto['href'].replace('mailto:', '').split('?')[0].strip().lower()
        except:
            pass
        return None

# Global scraper instance
scraper = FacultyScraper()
