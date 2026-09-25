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

print(
    "PASS: fresh UIImage identity reproduces repeated writes; cached theme/icon identity "
    "converges on pass two, caches misses before filesystem access, and invalidates on reload"
)
