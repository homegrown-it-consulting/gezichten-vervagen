# Vendored third-party files

Taken unmodified from the npm package `@vladmandic/face-api@1.7.15` (MIT):

| File | From package path |
|---|---|
| face-api.js | dist/face-api.js (bundles TensorFlow.js 4.22.0, Apache-2.0) |
| ssd_mobilenetv1_model.bin | model/ssd_mobilenetv1_model.bin |
| ssd_mobilenetv1_model-weights_manifest.json | model/ssd_mobilenetv1_model-weights_manifest.json |
| LICENSE.face-api | LICENSE |

Only the face DETECTOR (SSD MobileNet v1) is vendored. The recognition, landmark,
age/gender and expression models in that package are deliberately left out.
Checksums: SOURCES.sha256. Reproduce with `npm pack @vladmandic/face-api@1.7.15`.
