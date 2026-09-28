# Flashlight glyphs

Flashlight glyph substitution replaces the stock Control Center Flashlight module glyph with PlampyCC art at measured-peer optical sizing and maps the on/off state to distinct images. Surface: compact/header Flashlight glyph substitution, optical sizing, and on/off state mapping.

Sources: `src/Tweak.xm` (`SizedGlyphArt`, `SizedCompactGlyphArt`, `kGlyphSourceCanvas`), `src/FlashlightOpticalPolicy.hpp`, `layout/Library/Application Support/PlampyCC/{Plampy,Pulsar}/Icon/Flashlight{On,Off}.png`, `docs/FLASHLIGHT-OPTICAL-SIZING.md`, `docs/FLASHLIGHT-DIAGNOSTIC.md`.

## Sub-features

- `glyph-optical-sizing` renders the compact glyph at measured-peer scale (79/52 within [73/53, 80/51]; geometric-equality and raw-canvas fallbacks rejected).
- `glyph-state-mapping` maps Flashlight on → `FlashlightOn.png` and off → `FlashlightOff.png` in both themes.
- `glyph-source-recovery` recovers the original 80x144 source canvas (`kGlyphSourceCanvas`) when incoming art was resized.
- `glyph-cache` keeps separate header/compact cache keys and invalidates on theme reload.
- `glyph-fail-open` falls back to the stock glyph on disabled state, other classes, and nil/missing/invalid themed images.

## How to get to it (user POV)

- Open Control Center and look at the Flashlight module glyph in the compact row.
- Expand the Flashlight module (long-press / Haptic Touch) to see the header glyph.
- Toggle the flashlight on and off and watch the glyph image change.
- Switch between the Plampy and Pulsar themes, re-open Control Center, and compare the glyph against a measured peer module glyph.

## Driving it with the native optical-policy harness

Preconditions:

- Repo root as CWD on the Linux host ([ADDRESS], g++).
- `git status --porcelain` shows exactly the intended diff.

- **Sizing policy.** (User action: compare the compact glyph against a measured peer module glyph.) Run `python3 -B tests/flashlight-optical-contract.py`. One PASS line, exit 0. It compiles `tests/native-flashlight-optical.cpp` against the production `FlashlightOpticalPolicy.hpp` constants and asserts the measured-peer bounds (scale 79/52 within [73/53, 80/51]; geometric-equality and raw-canvas fallbacks rejected; feedback model stable), plus source wiring: optical policy integrated, source-canvas recovery, separate header/compact cache keys, reload invalidation.
- **On/off art.** (User action: toggle the flashlight and watch the glyph change.) Run `python3 -B tests/flashlight-asset-contract.py`. One PASS line, exit 0. Flashlight on/off art keeps the original 80x144 canvas and 56x80 content geometry in source and staged trees, byte-identical across packaging inputs; render sizing belongs to the peer-canvas normalization, not pixel padding.
- **Failure traceability.** Run `python3 -B tests/glyph-trace-contract.py`. One PASS line, exit 0. Ranked Flashlight failure causes map to distinct approved trace tokens, tokens serialize untruncated under the wire limit, the header-glyph observer is class/state-bounded and shares the collector's admission/dedup/privacy path.
- **Substitution admission.** (User action: open Control Center in a disabled state or on a non-PlampyCC class.) Run `python3 -B tests/icon-cache-contract.py`. One PASS line, exit 0. Icon identity/cache convergence and reload invalidation; header-glyph substitution fails open on disabled state, other classes, and nil/missing/invalid themed images; recorded forwarding decision matches the bypass/substitute/fail-open model.

## Gotchas

- Wrong size but right image → optical constants or `kGlyphSourceCanvas` recovery (the optical contract names the bound that failed). Right size but wrong state → `FlashlightOn`/`FlashlightOff` slot mapping in `Tweak.xm`. Stock glyph showing → substitution admission or asset path (icon-cache contract's fail-open cases).
- Host gates prove constants, wiring, and models — not UIKit rendering or Objective-C association behavior.
- The gates compile native C++ themselves (`tests/native-flashlight-optical.cpp`); do not run a separate native build step.
- `glyph-trace-contract.py` is shared with the recorder map — one run covers both, do not double-report.

## Observable proof

Non-device boundary (what one verification run must reach): the four gate commands above, each with one PASS line and exit 0, captured under `evidence/verify-<YYYYMMDD-HHMM>/` (e.g. `drive-flashlight-glyphs.txt`) at a repo state whose `git status --porcelain` matches the change under review.

Device-only gap (separate authorized task): install the package on the jailbroken iPhone, open Control Center, expand/collapse Flashlight once in each theme (Plampy and Pulsar), and confirm the compact glyph matches measured peer sizing and the on/off states map correctly. Expected evidence: one screen capture per theme per state showing PlampyCC glyph art at peer scale.
