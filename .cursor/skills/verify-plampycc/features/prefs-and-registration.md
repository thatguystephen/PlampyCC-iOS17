# Feature map: preferences and registration

Surface: preference bundle build discipline and the logical-path registration chain.

Sources: `prefs/` (`RootListController.m`, `Makefile`, `Root.plist`, `Info.plist`), `layout/Library/PreferenceLoader/Preferences/PlampyCC.plist`, `layout/Library/MobileSubstrate/DynamicLibraries/PlampyCC.plist`, `PlampyCC.plist`, `control`.

## Gates (repo root)

```bash
python3 -B tests/prefs-arc-contract.py
python3 -B tests/manifest-contract.py
bun tests/static-check.ts
```

What each proves:

- `prefs-arc-contract.py` — reproduces the MRC dangling-`_specifiers` failure against the retained/ARC assignment that survives a pool drain; asserts the prefs bundle compiles with `-fobjc-arc` and the flag lands before the bundle make include; asserts the gate is wired into CI.
- `bun tests/static-check.ts` — PreferenceLoader entry contract (controller class name without `.bundle`, `icon.png`, `isController=1`), logical install paths with no second `/var/jb` prefix anywhere in `Makefile`/`prefs/Makefile`, staged registration files exist, preference lifecycle (`setPreferenceValue` + Darwin notification post), `control` metadata fields.
- `manifest-contract.py` — the preferences binary is a declared manifest target alongside the tweak in both architectures.

## Device gap

Host gates prove build flags and registration shapes, not that the pane loads. Device proof (separate authorized task): open Settings → PlampyCC, toggle each switch, confirm the preference notification reconciles live state.

## Triage

Pane missing on device → PreferenceLoader registration path or `isController`/`bundle` fields (static-check names the exact assertion). Pane crashes on open → specifier lifecycle (`prefs-arc-contract.py`'s failing fixture shows the MRC symptom). Toggles do nothing live → notification seam (`CFNotificationCenterPostNotification` in the controller) or the consumer reconcile path (see `caml-replacement-route.md`).