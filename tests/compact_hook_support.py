"""Shared compact-glyph hook contract assertions.

src/Tweak.xm classifies Flashlight ownership once at the ReconcileGlyphView
lifecycle seam and caches the verdict in the kFlashlightOwnedView associated
marker (commit dc9570e moved classification out of the setter path). The hot
compact substitution (CompactSubstitutedArgument) reads only that cached
marker: no ancestry traversal and no runtime class discovery may return to the
setter hot path.

tests/icon-cache-contract.py and tests/compact-glyph-hook-contract.py both run
these assertions so the safe cached-marker shape and the old
synchronous-ancestry shape cannot drift between the two gates. Both test
commands must also stay wired into the CI build gate and the verify-plampycc
Doctor surface; that wiring is asserted here as well.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Never

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-rootless.yml"
DOCTOR = ROOT / ".cursor/skills/verify-plampycc/SKILL.md"

MARKER_WRITE = (
    "objc_setAssociatedObject(view, &kFlashlightOwnedView, "
    "@(flashlightOwned), OBJC_ASSOCIATION_RETAIN_NONATOMIC)"
)
MARKER_READ = "objc_getAssociatedObject(self, &kFlashlightOwnedView)"

# Both contracts must run in both gate surfaces (build gate and Doctor), or the
# two source shapes could diverge silently behind one green gate.
GATE_COMMANDS = (
    "python3 -B tests/icon-cache-contract.py",
    "python3 -B tests/compact-glyph-hook-contract.py",
)


def fail(message: str) -> Never:
    raise SystemExit(message)


def check(value: bool, message: str) -> None:
    if not value:
        fail(message)


def function_body(text: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\(", text)
    if not match:
        fail(f"missing function {name}")
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index]
    fail(f"unterminated function {name}")


def assert_compact_hook_contract(source: str) -> None:
    """The safe hot/cold split for compact Flashlight substitution."""
    compact = function_body(source, "CompactSubstitutedArgument")
    reconcile = function_body(source, "ReconcileGlyphView")
    setters = {
        "compactSetGlyph": function_body(source, "compactSetGlyph"),
        "compactSetSelectedGlyph": function_body(source, "compactSetSelectedGlyph"),
    }

    # Hot path: the compact gate consults only the cached ownership marker and
    # fails open to the caller's image when the marker or the themed art is
    # missing.
    check("kFlashlightOwnedView" in compact,
          "hot compact substitution does not consult the kFlashlightOwnedView marker")
    check(MARKER_READ in compact,
          "hot compact substitution does not read the cached ownership marker")
    check(compact.index(MARKER_READ) < compact.index("CompactGlyphSubstitute("),
          "hot compact substitution is not gated on the cached ownership marker")
    check("CompactGlyphSubstitute(image, selectedSlot)" in compact,
          "hot compact substitution does not delegate to the fail-open substitute")
    check("return image;" in compact,
          "hot compact substitution lacks the fail-open original-argument fallback")
    for token, description in (
        ("AncestorController", "ancestry traversal"),
        ("_viewControllerForAncestor", "ancestry traversal"),
        ("NSClassFromString", "runtime class discovery"),
        ("isKindOfClass", "runtime class probing"),
    ):
        check(token not in compact,
              f"hot compact substitution performs {description} ({token})")

    # Cold path: ReconcileGlyphView owns the lifecycle classification. It
    # resolves the Flashlight module class, traverses the ancestor seam once,
    # and writes the marker unconditionally before the Flashlight branch, so a
    # non-Flashlight reuse clears ownership instead of inheriting it.
    check('NSClassFromString(@"CCUIFlashlightModuleViewController")' in reconcile,
          "cold lifecycle classification does not resolve the Flashlight module class")
    check("AncestorController(view)" in reconcile,
          "cold lifecycle classification does not traverse the ancestor seam")
    check(reconcile.count("objc_setAssociatedObject(view, &kFlashlightOwnedView") == 1,
          "ownership classification must write the marker at exactly one site")
    check(MARKER_WRITE in reconcile,
          "lifecycle classification does not cache the kFlashlightOwnedView verdict")
    check(reconcile.index("AncestorController(view)") < reconcile.index(MARKER_WRITE)
          < reconcile.index("if (flashlightOwned)"),
          "the ownership marker is not written before the Flashlight branch")
    check("ReleaseFlashlightGlyphs(view)" in reconcile
          and reconcile.index(MARKER_WRITE) < reconcile.index("ReleaseFlashlightGlyphs(view)"),
          "non-Flashlight reuse does not clear Flashlight glyph ownership")

    # Both setters keep the thread-local exactly-once forwarding behavior: the
    # guard is thread-local, checked before substitution, set around exactly
    # one predecessor call, and always reset.
    check(source.count("static __thread BOOL gCompactGlyphForwarding;") == 1,
          "compact setters do not share exactly one thread-local forwarding guard")
    for name, setter in setters.items():
        check("gCompactGlyphForwarding ? image : CompactSubstitutedArgument" in setter,
              f"{name} does not consult the thread-local forwarding guard first")
        check(setter.count("(self, cmd, argument)") == 1,
              f"{name} does not invoke its captured predecessor exactly once")
        check("gCompactGlyphForwarding = YES" in setter
              and "@finally { gCompactGlyphForwarding = NO; }" in setter,
              f"{name} does not bracket the predecessor call with the forwarding guard")
        check(setter.index("gCompactGlyphForwarding = YES")
              < setter.index("(self, cmd, argument)")
              < setter.index("@finally { gCompactGlyphForwarding = NO; }"),
              f"{name} does not hold the forwarding guard across exactly one predecessor call")


def assert_compact_hook_gate_wiring() -> None:
    """Both contract tests stay wired into CI and the Doctor surface."""
    workflow = WORKFLOW.read_text()
    doctor = DOCTOR.read_text()
    for command in GATE_COMMANDS:
        check(command in workflow,
              f"{command} is not wired into the build gate")
        check(command in doctor,
              f"{command} is not wired into the verify-plampycc Doctor surface")
