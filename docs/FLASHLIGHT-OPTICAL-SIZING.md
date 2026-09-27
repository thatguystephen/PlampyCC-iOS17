# Flashlight compact optical sizing

Task: t_99f371b1. Baseline: `d0e77a9b62d0f1388827531420bda762753cdb73`.
Status: implemented candidate, local contracts verified; NOT device-accepted.

## Scope and evidence boundary

Bug-fix route, with optical-policy comparison. Source/test edits and one local
commit are authorized. No push, package dispatch, device write, install or
respring is part of this phase. No SSH was necessary: the existing token-only
diagnostics cannot measure UIImage geometry or optical bounds. The card's
explicit report establishes correct ON/OFF behavior and undersized compact art
on the installed baseline. The screenshot is human red evidence; tests below
are source/native contracts, not an iOS render harness. Review and a separately
authorized build/device gate must precede any claim that the visual defect is
fixed. Rollback is the exact baseline, not earlier reversed-state candidates.

## Measurements (observed, not simulated)

Input: `/mnt/truenas/IMG_1095.JPG`, 1107x276.
SHA256: `00f277b2c418bdd584cf7b1e8a6ff1a0f18d5d671a3e1819a51b0fa10a6b2495`.
Replay: `sh tests/measure-flashlight-optics.sh /mnt/truenas/IMG_1095.JPG`.
ImageMagick trims each declared crop against its corner background. Bounds are
half-open, in original screenshot pixels. Whole themed silhouettes (including
power/VPN background shapes), not just white/text strokes, are the peers.

| Glyph | Bounds at 10% fuzz | Width x height | At 5% fuzz | At 15% fuzz |
|---|---|---|---|---|
| Flashlight | (402,121)-(437,173) | 35x52 | 37x53 | 35x51 |
| Battery | (107,120)-(180,173) | 73x53 | 73x53 | 73x53 |
| Power | (656,107)-(736,187) | 80x80 | 80x80 | 80x80 |
| VPN | (931,116)-(1010,178) | 79x62 | 81x64 | 67x29 |

The 15% VPN measurement loses its dark backing and is excluded from calibration.
The 5%/10% silhouettes agree closely; JPEG boundary uncertainty is real. These
are extent measurements, not alpha-area or perceptually weighted mass estimates.

## Why canvas equality is not optical equality

The production assets have an 80x144 canvas, with alpha bounds
(12,32)-(68,112): visible occupancy is 56x80, or 70% of width and 55.56% of
height. `SizedGlyphArt` aspect-fits the ENTIRE padded canvas, not the alpha
bounds. At the historical 25x48 fallback this gives only 17.5x25 points of
visible art. That example is arithmetic, NOT a measured stock UIImage size.
A stock SF Symbol's point size/configuration and optical/alignment metrics are
not a contract that a differently shaped, padded raster will look equally big.
The observed 35x52 compact silhouette demonstrates the resulting imbalance.

History constrains the correction: raw 80x144 substitution was too large;
changing alpha bounds alone in that canvas did not visibly fix it; stock-canvas
normalization then became too small. This establishes canvas size as an
empirically effective control, but does not prove that alpha content is ignored
by every downstream iOS layout path. We preserve the assets and adjust the
compact output canvas instead of repeating the failed content-only hypothesis.

Stock configuration inspection on the extracted 21D50 FlashlightModule:

- `ipsw macho disass <FlashlightModule> --vaddr 0x21f0be7d8 --force` identifies
  `-[CCUIFlashlightModule contentViewControllerForContext:]`.
- 0x21f0be80c loads point-size 30; 0x21f0be810/814 load weight=4, scale=2.
  The call at 0x21f0be818 enters stub 0x21f0bfba0, whose selector ref is
  0x2391813e0. Reading the extracted __objc_selrefs entry gives 0x182ed5255;
  `ipsw dyld objc sel <cache> --image <FlashlightModule image path>` resolves
  it to `configurationWithPointSize:weight:scale:`.
- The off/on strings at 0x21f0be830/85c feed the same configured image route.
  Stub 0x21f0bff80 uses selector ref 0x239181528, whose entry is 0x182f47340,
  resolved by that same selector dump as `systemImageNamed:withConfiguration:`.
- The header update at 0x21f0bdf7c uses point-size 30, weight=3, scale=2 and
  passes 30 to the header setter. Compact and header configuration are not
  identical; compact calibration must not silently resize the header.
- Exact resulting device UIImage dimensions/alignment rects remain unmeasured.
  Source reads the pushed UIImage.size rather than hardcoding an inferred size.

Initial symbolic lookup failed because the named method was not in the extracted
symbol table. Full ObjC parsing hit an out-of-image protocol pointer; dyld
symbol disassembly aborted in ipsw getHeaderInfoRO with an allocation error.
Bounded address disassembly plus selector references succeeded instead. These
are analysis-tool failures, not SpringBoard failures.

## Policy comparison and decision

1. Median peer height: 62/52 = 1.19231. Conservative and viable, but horizontally
   broad battery/VPN peers bias this height statistic downward; the slender
   Flashlight stays optically small. Applying it to the expanded header would
   still be unsupported by this crop.
2. Median peer LONGEST extent: median(73,80,79)/52 = 79/52 = 1.519230769.
   Chosen. Treats horizontal, circular and vertical art symmetrically without
   demanding equal filled area. Predicted compact bounds are about 53.17x79,
   conditional on local size scaling remaining linear. That prediction is NOT
   a new screenshot or observed device outcome.
3. Equal bounding-box area: sqrt((79*62)/(35*52)) = 1.64049. Rejected: a bbox
   is not ink mass, and this pushes the tall silhouette beyond the peer extent
   envelope. Full alpha/contrast mass normalization would need more data and
   complexity than this bounded correction warrants.

The named compile-time `flashlight_optical::kCompactScale` is 79/52, bounded by
73/53 through 80/51 (1.377358491–1.568627451), using peer extent and measured
flashlight boundary uncertainty. These are a calibration envelope, NOT general
accessibility/device-size limits. The factor is not a preference and cannot
expand through a runtime configuration. Both bundled theme selections use the
same Flashlight art via the existing Pulsar fallback; no arbitrary theme files
or future artwork are claimed calibrated. Header remains factor 1.0. No views,
frames, Assets.car, symbols, module routing or PNGs are changed.

## Integration invariants

The renderer caches by theme, art, source canvas and optical factor. Every
render retains its unscaled source canvas in a private UIImage association.
The compact helper recovers that canvas before resizing; both in-flight setters
and layout reconciliation call it. Thus passing a generated image through a
hook again does not multiply its size repeatedly. Metadata survives clearing
the render cache while a glyph still retains the old image. Cache keys separate
header and compact policies even if their output dimensions happen to coincide.

Normal slot still uses FlashlightOff; selected slot uses FlashlightOn. Header
positive-off identity, both ABI gates, receiver/module scope, original-argument
fallback, diagnostics tokens/privacy and preference invalidation remain intact.
Nonfinite incoming dimensions now fail open rather than creating an invalid
context. Source-canvas identity relies on UIKit retaining the image object;
copying/transforming it and dropping associations is an explicit device risk.

## Verification and remaining gates

Red source contract before integration: `python3 -B tests/flashlight-optical-contract.py`
failed with `AssertionError: optical policy not integrated`. This supplements,
not replaces, the actual screenshot red evidence.

Green local suite (all exit zero):

- icon-cache-contract.py; flashlight-optical-contract.py (compiles/runs native
  production constant bounds and a labelled feedback model); prefs-arc-contract.py
- caml-diagnostic-contract.py (native policies); glyph-trace-contract.py
- signature-contract.py (fixtures, NOT a newly built package)
- flashlight-asset-contract.py; assets-contract.py (81 CAML references)
- manifest-contract.py; caml-diagnostic-output.py (native directory policies)
- rejected-regression.py; `bun tests/static-check.ts`; `git diff --check`

The generic theos-package-build inspector was also run and exits 1 on unchanged
baseline content: tests/static-check.ts:40, prefs/Makefile:13 (logical Theos
install paths), and src/CAMLDiagnostic.xm:255-257 (comments describing rootless
rewriting). It additionally warns about existing Preferences imports. These
are not silently counted as passing; the repository-specific rootless/static
contracts pass and no flagged file was changed. The new optical test is wired
into the existing macOS workflow without changing toolchain/provenance pins.
No new UIKit/arm64e package build or twelve-gate package verification was run
in this Linux/local-only phase. No native model is claimed to execute UIKit.

Required device matrix after independent review and an authorized exact-SHA build:

| Surface/action | Required result | Current evidence |
|---|---|---|
| Compact OFF / ON | Correct art, peer-sized footprint, no clipping | Mapping preserved locally; visual pending |
| ON levels 1–4 | Stable optical size and state through re-pushes | Pending device |
| Close/reopen CC, repeat layout | No cumulative enlargement or setter loop | Source/feedback model; device pending |
| Expanded header OFF / ON | Baseline size and working state unchanged | Default scale preserved; device pending |
| Toggle theme / enable | Fresh cache, no cumulative growth, stock when disabled | Existing contracts; device pending |
| Non-Flashlight peers | No change | Scope/diff contracts; device pending |

Obtain a same-scale compact screenshot for comparison; do not require it to hit
79 pixels exactly if the screen capture scale changes. Verify extent relative
to the same peers and inspect retained token-only diagnostics after the matrix.
If image association identity is lost or downstream layout normalizes the new
canvas, return for rework rather than increasing the factor speculatively.
