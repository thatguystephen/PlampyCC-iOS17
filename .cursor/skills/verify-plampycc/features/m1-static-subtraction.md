# M1 static-substitution subtraction

M1 removes every PlampyCC-owned static, compact, Flashlight, and header glyph
substitution route, so the Flashlight module and every static/custom glyph path
are stock by construction, while overlay wallpaper/blur/presentation and the
animated CAML route keep their existing hooks. Surface: absence of the removed
substitution surface, retained overlay/CAML behavior, and an empty-Q0,
byte-identical M0 catalog. Sources: `src/Tweak.xm`, `src/CAMLDiagnostic.*`,
`src/CAMLDiagnosticCore.hpp`, `tests/m1-static-subtraction-contract.py`,
`docs/M1-STATIC-SUBTRACTION-CUTOVER.md`.

## Sub-features

- `substitution-absence` — no removed substitution IMP, predecessor slot, installer call edge, ownership key, cache/registry, render helper, ancestry/identifier route, delayed probe, compact/header substitution hook, or substitution-only trace name remains in production source.
- `no-glyph-replacement` — no non-CAML hook can replace a module glyph: no glyph-setter write exists in source, and the header-glyph selector's remaining hook is the observer-only diagnostic seam (removed atomically at [ADDRESS] only — hook bodies, predecessor slots, installer edges, preference publication, and the three verified CAML setter seams keep working exactly as before.
- `catalog-stock-boundary` — the generated M0 Q0 catalog is byte-identical to accepted base `7f8a314`, activation is empty, and every static/Flashlight catalog capability resolves stock-only.
- `cutover-boundary` — `docs/M1-STATIC-SUBTRACTION-CUTOVER.md` states the verified-stock installation boundary (verified stock SpringBoard state; separately authorized clean SpringBoard restart + stock verification; no device action in this milestone).

## How to get to it (user POV)

- Open Control Center and look at the Flashlight module: its glyph is the stock SF Symbol in every theme and state.
- Expand/collapse the overlay: wallpaper, blur, and presentation animation behave as before.
- Switch themes in Settings and re-open Control Center: enable/disable/theme preferences still publish to the retained behavior.

## Driving it with the M1 stock-preservation/deletion contract

Preconditions:

- Repo root as CWD on the Linux host ([ADDRESS], bun).
- `git status --porcelain` shows exactly the intended diff.

- **Deletion + preservation.** (User action: the whole surface above.) Run `python3 -B tests/m1-static-subtraction-contract.py`. One PASS line, exit 0. It asserts the full removal inventory is absent from production source, no non-CAML hook can replace a module glyph, overlay wallpaper/presentation and the CAML route keep hooks/predecessor slots/installer edges, the M0 Q0 catalog is byte-identical with empty activation and stock-only static/Flashlight routes, the cutover note carries the installation boundary, and the gate wiring/count is coherent.
- **Red proof.** The same command on base `7f8a314` fails on its first absence assertion (the removed identifiers still exist there) — capture both runs when proving a subtraction.

## Gotchas

- The M0 generated tables (`src/generated/`) legitimately name `FlashlightOn`/`FlashlightOff` as stock aliases; the absence scan covers hand-written source only, and the generated tables are separately gated as byte-identical to base.
- The header-glyph **diagnostic observer** (site 7) is not a substitution hook: it forwards unchanged and is removed atomically at [ADDRESS] five non-setter diagnostic interceptors. Do not delete it in an M1 change.
- Staged Flashlight/Icon PNGs remain inert package payload (mirror-checked by `tests/assets-contract.py`); nothing loads them after M1.
- Host gates prove source shape and catalog state — not UIKit rendering or installation.

## Observable proof

Non-device boundary: `python3 -B tests/m1-static-subtraction-contract.py` with one PASS line and exit 0 at a repo state whose `git status --porcelain` matches the change under review, plus the red run on base `7f8a314` failing. Package-slice absence (arm64/arm64e symbols) requires the pinned macOS CI build and is reported BLOCKED for AIDA's H0 CI run until that runs.

Device-only gap (separate authorized task): install from a verified stock SpringBoard state per `docs/M1-STATIC-SUBTRACTION-CUTOVER.md`, then confirm Flashlight and every static module render stock in both themes with overlay wallpaper/presentation unchanged.
