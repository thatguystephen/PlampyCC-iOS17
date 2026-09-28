# Feature map: CAML diagnostic recorder

Surface: the compile-gated event recorder — admission policy, bounded ring, atomic output, descriptor-confined directory walk.

Sources: `src/CAMLDiagnostic.xm`, `src/CAMLDiagnosticCore.hpp`, `src/CAMLDiagnosticIO.hpp`, `src/CAMLDiagnostic.h`, `docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md`.

## Gates (repo root)

```bash
python3 -B tests/caml-diagnostic-contract.py
python3 -B tests/caml-diagnostic-output.py
python3 -B tests/glyph-trace-contract.py
```

What each proves:

- `caml-diagnostic-contract.py` — primitive admission is POD-only and fails closed; the compile-time constant supersedes cfprefsd (a release binary can never record, no preference can enable it); source boundary split (non-ARC hooks / ARC observers / portable policies / injected syscall adapter); deterministic descriptor construction precedes installation; invokes `tests/native-caml-diagnostic.cpp` for allowlists, dedup, ring/session bounds, short-write and state-fault transitions.
- `caml-diagnostic-output.py` — compiles `tests/native-caml-directory-walk.cpp`; the shared production walk admits the observed mobile 0755/0775 platform parents, creates and validates `CAML-Diagnostic/events.jsonl` in the rootless rewrite tree at 0700/0600, rejects adversarial symlink/ownership/mode topologies fail-closed.
- `glyph-trace-contract.py` — trace tokens stay within the fixed allowlist and wire limit and share the collector's admission/dedup/privacy path.

## Build-mode contract

Release (shipping) builds omit the Makefile's `DIAGNOSTIC` flag and can never record — `tests/static-check.ts` pins the shipping workflow to this mode. The temporary collector (`make clean package FINALPACKAGE=1 STRIP=0 DIAGNOSTIC=1 THEOS_PACKAGE_SCHEME=rootless`, build ID `plampycc-caml-observer-v2-diag`) is a local fault-isolation act only. Disposition record: `docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md` § "Shipped build disposition".

## Device gap

Collector output itself can only exist from a device run. Device proof (separate authorized task): install a collector build, open Control Center once, expand/collapse Flashlight once, pull `events.jsonl` from `/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/`. Stop immediately on zero events across two opens or any full-path/PII leak.

## Triage

No events at all → install-event `q` column (per-site installation truth) or directory admission (the `caml-diagnostic-output.py` matrix names the failing chain). Events but wrong schema → `SerializeEvent` literal block (contract test pins the exact JSON keys). Recording in a release binary → the admission gate is broken; treat as a release-safety defect.