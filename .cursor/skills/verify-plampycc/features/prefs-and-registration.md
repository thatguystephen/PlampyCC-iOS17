# Preferences and registration

The preference pane is a Settings bundle whose build discipline and registration chain decide whether the user can reach PlampyCC's toggles at all. Surface: preference bundle build discipline and the logical-path registration chain.

Sources: `prefs/` (`RootListController.m`, `Makefile`, `Root.plist`, `Info.plist`), `layout/Library/PreferenceLoader/Preferences/PlampyCC.plist`, `layout/Library/MobileSubstrate/DynamicLibraries/PlampyCC.plist`, `PlampyCC.plist`, `control`.

## Sub-features

- `prefs-arc-lifecycle` keeps specifier storage valid across a pool drain (retained/ARC assignment, not MRC dangling `_specifiers`).
- `prefs-compile-discipline` compiles the bundle with `-fobjc-arc`, the flag landing before the bundle make include, wired into CI.
- `prefs-registration` exposes the pane through PreferenceLoader (controller class name without `.bundle`, `icon.png`, `isController=1`).
- `prefs-paths` installs through logical paths with no second `/var/jb` prefix anywhere in `Makefile`/`prefs/Makefile`.
- `prefs-lifecycle-notify` writes preferences via `setPreferenceValue` and posts the Darwin notification consumers reconcile through.

## How to get to it (user POV)

- Open Settings → PlampyCC on the jailbroken iPhone.
- Toggle each switch and watch the Control Center module state reconcile live (no respring).
- Relaunch Settings and confirm the pane and its values survive.

## Driving it with the prefs ARC harness

Preconditions:

- Repo root as CWD on the Linux host ([ADDRESS], g++, bun).
- `git status --porcelain` shows exactly the intended diff.

- **Specifier lifecycle.** (User action: open the pane, scroll, leave and reopen it.) Run `python3 -B tests/prefs-arc-contract.py`. One PASS line, exit 0. The gate reproduces the MRC dangling-`_specifiers` failure against the retained/ARC assignment that survives a pool drain; asserts the prefs bundle compiles with `-fobjc-arc` and the flag lands before the bundle make include; asserts the gate is wired into CI.
- **Registration chain.** (User action: find the PlampyCC row in Settings.) Run `bun tests/static-check.ts`. One PASS line, exit 0. PreferenceLoader entry contract (controller class name without `.bundle`, `icon.png`, `isController=1`), logical install paths with no second `/var/jb` prefix anywhere in `Makefile`/`prefs/Makefile`, staged registration files exist, preference lifecycle (`setPreferenceValue` + Darwin notification post), `control` metadata fields.
- **Manifest presence.** Run `python3 -B tests/manifest-contract.py`. One PASS line, exit 0. The preferences binary is a declared manifest target alongside the tweak in both architectures.

## Gotchas

- Pane missing on device → PreferenceLoader registration path or `isController`/`bundle` fields (static-check names the exact assertion). Pane crashes on open → specifier lifecycle (`prefs-arc-contract.py`'s failing fixture shows the MRC symptom). Toggles do nothing live → notification seam (`CFNotificationCenterPostNotification` in the controller) or the consumer reconcile path (see `caml-replacement-route.md`).
- Host gates prove build flags and registration shapes, not that the pane actually loads — that is device-only.
- `manifest-contract.py` and `static-check.ts` are shared with the package/registration maps — one run covers all, do not double-report.

## Observable proof

Non-device boundary: the three gate commands above, each with one PASS line and exit 0, captured under `evidence/verify-<YYYYMMDD-HHMM>/` (e.g. `drive-prefs-and-registration.txt`), including the MRC-vs-ARC pool-drain reproduction and the exact registration-field assertions.

Device-only gap (separate authorized task): open Settings → PlampyCC on the jailbroken iPhone, toggle each switch, and confirm the preference notification reconciles live state in Control Center. Expected evidence: pane screenshot, per-toggle before/after module captures, and a relaunch showing persisted values.
