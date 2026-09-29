"""Regression contract for compact glyph routing and repeated module updates.

Ownership classification and the safe hot-path shape are asserted in the shared
helper so this gate and tests/icon-cache-contract.py cannot drift: src/Tweak.xm
classifies Flashlight ownership once at the ReconcileGlyphView lifecycle seam
(Timer and Notes views never invoke ancestry traversal from either global
setter) and caches it in the kFlashlightOwnedView marker that the hot
CompactSubstitutedArgument reads. Both contracts must stay wired into the CI
build gate and the verify-plampycc Doctor surface.
"""
from pathlib import Path

from compact_hook_support import (
    assert_compact_hook_contract,
    assert_compact_hook_gate_wiring,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Tweak.xm").read_text()

assert_compact_hook_contract(SOURCE)
assert_compact_hook_gate_wiring()

print(
    "PASS: compact setter forwarding is ancestry-free, Flashlight-owned only, "
    "and reentrancy-guarded for repeated Timer/Notes updates"
)