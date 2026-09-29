---
name: verify-plampycc
description: "Use when verifying a PlampyCC-iOS17 change before handoff or acceptance. PlampyCC is a jailbreak tweak whose user surface is the iOS Control Center module shelf (Flashlight glyphs, animated CAML module packages, a Settings preference pane). Runs the repo-grounded host gates per feature map, verifies the rootless package when packaging is touched, and stops at the device boundary."
---

# Verify PlampyCC

Verification is host-first: every claim is a command in this repo with its output captured. A green host suite is source-and-contract proof, never device/runtime proof — the report always ends with the remaining device-only gap. The device boundary is hard: no SSH, install, respring, or on-device log collection unless a separate task explicitly authorizes device work.

## Launch

For this tweak, "launch" is the build boundary: a verified rootless package. The host cannot compile the arm64e ABI — that requires the pinned macOS CI boundary — so the default lane verifies a preserved CI artifact instead of building one.

Non-device lane (default; always available, no dispatch):

```bash
bun /home/steph/.hermes/skills/software-development/theos-package-build/scripts/verify-package.ts --json .ci-artifacts/run-36345021394/plampycc-rootless-package
```

Ready when the JSON result reports all twelve gates passing (deb payload ownership/modes, unstripped companions, final CodeDirectory signatures, declared checksums, manifest). The named artifact is the preserved output of CI run run-36345021394.

CI lane (only when the change touches packaging inputs AND a separate task explicitly authorizes a dispatch):

```bash
gh workflow run build-rootless.yml
gh run watch
gh run download <run-id> --dir .ci-artifacts/run-<run-id>
python3 -B tests/caml-diagnostic-artifact.py .ci-artifacts/run-<run-id>/plampycc-rootless-package
```

The workflow is `workflow_dispatch` on `thatguystephen/PlampyCC-iOS17`, pinned to the Apple Silicon `macos-15` runner, Xcode 16.4, Theos `5280bd0…`, SDK `146e41ff…`. It builds release mode (the `DIAGNOSTIC` flag omitted), retains unstripped companions in `symbols/{arm64,arm64e}`, strips and re-signs the packaged bytes, and emits `packages/`, `SHA256SUMS`, `build-manifest.json`, `source-commit.txt`, `toolchain.txt`, `xcode-version.txt`. `tests/caml-diagnostic-artifact.py` needs otool/lipo/nm and runs on macOS only (the CI runner or a Mac), not on the Linux host — on this host use the non-device lane's `verify-package.ts` instead.

Teardown: none. `.ci-artifacts/` is preserved input evidence, not verification-started state — never delete it.

## Doctor

One read-only answer to "is this tree worth driving?" — the full cross-cutting suite plus read-only project inspection, run from the repo root on the Linux host (python3, g++, bun):

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
bun install --frozen-lockfile
./node_modules/.bin/tsc --noEmit
bun tests/static-check.ts
bun tests/theme-manifest-parity.ts
bun tests/theme-catalog-generation.ts
bun tests/theme-catalog-validation.ts
bun tools/theme-catalog/generate.ts --check
bun /home/steph/.hermes/skills/software-development/theos-package-build/scripts/inspect-project.ts . --json
```

Healthy when: all eighteen gate commands exit 0 and their PASS lines are captured (`bun install --frozen-lockfile` is a prerequisite, not a gate); `inspect-project.ts` reports no violations beyond the documented baseline below (warnings do not block); `git status --porcelain` shows exactly the intended diff — a working tree that differs from the change under review invalidates the run.

Known inspector baseline (heuristic false positives of `inspect-project.ts`'s rootful-path scan against this repo's pinned contract; any other violation is a real finding):

- `ROOTFUL_PATH` at `tests/static-check.ts:40` — the assertion literal that *enforces* the logical install path.
- `ROOTFUL_PATH` at `src/CAMLDiagnostic.xm:262-264` — comments that forbid bare rootful literals.
- `ROOTFUL_PATH` at `prefs/Makefile:13` (`PlampyCC_INSTALL_PATH = /Library/PreferenceBundles`) — the logical path Theos's rootless scheme rewrites under `/var/jb`; `tests/static-check.ts` requires it verbatim (a second `/var/jb` prefix is the defect), and the verified package proves the rewrite (`./var/jb/Library/PreferenceBundles/...`).
- `PRIVATE_FRAMEWORK_IMPORT` warnings at `prefs/RootListController.m:2-3` (`Preferences/PSListController.h`, `Preferences/PSSpecifier.h`) — warnings only, non-blocking.

The Python gates compile and run the native C++ policies themselves (`g++`/`c++`): `caml-diagnostic-contract.py` builds `tests/native-caml-diagnostic.cpp`, `caml-diagnostic-output.py` builds `tests/native-caml-directory-walk.cpp`, `flashlight-optical-contract.py` builds `tests/native-flashlight-optical.cpp`. The theme-catalog generation gate follows the same self-compile pattern (`tests/theme-catalog-generation.ts` builds `tests/native-theme-catalog.cpp`). There is no separate native step and no host-side package build — the arm64e ABI requires the pinned macOS CI boundary.

## Drive

Map the change to its feature file(s) in `features/` (index: `features/README.md`):

- Flashlight glyph sizing/state/icons → `features/flashlight-glyphs.md`
- Animated CAML replacement/reconciliation → `features/caml-replacement-route.md`
- Diagnostic recorder/admission/output → `features/caml-diagnostic-recorder.md`
- Packaging, signatures, manifest, staged assets → `features/package-integrity.md`
- Preference bundle/registration → `features/prefs-and-registration.md`
- Theme catalog / M0 manifest / generated stock catalog → `features/theme-catalog.md`

A change spanning several surfaces runs each map; docs/cleanup-only changes run the cross-cutting suite once. Completion: every touched surface has a map.

Each feature file's `Driving it with <harness>` section is the drive recipe: the user action the harness stands for, the exact command, and the observable result. Drive to the boundary that harness can reach. Host gates prove constants, wiring, and models — not UIKit rendering, Objective-C association behavior, or installation. Device interaction (SSH, install, respring, on-device logs) is authorized only by a separate task naming it; when verification needs runtime proof, stop and report the exact commands and evidence that task must collect (install command, interaction steps, expected log/visual outcome — see the `Observable proof` section of the relevant feature file). A SpringBoard crash, zero events across two Control Center opens, or any full-path/PII leak in collector output ends a device run immediately.

Completion: every drive command exited 0 and its PASS line is captured for the report.

## Evidence

Proof goes under `evidence/verify-<YYYYMMDD-HHMM>/` at the repo root (create it at run start, named with the run's local timestamp). Capture:

- the Launch invocation and its full verifier output (all twelve gates, JSON included),
- every Doctor command with stdout, stderr, and exit code, PASS lines intact,
- the driven feature's harness commands with their PASS lines,
- `report.md`: commands run with PASS lines, changed paths, and the device-only gap that remains.

Proof standards: exercise the real user path, not internal setters or test-only endpoints; capture the action and the resulting state, not just the final screen; verify side effects (files written, rows inserted, packages signed) alongside what is visible; mocks only where a production boundary already isolates the external system. When the safe path is a dry-run or test mode, verify what it actually skips by observing (files, network, git refs) rather than trusting its name. Never substitute a model, a fixture, or "it compiles" for runtime proof.

## Cleanup

Tear down only state the verification run started: scratch downloads, verifier temp outputs, compiled native gate binaries the gates left behind. Never kill by process name — the host lane starts no long-lived process; if a run did leave one, kill the exact PID that run started. Cleanup removes instances and scratch state, never the evidence: `evidence/verify-<YYYYMMDD-HHMM>/` and everything named in it survives teardown, and so do `.ci-artifacts/` inputs. After cleanup, confirm the evidence directory still exists and its files still open — a cleanup that eats the proof is a failed run.

## Helpers

Repo gates live in `tests/` and are invoked exactly as shown above. Three named helpers:

- `bun /home/steph/.hermes/skills/software-development/theos-package-build/scripts/inspect-project.ts . --json` — read-only Makefile, metadata, path, import, workflow, and artifact inspection; exits nonzero on a violation, warnings alone do not block.
- `bun /home/steph/.hermes/skills/software-development/theos-package-build/scripts/verify-package.ts --json <artifact-dir>` — twelve-gate deb, Mach-O, checksum, symbol, and manifest verifier for a downloaded CI artifact directory.
- `python3 -B tests/caml-diagnostic-artifact.py <artifact-dir>` — the CI-side twelve-gate artifact gate (source ordering/shared-walker termination, exact unstripped companions, single package, payload ownership/modes, final CodeDirectory signatures, UUID-matched stripped hook boundaries, literals gate, declared checksums); needs otool/lipo/nm, so it runs on macOS only.
