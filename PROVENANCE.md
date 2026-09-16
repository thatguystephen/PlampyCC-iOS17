# PlampyCC iOS 17 clean-room reconstruction

This project reconstructs the PlampyCC 1.0.2 behavior from the supplied package and static evidence; it does not claim the original source or authorship. Upstream/package attribution: **sugiuta**, package maintained by **CyPwn**, package identifier `xyz.cypwn.plampycc`, version 1.0.2. Preference compatibility intentionally retains domain `com.misakaproject.plampyCC`.

Assets are copied from the supplied package into this isolated project. The logical runtime location is `/var/mobile/Library/Application Support/PlampyCC/<theme>`; `ROOT_PATH_NS` resolves it to the rootless namespace, and the staged payload is under `layout/var/jb/var/mobile/...`. CAML references use that same installed root. The source never uses the legacy `/var/mobile/Documents/.plampyCC` working directory.

The tweak and preference bundle each declare logical install paths; Theos applies the rootless package prefix once. The hand-maintained `layout/var/jb` entries are already staged paths and are not passed through a second prefixing rule.

The original `selectImage` preference action is deferred: this reconstruction preserves the stock wallpaper source when the feature is unavailable, and makes no parity claim. Enabling it requires separate approval and an identified original contract.

The staged macOS workflow pins Theos, SDK, checkout, Bun, and artifact-upload revisions. It is not dispatched by this task. A production arm64e package remains unbuilt on this Linux host because the modern arm64e ABI requires the pinned macOS build boundary.

Runtime parity remains unproved for the active beta build `21D5044a`; static compatibility evidence is for final iOS 17.3 `21D50`.
