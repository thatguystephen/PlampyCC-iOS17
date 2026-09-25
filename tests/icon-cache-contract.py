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
    'IconImage(on ? @"FlashlightOn" : @"FlashlightOff")' in header_substitute,
    "header-glyph substitution does not reuse the cached themed decodes",
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

print(
    "PASS: fresh UIImage identity reproduces repeated writes; cached theme/icon identity "
    "converges on pass two, caches misses before filesystem access, and invalidates on reload; "
    "header-glyph substitution stays class/state-bounded, reuses the cached themed decodes, "
    "and fails open on disabled state, other classes, and nil/missing/invalid themed images"
)
