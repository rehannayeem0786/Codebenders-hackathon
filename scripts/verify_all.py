"""Full integration verification of all features"""
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.main import app

client = TestClient(app)
checks = []

# 1. Health
r = client.get("/api/health")
h = r.json()
checks.append(("health", r.status_code == 200 and h["graph"]["schemes"] == 26))

# 2. SW
r = client.get("/sw.js")
checks.append(("sw.js", r.status_code == 200 and "schemesetu-v1" in r.text))

# 3. Manifest
r = client.get("/manifest.json")
checks.append(("manifest", r.status_code == 200 and r.json()["short_name"] == "SchemeSetu"))

# 4. Favicon
r = client.get("/static/favicon.svg")
checks.append(("favicon", r.status_code == 200 and "<svg" in r.text))

# 5. Index HTML has all meta tags
r = client.get("/")
html = r.text
checks.append(("meta-manifest", 'rel="manifest"' in html))
checks.append(("meta-theme", "theme-color" in html))
checks.append(("meta-apple", "apple-mobile-web-app" in html))
checks.append(("theme-toggle-btn", "btn-theme-toggle" in html))
checks.append(("shortcuts-tooltip", "shortcuts-tooltip" in html))
checks.append(("sw-register", "serviceWorker.register" in html))

# 6. App.js has new features
r = client.get("/static/app.js")
js = r.text
checks.append(("category-icons", "CATEGORY_ICONS" in js))
checks.append(("toast-system", "showToast" in js))
checks.append(("theme-toggle", "toggleTheme" in js))
checks.append(("confetti", "launchConfetti" in js))
checks.append(("keyboard-shortcuts", "handleKeyboard" in js))
checks.append(("footer-stats", "updateFooterStats" in js))

# 7. CSS has new themes
r = client.get("/static/styles.css")
css = r.text
checks.append(("light-theme-css", "body.light-theme" in css))
checks.append(("skeleton-loading", "skeleton" in css))
checks.append(("toast-css", "toast-container" in css))
checks.append(("confetti-css", "confettiFall" in css))
checks.append(("verdict-stripe", "verdict-eligible" in css))
checks.append(("category-icon-css", "category-icon" in css))
checks.append(("kbd-css", ".kbd" in css))

# 8. Full intake still works
intake = client.post("/api/intake", json={
    "text": "widow 59 years old BPL Telangana no land",
    "language": "en", "form": {}, "save": True, "consent": True
})
d = intake.json()
checks.append(("intake-works", intake.status_code == 200 and len(d.get("matches", [])) > 0))

pid = d.get("profile_id", "")

# 9. Checklist with WhatsApp
if pid:
    cl = client.get(f"/api/checklist/{pid}?lang=en")
    cld = cl.json()
    checks.append(("checklist-wa", "whatsapp_url" in cld and "operator_token" in cld))
else:
    checks.append(("checklist-wa", False))

# 10. Graphify
checks.append(("graphify", h["graph"]["graphify"]["imported"] and h["graph"]["graphify"]["nodes"] > 50))

passed = sum(1 for _, ok in checks if ok)
failed = sum(1 for _, ok in checks if not ok)

for name, ok in checks:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")

print(f"\n=== {passed}/{len(checks)} CHECKS PASSED ===")
if failed:
    print(f"!!! {failed} FAILED !!!")
else:
    print("ALL FEATURES VERIFIED AND PASSING")
