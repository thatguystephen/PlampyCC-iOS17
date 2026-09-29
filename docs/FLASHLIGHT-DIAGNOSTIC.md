# Flashlight compact-glyph diagnostic — iOS 17.2 (21D50)

Task: `t_5c22b84e`. This note recorded the static conclusion and the bounded
runtime observation added for the remaining Flashlight stock-glyph failure.
It does not authorize device access, installation, respring, or deployment.

**M1 status (static-substitution subtraction).** The static, compact, and
header glyph substitution routes — and every substitution-only trace they
emitted (`glyph-recon`, `glyph-probe`, the `skip-*`/`glyph-*`/`stable-*`
outcome tokens, and the functional `header-hook` decision tokens
`hdr-bypass`/`hdr-subst`/`hdr-failop`) — were removed from the shipping dylib
at M1; see `docs/M1-STATIC-SUBTRACTION-CUTOVER.md`. What remains of this note
is (a) the proven path-admission contract below, which the collector still
obeys, and (b) the input-side `header-glyph` runtime observer, which is a
diagnostic interceptor (not a substitution hook) and stays until the M2
diagnostic-interceptor removal. The sections describing the substitution
trace are retained as history only.

## Static conclusion (historical)

`FlashlightModule` has no `glyphPackageDescription:` route. The compact
controller is `CCUIFlashlightModuleViewController`, a
`CCUIButtonModuleViewController` subclass, and the compact host is the stock
`CCUIButtonModuleView`. The module updates static images through
`setGlyphImage:` and, where present, `setSelectedGlyphImage:` from
`_updateGlyphForFlashlightLevel:`. `CCUIRoundButton` exposes the primary glyph
slot but not the selected slot. Therefore another CAML/package hook is not a
supported fix for this failure.

The ranked falsifiable causes and the bounded reconciler trace that tested
them (outcome tokens `skip-*`, `glyph-*`, `stable-*`, site labels
`glyph-recon`/`glyph-probe`, plus the functional `header-hook` forwarding
decision) existed only to diagnose that static substitution route and were
removed with it at M1.

## Diagnostic fields and interpretation

`events.jsonl` records the existing view tag and approved ancestor class. The
serialized `state` field (`g`) uses a `%.12s` wire precision. Every approved
state token is therefore unique and no longer than 12 characters;
`CAMLDiagnosticCore.hpp` enforces that contract at compile time, and
`tests/caml-diagnostic-contract.py` keeps the constant equal to the
serializer's precision. After M1 the approved state values are the observed
button/slider states (`default`, `disabled`, `expanded`, `highlighted`,
`collapsed`, `off`, `on`, `selected`) and the header-glyph stock-image
comparison tokens (`hdr-stock`, `hdr-other`, `hdr-nil`, `hdr-unclass`).

## Proven path-admission failure and corrected path contract

Device-authorized read-only inspection of the collector build
(`plampycc-caml-observer-v2-diag`, package `xyz.cypwn.plampycc` 1.0.2-1)
found no diagnostic directory and no events despite `kEnabled=true`, a
running SpringBoard, and no relevant crashes. The absence has a proven
cause: `OpenDirectoryUnderTrustedPrefix` validated the platform parent
`/var/jb/var/mobile/Library/Application Support` (observed `mobile:mobile`
mode `0775`) with the strict owned-suffix rule `(st_mode & 0022) == 0`, so
`ValidateDirectoryDescriptor` rejected the legitimate group-writable
platform directory and the walk aborted before creating the tweak-owned
`PlampyCC/CAML-Diagnostic` leaf. No event could ever flush. The boundary
was placed one level too low: a platform-owned parent was being judged by
tweak-owned policy.

Routing is unchanged and intentional: writable tweak state lives under the
rootless rewrite `ROOT_PATH_NS("/var/mobile/...")`, which expands to
`/var/jb/var/mobile/...` (libroot rewrites absolute `/var/mobile` paths
into the jbroot and the jailbreak sandbox sanctions mobile writes there).
The source never embeds `/var/jb` and never emits an unwrapped bare
`/var/mobile` path.

The corrected path contract:

- Trusted prefix: `ROOT_PATH_NS("/var/mobile/Library/Application Support")`,
  opened once with normal symlink resolution and validated by
  `ValidatePlatformPrefixDescriptor`: a directory owned by root or the
  effective (mobile) user; the mobile-owned form may be group-writable
  (observed `mobile:mobile 0755` and `0775` chains) but is never
  world-writable; a root-owned prefix must have no group/world write.
- Owned suffix: `PlampyCC/CAML-Diagnostic`, walked [ADDRESS]  descriptor-confined: every component opened relative to the held
  descriptor with `O_NOFOLLOW`, created `0700` when absent, owner must be
  the effective user, intermediates never group/world-writable
  (`(mode & 0022) == 0`), leaf exactly `0700`, event files `0600`.
- Fail closed: a planted symlink, foreign-owned component, world-writable
  platform parent, or non-`0700` leaf aborts the walk with no descriptor
  leak. `tests/caml-diagnostic-output.py` and
  `tests/native-caml-directory-walk.cpp` cover the observed uid/gid/mode
  chains and adversarial ownership/world-writable/symlink topologies.

The ownership guarantees are uid-based: same-uid processes (other
mobile-uid apps) are outside the model.

## Authorized device collection sequence (historical)

The glyph-recon collection this sequence was written for diagnosed the
substitution route removed at M1. The collection hygiene below is retained
for any future separately device-authorized collector run; the only bounded
collector output path is
`/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/events.jsonl`
(created by `DiagnosticOutputDirectory`):

1. Build the diagnostic variant with `DIAGNOSTIC=1` and enable the existing
   diagnostic preference. Do not install or respring as part of any
   host-only task.
2. Collect only the bounded `events.jsonl` file above. Do not collect crash
   logs, paths, identifiers, or unrelated SpringBoard logs in the same
   artifact.
3. Flush at the existing dismissal seam, then verify the file contains only
   allowlisted package/state/class values. Delete the diagnostic artifact after
   review according to the operator's device policy.

No result is claimed until a device-authorized collection supplies a record.

## Header-glyph runtime observer (`header-glyph`)

Task: `t_61ba299e`. This section records the one additional bounded observer
from the completed seam investigation, and the static evidence it rests on. It
does not patch visual behavior: the original setter receives the unchanged
image and point size, no replacement is constructed, and the recorder stays
compile-time disabled outside collector builds. (M1 removed the substitution
hook that used to chain on this seam; the observer itself is a shipping
diagnostic interceptor and is removed atomically with the other non-setter
diagnostic interceptors at [ADDRESS], not here.)

Static basis (21D50 inputs, read-only `strings` / `ipsw macho disass`; no
device):

- `FlashlightModule` carries the selector string
  `setHeaderGlyphImage:unscaledSymbolPointSize:` (the module imports plain
  `_objc_msgSend`, so the bare selector string is a selector reference), which
  is the caller-side participation the static xref map left open.
- `ControlCenterUIKit` implements
  `-[CCUICustomContentModuleBackgroundViewController
  setHeaderGlyphImage:unscaledSymbolPointSize:]`; its prologue keeps the point
  size in `d0` (`fmov d8, d0`), so the compiled ABI shape is the object plus
  64-bit `CGFloat` form `v32@0:8@16d24`. The site installer re-verifies that
  shape against the runtime encoding (`ABIShapeMatches`) and refuses the [ADDRESS]  on any mismatch, recording the refusal like every other site.
- `FlashlightModule` ships the two stock level symbols `flashlight.off.fill`
  and `flashlight.on.fill` — the `systemImageNamed:withConfiguration:` inputs
  of `_updateGlyphForFlashlightLevel:`. They are the comparison constants for
  the stock-glyph classification below.

Fields at this site (the serialized schema and every wire precision are
unchanged; only the per-site meaning of three keys differs):

- `s` is the selector token `header-glyph`;
- `c` is the bounded receiver class
  `CCUICustomContentModuleBackgroundViewController` (the `%.20s` class wire
  precision shows its first 20 characters);
- `a` is the bounded caller identity: the leaf image name of the one-frame
  return address, allowlisted to `ControlCenterUIKit`, `FlashlightModule`,
  `UIKitCore`, `PlampyCC`, `SpringBoard`, else `unknown-caller`. No raw
  address is ever recorded;
- `g` is the stock-glyph comparison token: `hdr-stock`, `hdr-other`,
  `hdr-nil`, `hdr-unclass`;
- `i` is `unscaledSymbolPointSize` in hundredths of a point;
- `x` is the bounded image size token `w<width>h<height>` in whole points;
- `n` reuses the bounded seen-table identity: 1 when this image pointer is new
  for this receiver, 0 when the same image pointer repeats;
- `d` is the bounded image class (`UIImage`, `_UIImageSymbolImage`, else
  `unknown-class`);
- `h` is `header`; `p`, `f`, `y`, and `o` stay empty or `none` at this site.

Comparison rule for `g`, in order: a nil image is `hdr-nil`; an image
identical to a freshly requested stock reference (`flashlight.off.fill` and
`flashlight.on.fill`, default or point-size configuration) is `hdr-stock`; a locally extracted symbol
name equal to a stock symbol is `hdr-stock`, and a different extracted symbol
name is `hdr-other`; an image that carries no symbol configuration is
`hdr-other` (the stock level glyphs are always SF Symbol images); anything [ADDRESS] cannot decide safely is `hdr-unclass`. The symbol name is compared
locally and never recorded.

Observation rule: expand the Flashlight module once with a collector build
installed. A record with `a`=`FlashlightModule` proves expanded Flashlight uses
the header-glyph seam at all; `g`=`hdr-stock` proves it writes its stock image
through that seam. Any `hdr-unclass` record keeps the stock-image question
open and must be read together with `a`, `i`, and `x`.

Standing finding (recorded, not changed here): `hdr-unclass` on a caller-side
stock push shows the input-side stock comparison matched on neither image
identity against freshly requested stock references nor `_symbolName`, so a
real push can only reach `hdr-stock` when one of those discriminators happens
to hit.

## Removed at M1: functional header substitution (`header-hook`)

Task `t_de25592e` added a substitution hook on this seam with one bounded
decision token per invocation (`hdr-bypass`, `hdr-subst`, `hdr-failop`, site
label `header-hook`), and task `t_724201a5` fixed its install to target the
linked seam owner `CCUICustomContentModuleBackgroundViewController` (the
`CCUIFlashlightBackgroundViewController` plugin class loads too late for a
constructor-time install). M1 removed that substitution hook, its install
edge, and its decision tokens together with the whole static substitution
surface: the header glyph is stock by construction again. The input-side
`header-glyph` observer above cannot substitute anything and remains until
the M2 diagnostic-interceptor removal.
