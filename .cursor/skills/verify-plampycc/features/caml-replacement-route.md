# Feature map: animated CAML replacement route

Surface: construct-and-pass CAML package-description replacement on the three verified setter seams, plus live preference reconciliation.

Sources: `src/CAMLReplacement.xm` (Objective-C adapter), `src/CAMLReplacementCore.hpp` (production decision policy: `ClassifyIncoming`, `PlanConstruction`, `RecordInstall`, `ObserveReconcile`, `PlanReconcileAction`), `src/CAMLDiagnosticHooks.mm` (the seven non-ARC hook IMPs), `src/CAMLVerifiedABI.h`, `CAML-ROUTING-BLOCKER.md` (status).

## Gates (repo root)

```bash
python3 -B tests/caml-diagnostic-contract.py
python3 -B tests/rejected-regression.py
bun tests/static-check.ts
```

What each proves:

- `caml-diagnostic-contract.py` — hook shim is the non-ARC boundary: observe → replace → original → record → exactly-once release ordering, borrowed description never released, fail-open factory boundary, MRR release form centralized in one helper. Compiles and runs `tests/native-caml-diagnostic.cpp`, which exercises the production recovery transitions across all three setter seams (owned re-assignment keeps the real stock original, factory misses keep ownership, only genuinely newer stock is adopted).
- `rejected-regression.py` — the current tree passes while the rejected candidate `97eabba5…` fails: live glyph reconciliation, owned recovery state, visible wallpaper transition, exact mapping checks stay present.
- `bun tests/static-check.ts` — construct-and-pass route with verified initializer, rooted theme bundle construction, fail-open `replacement ?: description`, mapping table ↔ staged payload agreement in both themes, weak consumer registry, main-thread confinement, reconcile through original-IMP slots only.

## Device gap

The five runtime observations in `CAML-ROUTING-BLOCKER.md` remain open: dictionary completeness, concrete slider subclass, other-module seam coverage, state-handler ordering, AMFI/sandbox acceptance. PROVENANCE.md does not claim runtime-verified CAML. Device proof (separate authorized task): install, toggle modules with animated CAML packages in both themes, flip preferences live, confirm themed animation and no SpringBoard instability.

## Triage

Replacement never applies → factory admission or mapping entry (`BundleDirectoryForPackage` in the core). Applies but reverts on preference change → reconcile policy (`PlanReconcileAction`). Crash in setter → hook ABI/ownership boundary (`CAMLDiagnosticHooks.mm`; the exactly-once release gates name the offending hook).