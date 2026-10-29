# Gezichten Vervagen (Face Blur Review)

Offline tool that finds faces in photos so a person can choose which to blur before publishing.
It does detection only (no recognition), runs entirely in the browser, and has a built-in
Content-Security-Policy that blocks all outgoing traffic.

There are three ways to use it, all from one HTML file:
online on your server, installed as an app (Chrome/Edge, Safari "Add to Dock"), or as a portable
ZIP (USB stick) on Windows, macOS and Linux.

```
VERSION, CHANGELOG.md     version + release notes (the top block feeds the download page)
build.py                  builds dist/ (reproducible)
src/app.html              the tool (source)
src/site/                 download page + service worker templates
src/icons/                icons (make_icons.py regenerates the PNGs)
src/docs/                 README, LICENSE (placeholder), third-party notices for the release ZIP
vendor/                   face-api.js + SSD MobileNet detector weights, licence texts (see SOURCES.md)
tests/                    end-to-end tests, Cloudflare Pages simulator, validation photos
docs/DEPLOY.md            hosting on Cloudflare Pages or Caddy, open points before going public
docs/TESTPLAN.md          manual cross-browser / cross-OS checklist
```

```bash
python3 build.py --base-url https://your-address/
python3 tests/test_release.py           # needs Python Playwright + Chromium; CADDY=/path/to/caddy
```

Status: **v0.9.0, test version.** See `docs/DEPLOY.md` §0 for what to settle before public release
(address, licence, model licence check, manual tests).
