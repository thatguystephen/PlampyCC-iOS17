from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Never

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Tweak.xm").read_text()
WORKFLOW = (ROOT / ".github/workflows/build-rootless.yml").read_text()


def fail(message: str) -> Never:
    raise SystemExit(message)


def assert_true(value: bool, message: str) -> None:
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


# UIImage uses object identity for this ownership state. A fresh decode on every
# layout pass therefore keeps invoking both setters, while a memoized decode
# reaches a fixed point after the first pass.
def setter_writes(loader: Callable[[str], object]) -> tuple[int, int]:
    current = {"off": object(), "on": object()}
    writes_per_pass = []
    for _ in range(2):
        writes = 0
        for slot, name in (("off", "FlashlightOff"), ("on", "FlashlightOn")):
            replacement = loader(f"0:{name}")
            if current[slot] is not replacement:
                current[slot] = replacement
                writes += 1
        writes_per_pass.append(writes)
    return writes_per_pass[0], writes_per_pass[1]


fresh_first, fresh_second = setter_writes(lambda _key: object())
assert_true(
    fresh_first == 2 and fresh_second == 2,
    "negative control no longer reproduces repeated layout writes",
)

objects: dict[str, object] = {}


def memoized_loader(key: str) -> object:
    if key not in objects:
        objects[key] = object()
    return objects[key]


cached_first, cached_second = setter_writes(memoized_loader)
assert_true(
    cached_first == 2 and cached_second == 0,
    "memoized image identity does not converge after the first layout pass",
)

icon = function_body(SOURCE, "IconImage")
reload = function_body(SOURCE, "ReloadPrefs")
reconcile = function_body(SOURCE, "ReconcileGlyphView")
assert_true(
    "static NSMutableDictionary<NSString *, id> *gIconImages" in SOURCE,
    "IconImage does not own a bounded process-local identity cache",
)
assert_true(
    'stringWithFormat:@"%ld:%@", (long)gTheme, name' in icon,
    "icon cache key does not include theme and icon identity",
)
assert_true(
    icon.index("gIconImages[cacheKey]") < icon.index("ThemeFile(relative)"),
    "IconImage performs filesystem lookup before consulting the cache",
)
assert_true(
    icon.count("imageWithContentsOfFile:") == 1
    and "gIconImages[cacheKey] = image ?: (id)NSNull.null" in icon,
    "IconImage does not cache both successful decodes and misses",
)
assert_true(
    "cached == NSNull.null ? nil : cached" in icon,
    "cached misses do not fail open without repeating filesystem I/O",
)
assert_true(
    reload.index("[gIconImages removeAllObjects]")
    < reload.index("for (id view in gGlyphViews)"),
    "preference reload does not invalidate icons before static glyph reconciliation",
)
assert_true(
    reconcile.index("[NSThread isMainThread]") < reconcile.index("ReconcileFlashlightView(view)"),
    "icon cache use is no longer confined behind the main-thread reconciliation hop",
)

assert_true(
    "python3 -B tests/icon-cache-contract.py" in WORKFLOW,
    "icon identity regression is not wired into the build gate",
)

# Header-glyph substitution contract (src/Tweak.xm): the Flashlight header
# setter substitutes the cached themed FlashlightOff/FlashlightOn decode for
# the pushed stock image only when the functional state is enabled and the
# receiver is exactly CCUIFlashlightBackgroundViewController. Every case that
# cannot be substituted faithfully — disabled state, any other class, or a
# nil/missing/invalid themed image — fails open and forwards the caller's
# arguments unchanged.
class Themed:
    def __init__(self, name: str) -> None:
        self.name = name


INCOMING = "incoming-image"

def header_argument(*, enabled: bool, exact_class: bool, on_state: bool,
                    cache: dict[str, object]) -> object:
    """Decision model of headerGlyph/HeaderGlyphSubstitute in src/Tweak.xm."""
    if not enabled or not exact_class:
        return INCOMING
    themed = cache.get("FlashlightOn" if on_state else "FlashlightOff")
    if not isinstance(themed, Themed):
        return INCOMING
    return themed.name


decoded: dict[str, object] = {"FlashlightOff": Themed("FlashlightOff"),
                              "FlashlightOn": Themed("FlashlightOn")}
assert_true(
    header_argument(enabled=True, exact_class=True, on_state=True, cache=decoded)
    == "FlashlightOn",
    "on-state header push does not substitute the cached FlashlightOn image",
)
assert_true(
    header_argument(enabled=True, exact_class=True, on_state=False, cache=decoded)
    == "FlashlightOff",
    "off-state header push does not substitute the cached FlashlightOff image",
)
fail_open_cases = {
    "disabled": dict(enabled=False, exact_class=True, on_state=True, cache=decoded),
    "other-class": dict(enabled=True, exact_class=False, on_state=True, cache=decoded),
    "nil-themed": dict(enabled=True, exact_class=True, on_state=True,
                       cache={"FlashlightOn": None, "FlashlightOff": Themed("FlashlightOff")}),
    "missing-themed": dict(enabled=True, exact_class=True, on_state=False,
                           cache={"FlashlightOn": Themed("FlashlightOn")}),
    "invalid-themed": dict(enabled=True, exact_class=True, on_state=False,
                           cache={"FlashlightOff": object(), "FlashlightOn": Themed("FlashlightOn")}),
}
for label, case in fail_open_cases.items():
    assert_true(
        header_argument(**case) == INCOMING,
        f"header-glyph {label} case does not fail open to the caller's arguments",
    )

# Forwarding-decision model (docs/FLASHLIGHT-DIAGNOSTIC.md): the verdict the
# functional hook records for every invocation. The not-applicable gate is a
# bypass; a gate pass with nothing valid to forward (nil push or a
# nil/missing/invalid themed decode) fails open to the caller's image; only a
# themed decode forwarded is a substitution.
def header_forward(*, enabled: bool, exact_class: bool, on_state: bool,
                   cache: dict[str, object], push: object = INCOMING) -> tuple[object, str]:
    """Decision-token model of headerGlyph in src/Tweak.xm."""
    if not enabled or not exact_class:
        return push, "hdr-bypass"
    themed = None if push is None else cache.get("FlashlightOn" if on_state else "FlashlightOff")
    if not isinstance(themed, Themed):
        return push, "hdr-failop"
    return themed.name, "hdr-subst"

assert_true(
    header_forward(enabled=True, exact_class=True, on_state=True, cache=decoded)
    == ("FlashlightOn", "hdr-subst"),
    "on-state substitution does not record hdr-subst",
)
assert_true(
    header_forward(enabled=True, exact_class=True, on_state=False, cache=decoded)
    == ("FlashlightOff", "hdr-subst"),
    "off-state substitution does not record hdr-subst",
)
for label, case in {
    "disabled": dict(enabled=False, exact_class=True, on_state=True, cache=decoded),
    "other-class": dict(enabled=True, exact_class=False, on_state=True, cache=decoded),
    "other-class-nil-push": dict(enabled=True, exact_class=False, on_state=False,
                                 cache=decoded, push=None),
}.items():
    assert_true(
        header_forward(**case)[1] == "hdr-bypass",
        f"header-glyph {label} case must record the gate-not-applicable verdict",
    )
for label, case in {
    "nil-push": dict(enabled=True, exact_class=True, on_state=False, cache=decoded,
                     push=None),
    "nil-themed": dict(enabled=True, exact_class=True, on_state=True,
                       cache={"FlashlightOn": None, "FlashlightOff": Themed("FlashlightOff")}),
    "missing-themed": dict(enabled=True, exact_class=True, on_state=False,
                           cache={"FlashlightOn": Themed("FlashlightOn")}),
    "invalid-themed": dict(enabled=True, exact_class=True, on_state=False,
                           cache={"FlashlightOff": object(), "FlashlightOn": Themed("FlashlightOn")}),
}.items():
    assert_true(
        header_forward(**case)[1] == "hdr-failop",
        f"header-glyph {label} case must record the fail-open verdict",
    )

header_hook = function_body(SOURCE, "headerGlyph")
header_substitute = function_body(SOURCE, "HeaderGlyphSubstitute")
header_install = function_body(SOURCE, "InstallHeaderGlyphHook")
header_abi = function_body(SOURCE, "HeaderGlyphEncodingMatches")
assert_true(
    'NSClassFromString(@"CCUIFlashlightBackgroundViewController")' in header_hook,
    "header-glyph substitution does not name the verified receiver class",
)
assert_true(
    "object_getClass(self) == flashlightClass" in header_hook,
    "header-glyph substitution is not confined to the exact receiver class",
)
assert_true(
    header_hook.index("gEnabled") < header_hook.index("HeaderGlyphSubstitute("),
    "header-glyph substitution does not consult the existing functional state first",
)
assert_true(
    'if (!image) return nil;' in header_substitute,
    "a nil header-glyph push does not fail open",
)
assert_true(
    'NSString *name = off ? @"FlashlightOff" : @"FlashlightOn";' in header_substitute
    and "SizedGlyphArt(name, image.size)" in header_substitute,
    "header-glyph substitution does not select the themed art by state and render it memoized",
)
assert_true(
    "[themed isKindOfClass:UIImage.class] ? themed : nil" in header_substitute,
    "header-glyph substitution does not fail open on a nil/missing/invalid themed image",
)
assert_true(
    "if (themed) argument = themed;" in header_hook,
    "header-glyph hook lacks the fail-open original-argument fallback",
)
assert_true(
    header_hook.index("HeaderGlyphSubstitute(image, pointSize)")
    < header_hook.index("orig_headerGlyph(self, cmd, argument, pointSize)"),
    "header-glyph substitution must decide before the original is invoked",
)
assert_true(
    "method_getTypeEncoding(method)" in header_install
    and "MSHookMessageEx(" in header_install,
    "header-glyph hook is not installed against the runtime encoding",
)
assert_true(
    header_install.index("HeaderGlyphEncodingMatches(") < header_install.index("MSHookMessageEx("),
    "header-glyph hook installs without passing the ABI shape check first",
)
assert_true(
    '"v32@0:8@16d24"' in header_abi and "strcmp(normalized, kExpected) == 0" in header_abi,
    "header-glyph ABI gate does not compare the verified encoding shape",
)
assert_true(
    SOURCE.count("@selector(setHeaderGlyphImage:unscaledSymbolPointSize:)") == 1,
    "exactly one header-glyph hook site is allowed in Tweak.xm",
)
assert_true(
    "InstallHeaderGlyphHook(" in function_body(SOURCE, "init_plampycc"),
    "the ABI-checked header-glyph hook is not installed at load",
)

# Install-availability contract (t_724201a5): zero header-hook records beside
# live header-glyph records proved the substitution hook never executed. The
# install was availability-gated at constructor time on
# CCUIFlashlightBackgroundViewController — a class defined in the Control
# Center plugin FlashlightModule.bundle, which loads after tweak constructors,
# so the lookup returned nil and the install silently skipped. The install must
# target the linked, load-time-registered seam owner instead; the
# exact-receiver-class gate in the hook body keeps behavior confined.
install_body = function_body(SOURCE, "init_plampycc")
assert_true(
    'NSClassFromString(@"CCUICustomContentModuleBackgroundViewController")' in install_body,
    "the header-glyph hook does not install against the linked seam-owner class",
)
assert_true(
    'NSClassFromString(@"CCUIFlashlightBackgroundViewController")' not in install_body,
    "the header-glyph install still depends on the lazily loaded Flashlight bundle class",
)

# Model/source coupling: the verdict the hook records is exactly the
# forwarding-decision model above — the not-applicable gate defaults to a
# bypass and the gate verdict is substitution versus fail-open.
assert_true('const char *decision = "hdr-bypass";' in header_hook
            and 'decision = themed ? "hdr-subst" : "hdr-failop";' in header_hook,
            "header-glyph hook verdicts do not match the forwarding-decision model")
assert_true('ObserveGlyph(self, decision, "header-hook");' in header_hook,
            "the forwarding-decision model is not what the hook records")

# Compact Flashlight substitution contract ([ADDRESS], src/Tweak.xm): the
# Flashlight module re-pushes per-level state symbols through both compact
# setters (evidence/ios17-module-glyph-seams-21D50.md section 2), so
# substitution is in flight like the header seam. State is deterministic from
# the setter slot, and the slot-to-art mapping follows the authoritative 21D50
# device observation: the normal setGlyphImage: slot displays while the
# flashlight is OFF and the setSelectedGlyphImage: slot while it is ON, so the
# normal setter carries the FlashlightOff art and the selected setter the
# FlashlightOn art. The 024a373 pairing (normal slot -> FlashlightOn art) is
# exactly the reversed-mapping regression this model rejects. Substitution
# renders through SizedGlyphArt at the pushed stock image's canvas (the sizing
# peer) because the pipelines size from the UIImage canvas, not the visible
# content: a content-only PNG shrink (56x80 -> 44x62 in the same 80x144
# canvas) left device rendering unchanged while the delivered package
# provably carried the new bytes. Every case that cannot be substituted
# faithfully fails open to the caller's image.
def compact_argument(*, enabled: bool, module_view: bool, push: object,
                     selected_slot: bool, cache: dict[str, object]) -> object:
    """Decision model of CompactSubstitutedArgument/CompactGlyphSubstitute."""
    if not enabled or not module_view or push is None:
        return push
    name = "FlashlightOn" if selected_slot else "FlashlightOff"
    if not isinstance(cache.get(name), Themed):
        return push
    return f"sized:{name}"

assert_true(
    compact_argument(enabled=True, module_view=True, push=INCOMING,
                     selected_slot=False, cache=decoded) == "sized:FlashlightOff",
    "setGlyphImage: does not render the FlashlightOff art for the resting slot",
)
assert_true(
    compact_argument(enabled=True, module_view=True, push=INCOMING,
                     selected_slot=True, cache=decoded) == "sized:FlashlightOn",
    "setSelectedGlyphImage: does not render the FlashlightOn art for the active slot",
)
for label, case in {
    "disabled": dict(enabled=False, module_view=True, push=INCOMING, selected_slot=False, cache=decoded),
    "other-module": dict(enabled=True, module_view=False, push=INCOMING, selected_slot=False, cache=decoded),
    "nil-push": dict(enabled=True, module_view=True, push=None, selected_slot=False, cache=decoded),
    "missing-themed": dict(enabled=True, module_view=True, push=INCOMING, selected_slot=False,
                           cache={"FlashlightOn": Themed("FlashlightOn")}),
    "invalid-themed": dict(enabled=True, module_view=True, push=INCOMING, selected_slot=False,
                           cache={"FlashlightOff": object(), "FlashlightOn": Themed("FlashlightOn")}),
}.items():
    assert_true(
        compact_argument(**case) == case["push"],
        f"compact {label} case does not fail open to the caller's image",
    )

compact_substitute = function_body(SOURCE, "CompactGlyphSubstitute")
compact_gate = function_body(SOURCE, "CompactSubstitutedArgument")
compact_install = function_body(SOURCE, "InstallCompactGlyphHooks")
compact_abi = function_body(SOURCE, "CompactGlyphEncodingMatches")
flashlight_body = function_body(SOURCE, "ReconcileFlashlightView")
header_sub = function_body(SOURCE, "HeaderGlyphSubstitute")
sized_art = function_body(SOURCE, "SizedGlyphArt")
assert_true(
    "if (!image) return nil;" in compact_substitute,
    "a nil compact push does not fail open",
)
assert_true(
    "CompactGlyphSubstitute(UIImage *image, BOOL selectedSlot)" in SOURCE
    and 'NSString *name = selectedSlot ? @"FlashlightOn" : @"FlashlightOff";' in compact_substitute,
    "compact substitution does not map setter slots to the authoritative state art",
)
assert_true(
    "SizedGlyphArt(name, image.size)" in compact_substitute,
    "compact substitution does not render at the pushed stock image's canvas",
)
assert_true(
    "[themed isKindOfClass:UIImage.class] ? themed : nil" in compact_substitute,
    "compact substitution does not fail open on a nil/missing/invalid themed image",
)
assert_true(
    "CompactSubstitutedArgument(self, image, NO)" in SOURCE
    and "CompactSubstitutedArgument(self, image, YES)" in SOURCE,
    "compact setter hooks do not pass their deterministic slot state",
)
assert_true(
    "UIGraphicsBeginImageContextWithOptions" in sized_art
    and "CGSizeMake(25.0, 48.0)" in sized_art
    and "drawInRect:" in sized_art,
    "sized glyph rendering does not mirror the original 25x48 currentImage construction",
)
assert_true(
    "if (!gSizedArt) gSizedArt = [NSMutableDictionary dictionary];" in sized_art
    and "id cached = gSizedArt[key];" in sized_art,
    "sized glyph renders are not memoized on image identity",
)
assert_true(
    "SetGlyphImage(view, offGlyph)" in flashlight_body
    and "SetSelectedGlyphImage(view, onGlyph)" in flashlight_body,
    "the reconcile does not write FlashlightOff to the resting slot and FlashlightOn to the active slot",
)
assert_true(
    '"appliedGlyph": offGlyph' in flashlight_body,
    "the reconcile does not track the resting-slot art as applied",
)
assert_true(
    'SizedGlyphArt(@"FlashlightOff", currentGlyph.size)' in flashlight_body
    and 'SizedGlyphArt(@"FlashlightOn", currentGlyph.size)' in flashlight_body,
    "the reconcile does not render at the replaced slot image's canvas",
)
assert_true(
    'kFlashlightOffSymbol = @"flashlight.off.fill"' in SOURCE
    and 'NSString *name = off ? @"FlashlightOff" : @"FlashlightOn";' in header_sub
    and "SizedGlyphArt(name, image.size)" in header_sub,
    "the header does not pin the positive off identity and render at the pushed canvas",
)
assert_true(
    'NSClassFromString(@"CCUIFlashlightModuleViewController")' in compact_gate
    and "[AncestorController(self) isKindOfClass:flashlightClass]" in compact_gate,
    "compact substitution is not confined to the Flashlight module button",
)
assert_true(
    compact_gate.index("gEnabled") < compact_gate.index("CompactGlyphSubstitute("),
    "compact substitution does not consult the existing functional state first",
)
assert_true(
    '"v24@0:8@16"' in compact_abi and "strcmp(normalized, kExpected) == 0" in compact_abi,
    "the compact ABI gate does not compare the verified setter shape",
)
assert_true(
    "@selector(setGlyphImage:)" in compact_install
    and "@selector(setSelectedGlyphImage:)" in compact_install,
    "the compact hooks do not cover both static glyph setters",
)
assert_true(
    compact_install.count("CompactGlyphEncodingMatches(") == 2
    and compact_install.index("CompactGlyphEncodingMatches(")
    < compact_install.index("MSHookMessageEx("),
    "the compact hooks install without passing the ABI shape check first",
)
assert_true(
    "InstallCompactGlyphHooks(" in install_body,
    "the compact glyph hooks are not installed at load",
)

# Compact slot-routing contract ([ADDRESS]): on 21D50 the normal
# glyphImage slot displays while the flashlight is OFF and the selected slot
# while it is ON (authoritative device observation), so the resting slot
# carries FlashlightOff and the active slot FlashlightOn — the inverse of the
# original route pairing at evidence/caml-static/orig-arm64-layoutglyphs.dis.txt
# 0x81a4/0x8218, which renders reversed and is deliberately not reproduced.
assert_true(
    'UIImage *onArt = IconImage(@"FlashlightOn");' in flashlight_body
    and 'UIImage *offArt = IconImage(@"FlashlightOff");' in flashlight_body,
    "the compact flashlight decodes are not both present for the state slots",
)
assert_true(
    "SetGlyphImage(view, offGlyph)" in flashlight_body
    and "SetSelectedGlyphImage(view, onGlyph)" in flashlight_body,
    "the compact flashlight slots are not filled per the authoritative state mapping",
)
assert_true(
    "ScheduleGlyphStabilityCheck(view, offGlyph)" in flashlight_body,
    "the stability probe no longer re-reads the applied glyph slot",
)

print(
    "PASS: fresh UIImage identity reproduces repeated writes; cached theme/icon identity "
    "converges on pass two, caches misses before filesystem access, and invalidates on reload; "
    "header-glyph substitution stays class/state-bounded, reuses the cached themed decodes, "
    "and fails open on disabled state, other classes, and nil/missing/invalid themed images; "
    "the recorded forwarding decision matches the bypass/substitute/fail-open model"
)
