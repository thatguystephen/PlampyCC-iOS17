"""Regression contract for compact glyph routing and repeated module updates."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Tweak.xm").read_text()


def body(name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\(", SOURCE)
    assert match, f"missing {name}"
    opening = SOURCE.find("{", match.start())
    depth = 0
    for index in range(opening, len(SOURCE)):
        depth += SOURCE[index] == "{"
        depth -= SOURCE[index] == "}"
        if depth == 0:
            return SOURCE[opening + 1:index]
    raise AssertionError(f"unterminated {name}")


compact = body("CompactSubstitutedArgument")
set_glyph = body("compactSetGlyph")
set_selected = body("compactSetSelectedGlyph")
reconcile = body("ReconcileGlyphView")

# Timer and Notes must never invoke ancestry traversal from either global setter;
# ownership is classified once at the view lifecycle seam instead.
assert "AncestorController" not in compact
assert "NSClassFromString" not in compact
assert "kFlashlightOwnedView" in compact
assert "AncestorController(view)" in reconcile
assert "kFlashlightOwnedView" in reconcile
assert "@(flashlightOwned)" in reconcile

# Every repeated Timer/Notes push forwards the original image unchanged, while
# Flashlight substitution is gated by the cached ownership marker.
for setter in (set_glyph, set_selected):
    assert "gCompactGlyphForwarding ? image : CompactSubstitutedArgument" in setter
    assert "gCompactGlyphForwarding = YES" in setter
    assert "gCompactGlyphForwarding = NO" in setter
    assert "orig_" in setter
assert "CompactGlyphSubstitute(image, selectedSlot)" in compact

# The lifecycle gate must clear ownership for non-Flashlight module views before
# the generic path, preventing reused Timer/Notes views from inheriting it.
assert "objc_setAssociatedObject(view, &kFlashlightOwnedView" in reconcile
assert reconcile.index("objc_setAssociatedObject(view, &kFlashlightOwnedView") < reconcile.index("if (flashlightOwned)")

print("PASS: compact setter forwarding is ancestry-free, Flashlight-owned only, and reentrancy-guarded for repeated Timer/Notes updates")
