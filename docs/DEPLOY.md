# Deploying Gezichten Vervagen

## 0. Before the first public release

| # | Open point | Where |
|---|---|---|
| 1 | **Choose the site address**: `GV_BASE_URL` on Cloudflare Pages, or `python3 build.py --base-url https://<your-address>/` | README, download page, footer link and Caddyfile all use it |
| 2 | **Make the GitHub repo public** (done: licence EUPL-1.2). The licence notice names the repo as the source location (EUPL Art. 3), so it must be publicly reachable once you distribute the tool | `src/docs/LICENSE.txt`, `src/app.html` |
| 3 | **Check the model licence.** The detector weights were, according to the face-api.js documentation, provided by *yeephycho* and trained on WIDER FACE. The WIDER FACE dataset card lists **CC BY-NC-ND 4.0** (non-commercial). Whether that carries over to a trained model is a legal grey area. Because you distribute as a business, get this checked, or plan the switch to a detector with clear terms | `THIRD-PARTY-NOTICES.txt` item 4 |
| 4 | Run the manual checklist in `docs/TESTPLAN.md` (Firefox, Safari, Windows, macOS, Linux) | |

Every rebuild changes nothing as long as the inputs are the same (reproducible build). Changing the base URL, the licence or the code changes the checksums. That's expected, and the download page always shows the current ones.

## 1. Build

```bash
python3 build.py --base-url https://vervagen.example.nl/
```

You deploy `dist/site/` as-is. `dist/server/Caddyfile` is for Caddy.
**The CSP script hashes in `_headers` and in the Caddyfile belong to this exact build.**
Always deploy the site and the server config of the same build together. A mismatch makes the browser refuse to run the tool (blank page with CSP errors in the console).

## 2a. Cloudflare Pages (Git integration)

Cloudflare builds the site itself on every push; `dist/` is not in Git.

1. Dashboard → **Workers & Pages** → **Create application** → choose **Pages** (not Workers) → **Connect to Git** / *Import an existing Git repository* → `homegrown-it-consulting/gezichten-vervagen`.
   If the form shows a **Deploy command** (`npx wrangler deploy`), you are in the *Workers* flow: go back and pick Pages.
2. Build settings:

   | Field | Value |
   |---|---|
   | Production branch | `main` |
   | Framework preset | `None` |
   | Build command | `python3 build.py` |
   | Build output directory | `dist/site` |
   | Root directory | *(empty)* |
   | Environment variable | `GV_BASE_URL` = `https://<project>.pages.dev/` (later your own domain) |
   | Environment variable (optional) | `PYTHON_VERSION` = `3.13` (pins the version; the v3 build image has 3.13 by default) |

   `build.py` uses only the Python standard library: no `pip install`, no `npm`.
3. **Save and Deploy**. `_headers` is picked up automatically (Pages doesn't serve it publicly).
4. Add the custom domain (**Custom domains** tab), then change `GV_BASE_URL` to it and **retry the deployment**:
   the base URL is baked into the files at build time.
   Set `GV_BASE_URL` for *Production*; preview builds (other branches) may keep the `pages.dev` value.
5. The ZIP's checksum depends on the build machine's compression library, so Cloudflare's build may produce
   a different ZIP checksum than your local build. The download page always shows the checksums of the build it
   came from; the HTML checksum is the same everywhere.
6. **Switch these off for this site/zone**, if they're on. Each one changes the HTML that's served, which conflicts with the strict security policy and/or the published checksum:
   - Rocket Loader
   - Email Address Obfuscation (Scrape Shield)
   - Web Analytics *automatic* setup (JS snippet injection) and Zaraz
   - Any HTML-rewriting Worker / Snippet on this hostname
7. Check, after deploying:
   ```bash
   curl -sI https://<address>/app/ | grep -i -E 'content-security|cache-control'
   curl -s https://<address>/app/ | sha256sum          # must equal SHA256SUMS.txt
   curl -sI https://<address>/download/<zip> | grep -i content-disposition
   curl -sI https://<address>/app/manifest.webmanifest | grep -i content-type
   ```
   If the served `/app/` hash differs from `SHA256SUMS.txt`, something in Cloudflare is rewriting the page (see step 6).

## 2b. Caddy

1. Copy `dist/site/` to the server, e.g. `/srv/gezichten-vervagen/`.
2. Import `dist/server/Caddyfile` in your main Caddyfile (`import /etc/caddy/gezichten-vervagen.caddy`), or paste the site block.
   Set the address and root via environment variables or by editing the defaults:
   `GV_SITE_ADDRESS=vervagen.example.nl  GV_SITE_ROOT=/srv/gezichten-vervagen`
3. `caddy validate --config /etc/caddy/Caddyfile` then `systemctl reload caddy`.
4. Run the same `curl` checks as above.

If Cloudflare proxies a Caddy origin (orange cloud), the step 6 settings of 2a apply too.

## 3. Updating to a new version

1. Bump `VERSION`, add a block at the top of `CHANGELOG.md` (same version, with date and `### nl` / `### en`).
2. `python3 build.py --base-url …` and `python3 tests/test_release.py`.
3. Deploy `dist/site/` (and, for Caddy, `dist/server/Caddyfile`). Old ZIPs can stay in `download/`.
4. Installed apps pick up the new version the next time they're opened online. USB copies don't; their users compare the version in the footer with the download page.

## 4. What the headers do

| Path | Notable headers |
|---|---|
| all | `nosniff`, `Referrer-Policy: no-referrer`, camera/mic/location disabled, no framing, HSTS |
| `/` | CSP without any script permission (the download page has no JavaScript) |
| `/app/` | Same CSP as inside the HTML (`connect-src 'none'`), plus `frame-ancestors 'none'`; `no-cache` so updates arrive |
| `/app/sw.js` | Its own CSP (`connect-src 'self'`): the service worker may only fetch the tool's own files |
| `/download/*` | `Content-Disposition: attachment`, cached as immutable (file names are versioned) |

## 5. Expected console messages

With the developer console open, you'll see **two** messages saying a WebAssembly compile was refused (`wasm-eval`). They come from *long.js*, a small integer-maths helper inside TensorFlow.js. It tries an optional speed-up inside a try/catch; the security policy blocks it and the helper falls back to plain JavaScript. Detection results are unaffected (verified against the validation set). Any **other** CSP message is unexpected and worth reporting.
