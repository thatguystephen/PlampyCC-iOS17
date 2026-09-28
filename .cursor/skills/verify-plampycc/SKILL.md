---
name: verify-plampycc
description: Use when verifying a PlampyCC-iOS17 change before handoff or acceptance. Runs the repo-grounded host gates per feature map, then the CI package path when packaging is touched, and stops at the device boundary.
---

# Verify PlampyCC

Verification is host-first: every claim is a command in this repo with its output captured. A green host suite is source-and-contract proof, never device/runtime proof — the report always ends with the remaining device-only gap. The device boundary is hard: no SSH, install, respring, or on-device log collection unless a separate task explicitly authorizes device work.

## Run

1. Map the change to its feature file(s) in `features/`:
   - Flashlight glyph sizing/state/icons → `features/flashlight-glyphs.md`
   - Animated CAML replacement/reconciliation → `features/caml-replacement-route.md`
   - Diagnostic recorder/admission/output → `features/caml-diagnostic-recorder.md`
   - Packaging, signatures, manifest, staged assets → `features/package-integrity.md`
   - Preference bundle/registration → `features/prefs-and-registration.md`

   A change spanning several surfaces runs each map; docs/cleanup-only changes run the cross-cutting suite once. Completion: every touched surface has a map.

2. Run the feature map's gate commands from the repo root. Each gate prints one PASS line and exits nonzero on a violation — a failure is a real defect. Fix it or hand the task back before continuing. Completion: every command exited 0 and its PASS line is captured for the report.

3. Run the cross-cutting suite (below). Completion: all twelve commands exit 0 and `git status --porcelain` shows exactly the intended diff — a working tree that differs from the change under review invalidates the run.

4. Any change touching `src/`, `Makefile`, `layout/`, `assets/`, `control`, or `.github/workflows/` also needs the package path in `features/package-integrity.md`: dispatch the pinned CI workflow and verify the downloaded artifact with `tests/caml-diagnostic-artifact.py` (all 12 gates; runs on macOS only — it needs otool/lipo/nm). Completion: CI run URL recorded and the 12-gate PASS line captured.

5. Report: commands run with PASS lines, changed paths, and the device-only gap that remains. Never substitute a model, a fixture, or "it compiles" for runtime proof.

## Cross-cutting suite

Run from the repo root on the Linux host (python3, g++, bun):

```bash
python3 -B tests/rejected-regression.py
python3 -B tests/assets-contract.py
python3 -B tests/manifest-contract.py
python3 -B tests/signature-contract.py
python3 -B tests/caml-diagnostic-contract.py
python3 -B tests/caml-diagnostic-output.py
python3 -B tests/icon-cache-contract.py
python3 -B tests/glyph-trace-contract.py
python3 -B tests/flashlight-optical-contract.py
python3 -B tests/flashlight-asset-contract.py
python3 -B tests/prefs-arc-contract.py
bun tests/static-check.ts
```

The Python gates compile and run the native C++ policies themselves (`g++`/`c++`): `caml-diagnostic-contract.py` builds `tests/native-caml-diagnostic.cpp`, `caml-diagnostic-output.py` builds `tests/native-caml-directory-walk.cpp`, `flashlight-optical-contract.py` builds `tests/native-flashlight-optical.cpp`. There is no separate native step and no host-side package build — the arm64e ABI requires the pinned macOS CI boundary.

## Device boundary

Device interaction is authorized only by a separate task naming it. When verification needs runtime proof, stop and report the exact commands and evidence that task must collect (install command, interaction steps, expected log/visual outcome — see the device-gap section of the relevant feature map). A SpringBoard crash, zero events across two Control Center opens, or any full-path/PII leak in collector output ends a device run immediately.