# Deploying Gezichten Vervagen

## 0. Before the first public release

| # | Open point | Where |
|---|---|---|
| 1 | **Choose the site address**: repository variable `GV_BASE_URL` (see §2a), or `python3 build.py --base-url https://<your-address>/` | README, download page, footer link and Caddyfile all use it |
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

## 2a. GitHub Releases + Cloudflare Pages (recommended)

Releases are built **once**, by GitHub Actions (`.github/workflows/release.yml`), when you push a version tag:

```
git tag v0.1.0  ──▶  GitHub Actions: build.py ──┬──▶ GitHub Release   (ZIP + SHA256SUMS.txt, provenance attestation)
                                                 └──▶ Cloudflare Pages (dist/site; download button → release asset)
```

Same bytes in both places, so the checksums on the download page always match the release. Pushing to `main`
does **not** change the live site; only a tag does.

### One-time setup

1. **Cloudflare: stop the automatic Git builds.** Your Pages project is connected to Git. That can't be switched to
   direct upload, but automatic deployments can be turned off, after which Wrangler can deploy to it:
   Workers & Pages → your project → **Settings → Build → Branch control** → turn off
   *Enable automatic production branch deployments*, and set *Preview branch* to **None**.
   (Environment variables you set in Cloudflare are no longer used; `GV_BASE_URL` moves to GitHub, step 3.)
2. **Cloudflare API token:** My Profile → **API Tokens** → *Create Token* → *Create Custom Token*,
   permission **Account · Cloudflare Pages · Edit**, limited to your account. Copy it.
   Your **Account ID** is on the Workers & Pages overview page.
3. **GitHub:** repository **Settings → Secrets and variables → Actions**:

   | Kind | Name | Value |
   |---|---|---|
   | Secret | `CLOUDFLARE_API_TOKEN` | the token from step 2 |
   | Secret | `CLOUDFLARE_ACCOUNT_ID` | your account ID |
   | Variable | `CF_PAGES_PROJECT` | the Pages project name |
   | Variable | `GV_BASE_URL` | `https://<project>.pages.dev/` (later your own domain) |

4. **GitHub:** **Settings → General → Releases** → enable **immutable releases** (published assets and their tag can
   then never be changed or moved). Do this before the first release.
5. Make the repository **public** before the first release: downloads, attestations and the EUPL source notice all
   point to it. (Build-provenance attestations on a *private* repository need a paid GitHub plan.)

### Releasing

1. Bump `VERSION` and add the matching block at the top of `CHANGELOG.md` (`### nl` / `### en`).
2. Optional but recommended: `python3 build.py && python3 tests/test_release.py --quick`.
3. Commit, then tag and push both:
   ```bash
   git tag v0.1.0
   git push github main v0.1.0
   ```
4. Watch **Actions → Release**. The workflow stops if the tag and `VERSION` differ or the variables are missing.
   It publishes the release first, then the site, then compares the live `/app/` with the build.

A mistake in a published release can't be fixed in place (immutable): release a new patch version instead.

### Custom domain

Add it in the Pages project (**Custom domains**), change the `GV_BASE_URL` variable, and release a new version
(the address is written into the files at build time).

### Cloudflare features to switch off

Each of these changes the HTML that's served, which conflicts with the strict security policy and/or the published
checksum. Switch them off for this site/zone if they're on:
- Rocket Loader
- Email Address Obfuscation (Scrape Shield)
- Web Analytics *automatic* setup (JS snippet injection) and Zaraz
- Any HTML-rewriting Worker / Snippet on this hostname

### Manual checks after a release

```bash
curl -sI https://<address>/app/ | grep -i -E 'content-security|cache-control'
curl -s https://<address>/app/ | sha256sum          # must equal SHA256SUMS.txt
curl -sI https://<address>/app/manifest.webmanifest | grep -i content-type
gh attestation verify gezichten-vervagen-v0.1.0.zip --repo homegrown-it-consulting/gezichten-vervagen
```
If the served `/app/` hash differs from `SHA256SUMS.txt`, something in Cloudflare is rewriting the page (see above).

## 2b. Caddy

1. Copy `dist/site/` to the server, e.g. `/srv/gezichten-vervagen/`.
2. Import `dist/server/Caddyfile` in your main Caddyfile (`import /etc/caddy/gezichten-vervagen.caddy`), or paste the site block.
   Set the address and root via environment variables or by editing the defaults:
   `GV_SITE_ADDRESS=vervagen.example.nl  GV_SITE_ROOT=/srv/gezichten-vervagen`
3. `caddy validate --config /etc/caddy/Caddyfile` then `systemctl reload caddy`.
4. Run the same `curl` checks as above.

Without `--release-repo` / `GV_RELEASE_REPO`, the build hosts the ZIP itself under `/download/` (self-hosted mode).
If Cloudflare proxies a Caddy origin (orange cloud), the features listed in 2a must be off there too.

## 3. Updating to a new version

Cloudflare Pages + GitHub: follow *Releasing* in §2a.
Caddy: bump `VERSION` + `CHANGELOG.md`, run `python3 build.py --base-url …` and the tests, then deploy `dist/site/`
and `dist/server/Caddyfile` together. Old ZIPs can stay in `download/`.

Installed apps pick up the new version the next time they're opened online. USB copies don't; their users compare
the version in the footer with the download page.

## 4. What the headers do

| Path | Notable headers |
|---|---|
| all | `nosniff`, `Referrer-Policy: no-referrer`, camera/mic/location disabled, no framing, HSTS |
| `/` | CSP without any script permission (the download page has no JavaScript) |
| `/app/` | Same CSP as inside the HTML (`connect-src 'none'`), plus `frame-ancestors 'none'`; `no-cache` so updates arrive |
| `/app/sw.js` | Its own CSP (`connect-src 'self'`): the service worker may only fetch the tool's own files |
| `/download/*` | Self-hosted mode only: `Content-Disposition: attachment`, cached as immutable (file names are versioned) |

## 5. Expected console messages

With the developer console open, you'll see **two** messages saying a WebAssembly compile was refused (`wasm-eval`). They come from *long.js*, a small integer-maths helper inside TensorFlow.js. It tries an optional speed-up inside a try/catch; the security policy blocks it and the helper falls back to plain JavaScript. Detection results are unaffected (verified against the validation set). Any **other** CSP message is unexpected and worth reporting.
