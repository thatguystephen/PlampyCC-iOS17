# PlampyCC iOS 17 clean-room reconstruction

This project reconstructs the PlampyCC 1.0.2 behavior from the supplied package and static evidence; it does not claim the original source or authorship. Upstream/package attribution: **sugiuta**, package maintained by **CyPwn**, package identifier `xyz.cypwn.plampycc`, version 1.0.2. Preference compatibility intentionally retains domain `com.misakaproject.plampyCC`.

Assets are copied from the supplied package into this isolated project. The logical runtime location is `/var/mobile/Library/Application Support/PlampyCC/<theme>`; `ROOT_PATH_NS` resolves it to the rootless namespace. The checked-in logical layout is `layout/var/mobile/...`, and the verified rootless scheme stages it at `/var/jb/var/mobile/...` exactly once. CAML references use that final installed root. The source never uses the legacy `/var/mobile/Documents/.plampyCC` working directory.

The tweak, filter, PreferenceLoader registration and preference bundle all use logical install paths; Theos revision `5280bd038207e14f8bd76f5417aa2fe641c03228` supplies `THEOS_PACKAGE_INSTALL_PREFIX=/var/jb`, rootless headers, scheme staging and verified `STRIP=0` behavior. No hand-maintained payload path includes `/var/jb`, so no second prefix is possible. The macOS workflow checks these exact rules before building.

The original `selectImage` preference action remains pending a Steph product decision: this reconstruction preserves the stock wallpaper source when the feature is unavailable, and makes no parity claim. Enabling it requires separate approval and an identified original contract.

Animated CAML routing now implements only the verified 21D50 construct-and-pass route: the three setter hooks, rooted theme bundle construction, exact ownership/release behavior, the verified slider superclass move, and fail-open original-description fallback. It is not runtime-verified and does not claim CAML success, animation parity, or device stability. Five runtime observations remain explicitly deferred in `CAML-ROUTING-BLOCKER.md`.

The staged macOS workflow pins Theos, SDK, checkout, Bun, and artifact-upload revisions. It is not dispatched by this task. A production arm64e package remains unbuilt on this Linux host because the modern arm64e ABI requires the pinned macOS build boundary.

Runtime parity remains unproved for the active beta build `21D5044a`; static compatibility evidence is for final iOS 17.3 `21D50`.
