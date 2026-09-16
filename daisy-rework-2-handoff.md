# Daisy rework 2 handoff

Candidate base: `d3600d9929d2a643653cb64976c4323dea73ef47`
Commit: dc3931a29eac59e4abd00349da6b715837a66af0 (non-CAML candidate; no package build was performed in this Linux session).

Completed non-CAML rework:

- Replaced the identity rootless macro with `<rootless.h>` and defined one logical runtime resource root. Staged resources now live under `layout/var/jb/var/mobile/...`; CAML references and provenance use the same installed root. Preference installation is logical (`/Library/PreferenceBundles`) so Theos applies the rootless prefix once.
- Reworked CI producer output to `dist/packages/*.deb`, `dist/symbols/{arm64,arm64e}/` with both tweak and preference targets, exact-relative `SHA256SUMS`, and the verifier's complete manifest schema via `.github/workflows/emit-manifest.py`.
- Replaced token-only checks with structural resource/path, mapping/fallback, CAML dependency, lifecycle-state, and producer-contract assertions. Every mapped icon is checked against installed layout; unsupported outcomes preserve stock and Pulsar falls back to Plampy.
- Hooks install regardless of initial enabled state. Preference notifications reconcile existing overlays on the main thread; wallpaper creation, removal, theme replacement, blur add/remove, presentation visibility, and captured stock glyph restoration are represented as explicit transitions.
- Documented original `selectImage` as deferred with no parity claim.

CAML decision:

Read-only `rg` over the supplied headers found only forward declarations/properties for `CCUICAPackageDescription`; no initializer, setter, producer, ownership, or call-site ABI. `file` identified supplied `ControlCenterUI` and `ControlCenterUIKit` as arm64e Mach-O. Filtered `nm -arch arm64e -gU` queries found no usable package-description or target symbols. No usable `rootless.h` was present in the supplied headers. CAML remains pass-through and acceptance is BLOCKED pending Steph scope waiver or better target declarations. `CAML-ROUTING-BLOCKER.md` records exact commands and evidence.

Evidence run:

- AIDA first rerun `bun tests/static-check.ts` and reached line 46; it failed because the test incorrectly searched the workflow text for `build-manifest.json`, while the workflow correctly delegates that output to `.github/workflows/emit-manifest.py`. This was a test/producer-contract mismatch, not evidence that the manifest was absent.
- Corrected `tests/static-check.ts` to verify the structured producer invocation, `Path('dist')` root, exact `dist/build-manifest.json` write, and required schema fields; it no longer weakens the manifest requirement or treats an incidental workflow token as proof.
- AIDA then ran `bun run /home/steph/github/PlampyCC-iOS17/tests/static-check.ts`: PASS, exit 0, with the structured rootless/mapping/fallback/lifecycle/CAML-dependency/CI-producer summary. The relative Bun invocation was intermittently hidden by Socket Firewall, so the absolute invocation is the accepted evidence.
- `python3 /tmp/validate_plampy.py`: PASS (offline structural/path/state/CAML dependency checks).
- `git diff --check`: PASS.
- `file`/`nm` framework inspection: completed read-only; no usable signatures.
- The profile-local `inspect-project.ts` invocation remains blocked by Socket Firewall; no inspector PASS is claimed.
- Theos inspector and verifier fixture/build were not accepted as run evidence: Bun invocation was likewise blocked, and no macOS build/deploy/device workflow was attempted.

Next gate: run `inspect-project.ts` in an environment that permits Bun repository reads, then build the exact committed SHA on the authorized pinned macOS workflow and run `verify-package.ts` against the downloaded `dist/`. CAML needs a separately authorized scope decision or verified declarations before implementation.
