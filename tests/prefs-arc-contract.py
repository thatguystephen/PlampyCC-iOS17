from __future__ import annotations

from pathlib import Path
from typing import Never

ROOT = Path(__file__).resolve().parents[1]
PREFS_MAKEFILE = (ROOT / "prefs/Makefile").read_text()
CONTROLLER = (ROOT / "prefs/RootListController.m").read_text()
WORKFLOW = (ROOT / ".github/workflows/build-rootless.yml").read_text()


def fail(message: str) -> Never:
    raise SystemExit(message)


def assert_true(value: bool, message: str) -> None:
    if not value:
        fail(message)


# Ownership model of the Preferences crash (main-thread SIGABRT,
# NSInvalidArgumentException on -[UIView removePropertyForKey:] and
# -[UIGestureRecognizerTarget propertyForKey:] while PSListController walked
# _specifiers). loadSpecifiersFromPlistName: returns an autoreleased array: it
# survives only while the autorelease pool holds it or an owner retains it.
# Under MRC the direct `_specifiers = <autoreleased>` assignment adds no owner,
# so the first pool drain frees the array and its memory is reused by unrelated
# UIKit objects — the observed unrecognized selectors. Under ARC the assignment
# itself is a strong store, so the walk after the pool drain still sees the
# live specifier objects. The model reproduces both outcomes.
class Specifier:
    pass


class ForeignObject:
    """Stand-in for whatever reuses the freed slot (UIView, gesture target)."""


class HeapSlot:
    def __init__(self, owners: int, entries: list[object]) -> None:
        self.owners = owners
        self.entries = entries

    def autorelease(self) -> None:
        self.owners -= 1

    def retain(self) -> None:
        self.owners += 1


def run_case(retain_on_assign: bool) -> list[str]:
    slot = HeapSlot(owners=1, entries=[Specifier(), Specifier(), Specifier()])
    if retain_on_assign:
        slot.retain()  # ARC strong store into _specifiers
    slot.autorelease()  # pool drain at the end of the runloop turn
    if slot.owners == 0:
        reused: list[object] = [ForeignObject()]  # freed memory reused
        slot.entries = reused
    return [entry.__class__.__name__ for entry in slot.entries]


mrc_walk = run_case(retain_on_assign=False)
assert_true(
    mrc_walk == ["ForeignObject"],
    "MRC model no longer reproduces the dangling _specifiers walk "
    "(unretained autoreleased assignment must expose reused foreign slots)",
)
arc_walk = run_case(retain_on_assign=True)
assert_true(
    arc_walk == ["Specifier", "Specifier", "Specifier"],
    "retained/ARC assignment does not keep the specifier array intact across "
    "the pool drain",
)

# Contract: the prefs translation unit is built with ARC enabled.
assert_true(
    "PlampyCC_CFLAGS = -fobjc-arc" in PREFS_MAKEFILE,
    "prefs bundle is not compiled with -fobjc-arc (MRC build dangles _specifiers)",
)
assert_true(
    PREFS_MAKEFILE.index("PlampyCC_CFLAGS = -fobjc-arc") < PREFS_MAKEFILE.index("bundle.mk"),
    "prefs ARC flag is not applied before the bundle make include",
)

# Contract: the controller is ARC-authored, so the flag is load-bearing.
assert_true(
    "release" not in CONTROLLER.replace("Release", "")
    and "retain" not in CONTROLLER.replace("Retain", "")
    and "autorelease" not in CONTROLLER,
    "RootListController.m mixes MRC ownership calls with the ARC build",
)
assert_true(
    "_specifiers = [self loadSpecifiersFromPlistName:@\"Root\" target:self]" in CONTROLLER,
    "specifiers getter no longer loads through loadSpecifiersFromPlistName:",
)
assert_true(
    "- (NSArray *)specifiers" in CONTROLLER,
    "specifiers getter is missing",
)

# Contract: the regression gate runs in the build workflow.
assert_true(
    "python3 -B tests/prefs-arc-contract.py" in WORKFLOW,
    "prefs ARC regression is not wired into the build gate",
)

print(
    "PASS: MRC autoreleased _specifiers assignment reproduces the dangling "
    "specifier walk while retained/ARC assignment survives the pool drain; "
    "the prefs bundle is built ARC and the gate is wired"
)
