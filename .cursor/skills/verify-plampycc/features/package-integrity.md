# Package integrity

Package integrity covers the rootless packaging pipeline end to end: staged asset coverage, manifest/provenance emission, code signatures, and the verified CI artifact. Surface: rootless packaging, code signatures, build manifest/provenance, staged asset coverage.

Sources: `Makefile`, `control`, `.github/workflows/build-rootless.yml`, `.github/workflows/emit-manifest.py`, `layout/`, `assets/`, `PROVENANCE.md`.

## Sub-features

- `pkg-assets` stages every CAML reference with exactly one `/var/jb` prefix and keeps `assets/` source and `layout/` staged trees byte-identical mirrors.
- `pkg-manifest` emits and consumer-checks all four target/architecture manifest entries.
- `pkg-signatures` accepts valid thin/universal CodeDirectory signatures and rejects unsigned, stale, tampered-code, tampered-hash, truncated, and malformed-directory ones.
- `pkg-provenance` pins the Theos/SDK revision, pre-strip symbol collection, and post-strip `ldid -S` re-sign ordering, and declares all checksums.

## How to get to it (user POV)

- The user-visible outcome is a single installable rootless `.deb` that installs cleanly on the jailbroken iPhone (Settings pane appears, tweak loads after respring).
- A verifier reaches the same surface by inspecting the CI artifact the workflow publishes: `packages/`, `SHA256SUMS`, `build-manifest.json`, `source-commit.txt`, `toolchain.txt`, `xcode-version.txt`, and `symbols/{arm64,arm64e}`.

## Driving it with the package verifier harness

Preconditions:

- The preserved artifact `.ci-artifacts/run-36345021394/plampycc-rootless-package/` exists (Launch lane in `../SKILL.md`), or a separately authorized CI dispatch produced `.ci-artifacts/run-<run-id>/plampycc-rootless-package`.
- Repo root as CWD on the Linux host ([ADDRESS], g++, bun) for the contract gates.

- **Staged assets.** Run `python3 -B tests/assets-contract.py`. One PASS line, exit 0. 81 CAML references each carry exactly one `/var/jb` prefix, all staged dependencies exist, and `assets/` source and `layout/` staged trees are byte-identical mirrors.
- **Manifest coverage.** Run `python3 -B tests/manifest-contract.py`. One PASS line, exit 0. `emit-manifest.py` produces and consumer-checks all four target/architecture entries; incomplete coverage is rejected.
- **Signature policy.** Run `python3 -B tests/signature-contract.py`. One PASS line, exit 0. Fixture self-test: valid thin/universal CodeDirectory signatures accepted; unsigned, stale, tampered-code, tampered-hash, truncated, and malformed-directory signatures rejected. `--package` mode validates real packages from CodeDirectory hashes.
- **Historical invariants.** Run `python3 -B tests/rejected-regression.py`. One PASS line, exit 0. The Theos/SDK pin, pre-strip symbol collection, and post-strip `ldid -S` re-sign ordering all hold.
- **Artifact proof.** Run `bun /home/steph/.hermes/skills/software-development/theos-package-build/scripts/verify-package.ts --json .ci-artifacts/run-36345021394/plampycc-rootless-package`. All twelve gates pass in the [ADDRESS] result: source ordering/shared-walker termination, exact unstripped companions (hook/boundary/slot symbols, descriptor-before-install), single package, extracted payload ownership/modes and final CodeDirectory signatures, UUID-matched stripped arm64/arm64e hook boundaries (admission before any ownership work, original-IMP indirect call after, exactly-once record/release), literals/legacy-initializer gate, all declared checksums.
- **CI lane (only when packaging inputs change AND a dispatch is separately authorized).** Run `gh workflow run build-rootless.yml`, then `gh run watch`, `gh run download <run-id> --dir .ci-artifacts/run-<run-id>`, then `[ADDRESS] -B tests/caml-diagnostic-artifact.py .ci-artifacts/run-<run-id>/plampycc-rootless-package`. Record the CI run URL and the 12-gate PASS line. This last gate needs otool/lipo/nm and runs on macOS only.

## Gotchas

- The host cannot build the package — the arm64e ABI requires the pinned macOS CI boundary (`macos-15`, Xcode 16.4, Theos `5280bd0…`, SDK `146e41ff…`). Never attempt a host-side `make package` as proof.
- Gate 2/4 fails → companion selection or dSYM contamination (the workflow's `select_unstripped_dylib` comments name the past failure modes). Gate 7/8/10 fails → signature lifecycle (strip/re-sign ordering). Gate 12 fails → checksum manifest drift. Rejected-regression red → a pinned historical invariant regressed; read its named violation list first.
- The workflow builds release mode (`DIAGNOSTIC` flag omitted): a collector package is never the shipping artifact.

## Observable proof

Non-device boundary: the four contract gates plus the artifact verifier, each with one PASS line / all-twelve-gates JSON, captured under `evidence/verify-<YYYYMMDD-HHMM>/` (e.g. `launch-verify-package.json`, `drive-package-integrity.txt`).

Device-only gap (separate authorized task): `dpkg -i` the verified package on the jailbroken iPhone, respring, confirm SpringBoard stays up and the tweak loads. Expected evidence: the dpkg transcript, a respring with no crash logs, and the PlampyCC pane visible in Settings.
