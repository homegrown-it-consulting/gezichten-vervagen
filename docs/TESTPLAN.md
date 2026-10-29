# Manual test checklist

The automated suite (`python3 tests/test_release.py`) covers Chromium on Linux only.
This checklist covers what it can't: other browsers, real operating systems, real GPUs and real installs.
Use the validation photos in `tests/data/` (expected: sample1 = 3 faces, sample5 = 5, sample6 = 4,
groep_klein ≈ 87, gedraaid = 0 and shown upright as portrait).

Tick per platform: **W** = Windows, **M** = macOS, **L** = Linux. Put an issue number or note next to a ✗.

## A. Portable copy (unzipped release ZIP, double-click the HTML)

| # | Check | Chrome W/M/L | Edge W/M | Firefox W/M/L | Safari M |
|---|---|---|---|---|---|
| A1 | Opens by double-click; footer shows the right version | | | | |
| A2 | "Detectiemodel klaar" appears; footer says GPU (WebGL), not CPU | | | | |
| A3 | Firefox/Safari: blue notice about "Opslaan in map" is shown. Chrome/Edge: not shown | | | | |
| A4 | Drop the **folder** `tests/data` (not single files): all 5 photos load | | | | |
| A5 | Face counts match the expected values (±2 for groep_klein) | | | | |
| A6 | `gedraaid.jpg` is shown portrait (upright), not landscape | | | | |
| A7 | Grid: click toggles blur; filters work | | | | |
| A8 | Per photo: click toggles; drag adds a box; × removes it; Delete key removes the selected box | | | | |
| A9 | Preview (V) shows the mosaic | | | | |
| A10 | Export to ZIP: file downloads, opens, photos are blurred correctly | | | | |
| A11 | Chrome/Edge: "Opslaan in map" writes into a new subfolder; originals untouched | | | | |
| A12 | An exported photo has no GPS/camera data (e.g. `exiftool`, or Properties → Details on Windows, Preview → Inspector on Mac) | | | | |
| A13 | Save session → reload page → open session → load same photos: choices restored | | | | |
| A14 | F12 → Console: only the 2 expected `wasm-eval` messages; Network: no requests while working | | | | |
| A15 | Large export (e.g. 150+ phone photos) in Firefox/Safari: arrives in parts, browser asks to allow multiple downloads | | | | |

## B. Hosted version (after deploying)

| # | Check | Chrome | Edge | Firefox | Safari |
|---|---|---|---|---|---|
| B1 | Download page loads, NL/EN switch works, no console errors | | | | |
| B2 | Download button saves the ZIP (doesn't open it); its SHA-256 matches the page | | | | |
| B3 | "Open de tool" works; detection works | | | | |
| B4 | Chrome/Edge: "Installeren als app" button appears and installs; app opens in its own window with icon | | | n/a | |
| B5 | Safari (macOS 14+): File → Add to Dock works | n/a | n/a | n/a | |
| B6 | Installed app: turn Wi-Fi off, open the app → still works, detection works | | | n/a | |
| B7 | Deploy a new version → open the installed app online → footer shows the new version (may need a second open) | | | n/a | |
| B8 | `curl` checks from DEPLOY.md all pass | | | | |

## C. Realistic trial (with consent)

- [ ] A real school-event set (50–200 photos) on a typical school laptop: time the detection and note the GPU/CPU line in the footer.
- [ ] A non-technical staff member completes load → review → export without help. Note where they hesitate.
- [ ] Count missed faces and false positives per 100 photos; note sideways/occluded cases.
