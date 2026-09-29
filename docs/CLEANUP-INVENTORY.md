# Cleanup inventory and diagnostics disposition — 2026-09-27

Post-build cleanup pass (task `t_274f0c57`). Rule applied: remove only artifacts proven unnecessary; classify everything else and leave it in place. Evidence is never deleted blindly — each deletion below carries a reproduction command.

**M1 supersession note (added later).** This inventory records the 2026-09-27 cleanup state and predates the M1 static-substitution subtraction (`docs/M1-STATIC-SUBTRACTION-CUTOVER.md`): `src/FlashlightOpticalPolicy.hpp` and the optical/cache/asset/trace contract tests referenced below were deleted at M1. History is retained as written; the current host gate is `tests/m1-static-subtraction-contract.py`.

## Deleted (proven unnecessary)

| Artifact | Proof it is unnecessary | Reproduce |
| --- | --- | --- |
| `tests/__pycache__/`, `.github/workflows/__pycache__/` | Python bytecode caches; regenerated on every interpreter run | regenerated automatically |
| `evidence/run-35869288564-new/payload/` (371 entries) | byte-for-byte `dpkg-deb -x` extraction of the preserved `.ci-artifacts/run-35869288564-new/packages/xyz.cypwn.plampycc_1.0.2-1_iphoneos-arm64.deb`; a fresh extraction diffed against the tree (`diff -r`) exited 0 with zero differences before deletion | `dpkg-deb -x .ci-artifacts/run-35869288564-new/packages/xyz.cypwn.plampycc_1.0.2-1_iphoneos-arm64.deb <dest>`; the run's `payload-list.txt`, `ci.log`, `control.txt` remain as manifest and provenance |

## Kept (classified)

| Artifact | Classification and rationale |
| --- | --- |
| `xyz.cypwn.plampycc_1.0.deb` | upstream clean-room input package; sha256 `70c81dd2…ecca54` matches the hash recorded in `evidence/caml-static/PROVENANCE.md`. Packaging/reference input, kept on disk and deliberately untracked (publishing the upstream binary is not authorized) |
| `.ci-artifacts/**` (41 MB) | downloaded CI artifacts backing accepted runs: unstripped arm64/arm64e symbol companions, `SHA256SUMS`, build manifests, gate logs, verifier handoffs. Not regenerable long-term — GitHub Actions artifact retention expires — so this is the durable copy |
| `evidence/caml-static/**`, `evidence/*.md`, `evidence/flashlight-optical-*` | clean-room static-analysis inputs and measured checks; the audit basis for the reconstruction |
| `evidence/run-35820863867/**` | reproducible verification fixture (`verify_exact.py`, `verification-command.txt`, checksummed reports) |
| `reviews/**` | review verdicts plus the candidate binaries those verdicts cite |
| `daisy-rework-handoff.md`, `daisy-rework-3-handoff.md`, `reviewer-report.md`, `reviewer-report-97eabba.md`, `reviewer-report-d3600d9.md` | historical handoff/review reports, cross-referenced by one another by path; kept in place so the references stay valid. Known pre-existing gap: `reviewer-report-97eabba.md` cites `daisy-rework-2-handoff.md`, which is absent from the tree and was not reconstructed |
| `docs/CAML-DIAGNOSTIC-DESIGN.md`, `docs/CAML-STATIC-ANALYSIS.md` | design/static-analysis docs referenced by tracked source and docs, intentionally untracked: publication of upstream-derived analysis is gated per `reviews/CAML-DIAGNOSTIC-REVIEW.md` ("publish only an explicitly authorized sanitized subset"; do not publish raw proprietary disassembly) |
| source (`src/`, `tests/`, `prefs/`), packaging inputs (`layout/`, `assets/`, `control`, `Makefile`, workflows) | untouched |

`.gitignore` now excludes the regenerable classes (`__pycache__/`, `*.pyc`, `.theos/`, `packages/`, `dist/`). The evidence directories stay visible-but-untracked on purpose.

## Companion record

`docs/REPO-CLEANUP-[PHONE].md` is the parallel cleanup pass's fuller record (per-set `.ci-artifacts/` disposition with citations, the supplied-package provenance of `xyz.cypwn.plampycc_1.0.deb`). Two additional proven-duplicate containers were removed by that pass and are recorded there: `.ci-artifacts/run-36264722853-zip/` (byte-identical to `run-36264722853/`) and `reviews/candidate-15327c1-artifact.zip` (byte-identical to `caml-diagnostic-15327c1/` contents). Both were moved, not deleted: the bytes sit in tool-managed scratch `~/.hermes/profiles/daisy/cache/scratch/repo-cleanup-[PHONE]/` (verified present on disk), which auto-prunes after 24h idle.

## Diagnostics disposition

Full record: `docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md` § "Shipped build disposition".

- The recorder is compile-gated (`PLAMPYCC_DIAGNOSTIC_BUILD`): a release binary can never record, regardless of preference state. The shipping path is now the release build — the workflow's make line omits the collector flag (it previously passed `DIAGNOSTIC=1`, which is why the installed build was a recording collector build).
- The collector capability is kept, not deleted: the hook surface is also the functional CAML replacement seam, and `make … DIAGNOSTIC=1` is the proven evidence path for future fault isolation (e.g. the five `CAML-ROUTING-BLOCKER.md` device observations). Release cost is one failing-closed POD admission check per hook; no logging, allocation, or filesystem write.
- No NSLog/os_log console logging exists anywhere in `src/`; verbose-only paths remain preference-gated inside collector builds.

## Exact changed files (this task)

- `src/FlashlightOpticalPolicy.hpp` — restored the derivation comment (`kCompactScale` provenance, "NOT a header calibration" guard) stripped by an unexplained post-commit working-tree edit; the comment was introduced alongside the constants in `3ac9e78` (the header itself was deleted at M1; see the supersession note above)
- `.github/workflows/build-rootless.yml` — shipping build is release mode
- `tests/static-check.ts` — build-mode pin inverted to assert the release-mode shipping path
- `Makefile` — collector comment corrected (build-ID suffix is `-diag`, not `-ct`) and disposition stated
- `docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md` — "Shipped build disposition" section
- `.gitignore`, `docs/CLEANUP-INVENTORY.md` — new
- `.cursor/skills/verify-plampycc/**` — project-local verification skill
