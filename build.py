#!/usr/bin/env python3
"""Build Gezichten Vervagen: the single-file tool, the website and the release ZIP.

    python3 build.py [--base-url https://vervagen.example.nl/] [--out dist]

The base URL can also come from the environment variable GV_BASE_URL
(handy on Cloudflare Pages: change the domain without touching the build command).

Output (dist/):
  site/                         web root, deploy as-is (Cloudflare Pages or Caddy)
    index.html                  download page (no scripts)
    app/index.html              the tool  == the HTML inside the release ZIP (same bytes)
    app/sw.js, app/manifest.webmanifest, app/icons/*
    download/gezichten-vervagen-vX.Y.Z.zip
    SHA256SUMS.txt, LICENSE.txt, THIRD-PARTY-NOTICES.txt
    _headers                    Cloudflare Pages header rules
  server/Caddyfile              Caddy site block with the same header rules
  gezichten-vervagen-vX.Y.Z.zip copy of the release ZIP

The build is reproducible: same inputs -> byte-identical HTML and ZIP (so checksums are stable).
Only the face DETECTOR is bundled; recognition models are deliberately never included.
"""
import argparse, base64, hashlib, html, json, os, pathlib, re, shutil, sys, zipfile
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent
SRC, VENDOR = ROOT / "src", ROOT / "vendor"
PLACEHOLDER_URL = "https://JOUW-DOMEIN.example/"
APP_FILE = "gezichten-vervagen.html"
LICENSE_TEXT = (SRC / "docs/LICENSE.txt").read_text(encoding="utf-8")
LICENSE_IS_PLACEHOLDER = "PLACEHOLDER" in LICENSE_TEXT
_spdx = re.search(r"SPDX-License-Identifier:\s*(\S+)", LICENSE_TEXT)
LICENSE_ID = _spdx.group(1) if _spdx else None


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        sys.exit(f"unfilled placeholders: {sorted(set(left))}")
    return text


def read_changelog(version: str):
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## (\S+) — (\d{4}-\d{2}-\d{2})\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        sys.exit("CHANGELOG.md: no '## X.Y.Z — YYYY-MM-DD' block found")
    if m.group(1) != version:
        sys.exit(f"CHANGELOG.md top version {m.group(1)} != VERSION {version}")
    body = m.group(3)
    def items(lang):
        sec = re.search(rf"^### {lang}\s*$(.*?)(?=^### |\Z)", body, re.M | re.S)
        return [l[2:].strip() for l in (sec.group(1) if sec else "").splitlines() if l.startswith("- ")]
    return m.group(2), items("nl"), items("en")


# ---------------------------------------------------------------- the tool
def inline_script_hashes(page: str):
    """sha256 of every inline script the browser will EXECUTE (data blocks are skipped)."""
    hashes = []
    for attrs, body in re.findall(r"<script(\s[^>]*)?>(.*?)</script>", page, re.S):
        t = re.search(r'type="([^"]+)"', attrs or "")
        if t and t.group(1) not in ("text/javascript", "module"):
            continue
        hashes.append("'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'")
    return hashes


def app_csp(hashes):
    return "; ".join([
        "default-src 'none'",
        "script-src " + " ".join(hashes),
        "style-src 'unsafe-inline'",
        "img-src 'self' blob: data:",
        "manifest-src 'self'",
        "worker-src 'self'",
        "connect-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "object-src 'none'",
    ])


def build_app(version: str, base_url: str):
    src = (SRC / "app.html").read_text(encoding="utf-8")
    lib = (VENDOR / "face-api/face-api.js").read_text(encoding="utf-8")
    manifest = json.loads((VENDOR / "face-api/ssd_mobilenetv1_model-weights_manifest.json").read_text())
    weights = (VENDOR / "face-api/ssd_mobilenetv1_model.bin").read_bytes()
    for bad in ("</script", "<!--", "<script"):
        if bad in lib.lower():
            sys.exit(f"face-api.js contains {bad!r}; cannot inline safely")
    b64 = base64.b64encode(weights).decode()
    b64 = "\n".join(b64[i:i + 4096] for i in range(0, len(b64), 4096))
    page = (src.replace("/*__FACEAPI__*/", lib, 1)
               .replace("/*__MANIFEST__*/", json.dumps(manifest, separators=(",", ":")), 1)
               .replace("/*__WEIGHTS__*/", b64, 1)
               .replace("__VERSION__", version)
               .replace("__BASE_URL__", base_url))
    hashes = inline_script_hashes(page)
    if len(hashes) != 2:
        sys.exit(f"expected 2 executable inline scripts, found {len(hashes)}")
    csp = app_csp(hashes)
    page = page.replace("__CSP__", csp, 1)
    for ph in ("__CSP__", "__VERSION__", "__BASE_URL__", "/*__"):
        if ph in page:
            sys.exit(f"placeholder {ph} left in app")
    return page.encode("utf-8"), csp


# ---------------------------------------------------------------- headers
INDEX_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'"
COMMON = [
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("X-Frame-Options", "DENY"),
    ("Strict-Transport-Security", "max-age=31536000"),
]
TEXT = [("Content-Type", "text/plain; charset=utf-8"), ("Cache-Control", "no-cache")]


def header_rules(csp_app):
    # exact paths only for CSP: Cloudflare Pages joins same-named headers of
    # overlapping rules with a comma, which would merge (= tighten) two policies.
    app = [("Content-Security-Policy", csp_app + "; frame-ancestors 'none'"), ("Cache-Control", "no-cache")]
    idx = [("Content-Security-Policy", INDEX_CSP + "; frame-ancestors 'none'"), ("Cache-Control", "no-cache")]
    return [
        ("/*", COMMON),
        ("/", idx), ("/index.html", idx),
        ("/app/", app), ("/app/index.html", app),
        ("/app/sw.js", [("Content-Security-Policy", "default-src 'none'; connect-src 'self'"), ("Cache-Control", "no-cache")]),
        ("/app/manifest.webmanifest", [("Content-Type", "application/manifest+json"), ("Cache-Control", "no-cache")]),
        ("/app/icons/*", [("Cache-Control", "public, max-age=86400")]),
        ("/download/*", [("Content-Disposition", "attachment"), ("Cache-Control", "public, max-age=31536000, immutable")]),
        ("/SHA256SUMS.txt", TEXT), ("/LICENSE.txt", TEXT), ("/THIRD-PARTY-NOTICES.txt", TEXT),
    ]


def render_cf_headers(rules, version):
    out = [f"# Cloudflare Pages header rules — Gezichten Vervagen v{version} (generated by build.py; do not edit)",
           "# The CSP script hashes match THIS build of app/index.html.", ""]
    for path, hdrs in rules:
        out.append(path)
        out += [f"  {k}: {v}" for k, v in hdrs]
        out.append("")
    return "\n".join(out)


def render_caddyfile(rules, version, host):
    q = lambda v: '"' + v.replace('"', '\\"') + '"'
    L = [f"# Gezichten Vervagen v{version} — Caddy site block (generated by build.py; do not edit by hand).",
         "# The CSP script hashes match THIS build. Rebuild + redeploy both together.",
         "# Set GV_SITE_ADDRESS / GV_SITE_ROOT, or replace the defaults below.",
         f"{{$GV_SITE_ADDRESS:{host}}} {{",
         "\troot * {$GV_SITE_ROOT:/srv/gezichten-vervagen}",
         "\tencode zstd gzip",
         "",
         "\t# _headers is for Cloudflare Pages only; don't publish it here",
         "\t@cfheaders path /_headers",
         "\trespond @cfheaders 404",
         ""]
    n = 0
    for path, hdrs in rules:
        if path == "/*":
            L.append("\theader {")
            L += [f"\t\t{k} {q(v)}" for k, v in hdrs]
            L.append("\t\t-Server")
            L.append("\t}")
            continue
        n += 1
        L.append(f"\t@r{n} path {path}")
        L.append(f"\theader @r{n} {{")
        # '>' = apply when the response is written, so it overrides file_server's Content-Type
        L += [f"\t\t{'>' if k == 'Content-Type' else ''}{k} {q(v)}" for k, v in hdrs]
        L.append("\t}")
    L += ["", "\tfile_server", "}", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- release zip
def deterministic_zip(path: pathlib.Path, folder: str, files: dict, date: str):
    y, m, d = map(int, date.split("-"))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(f"{folder}/{name}", date_time=(y, m, d, 12, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            z.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def human(n):
    return f"{n / 1e6:.1f} MB"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.environ.get("GV_BASE_URL") or PLACEHOLDER_URL,
                    help="public URL of the download page (with trailing /); default: $GV_BASE_URL")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    a = ap.parse_args()
    base_url = a.base_url if a.base_url.endswith("/") else a.base_url + "/"
    host = urlparse(base_url).hostname or "jouw-domein.example"

    version = (ROOT / "VERSION").read_text().strip()
    date, changes_nl, changes_en = read_changelog(version)
    year = date[:4]
    out = pathlib.Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    site = out / "site"
    (site / "app/icons").mkdir(parents=True)
    (site / "download").mkdir()
    (out / "server").mkdir()

    # 1. the tool
    app_bytes, csp = build_app(version, base_url)
    html_sha = sha256(app_bytes)
    (site / "app/index.html").write_bytes(app_bytes)

    # 2. docs
    vals = {"VERSION": version, "DATE": date, "YEAR": year, "BASE_URL": base_url}
    readme = fill((SRC / "docs/LEESMIJ-README.txt").read_text(encoding="utf-8"), vals)
    license_txt = fill((SRC / "docs/LICENSE.txt").read_text(encoding="utf-8"), vals)
    mit = (VENDOR / "face-api/LICENSE.face-api").read_text(encoding="utf-8")
    mit_body = mit[mit.index("Permission is hereby granted"):]
    notices = (fill((SRC / "docs/THIRD-PARTY-NOTICES.head.txt").read_text(encoding="utf-8"), vals)
               + mit_body.rstrip() + "\n\n------------------------------------------------------------------\n"
               + "B. Apache License 2.0 (applies to item 3)\n\n"
               + (VENDOR / "licenses/Apache-2.0.txt").read_text(encoding="utf-8"))
    sums_inner = f"{html_sha}  {APP_FILE}\n"

    # 3. release zip (reproducible)
    folder = f"gezichten-vervagen-v{version}"
    zip_name = f"{folder}.zip"
    zip_path = site / "download" / zip_name
    deterministic_zip(zip_path, folder, {
        APP_FILE: app_bytes,
        "LEESMIJ-README.txt": readme.encode(),
        "LICENSE.txt": license_txt.encode(),
        "THIRD-PARTY-NOTICES.txt": notices.encode(),
        "SHA256SUMS.txt": sums_inner.encode(),
    }, date)
    zip_bytes = zip_path.read_bytes()
    zip_sha = sha256(zip_bytes)
    shutil.copy(zip_path, out / zip_name)

    # 4. install-as-app files
    for f in (SRC / "icons").glob("*"):
        if f.suffix in (".png", ".svg"):
            shutil.copy(f, site / "app/icons" / f.name)
    (site / "app/sw.js").write_text((SRC / "site/sw.js").read_text(encoding="utf-8").replace("__VERSION__", version), encoding="utf-8")
    manifest = {
        "id": "./", "name": "Gezichten Vervagen", "short_name": "Vervagen", "lang": "nl",
        "description": "Vervaag gezichten op foto's, volledig offline in je eigen browser.",
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": "#0b1120", "theme_color": "#0d1424",
        "icons": [
            {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": "icons/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
        ],
    }
    (site / "app/manifest.webmanifest").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 5. download page + public text files
    li = lambda xs: "".join(f"<li>{html.escape(x)}</li>" for x in xs)
    page = fill((SRC / "site/index.html").read_text(encoding="utf-8"), {
        **vals, "ZIP_NAME": zip_name, "ZIP_SIZE": human(len(zip_bytes)), "ZIP_SHA": zip_sha, "HTML_SHA": html_sha,
        "CHANGES_NL": li(changes_nl), "CHANGES_EN": li(changes_en),
        "LICENSE_LABEL": ("licentie / licence (nog te kiezen / to be decided)" if LICENSE_IS_PLACEHOLDER
                          else f"licentie / licence: {LICENSE_ID}" if LICENSE_ID else "licentie / licence"),
    })
    (site / "index.html").write_text(page, encoding="utf-8")
    (site / "SHA256SUMS.txt").write_text(f"{zip_sha}  {zip_name}\n{html_sha}  {APP_FILE}\n", encoding="utf-8")
    (site / "LICENSE.txt").write_text(license_txt, encoding="utf-8")
    (site / "THIRD-PARTY-NOTICES.txt").write_text(notices, encoding="utf-8")

    # 6. server configs
    rules = header_rules(csp)
    (site / "_headers").write_text(render_cf_headers(rules, version), encoding="utf-8")
    (out / "server/Caddyfile").write_text(render_caddyfile(rules, version, host), encoding="utf-8")

    print(f"Gezichten Vervagen v{version}  ({date})  base URL: {base_url}")
    if base_url == PLACEHOLDER_URL:
        print("  ! base URL is still the PLACEHOLDER: rebuild with --base-url before going public")
    if LICENSE_IS_PLACEHOLDER:
        print("  ! LICENSE.txt is still the PLACEHOLDER text")
    print(f"  app      {human(len(app_bytes))}  sha256 {html_sha}")
    print(f"  zip      {human(len(zip_bytes))}  sha256 {zip_sha}  ({zip_name})")
    print(f"  output   {out}")


if __name__ == "__main__":
    main()
