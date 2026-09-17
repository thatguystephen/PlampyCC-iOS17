# CAML routing compatibility boundary

The source preserves CAML pass-through. All 81 source `src=` references are structurally extracted and normalized exactly once to `/var/jb/var/mobile/Library/Application Support/PlampyCC/<theme>/...`; the matching logical layout is `layout/var/mobile/...`, and the rootless scheme supplies `/var/jb` at packaging. This path correction does not implement or waive animated CAML routing.

Read-only evidence collected from `/home/steph/Downloads/21D50__iPhone15,2_headers`:

    rg -n 'CCUICAPackageDescription|setGlyphPackageDescription|packageDescription' /home/steph/Downloads/21D50__iPhone15,2_headers
    rg -l 'CCUI|ControlCenterUI|ControlCenterUIKit' /home/steph/Downloads/21D50__iPhone15,2_headers --glob '*.h'

The first command found only forward declarations and glyph-package properties in `SBElasticRouteDisplayContext.h` and `SBElasticRouteDisplaying-Protocol.h`; it found no initializer, setter declaration, ownership annotation, producer, or call-site ABI. Read-only Mach-O inspection also ran:

    file /home/steph/Downloads/21D50__iPhone15,2_headers/ControlCenterUI /home/steph/Downloads/21D50__iPhone15,2_headers/ControlCenterUIKit
    nm -arch arm64e -gU /home/steph/Downloads/21D50__iPhone15,2_headers/ControlCenterUI
    nm -arch arm64e -gU /home/steph/Downloads/21D50__iPhone15,2_headers/ControlCenterUIKit

`file` identified both supplied framework binaries as arm64e Mach-O. The filtered `nm` queries returned no `CCUICAPackageDescription`, glyph-package setter, target-class, or producer symbols. No usable `rootless.h` was present in the supplied headers. The supplied framework binaries were not modified or used as an authority for guessed private APIs. CAML acceptance is therefore BLOCKED pending Steph's scope waiver or better target declarations.

Because constructing a package description requires the exact iOS 17 initializer, ownership semantics, and setter/call-site ABI, manufacturing a replacement object or guessing selectors would risk SpringBoard crashes and would not be faithful implementation. The package callbacks therefore deliberately preserve the original package unchanged. Static icon routing remains active and has an explicit original-glyph fallback. Animated CAML routing is an unresolved acceptance gate and remains pass-through. Steph must decide whether to waive it or provide verified declarations before implementation; no waiver is inferred here.

Next gate: obtain a bounded iOS 17 class-dump/selector map for the package-description producer and each target setter, then implement and runtime-test a retained `CCUICAPackageDescription` replacement against both themes. Do not claim animation parity from the shipped assets alone.
