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
The serialized `state` field (`g`) uses a `%.12s` wire precision. Every
approved state token is therefore unique and no longer than 12 characters;
`CAMLDiagnosticCore.hpp` enforces that contract at compile time. The literal
values in `events.jsonl` are:

- `skip-disable`, `skip-no-api`, `skip-no-img`, `skip-nil`, `skip-id-nil`,
  `skip-no-icon`: a ranked admission/bail cause;
- `glyph-appl`, `glyph-sel-ap`, `generic-app`: an image was written by the
  corresponding reconcile path;
- `stable-kept`, `stable-repl`, `stable-miss`, `stable-gone`: a read-only check
  two seconds after application.

`stable-repl` is the discriminator for a post-reconcile overwrite;
`skip-*` plus `unknown-class` identifies topology/admission failure. The
identifier-change nil-glyph bail emits `skip-id-nil` before returning, so a
stock glyph disappearing during identity recovery remains observable. The
observer site labels are `glyph-recon` and `glyph-probe`; they are also
bounded and allowlisted. The probe never invokes a setter, layout invalidation,
or recursive reconcile, so it cannot recreate the prior watchdog loop.

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
- Owned suffix: `PlampyCC/CAML-Diagnostic`, walked strictly
  descriptor-confined: every component opened relative to the held
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
   - no `glyph-recon` record: admission/initialization gate;
   - `skip-no-icon` or `unknown-class`: ownership/topology mismatch;
   - `glyph-appl` followed by `stable-repl`: later overwrite;
   - `glyph-appl` plus `stable-kept` but stock display: selected-slot or
     rendering mismatch, not a missing write.
5. Flush at the existing dismissal seam, then verify the file contains only
   allowlisted package/state/class values. Delete the diagnostic artifact after
   review according to the operator's device policy.

No result is claimed until a device-authorized collection supplies one of these
records. The source/test change is therefore instrumentation, not a speculative
functional hook.
