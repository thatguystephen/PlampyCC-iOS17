# CAML routing compatibility boundary

The verified 21D50 construct-and-pass route is implemented for the three setter seams. The implementation is intentionally bounded by `evidence/CAML-ABI-MAP-21D50.md`: it constructs a fresh `CCUICAPackageDescription` from the rooted theme bundle and passes it through the stock setter; it does not mutate live package-description ivars, bypass the setter, or claim runtime animation parity.

The three setter hooks are:

- `CCUIButtonModuleView setGlyphPackageDescription:`
- `CCUIRoundButton setGlyphPackageDescription:`
- `CCUIBaseSliderView setGlyphPackageDescription:` (the 21D50 superclass move from `CCUIContinuousSliderView`)

The route uses the incoming description's `packageURL` filename stem as module identity, the reconstructed exact-name map for button/round sites, the verified `Brightness`/`Volume` contains-string route for the slider site, the `timer` + Pulsar fail-open special case, and a rootless logical theme path. An unmapped package, disabled feature, non-conforming description, missing bundle/initializer/resource URL, or exception forwards the original description unchanged.

Ownership is explicit: the ARC factory returns the `alloc/init` replacement at +1 (`ns_returns_retained`); the non-ARC setter shim passes that replacement (or the original description on fail-open) to the original IMP, then performs exactly one `objc_release` after the original call. The incoming borrowed description is never released. The original setter remains responsible for its verified retain/store behavior.

The staged assets are checked in under `layout/var/mobile/Library/Application Support/PlampyCC/<theme>/Assets/...`; `ROOT_PATH_NS` supplies the rootless namespace at runtime. The source never embeds `/var/jb` or a second rootless prefix.

Five runtime observations remain explicit and unclaimed, as listed by the verified ABI map:

1. The complete original package-name dictionary contents were not enumerated; the implementation uses only the reconstructed shipped-package map and fails open on misses.
2. The concrete on-screen slider subclass is not confirmed; the `CCUIBaseSliderView` hook covers the verified superclass path.
3. The exact base-class seam used by Flashlight, TVRemote, and other modules without per-module setter overrides remains unconfirmed.
4. `stateUpdateHandlers` re-registration ordering when a live description is swapped remains unconfirmed.
5. On-device AMFI/sandbox acceptance of loading the rooted theme bundle outside the app container remains unconfirmed.

The unrelated `selectImage` preference action remains pending a Steph product decision; this CAML implementation does not waive or implement it. Steph must decide that feature separately.

These observations require separately authorized device verification. This implementation does not claim runtime CAML success, animation parity, device installation, or SpringBoard stability.