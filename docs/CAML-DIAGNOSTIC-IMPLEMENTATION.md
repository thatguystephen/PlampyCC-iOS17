# CAML Diagnostic Implementation — PlampyCC iOS 17

Status: observer-only implementation; disabled by default.

## Hook list

The diagnostic is split into three explicit boundaries: `src/CAMLDiagnosticHooks.mm` contains the six replacement IMPs and is compiled with ARC disabled; `src/CAMLDiagnostic.xm` owns ARC observer bodies and install-once descriptors; `src/CAMLDiagnosticCore.hpp` and `src/CAMLDiagnosticIO.hpp` contain the portable policies and injected Darwin syscall adapter. The observer module constructs six POD descriptors synchronously inside the process constructor, then installs each PAC-safe `MSHookMessageEx` observer once after class, selector, and runtime ABI checks:

- `-[CCUIButtonModuleView setGlyphPackageDescription:]` — `v24@0:8@16`
- `-[CCUIRoundButton setGlyphPackageDescription:]` — `v24@0:8@16`
- `-[CCUIBaseSliderView setGlyphPackageDescription:]` — `v24@0:8@16`; this superclass covers the static-analysis candidate `CCUIContinuousSliderView`
- `+[CCUICAPackageDescription descriptionForPackageNamed:inBundle:]` — `@32@0:8@16@24`; observer body additionally requires `kDiagnosticVerbose`
- `-[CCUIButtonModuleView setGlyphState:]` — `v24@0:8@16`
- `-[CCUIBaseSliderView setGlyphState:]` — `v24@0:8@16`

Quoted Objective-C class annotations are normalized before ABI-shape comparison. A missing class, selector, or incompatible runtime encoding skips that site without changing the stock implementation. The constructor records truthful per-site installation results (`q` in the install event) rather than treating constructor completion as installation success. The existing functional `dismiss` hook calls the narrow `CAMLDiagnosticFlushAtDismiss()` interface after the original dismiss call; when diagnostics are disabled this is a no-op, so functional behavior remains unchanged. No route-context hook is included.

Every replacement keeps a separate original-IMP slot, performs one POD-only `CAMLDiagnosticPrimitiveAdmission` check before entering the observer, records at most one observation, and calls the original exactly once with the original arguments. Factory return values are returned unchanged. No setter argument, package description, glyph state, or return value is replaced. The primitive boundary performs no message send, retain, allocation, logging, or filesystem operation; the ARC observer body owns all Objective-C work and fails closed on exceptions.

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

Final workflow run URL/ID and downloaded artifact verification are recorded in the handoff after the exact pushed SHA is built. No device or runtime evidence is claimed by this document.

## Verification performed locally

`tests/caml-diagnostic-contract.py` verifies the source-level boundary split, non-ARC compile guard, exact hook ordering and pass-through, primitive admission purity, deterministic descriptors, adapter wiring, and invokes `tests/native-caml-diagnostic.cpp` against the production C++ headers. The native test injects a fake syscall adapter for short writes and exercises policy, recovery, and atomic-state fault transitions; it does not reimplement those policies in Python. `tests/caml-diagnostic-artifact.py` audits both unstripped slices and thin slices extracted from the final packaged `.deb`. The existing `src/Tweak.xm` functional behavior remains unchanged apart from the no-op-when-disabled dismissal flush seam; diagnostics are isolated in the added module.

## Known limitations

- This is not a functional CAML replacement and does not prove package coverage, animation parity, or third-party bundle loading.
- Exact runtime class coverage, concrete slider subclass use, state-handler ordering, and arbitrary bundle behavior remain device questions.
- The diagnostic does not dynamically unhook; preference transitions affect observer behavior at a safe subsequent hook boundary.
- The workflow proves source contracts, generated observer-boundary code, packaging, and both final arm64/arm64e slices. It cannot substitute for a separately authorized iPhone runtime test.

## Exact future device-test gate

A separate task must explicitly authorize device SSH/access, transfer, installation, respring, interaction, and log/crash collection. Before that task, verify the downloaded package and symbols offline. During it, stop immediately on any SpringBoard crash, zero events across two opens, missing visible-module events, or any full-path/PII leak. No device activity is authorized by this implementation task.
