# Feature map: package integrity

Surface: rootless packaging, code signatures, build manifest/provenance, staged asset coverage.

Sources: `Makefile`, `control`, `.github/workflows/build-rootless.yml`, `.github/workflows/emit-manifest.py`, `layout/`, `assets/`, `PROVENANCE.md`.

## Gates (repo root)

```bash
python3 -B tests/assets-contract.py
python3 -B tests/manifest-contract.py
python3 -B tests/signature-contract.py
python3 -B tests/rejected-regression.py
```

What each proves:

- `assets-contract.py` — 81 CAML references each carry exactly one `/var/jb` prefix, all staged dependencies exist, and `assets/` source and `layout/` staged trees are byte-identical mirrors.
- `manifest-contract.py` — `emit-manifest.py` produces and consumer-checks all four target/architecture entries; incomplete coverage is rejected.
- `signature-contract.py` — fixture self-test: valid thin/universal CodeDirectory signatures accepted; unsigned, stale, tampered-code, tampered-hash, truncated, and malformed-directory signatures rejected. `--package` mode validates real packages from CodeDirectory hashes.
- `rejected-regression.py` — pins the Theos/SDK revision, pre-strip symbol collection, and post-strip `ldid -S` re-sign ordering.

## CI package path (required when packaging inputs change)

The host cannot build the package (the arm64e ABI requires the pinned macOS boundary). From the repo root:

```bash
gh workflow run build-rootless.yml
gh run watch
gh run download <run-id> --dir .ci-artifacts/run-<run-id>
python3 -B tests/caml-diagnostic-artifact.py .ci-artifacts/run-<run-id>/plampycc-rootless-package
```

The workflow is `workflow_dispatch` on `thatguystephen/PlampyCC-iOS17`, pinned to the Apple Silicon `macos-15` runner, Xcode 16.4, Theos `5280bd0…`, SDK `146e41ff…`. It builds release mode (`DIAGNOSTIC` flag omitted), retains unstripped companions in `symbols/{arm64,arm64e}`, strips and re-signs the packaged bytes, and emits `packages/`, `SHA256SUMS`, `build-manifest.json`, `source-commit.txt`, `toolchain.txt`, `xcode-version.txt`.

The final gate `tests/caml-diagnostic-artifact.py <artifact-dir>` runs 12 gates: source ordering/shared-walker termination, exact unstripped companions (hook/boundary/slot symbols, descriptor-before-install), single package, extracted payload ownership/modes and final CodeDirectory signatures, UUID-matched stripped arm64/arm64e hook boundaries (admission before any ownership work, original-IMP indirect call after, exactly-once record/release), literals/legacy-initializer gate, all declared checksums. It needs otool/lipo/nm — run it on macOS (the CI runner or a Mac), not on the Linux host.

## Device gap

Nothing above proves installation. Device proof (separate authorized task): `dpkg -i` the verified package on the jailbroken device, respring, confirm SpringBoard stays up and the tweak loads.

## Triage

Gate 2/4 fails → companion selection or dSYM contamination (the workflow's `select_unstripped_dylib` comments name the past failure modes). Gate 7/8/10 fails → signature lifecycle (strip/re-sign ordering). Gate 12 fails → checksum manifest drift. Rejected-regression red → a pinned historical invariant regressed; read its named violation list first.