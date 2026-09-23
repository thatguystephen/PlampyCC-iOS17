# CAML Diagnostic Implementation — PlampyCC iOS 17

Status: observer implementation plus the bounded, verified 21D50 construct-and-pass CAML replacement route; runtime verification is separately authorized and not claimed.

## Hook list

The diagnostic is split into three explicit boundaries: `src/CAMLDiagnosticHooks.mm` contains the six replacement IMPs and is compiled with ARC disabled; `src/CAMLDiagnostic.xm` owns ARC observer bodies and install-once descriptors; `src/CAMLDiagnosticCore.hpp` and `src/CAMLDiagnosticIO.hpp` contain the portable policies and injected Darwin syscall adapter. The observer module constructs six POD descriptors synchronously inside the process constructor, then installs each PAC-safe `MSHookMessageEx` observer once after class, selector, and runtime ABI checks:

- `-[CCUIButtonModuleView setGlyphPackageDescription:]` — `v24@0:8@16`
- `-[CCUIRoundButton setGlyphPackageDescription:]` — `v24@0:8@16`
- `-[CCUIBaseSliderView setGlyphPackageDescription:]` — `v24@0:8@16`; this superclass covers the static-analysis candidate `CCUIContinuousSliderView`
- `+[CCUICAPackageDescription descriptionForPackageNamed:inBundle:]` — `@32@0:8@16@24`; observer body additionally requires `kDiagnosticVerbose`
- `-[CCUIButtonModuleView setGlyphState:]` — `v24@0:8@16`
- `-[CCUIBaseSliderView setGlyphState:]` — `v24@0:8@16`

Quoted Objective-C class annotations are normalized before ABI-shape comparison. A missing class, selector, or incompatible runtime encoding skips that site without changing the stock implementation. The constructor records truthful per-site installation results (`q` in the install event) rather than treating constructor completion as installation success. The existing functional `dismiss` hook calls the narrow `CAMLDiagnosticFlushAtDismiss()` interface after the original dismiss call; when diagnostics are disabled this is a no-op, so functional behavior remains unchanged. No route-context hook is included.

Every replacement keeps a separate original-IMP slot and performs one POD-only `CAMLDiagnosticPrimitiveAdmission` check before entering the observer. The three package setter hooks additionally invoke the ARC-side `CAMLCreateReplacementDescription` boundary after observation. That factory uses only the verified initializer and `packageURL`, returns a +1 replacement or nil, and fails open on every miss. The non-ARC shim calls the original setter exactly once with `replacement ?: description`, records the owned/applied recovery state, then releases the +1 replacement exactly once after the original call through the shared message-send release helper (valid in a non-ARC translation unit regardless of the pinned SDK's runtime release entry-point declaration); the borrowed incoming description is never released. Factory/state observer return values remain unchanged. The primitive boundary performs no message send, retain, allocation, logging, or filesystem operation; the ARC bodies own Objective-C work and fail closed on exceptions.

Live preference reconciliation extends the same construct-and-pass route across preference changes. Each intercepted install records the newest stock description and distinguishes the owned replacement from untouched stock in consumer-scoped association state, and consumers are tracked weakly so consumer destruction bounds the recovery record. The `glyphPackageDescription` read-back verifies recovery state before the factory takes ownership and before reconcile-time installation or restoration; it never modifies private description state. Every preference reload reconciles all tracked consumers on the main thread through the decision policy in `src/CAMLReplacementCore.hpp`: disabled-start→enable themes preserved stock; Plampy↔Pulsar theme changes swap only owned replacements while preserving the captured stock; disable restores and re-enable re-themes; missing or unsupported resources restore stock instead of leaving overrides installed; and newer stock assignments are adopted and never overwritten. Reconcile-time setter calls go through the original-IMP slots (`CAMLInvokeOriginalPackage`), never the intercepted hooks, and the transition tests exercise these states across all three verified setter seams.

## Preferences

- Domain: `com.misakaproject.plampyCC`
- `kDiagnosticEnabled`: BOOL, default `NO`
- `kDiagnosticVerbose`: BOOL, default `NO`; gates factory events

The hooks are installed once and are never dynamically unhooked or rehooked. `kDiagnosticEnabled` and `kDiagnosticVerbose` gate observer bodies; disabled and preference-transition paths are no-op observer paths. Preference changes refresh those atomic gates through the existing Darwin notification seam only; no preference writes occur from a hook. Logging failures disable diagnostics for the remainder of the process and the original IMP continues.

## Log path and fixed schema

When enabled, bounded events are appended to the tweak-owned rootless path:

`/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/events.jsonl`

The directory is created with mode `0700`; the file is restricted to `0600`. Events use fixed compact JSON keys (`v` version, `t` monotonic milliseconds, `w` wall-clock seconds, `s` site, `p` package name, `x` path prefix, `n` description-is-new, `g` glyph state, `d` description class, `i` view tag, `a` ancestor class, `r` repeat, `q` per-site installation success, `b` build ID, `u` Mach-O UUID).

`x` is a coarse path classification (`private`, `var`, `app-container`, `Applications`, or `other`). Full paths, package URLs, CAML/XML contents, asset bytes, user data, and raw pointer values are never serialized. Package names, class names, and state strings are emitted only when they exactly match the fixed approved-value allowlists; every other value becomes `unknown`, `unknown-class`, or `unknown-state`.

The in-memory ring contains at most 512 events. The shared `CAMLDiagnosticCore.hpp` policy owns allowlists, tuple/pair deduplication, session/ring limits, complete-line recovery, and the atomic output state machine; the observer calls those helpers directly rather than maintaining a second host-only model. Flushes use the injected `CAMLDiagnosticIO.hpp` adapter: the Darwin implementation supplies `openat`/`pread`/`write`/`fsync`/`renameat`/`unlinkat`/`close`, while native tests inject deterministic short-write and state-fault callbacks. Descriptor-based `O_NOFOLLOW` confinement rejects unsafe owners/modes/non-regular files, writes a complete bounded replacement to a temporary file, syncs it, atomically renames it, and syncs the directory. Restart recovery discards an incomplete final line and retains at most the newest 1 MiB of complete records. C++ RAII owns every directory/temp descriptor; a temp is unlinked on every pre-rename failure/exception, while a post-rename directory-fsync failure leaves the complete committed file and disables further logging. No synchronous queue dispatch is used.

## Build ID and provenance

Source build ID: `plampycc-caml-observer-v1`.

The install event records the build ID and the tweak Mach-O UUID discovered from the loaded image's `LC_UUID` command; ordinary events retain those fixed fields as empty values to stay within the 256-byte ceiling. The Apple Silicon workflow also records the exact source SHA, workflow run, Xcode version, pinned Theos revision, pinned SDK revision/name, package hashes, and unstripped symbol hashes in `dist/build-manifest.json` and `dist/SHA256SUMS`.

Final package signing follows the pinned toolchain exactly. Theos signs each linked binary at build time with `ldid -S` (`makefiles/instance/rules.mk` `_THEOS_CODESIGN_COMMANDLINE`, `TARGET_CODESIGN = ldid`, `TARGET_CODESIGN_FLAGS ?= -S` in `makefiles/targets/_common/darwin_head.mk`; the workflow greps these exact rules), and the release repack's in-place `strip -x` mutates code bytes and stale-invalidates that signature. The workflow therefore re-signs every final packaged Mach-O with `ldid -S` after stripping and before `dpkg-deb -b`, and nothing mutates the staged payload afterwards: each packaged Mach-O is byte-compared against the signed staged file, and `tests/signature-contract.py` recomputes CodeDirectory page and special-slot hashes over the shipped bytes (missing, stale, truncated, or partially hashed signatures fail) as both a build assertion and the artifact gate.

Final workflow run URL/ID and downloaded artifact verification are recorded in the handoff after the exact pushed SHA is built. No device or runtime evidence is claimed by this document.

## Verification performed locally

`tests/caml-diagnostic-contract.py` verifies the source-level boundary split, non-ARC compile guard, exact hook ordering, construct-and-pass ownership/release sequence, fail-open factory boundary, deterministic descriptors, adapter wiring, and invokes `tests/native-caml-diagnostic.cpp` against the production C++ headers. The native test injects a fake syscall adapter for short writes, exercises policy/recovery/atomic-state fault transitions, and covers the production CAML mapping core. `tests/caml-diagnostic-artifact.py` audits both unstripped slices and thin slices extracted from the final packaged `.deb`. `tests/signature-contract.py` is host-runnable: its fixture self-test accepts synthetic thin and universal signed Mach-Os and rejects unsigned, stale, tampered-code, tampered-hash, and truncated-signature fixtures, and its `--package` mode validates real packages from their CodeDirectory hashes. No runtime CAML success is claimed; the five ABI-map runtime observations remain explicit in `CAML-ROUTING-BLOCKER.md`.

## Known limitations

- The replacement is bounded to the verified construct-and-pass route and reconstructed package map; it does not prove package coverage, animation parity, or third-party bundle loading.
- The five exact runtime observations listed in `CAML-ROUTING-BLOCKER.md` remain device questions: dictionary completeness, concrete slider subclass, other-module seam coverage, state-handler ordering, and AMFI/sandbox acceptance.
- The diagnostic does not dynamically unhook; preference transitions affect observer behavior at a safe subsequent hook boundary.
- The workflow proves source contracts, generated observer-boundary code, packaging, and both final arm64/arm64e slices. It cannot substitute for a separately authorized iPhone runtime test.

## Exact future device-test gate

A separate task must explicitly authorize device SSH/access, transfer, installation, respring, interaction, and log/crash collection. Before that task, verify the downloaded package and symbols offline. During it, stop immediately on any SpringBoard crash, zero events across two opens, missing visible-module events, or any full-path/PII leak. No device activity is authorized by this implementation task.
