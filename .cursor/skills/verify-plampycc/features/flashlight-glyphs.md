# Feature map: Flashlight glyph sizing and state

Surface: compact/header Flashlight glyph substitution, optical sizing, and on/off state mapping.

Sources: `src/Tweak.xm` (`SizedGlyphArt`, `SizedCompactGlyphArt`, `kGlyphSourceCanvas`), `src/FlashlightOpticalPolicy.hpp`, `layout/Library/Application Support/PlampyCC/{Plampy,Pulsar}/Icon/Flashlight{On,Off}.png`, `docs/FLASHLIGHT-OPTICAL-SIZING.md`, `docs/FLASHLIGHT-DIAGNOSTIC.md`.

## Gates (repo root)

```bash
python3 -B tests/flashlight-optical-contract.py
python3 -B tests/flashlight-asset-contract.py
python3 -B tests/glyph-trace-contract.py
python3 -B tests/icon-cache-contract.py
```

What each proves:

- `flashlight-optical-contract.py` — compiles `tests/native-flashlight-optical.cpp` against the production `FlashlightOpticalPolicy.hpp` constants and asserts the measured-peer bounds (scale 79/52 within [73/53, 80/51]; geometric-equality and raw-canvas fallbacks rejected; feedback model stable). Also asserts source wiring: optical policy integrated, source-canvas recovery, separate header/compact cache keys, reload invalidation.
- `flashlight-asset-contract.py` — Flashlight on/off art keeps the original 80x144 canvas and 56x80 content geometry in source and staged trees, byte-identical across packaging inputs; render sizing belongs to the peer-canvas normalization, not pixel padding.
- `glyph-trace-contract.py` — ranked Flashlight failure causes map to distinct approved trace tokens, tokens serialize untruncated under the wire limit, the header-glyph observer is class/state-bounded and shares the collector's admission/dedup/privacy path.
- `icon-cache-contract.py` — icon identity/cache convergence and reload invalidation; header-glyph substitution fails open on disabled state, other classes, and nil/missing/invalid themed images; recorded forwarding decision matches the bypass/substitute/fail-open model.

## Device gap

Host gates prove constants, wiring, and models — not UIKit rendering or Objective-C association behavior. Device proof (separate authorized task): install the package, open Control Center, expand/collapse Flashlight once in each theme, confirm compact glyph matches measured peer sizing and on/off states map correctly.

## Triage

Wrong size but right image → optical constants or `kGlyphSourceCanvas` recovery (optical contract names the bound that failed). Right size but wrong state → `FlashlightOn`/`FlashlightOff` slot mapping in `Tweak.xm`. Stock glyph showing → substitution admission or asset path (icon-cache contract's fail-open cases).