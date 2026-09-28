# CAML diagnostic recorder

The recorder is a compile-gated event collector for CAML replacement faults: POD-only admission, a bounded ring with dedup, atomic output, and a descriptor-confined directory walk. Surface: the compile-gated event recorder — admission policy, bounded ring, atomic output, descriptor-confined directory walk.

Sources: `src/CAMLDiagnostic.xm`, `src/CAMLDiagnosticCore.hpp`, `src/CAMLDiagnosticIO.hpp`, `src/CAMLDiagnostic.h`, `docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md`.

## Sub-features

- `recorder-admission` admits only POD events and fails closed; the compile-time constant supersedes cfprefsd (a release binary can never record, no preference can enable it).
- `recorder-ring` bounds the ring/session with allowlists and dedup.
- `recorder-output` writes `CAML-Diagnostic/events.jsonl` atomically in the rootless rewrite tree at 0700/0600.
- `recorder-walk` walks platform parents descriptor-confined (observed mobile 0755/0775 parents admitted; adversarial symlink/ownership/mode topologies rejected fail-closed).
- `recorder-trace` serializes approved trace tokens untruncated under the wire limit, sharing the collector's admission/dedup/privacy path.

## How to get to it (user POV)

This surface is deliberately invisible in shipping builds (release mode omits the `DIAGNOSTIC` flag). On a collector build the user path is: install the collector package, open Control Center once, expand/collapse Flashlight once — events accumulate without any user-visible UI — then read `events.jsonl` from the device's `CAML-Diagnostic/` directory.

## Driving it with the native diagnostic harness

Preconditions:

- Repo root as CWD on the Linux host (python3, g++).
- `git status --porcelain` shows exactly the intended diff.

- **Admission and ring behavior.** (Collector build action: any hook firing produces at most one admitted event per site.) Run `python3 -B tests/caml-diagnostic-contract.py`. One PASS line, exit 0. Primitive admission is POD-only and fails closed; the compile-time constant supersedes cfprefsd; source boundary split (non-ARC hooks / ARC observers / portable policies / injected syscall adapter); deterministic descriptor construction precedes installation; `tests/native-caml-diagnostic.cpp` exercises allowlists, dedup, ring/session bounds, short-write and state-fault transitions.
- **Output and walk.** (Collector build action: the first event creates the output file.) Run `python3 -B tests/caml-diagnostic-output.py`. One PASS line, exit 0. It compiles `tests/native-caml-directory-walk.cpp`; the shared production walk admits the observed mobile 0755/0775 platform parents, creates and validates `CAML-Diagnostic/events.jsonl` in the rootless rewrite tree at 0700/0600, and rejects adversarial symlink/ownership/mode topologies fail-closed.
- **Trace tokens.** Run `python3 -B tests/glyph-trace-contract.py`. One PASS line, exit 0. Trace tokens stay within the fixed allowlist and wire limit and share the collector's admission/dedup/privacy path.

## Gotchas

- No events at all → install-event `q` column (per-site installation truth) or directory admission (the `caml-diagnostic-output.py` matrix names the failing chain). Events but wrong schema → `SerializeEvent` literal block (the contract test pins the exact JSON keys). Recording in a release binary → the admission gate is broken; treat as a release-safety defect.
- Release (shipping) builds omit the Makefile's `DIAGNOSTIC` flag and can never record — `bun tests/static-check.ts` pins the shipping workflow to this mode. The temporary collector (`make clean package FINALPACKAGE=1 STRIP=0 DIAGNOSTIC=1 THEOS_PACKAGE_SCHEME=rootless`, build ID `plampycc-caml-observer-v2-diag`) is a local fault-isolation act only. Disposition record: `docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md` § "Shipped build disposition".
- `caml-diagnostic-contract.py` and `glyph-trace-contract.py` are shared with the replacement/Flashlight maps — one run covers all, do not double-report.

## Observable proof

Non-device boundary: the three gate commands above, each with one PASS line and exit 0, captured under `evidence/verify-<YYYYMMDD-HHMM>/` (e.g. `drive-caml-diagnostic-recorder.txt`), including the fail-closed adversarial walk matrix and the exact-JSON-key schema assertion.

Device-only gap (separate authorized task): install a collector build, open Control Center once, expand/collapse Flashlight once, and pull `events.jsonl` from `/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/`. Stop immediately on zero events across two opens or any full-path/PII leak. Expected evidence: the pulled `events.jsonl` with admitted, schema-valid events and no absolute paths or PII.
