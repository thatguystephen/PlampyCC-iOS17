# PlampyCC iOS 17 clean-room reconstruction

This project reconstructs the PlampyCC 1.0.2 behavior from the supplied package and static evidence; it does not claim the original source or authorship. Upstream/package attribution: **sugiuta**, package maintained by **CyPwn**, package identifier `xyz.cypwn.plampycc`, version 1.0.2. Preference compatibility intentionally retains domain `com.misakaproject.plampyCC`.

Assets are copied from the supplied package into this isolated project and are installed by the eventual rootless package under `/var/mobile/Library/Application Support/PlampyCC/<theme>`. The source never uses the legacy `/var/mobile/Documents/.plampyCC` working directory.

The staged macOS workflow pins Theos, SDK, checkout, Bun, and artifact-upload revisions. It is not dispatched by this task. A production arm64e package remains unbuilt on this Linux host because the modern arm64e ABI requires the pinned macOS build boundary.

Runtime parity remains unproved for the active beta build `21D5044a`; static compatibility evidence is for final iOS 17.3 `21D50`.
