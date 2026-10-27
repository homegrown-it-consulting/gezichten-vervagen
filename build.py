#!/usr/bin/env python3
"""Inline face-api + SSD MobileNet detector weights into one offline HTML file.

Only the face *detector* is bundled. The recognition/landmark/age models in the
face-api package are deliberately left out, so the result cannot identify people.
"""
import base64, json, pathlib, sys

here = pathlib.Path(__file__).parent
pkg = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else here.parent / "package")
out = here / "gezichten-vervagen.html"

src = (here / "src.html").read_text(encoding="utf-8")
lib = (pkg / "dist/face-api.js").read_text(encoding="utf-8")
manifest = json.loads((pkg / "model/ssd_mobilenetv1_model-weights_manifest.json").read_text())
weights = (pkg / "model/ssd_mobilenetv1_model.bin").read_bytes()

for bad in ("</script", "<!--", "<script"):
    if bad in lib.lower():
        sys.exit(f"bundle contains {bad!r}; cannot inline safely")

b64 = base64.b64encode(weights).decode()
b64 = "\n".join(b64[i:i + 4096] for i in range(0, len(b64), 4096))

html = (src
        .replace("/*__FACEAPI__*/", lib, 1)
        .replace("/*__MANIFEST__*/", json.dumps(manifest, separators=(",", ":")), 1)
        .replace("/*__WEIGHTS__*/", b64, 1))
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
