
import re

text = "Abreu, Elsa, Prof. Dr."
regex = r'^[A-Z\u00C0-\u017F][A-Za-z\u00C0-\u017F\-\.\s\',]+$'
is_name_like = re.search(regex, text)
is_prof = any(kw in text for kw in ["Professor", "Prof.", "Dr."])
is_valid_name = (is_name_like or is_prof) and 2 < len(text) < 50 and ' ' in text

print(f"Name: {text}")
print(f"Is Name Like: {bool(is_name_like)}")
print(f"Is Prof: {is_prof}")
print(f"Is Valid: {is_valid_name}")

text2 = "A"
print(f"Name: {text2}")
print(f"Is Name Like: {bool(re.search(regex, text2))}")
