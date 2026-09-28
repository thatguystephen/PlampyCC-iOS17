# PlampyCC verification map

This directory is the maintained source for verifying the user-facing behavior of PlampyCC, a jailbreak tweak whose surface is the iOS Control Center module shelf (plus its Settings preference pane). Read this index before driving anything, then use the matching feature file as the recipe.

## Feature index (feature file -> surface -> harness -> boundary)

| Feature file | Surface | Harness | Boundary |
| --- | --- | --- | --- |
| [flashlight-glyphs.md](./flashlight-glyphs.md) | Control Center Flashlight module: glyph substitution, optical sizing, on/off state | native optical-policy harness (`python3 -B tests/flashlight-optical-contract.py`) | host contracts (constants, wiring, models); UIKit rendering is device-only |
| [caml-replacement-route.md](./caml-replacement-route.md) | Animated CAML module package replacement at the three verified setter seams + live reconcile | native CAML replacement-core harness (`python3 -B tests/caml-diagnostic-contract.py`) | host contracts (hook ordering, ownership, routing wiring); runtime observations are device-only |
| [caml-diagnostic-recorder.md](./caml-diagnostic-recorder.md) | Compile-gated diagnostic event recorder (admission, ring, atomic output) | native diagnostic harness (`python3 -B tests/caml-diagnostic-output.py`) | host contracts (admission, walk, schema); collector output itself is device-only |
| [package-integrity.md](./package-integrity.md) | Rootless packaging, signatures, manifest/provenance, staged assets | package verifier harness (`bun /home/steph/.hermes/skills/software-development/theos-package-build/scripts/verify-package.ts --json <artifact-dir>`) | verified CI artifact (12 gates); installation is device-only |
| [prefs-and-registration.md](./prefs-and-registration.md) | Settings preference pane: build discipline and the registration chain | prefs ARC harness (`python3 -B tests/prefs-arc-contract.py`) | host contracts (flags, registration shapes); pane loading is device-only |

## Baseline preconditions

- Run from the repo root of `/home/steph/github/PlampyCC-iOS17` on the Linux host with `python3`, `g++`, `bun` on `PATH`.
- `git status --porcelain` shows exactly the intended diff before and after the drive.
- The preserved CI artifact `.ci-artifacts/run-36345021394/plampycc-rootless-package/` exists for Launch (see `../SKILL.md`).
- Never drive a device you were not explicitly authorized to touch.

## Driving conventions

- Start every recipe from the baseline state unless its preconditions say otherwise.
- Treat every command as literal. Keep quoted names and flags unchanged.
- Each gate prints one PASS line and exits nonzero on a violation — a failure is a real defect, not a flake.
- The Python gates compile and run the native C++ policies themselves; there is no separate native step.
- Restore any fixture state a recipe mutates. Do not remove proof artifacts during cleanup.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final output.
- Gate proof includes the command, stdout, stderr, exit code, and the PASS line.
- Package proof includes the verifier's [ADDRESS] result (all twelve gates).
- Record the feature ID and entry point used with every artifact.
- Report an unreachable path with the attempted command and the unmet precondition.
- Do not report a skipped entry point as verified through a different path; the device-only gap is always stated explicitly.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior (with its source pointers), then the four H2 sections in this order — `Sub-features`, `How to get to it (user POV)`, `Driving it with <harness>` (harness named per file), `Gotchas` — followed by `Observable proof` stating what a completed run must show at the available boundary and what remains device-only.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.
