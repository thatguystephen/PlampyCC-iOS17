# CAML Diagnostic Implementation — PlampyCC iOS 17

Status: observer-only implementation; disabled by default.

## Hook list

The dedicated `src/CAMLDiagnostic.xm` module installs six PAC-safe `MSHookMessageEx` observers once at process initialization, after class, selector, and runtime ABI checks:

- `-[CCUIButtonModuleView setGlyphPackageDescription:]` — `v24@0:8@16`
- `-[CCUIRoundButton setGlyphPackageDescription:]` — `v24@0:8@16`
- `-[CCUIBaseSliderView setGlyphPackageDescription:]` — `v24@0:8@16`; this superclass covers the static-analysis candidate `CCUIContinuousSliderView`
- `+[CCUICAPackageDescription descriptionForPackageNamed:inBundle:]` — `@32@0:8@16@24`; observer body additionally requires `kDiagnosticVerbose`
- `-[CCUIButtonModuleView setGlyphState:]` — `v24@0:8@16`
- `-[CCUIBaseSliderView setGlyphState:]` — `v24@0:8@16`

Quoted Objective-C class annotations are normalized before ABI-shape comparison. A missing class, selector, or incompatible runtime encoding skips that site without changing the stock implementation. The existing functional `dismiss` hook calls the narrow `CAMLDiagnosticFlushAtDismiss()` interface after the original dismiss call; when diagnostics are disabled this is a no-op, so functional behavior remains unchanged. No route-context hook is included.

Every replacement keeps a separate original-IMP slot, records only an observation, and calls the original exactly once with the original arguments. Factory return values are returned unchanged. No setter argument, package description, glyph state, or return value is replaced.

## Preferences

- Domain: `com.misakaproject.plampyCC`
- `kDiagnosticEnabled`: BOOL, default `NO`
- `kDiagnosticVerbose`: BOOL, default `NO`; gates factory events

The hooks are installed once, but disabled and preference-transition paths are no-op observer paths. Preference changes are read through the existing Darwin notification seam; no preference writes occur from a hook. Logging failures disable diagnostics for the remainder of the process and the original IMP continues.

## Log path and fixed schema

When enabled, bounded events are appended to the tweak-owned rootless path:

`/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/events.jsonl`

The directory is created with mode `0700`; the file is restricted to `0600`. Events use fixed compact JSON keys (`v` version, `t` monotonic milliseconds, `w` wall-clock seconds, `s` site, `p` package name, `x` path prefix, `n` description-is-new, `g` glyph state, `d` description class, `i` view tag, `a` ancestor class, `r` repeat, `b` build ID, `u` Mach-O UUID).

`x` is a coarse path classification (`private`, `var`, `app-container`, `Applications`, or `other`). Full paths, package URLs, CAML/XML contents, asset bytes, user data, and raw pointer values are never serialized. Package names and class/state strings are sanitized and bounded.

The in-memory ring contains at most 512 events. Identical `(site, pkg, state)` tuples are suppressed for 1000 ms; repeats inside 100 ms update one event's `repeat` count. Matching `(site, pkg)` repeats inside 100 ms are also collapsed. A process-session cap of 2000 accepted events prevents unbounded growth. Ring flushes append complete bounded lines and synchronize the file under one `os_unfair_lock`; no synchronous queue dispatch is used.

## Build ID and provenance

Source build ID: `plampycc-caml-observer-v1`.

The install event records the build ID and the tweak Mach-O UUID discovered from the loaded image's `LC_UUID` command; ordinary events retain those fixed fields as empty values to stay within the 256-byte ceiling. The Apple Silicon workflow also records the exact source SHA, workflow run, Xcode version, pinned Theos revision, pinned SDK revision/name, package hashes, and unstripped symbol hashes in `dist/build-manifest.json` and `dist/SHA256SUMS`.

Final workflow run URL/ID and downloaded artifact verification are recorded in the handoff after the exact pushed SHA is built. No device or runtime evidence is claimed by this document.

## Verification performed locally

`tests/caml-diagnostic-contract.py` models disabled and enabled pass-through, original-call identity/count, unchanged factory returns, ABI normalization and mismatch skipping, missing-site fail-open behavior, deduplication, ring/session bounds, reentrancy, logger failure isolation, redacted event fields, and the no-device workflow contract. The existing `src/Tweak.xm` functional behavior remains unchanged apart from the no-op-when-disabled dismissal flush seam; diagnostics are isolated in the added module.

## Known limitations

- This is not a functional CAML replacement and does not prove package coverage, animation parity, or third-party bundle loading.
- Exact runtime class coverage, concrete slider subclass use, state-handler ordering, and arbitrary bundle behavior remain device questions.
- The diagnostic does not dynamically unhook; preference transitions affect observer behavior at a safe subsequent hook boundary.
- The current workflow can prove packaging and symbols only. It cannot substitute for a separately authorized iPhone test.

## Exact future device-test gate

A separate task must explicitly authorize device SSH/access, transfer, installation, respring, interaction, and log/crash collection. Before that task, verify the downloaded package and symbols offline. During it, stop immediately on any SpringBoard crash, zero events across two opens, missing visible-module events, or any full-path/PII leak. No device activity is authorized by this implementation task.
