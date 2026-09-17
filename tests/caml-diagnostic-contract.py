from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/CAMLDiagnostic.xm").read_text()
MAKEFILE = (ROOT / "Makefile").read_text()
WORKFLOW = (ROOT / ".github/workflows/build-rootless.yml").read_text()
IMPLEMENTATION_DOC = (ROOT / "docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md").read_text()


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def function_body(name: str) -> str:
    marker = SOURCE.find(name)
    assert_true(marker >= 0, f"missing function {name}")
    opening = SOURCE.find("{", marker)
    depth = 0
    for index in range(opening, len(SOURCE)):
        if SOURCE[index] == "{":
            depth += 1
        elif SOURCE[index] == "}":
            depth -= 1
            if depth == 0:
                return SOURCE[opening + 1 : index]
    fail(f"unterminated function {name}")


# The site table is one structural source of truth for target, selector, ABI, and replacement.
site_rows = re.findall(
    r'\{\s*@"([^"]+)",\s*@selector\(([^)]+)\),\s*"([^"]+)",\s*\(IMP\)(\w+),\s*&\w+,\s*(true|false)\s*\}',
    SOURCE,
)
expected_sites = {
    ("CCUIButtonModuleView", "setGlyphPackageDescription:", "v24@0:8@16", "CAMLButtonPackageHook", "false"),
    ("CCUIRoundButton", "setGlyphPackageDescription:", "v24@0:8@16", "CAMLRoundPackageHook", "false"),
    ("CCUIBaseSliderView", "setGlyphPackageDescription:", "v24@0:8@16", "CAMLSliderPackageHook", "false"),
    ("CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:", "@32@0:8@16@24", "CAMLFactoryHook", "true"),
    ("CCUIButtonModuleView", "setGlyphState:", "v24@0:8@16", "CAMLButtonStateHook", "false"),
    ("CCUIBaseSliderView", "setGlyphState:", "v24@0:8@16", "CAMLSliderStateHook", "false"),
}
assert_true(set(site_rows) == expected_sites and len(site_rows) == 6, "phase-one site table is incomplete or has an unexpected hook")
assert_true("CCUIContinuousSliderView" not in SOURCE, "diagnostic must hook CCUIBaseSliderView, not the subclass")
assert_true("SBElasticRouteDisplayContext" not in SOURCE, "route-context hook is a later escalation")
assert_true("src/CAMLDiagnostic.xm" in MAKEFILE, "diagnostic module is not part of the tweak target")
assert_true("kDiagnosticEnabledKey" in SOURCE and "kDiagnosticVerboseKey" in SOURCE, "diagnostic preferences are not declared")
assert_true("boolForKey:kDiagnosticEnabledKey" in SOURCE and "boolForKey:kDiagnosticVerboseKey" in SOURCE, "preferences are not read as BOOLs")
assert_true("std::atomic<bool> gDiagnosticEnabled(false)" in SOURCE, "enabled default is not disabled")
assert_true("std::atomic<bool> gDiagnosticVerbose(false)" in SOURCE, "verbose default is not disabled")
assert_true("ROOT_PATH_NS(@\"/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic\")" in SOURCE, "diagnostic output is not isolated under rootless Application Support")
assert_true("@0700" in SOURCE and "@0600" in SOURCE and "chmod(path.fileSystemRepresentation, 0600)" in SOURCE, "diagnostic output permissions are not restrictive")
assert_true("kRingCapacity = 512" in SOURCE and "kSerializedEventCapacity = 256" in SOURCE and "kSessionEventCap = 2000" in SOURCE, "bounded logging constants are missing")
assert_true("kRepeatCollapseWindowMs = 100" in SOURCE and "kTupleDedupWindowMs = 1000" in SOURCE, "dedup windows are missing")
assert_true('kDiagnosticBuildId = "plampycc-caml-observer-v1"' in SOURCE and '%.25s\\",\\"u\\"' in SOURCE, "install provenance build ID is truncated or missing")
assert_true("std::atomic<bool> gLoggingDisabled(false)" in SOURCE and "DisableLoggingForSession" in SOURCE, "session fail-open disable is missing")
assert_true("os_unfair_lock" in SOURCE and "dispatch_sync" not in SOURCE and "dispatch_async" not in SOURCE, "hook logging violates the synchronization contract")
assert_true("method_getTypeEncoding" in SOURCE and "ABIShapeMatches" in SOURCE, "runtime ABI validation is missing")
assert_true("MSHookMessageEx" in SOURCE and "gOriginalFactory" in SOURCE, "PAC-safe original IMP slots are missing")
assert_true("objc_setAssociatedObject" not in SOURCE, "observer introduced mutable associated state")
for wrapper in ("CAMLButtonPackageHook", "CAMLRoundPackageHook", "CAMLSliderPackageHook"):
    assert_true("setGlyphPackageDescription:" not in function_body(wrapper), f"{wrapper} mutates the package after its seam")

# Every wrapper observes first, then invokes its saved original exactly once with unchanged arguments.
wrapper_contracts = {
    "CAMLButtonPackageHook": ("ObservePackage(self, description, \"button-view\")", "gOriginalButtonPackage)(self, cmd, description)"),
    "CAMLRoundPackageHook": ("ObservePackage(self, description, \"round-button\")", "gOriginalRoundPackage)(self, cmd, description)"),
    "CAMLSliderPackageHook": ("ObservePackage(self, description, \"slider-view\")", "gOriginalSliderPackage)(self, cmd, description)"),
    "CAMLFactoryHook": ("ObserveFactory(packageName, bundle)", "gOriginalFactory)(self, cmd, packageName, bundle)"),
    "CAMLButtonStateHook": ("ObserveState(self, state, \"glyph-state\")", "gOriginalButtonState)(self, cmd, state)"),
    "CAMLSliderStateHook": ("ObserveState(self, state, \"glyph-state\")", "gOriginalSliderState)(self, cmd, state)"),
}
for name, (observer_call, original_call) in wrapper_contracts.items():
    body = function_body(name)
    assert_true(body.count(observer_call) == 1, f"{name} does not have one observer call")
    assert_true(body.count(original_call) == 1, f"{name} does not have one saved-original call")
    assert_true(body.index(observer_call) < body.index(original_call), f"{name} does not observe before pass-through")


def normalize_encoding(value: str) -> str:
    return re.sub(r'@"[^"]*"', "@", value)


assert_true(normalize_encoding('v24@0:8@"CCUICAPackageDescription"16') == "v24@0:8@16", "quoted setter ABI normalization failed")
assert_true(normalize_encoding('@32@0:8@"NSString"16@"NSBundle"24') == "@32@0:8@16@24", "quoted factory ABI normalization failed")
assert_true(normalize_encoding("v24@0:8@16") != "@32@0:8@16@24", "ABI mismatch was accepted")


@dataclass(frozen=True)
class Token:
    value: str


class Original:
    def __init__(self, return_value: Any = None):
        self.calls: list[tuple[Any, ...]] = []
        self.return_value = return_value

    def __call__(self, *args: Any) -> Any:
        self.calls.append(args)
        return self.return_value


class ObserverHarness:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.observed: list[tuple[str, tuple[Any, ...]]] = []
        self.in_observer = False
        self.logging_failed = False

    def observe(self, site: str, args: tuple[Any, ...]) -> None:
        if not self.enabled or self.logging_failed or self.in_observer:
            return
        self.in_observer = True
        try:
            self.observed.append((site, args))
        finally:
            self.in_observer = False

    def invoke_void(self, site: str, original: Original, self_token: Token, argument: Token) -> None:
        self.observe(site, (self_token, argument))
        original(self_token, argument)

    def invoke_factory(self, original: Original, self_token: Token, package: Token, bundle: Token) -> Any:
        self.observe("factory", (package, bundle))
        return original(self_token, package, bundle)


sites_for_behavior = ["button-view", "round-button", "slider-view", "glyph-state"]
for site in sites_for_behavior:
    harness = ObserverHarness(enabled=False)
    original = Original()
    self_token, arg = Token("self"), Token("argument")
    harness.invoke_void(site, original, self_token, arg)
    assert_true(original.calls == [(self_token, arg)] and harness.observed == [], f"disabled {site} changed production pass-through")

    harness = ObserverHarness(enabled=True)
    original = Original()
    harness.invoke_void(site, original, self_token, arg)
    assert_true(original.calls == [(self_token, arg)], f"{site} did not invoke original exactly once with identity-preserved args")
    assert_true(harness.observed == [(site, (self_token, arg))], f"{site} did not observe the original identity")

factory = ObserverHarness(enabled=True)
factory_original = Original(return_value=Token("stock-return"))
package, bundle, receiver = Token("package"), Token("bundle"), Token("class")
returned = factory.invoke_factory(factory_original, receiver, package, bundle)
assert_true(returned is factory_original.return_value, "factory observer changed the original return value")
assert_true(factory_original.calls == [(receiver, package, bundle)], "factory observer changed arguments or call count")

# Installation is fail-open per site when a class, method, or ABI is absent.
def install_sites(available: dict[tuple[str, str], str]) -> set[tuple[str, str]]:
    installed = set()
    for class_name, selector, encoding, _replacement, _class_method in site_rows:
        if (class_name, selector) in available and normalize_encoding(available[(class_name, selector)]) == encoding:
            installed.add((class_name, selector))
    return installed

available = {(row[0], row[1]): row[2] for row in site_rows}
assert_true(len(install_sites(available)) == 6, "complete ABI fixture did not install all six sites")
assert_true(("CCUIButtonModuleView", "setGlyphPackageDescription:") not in install_sites({}), "missing classes/methods did not fail open")
bad_factory = dict(available)
bad_factory[("CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:")] = "v24@0:8@16"
assert_true(("CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:") not in install_sites(bad_factory), "factory ABI mismatch did not skip installation")


class BoundedLogger:
    def __init__(self, flush_ok: bool = True):
        self.enabled = True
        self.flush_ok = flush_ok
        self.ring: list[dict[str, Any]] = []
        self.session_events = 0
        self.counters = 0
        self.last_tuple: tuple[str, str, str] | None = None
        self.last_pair: tuple[str, str] | None = None
        self.last_time = 0

    def emit(self, site: str, package: str, state: str, now: int, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        if self.session_events >= 2000:
            self.counters += 1
            return
        current_tuple = (site, package, state)
        current_pair = (site, package)
        if self.last_tuple == current_tuple and now - self.last_time <= 1000:
            if now - self.last_time <= 100 and self.ring:
                self.ring[-1]["repeat"] += 1
            return
        if self.last_pair == current_pair and now - self.last_time <= 100:
            if self.ring:
                self.ring[-1]["repeat"] += 1
            return
        self.last_tuple, self.last_pair, self.last_time = current_tuple, current_pair, now
        event = {"v": 1, "site": site, "pkg": package, "state": state, "repeat": 1, **payload}
        serialized = json.dumps(event, separators=(",", ":"))
        assert_true(len(serialized.encode()) < 256, "serialized event exceeds the 256-byte contract")
        self.ring.append(event)
        self.session_events += 1
        if len(self.ring) == 512:
            if not self.flush_ok:
                self.enabled = False
                return
            self.ring.clear()


logger = BoundedLogger()
logger.emit("button-view", "Camera", "", 0, {"prefix": "private", "desc": "CCUICAPackageDescription", "tag": 1, "anc": "VC"})
logger.emit("button-view", "Camera", "", 50, {"prefix": "private", "desc": "CCUICAPackageDescription", "tag": 1, "anc": "VC"})
assert_true(len(logger.ring) == 1 and logger.ring[0]["repeat"] == 2, "100 ms repeat collapse did not update one bounded event")
logger.emit("button-view", "Camera", "", 500, {"prefix": "private", "desc": "CCUICAPackageDescription", "tag": 1, "anc": "VC"})
assert_true(len(logger.ring) == 1, "1000 ms tuple dedup emitted a duplicate")
logger.emit("button-view", "Camera", "", 1501, {"prefix": "private", "desc": "CCUICAPackageDescription", "tag": 1, "anc": "VC"})
assert_true(len(logger.ring) == 2, "tuple was not accepted after the dedup window")

for index in range(2500):
    logger.emit("glyph-state", f"pkg{index}", "default", 3000 + index * 2, {"prefix": "var", "desc": "CCUICAPackageDescription", "tag": 0, "anc": "VC"})
assert_true(logger.session_events <= 2000 and logger.counters > 0 and len(logger.ring) <= 512, "session/ring bounds are not enforced")
failed_logger = BoundedLogger(flush_ok=False)
for index in range(512):
    failed_logger.emit("glyph-state", f"pkg{index}", "default", index * 2, {"prefix": "var", "desc": "CCUICAPackageDescription", "tag": 0, "anc": "VC"})
assert_true(not failed_logger.enabled, "logging failure did not disable the session")

# The event shape deliberately accepts classifications, not paths, XML, asset bytes, or pointer strings.
serialized = json.dumps({"site": "factory", "pkg": "Brightness", "prefix": "app-container", "desc": "CCUICAPackageDescription", "state": "default", "repeat": 1}, separators=(",", ":"))
for prohibited in ("/private/var/", "<contents", "Assets.car", "0xdeadbeef"):
    assert_true(prohibited not in serialized, f"prohibited diagnostic field leaked: {prohibited}")
assert_true("packageURL" in SOURCE and "pathPrefix" in SOURCE and "packageName" in SOURCE, "package identity classification is not implemented")

# A logging failure/reentrancy path is isolated from production call behavior.
harness = ObserverHarness(enabled=True)
harness.logging_failed = True
original = Original()
harness.invoke_void("button-view", original, receiver, package)
assert_true(original.calls == [(receiver, package)], "logging failure affected original pass-through")
harness = ObserverHarness(enabled=True)
harness.in_observer = True
original = Original()
harness.invoke_void("button-view", original, receiver, package)
assert_true(original.calls == [(receiver, package)] and harness.observed == [], "reentrancy guard did not suppress nested logging")

# Workflow/script review: no device access or deployment operation is present.
for path in sorted((ROOT / ".github/workflows").rglob("*")):
    if path.is_file():
        text = path.read_text()
        for forbidden in ("ssh", "scp", "idevice", "ios-deploy", "respring", "install_package"):
            assert_true(forbidden not in text.lower(), f"device/deployment command present in {path}: {forbidden}")
assert_true("runs-on: macos-15" in WORKFLOW and "test \"$(uname -m)\" = arm64" in WORKFLOW, "Apple Silicon workflow preflight is missing")

# The existing functional module has only the narrow dismissal flush seam; no functional state or argument path changed.
tweak_source = (ROOT / "src/Tweak.xm").read_text()
assert_true(tweak_source.count('#import "CAMLDiagnostic.h"') == 1 and tweak_source.count("CAMLDiagnosticFlushAtDismiss();") == 1, "Tweak.xm diagnostic seam is missing or duplicated")
assert_true("if (orig_dismiss) orig_dismiss(self, cmd, animated, completion);" in tweak_source, "dismissal original call was not preserved")
for phrase in ("Hook list", "kDiagnosticEnabled", "events.jsonl", "build ID", "device-test gate"):
    assert_true(phrase in IMPLEMENTATION_DOC, f"implementation document omits {phrase}")

print("PASS: six observer sites, ABI/fail-open model, identity-preserving pass-through, bounded/redacted logging model, reentrancy/failure behavior, and no-device workflow checks")
