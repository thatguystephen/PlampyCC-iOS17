# Animated CAML replacement route

The replacement route swaps an incoming animated CAML package description for a themed one at three verified setter seams, constructs the replacement through a rooted theme bundle, and reconciles live when preferences change. Surface: construct-and-pass CAML package-description replacement on the three verified setter seams, plus live preference reconciliation.

Sources: `src/CAMLReplacement.xm` (Objective-C adapter), `src/CAMLReplacementCore.hpp` (production decision policy: `ClassifyIncoming`, `PlanConstruction`, `RecordInstall`, `ObserveReconcile`, `PlanReconcileAction`), `src/CAMLDiagnosticHooks.mm` (the seven non-ARC hook IMPs), `src/CAMLVerifiedABI.h`, `CAML-ROUTING-BLOCKER.md` (status).

## Sub-features

- `route-classify` classifies an incoming package description and admits only mapped PlampyCC packages (`ClassifyIncoming`, `BundleDirectoryForPackage`).
- `route-construct` builds the themed replacement through the rooted theme bundle and passes it through the verified initializer (`PlanConstruction`).
- `route-install-record` records installation with owned recovery state (`RecordInstall`).
- `route-reconcile` applies live preference changes through original-IMP slots only (`ObserveReconcile`, `PlanReconcileAction`).
- `route-fail-open` passes the original description through (`replacement ?: description`) whenever admission or construction misses.

## How to get to it (user POV)

- Install a module with an animated CAML package and open Control Center — the module shows the themed animation instead of the stock one.
- Toggle the module and watch the animation follow its state.
- Flip the module's preference live in Settings → PlampyCC and watch Control Center reconcile without a respring.

## Driving it with the native CAML replacement-core harness

Preconditions:

- Repo root as CWD on the Linux host (python3, g++, bun).
- `git status --porcelain` shows exactly the intended diff.

- **Hook ordering and ownership.** (User action: install, re-toggle, and re-assign the module — the setter seams.) Run `python3 -B tests/caml-diagnostic-contract.py`. One PASS line, exit 0. The hook shim is the non-ARC boundary: observe → replace → original → record → exactly-once release ordering, borrowed description never released, fail-open factory boundary, MRR release form centralized in one helper. It compiles and runs `tests/native-caml-diagnostic.cpp`, exercising the production recovery transitions across all three setter seams (owned re-assignment keeps the real stock original, factory misses keep ownership, only genuinely newer stock is adopted).
- **No regression of rejected behavior.** Run `python3 -B tests/rejected-regression.py`. One PASS line, exit 0. The current tree passes while the rejected candidate `97eabba5…` fails: live glyph reconciliation, owned recovery state, visible wallpaper transition, exact mapping checks stay present.
- **Routing wiring.** Run `bun tests/static-check.ts`. One PASS line, exit 0. Construct-and-pass route with verified initializer, rooted theme bundle construction, fail-open `replacement ?: description`, mapping table ↔ staged payload agreement in both themes, weak consumer registry, main-thread confinement, reconcile through original-IMP slots only.

## Gotchas

- Replacement never applies → factory admission or mapping entry (`BundleDirectoryForPackage` in the core). Applies but reverts on a preference change → reconcile policy (`PlanReconcileAction`). Crash in a setter → hook ABI/ownership boundary (`CAMLDiagnosticHooks.mm`; the exactly-once release gates name the offending hook).
- The five runtime observations in `CAML-ROUTING-BLOCKER.md` remain open: dictionary completeness, concrete slider subclass, other-module seam coverage, state-handler ordering, AMFI/sandbox acceptance. PROVENANCE.md does not claim runtime-verified CAML.
- `caml-diagnostic-contract.py` is shared with the recorder map — one run covers both, do not double-report.

## Observable proof

Non-device boundary: the three gate commands above, each with one PASS line and exit 0, captured under `evidence/verify-<YYYYMMDD-HHMM>/` (e.g. `drive-caml-replacement-route.txt`), with the three-seam recovery transitions of `tests/native-caml-diagnostic.cpp` among the asserted paths.

Device-only gap (separate authorized task): install the package on the jailbroken iPhone, toggle modules with animated CAML packages in both themes, flip preferences live, and confirm themed animation and no SpringBoard instability. Expected evidence: per-theme capture of the animated module, a live reconcile capture, and the absence of SpringBoard crash logs.
