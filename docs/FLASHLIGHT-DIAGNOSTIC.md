# Flashlight compact-glyph diagnostic — iOS 17.2 (21D50)

Task: `t_5c22b84e`. This note records the static conclusion and the bounded
runtime observation added for the remaining Flashlight stock-glyph failure.
It does not authorize device access, installation, respring, or deployment.

## Static conclusion

`FlashlightModule` has no `glyphPackageDescription:` route. The compact
controller is `CCUIFlashlightModuleViewController`, a
`CCUIButtonModuleViewController` subclass, and the compact host is the stock
`CCUIButtonModuleView`. The module updates static images through
`setGlyphImage:` and, where present, `setSelectedGlyphImage:` from
`_updateGlyphForFlashlightLevel:`. `CCUIRoundButton` exposes the primary glyph
slot but not the selected slot. Therefore another CAML/package hook is not a
supported fix for this failure.

The remaining falsifiable causes are ranked as follows:

1. The hooked view is not the runtime compact host or its
   `_viewControllerForAncestor` is not the expected Flashlight controller.
2. The reconcile path is admitted but one required image/API/glyph slot is
   absent at the first layout pass.
3. The primary glyph is applied but a later `SBUIFlashlightController` level
   callback overwrites it.
4. The master preference or hook initialization prevents admission.

The implementation makes no new hook and does not alter the original
Flashlight callback. It records only bounded tokens through the existing
compile-time diagnostic gate and shared ring/allowlist/dedup path.

## Diagnostic fields and interpretation

`events.jsonl` records the existing view tag and approved ancestor class. The
new `state` tokens are:

- `skip-disabled`, `skip-no-api`, `skip-no-image`, `skip-nil-glyph`,
  `skip-no-icon`: a ranked admission/bail cause;
- `glyph-applied`, `glyph-selected-applied`, `generic-applied`: an image was
  written by the corresponding reconcile path;
- `stability-kept`, `stability-replaced`, `stability-missing`,
  `stability-deallocated`: a read-only check two seconds after application.

`stability-replaced` is the discriminator for a post-reconcile overwrite;
`skip-*` plus `unknown-class` identifies topology/admission failure. The probe
never invokes a setter, layout invalidation, or recursive reconcile, so it
cannot recreate the prior watchdog loop.

## Authorized device collection sequence

Run only under a separate device-authorized task:

1. Build the diagnostic variant with `DIAGNOSTIC=1` and enable the existing
   diagnostic preference. Do not install or respring as part of this task.
2. Open Control Center once and expand/collapse Flashlight once. Reproduce the
   stock-glyph observation once, then stop on any crash, watchdog symptom, or
   unexpected filesystem path.
3. Collect only the bounded file
   `/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/events.jsonl`
   (the production path is created by `DiagnosticOutputDirectory`). Do not
   collect crash logs, paths, identifiers, or unrelated SpringBoard logs in the
   same artifact.
4. Group records by `site` and `viewTag`; compare `ancestorClass` and `state`.
   Expected decisive outcomes:
   - no `glyph-reconcile` record: admission/initialization gate;
   - `skip-no-icon` or `unknown-class`: ownership/topology mismatch;
   - `glyph-applied` followed by `stability-replaced`: later overwrite;
   - `glyph-applied` plus `stability-kept` but stock display: selected-slot or
     rendering mismatch, not a missing write.
5. Flush at the existing dismissal seam, then verify the file contains only
   allowlisted package/state/class values. Delete the diagnostic artifact after
   review according to the operator's device policy.

No result is claimed until a device-authorized collection supplies one of these
records. The source/test change is therefore instrumentation, not a speculative
functional hook.
