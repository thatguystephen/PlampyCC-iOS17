# M1 static-substitution subtraction — release/deployment note

Scope: milestone M1 of Issue #8/#9, implemented from accepted M0 base
`7f8a314ddf9033504ca7c9b17e86f16b9ccdde36`. This artifact removes every
PlampyCC-owned static, compact, Flashlight, and header glyph substitution
route. Flashlight and every static/custom glyph path are stock by
construction.

## Installation boundary (normative)

- This artifact may be installed **only from a verified stock SpringBoard
  state**. M1 source removal cannot restore live representations after the old
  ownership records are gone, and no runtime migration shim exists or may be
  invented to keep the deleted owners alive.
- The allowed path for this cutover is a **separately authorized clean
  SpringBoard restart followed by stock verification before candidate
  installation**. Restoring and clearing every live legacy-owned
  representation while its recovery record remains valid is the only
  alternative, and it requires the same separate authorization.
- **No device action is performed by this task.** M1 is host-only: source
  edits and host tests. Device transfer, installation, restart, verification,
  and diagnostics collection each require their own action-scoped
  authorization.

## What M1 removes (source-symbol inventory)

- `buttonLayout`/`orig_layout` and the `layoutSubviews` hook installation;
- `roundMove`/`orig_roundMove` and the `didMoveToWindow` hook installation;
- `compactSetGlyph`, `compactSetSelectedGlyph`, their original slots, the
  thread-local recursion flag, and both compact setter installations;
- `headerGlyph`, `HeaderGlyphSubstitute`, `orig_headerGlyph`, the header ABI
  gate, and `InstallHeaderGlyphHook`;
- the static-image identifier map, PNG decode/render/cache path
  (`IconForIdentifier`, `IconImage`, `SizedGlyphArt`, `SizedCompactGlyphArt`,
  `gIconImages`, `gSizedArt`, `kGlyphSourceCanvas`), the substitution-only
  optical policy (`FlashlightOpticalPolicy.hpp`),
  `ReconcileGlyphView`/`ReconcileFlashlightView`, the ownership releases, the
  `plampy.glyphOverride` / `plampy.flashlightGlyphs` ownership keys,
  `gGlyphViews`, `kFlashlightOwnedView`, ancestry/identifier routing
  (`AncestorController`, `ButtonIdentifier`), the delayed glyph stability
  probe, and every substitution-only trace call (`TraceGlyph`, `ObserveGlyph`
  and its outcome tokens).

## What M1 retains

- overlay `viewDidLoad` / present / dismiss hooks with predecessor slots,
  owning wallpaper/blur/presentation behavior (including the diagnostic flush
  at dismiss, which stays while the shipping collector is installed);
- preference loading/notification and functional enable/disable/theme
  publication (`PlampyCCFunctionalEnabled`, `PlampyCCThemeType`);
- the current CAML setter/replacement route until M2 replaces it;
- the shipping diagnostic collector and its eight install sites, including the
  **observer-only header-glyph diagnostic seam**. Scope decision recorded for
  review: that seam is a diagnostic interceptor, not a substitution hook — it
  forwards the caller's image and point size unchanged and cannot replace a
  module glyph. Issue #8's exact deletion gates place the atomic removal of the
  five non-setter diagnostic interceptors (and the eight-site installer) at
  the M2 cutover, and M2 work is outside this task. The M1 host gate proves
  the seam stays observer-only.

## Verification

`tests/m1-static-subtraction-contract.py` is the M1 stock-preservation/deletion
contract (absence of every removed name/key/selector, no non-CAML hook able to
replace a module glyph, retained overlay/CAML behavior, byte-identical M0 Q0
catalog with empty activation, and this note's installation boundary). The
package-slice proof (arm64/arm64e absence of removed substitution symbols)
requires the pinned macOS CI build and is reported **BLOCKED** for AIDA's H0 CI
run; it is not claimed here.
