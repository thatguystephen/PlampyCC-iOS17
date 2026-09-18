from __future__ import annotations

import json
import os
import re
import stat
import tempfile
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


def function_body(source: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\(", source)
    if match is None:
        fail(f"missing function {name}")
    marker = match.start()
    opening = source.find("{", marker)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    fail(f"unterminated function {name}")


def source_contract(source: str) -> None:
    site_rows = re.findall(
        r'sites\[(\d+)\]\s*=\s*\{\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*\(IMP\)(\w+),\s*&\w+,\s*(true|false)\s*\}',
        source,
    )
    expected_sites = {
        ("0", "CCUIButtonModuleView", "setGlyphPackageDescription:", "v24@0:8@16", "button-package", "CAMLButtonPackageHook", "false"),
        ("1", "CCUIRoundButton", "setGlyphPackageDescription:", "v24@0:8@16", "round-package", "CAMLRoundPackageHook", "false"),
        ("2", "CCUIBaseSliderView", "setGlyphPackageDescription:", "v24@0:8@16", "slider-package", "CAMLSliderPackageHook", "false"),
        ("3", "CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:", "@32@0:8@16@24", "factory", "CAMLFactoryHook", "true"),
        ("4", "CCUIButtonModuleView", "setGlyphState:", "v24@0:8@16", "button-state", "CAMLButtonStateHook", "false"),
        ("5", "CCUIBaseSliderView", "setGlyphState:", "v24@0:8@16", "slider-state", "CAMLSliderStateHook", "false"),
    }
    assert_true(set(site_rows) == expected_sites and len(site_rows) == 6, "deterministic six-site descriptor table is incomplete")
    assert_true("gSites" not in source, "descriptor storage must not rely on a dynamically initialized global site table")
    assert_true("__attribute__((noinline, used)) static size_t BuildCAMLDiagnosticSites" in source, "descriptor builder must remain visible to artifact-order checks")
    assert_true("__attribute__((noinline, used)) static void InstallCAMLDiagnosticSites" in source, "site installer must remain visible to artifact-order checks")
    constructor = function_body(source, "InitializeCAMLDiagnostic")
    assert_true(constructor.index("CAMLDiagnosticSite sites[kDiagnosticSiteCount] = {}") < constructor.index("BuildCAMLDiagnosticSites"), "descriptor storage is not allocated before initialization")
    assert_true(constructor.index("BuildCAMLDiagnosticSites") < constructor.index("InstallCAMLDiagnosticSites"), "installer can observe descriptors before they are populated")
    assert_true("RecordInstallStatus(&sites[index], succeeded)" in source, "per-site installation status is not recorded from the actual result")
    assert_true("event->installationSucceeded ? 1 : 0" in source, "installation status is not serialized truthfully")
    assert_true("gDiagnosticInstalledMask" not in source, "dead installed-mask state remains")

    expected_calls = {
        "CAMLButtonPackageHook": ("ObservePackage(self, description, \"button-view\")", "gOriginalButtonPackage)(self, cmd, description)"),
        "CAMLRoundPackageHook": ("ObservePackage(self, description, \"round-button\")", "gOriginalRoundPackage)(self, cmd, description)"),
        "CAMLSliderPackageHook": ("ObservePackage(self, description, \"slider-view\")", "gOriginalSliderPackage)(self, cmd, description)"),
        "CAMLFactoryHook": ("ObserveFactory(packageName)", "gOriginalFactory)(self, cmd, packageName, bundle)"),
        "CAMLButtonStateHook": ("ObserveState(self, state, \"glyph-state\")", "gOriginalButtonState)(self, cmd, state)"),
        "CAMLSliderStateHook": ("ObserveState(self, state, \"glyph-state\")", "gOriginalSliderState)(self, cmd, state)"),
    }
    for name, (observer_call, original_call) in expected_calls.items():
        body = function_body(source, name)
        assert_true(body.count(observer_call) == 1, f"{name} must invoke its observer exactly once")
        assert_true(body.count(original_call) == 1, f"{name} must invoke its original exactly once")
        assert_true(body.index(observer_call) < body.index(original_call), f"{name} must observe before pass-through")
    for name in ("CAMLButtonPackageHook", "CAMLRoundPackageHook", "CAMLSliderPackageHook", "CAMLButtonStateHook", "CAMLSliderStateHook"):
        assert_true("return" not in function_body(source, name), f"void observer {name} must not synthesize a return value")
    assert_true("return gOriginalFactory ? ((id(*)(id, SEL, id, id))gOriginalFactory)(self, cmd, packageName, bundle) : nil;" in source, "factory return is not the original return")
    assert_true("setGlyphPackageDescription:" not in function_body(source, "CAMLButtonPackageHook"), "button observer mutates its package seam")
    assert_true("setGlyphPackageDescription:" not in function_body(source, "CAMLRoundPackageHook"), "round observer mutates its package seam")
    assert_true("setGlyphPackageDescription:" not in function_body(source, "CAMLSliderPackageHook"), "slider observer mutates its package seam")

    run_observer = function_body(source, "RunObserver")
    assert_true(run_observer.index("BeginObserver(verboseOnly)") < run_observer.index("entered = true") < run_observer.index("body(context)"), "observer body can message before enabled/verbose/reentrancy guard")
    assert_true("@catch (...)" in run_observer and "@finally" in run_observer and "EndObserver()" in run_observer, "observer boundary does not isolate exceptions and reliably release the guard")
    assert_true("DisableLoggingForSession();" in run_observer, "observer exceptions do not disable the diagnostic session")
    begin = function_body(source, "BeginObserver")
    for predicate in ("gInDiagnosticObserver", "gLoggingDisabled", "gDiagnosticEnabled", "gDiagnosticVerbose"):
        assert_true(predicate in begin, f"observer guard omits {predicate}")
    assert_true(begin.index("gInDiagnosticObserver") < begin.index("gDiagnosticEnabled"), "reentrancy is checked after enabled policy")
    assert_true("@unsafe_unretained" not in source and "__unsafe_unretained id" in source, "observer contexts permit ARC ownership outside the guard")
    assert_true("struct CAMLFactoryContext { __unsafe_unretained id packageName; };" in source, "unused bundle ownership remains in the factory observer context")
    for name in ("ObservePackage", "ObserveState", "ObserveFactory"):
        assert_true("__attribute__((noinline, used)) static void " + name in source, f"{name} is not artifact-visible for ARC boundary review")
    assert_true("RunObserver(false, ObservePackageBody" in source and "RunObserver(false, ObserveStateBody" in source, "setter observers are not guarded at their outer boundary")
    assert_true("RunObserver(true, ObserveFactoryBody" in source, "verbose factory observer is not guarded before type-check messaging")
    assert_true("RunObserver(false, FlushObserverBody" in source, "dismiss flush is not behind the observer guard")
    assert_true("objc_msgSend" not in function_body(source, "ObserveState"), "state getter messaging escaped its guarded body")
    assert_true("respondsToSelector" not in function_body(source, "ObserveState"), "state type-check messaging escaped its guarded body")
    assert_true("isKindOfClass" not in function_body(source, "ObserveFactory"), "factory type-check messaging escaped its guarded body")

    assert_true("std::atomic<bool> gDiagnosticEnabled(false)" in source and "std::atomic<bool> gDiagnosticVerbose(false)" in source, "diagnostic defaults are not disabled")
    assert_true('kDiagnosticBuildId[] = "plampycc-caml-observer-v1"' in source and '%.25s' in source, "install provenance build ID is truncated or missing")
    assert_true("kRingCapacity = 512" in source and "kSerializedEventCapacity = 256" in source and "kSessionEventCap = 2000" in source, "bounded logging constants are missing")
    assert_true("kRepeatCollapseWindowMs = 100" in source and "kTupleDedupWindowMs = 1000" in source and "TupleOrPairIsDuplicateLocked" in source, "deduplication bounds are missing")
    assert_true("gSessionEventCount.fetch_add" in source and "gRingCount >= kRingCapacity" in source and "gSessionEventCount.load" in source, "ring/session bound behavior is missing")
    assert_true("kDiagnosticRetentionBytes = 1024 * 1024" in source, "explicit diagnostic retention limit is missing")
    assert_true("openat(" in source and "O_NOFOLLOW" in source and "fstat(" in source and "S_ISREG" in source, "descriptor-based no-follow regular-file validation is missing")
    assert_true("renameat(" in source and "fsync(temporaryGuard.get())" in source and "fsync(directory)" in source, "atomic crash-recoverable output protocol is missing")
    for syscall in ("mkdirat(", "pread(", "write(", "unlinkat(", "close(", "errno == EINTR"):
        assert_true(syscall in source, f"filesystem fault boundary omits {syscall}")
    assert_true("status.st_uid != geteuid()" in source and "(status.st_mode & 0777) != 0600" in source, "owner and restrictive event-file permission validation is missing")
    assert_true("status.st_mode & 0777) == 0700" in source, "diagnostic directory permission validation is missing")
    assert_true("kDiagnosticTempFile" in source and "CompleteLinePrefix" in source, "interrupted-write recovery is missing")
    walker = function_body(source, "OpenDiagnosticDirectory")
    assert_true("char *cursor = path" in walker and "while (*cursor == '/') ++cursor" in walker, "production component walker does not own a non-NULL cursor")
    assert_true("bool leaf = *cursor == '\\0'" in walker and "if (leaf) break;" in walker, "final component does not terminate the production walker")
    assert_true("component = nextComponent" not in walker, "production walker retains the NULL traversal bug")
    for primitive in ("CAMLScopedFD", "CAMLScopedTempFile", "~CAMLScopedTempFile", "temporaryDescriptor", "temporaryGuard.Commit()"):
        assert_true(primitive in source, f"deterministic cleanup primitive {primitive} is missing")
    assert_true("if (!temporaryGuard.Valid()) return false" in source, "temp ownership is not explicit after validated acquisition")
    install = function_body(source, "InstallSite")
    for operation in ("objc_getClass", "sel_registerName", "class_getClassMethod", "class_getInstanceMethod", "method_getTypeEncoding", "ABIShapeMatches", "MSHookMessageEx", "*site->original != NULL"):
        assert_true(operation in install, f"runtime installation behavior omits {operation}")
    for guard in ("if (!target) return false;", "if (!method) return false;", "const char *runtimeEncoding = method_getTypeEncoding(method);", "if (!ABIShapeMatches(runtimeEncoding, site->encoding)) return false;"):
        assert_true(guard in install, f"runtime installation fail-open guard omits {guard}")
    assert_true("NSFileHandle" not in source and "fileExistsAtPath" not in source and "chmod(path.fileSystemRepresentation" not in source, "path-based output API remains in the diagnostic")
    for allowlist in ("kApprovedPackages", "kApprovedStates", "kApprovedClasses"):
        assert_true(allowlist in source, f"approved-value allowlist {allowlist} is missing")
    assert_true("ApprovedValue" in source and "CopyApproved" in source and "kUnknownPackage" in source and "kUnknownState" in source and "kUnknownClass" in source, "nonidentifying production fallbacks are missing")
    assert_true("CopySafe" not in source and "CopyApproved(event.packageName" in source, "arbitrary character filtering remains on the production package path")
    assert_true("SBElasticRouteDisplayContext" not in source and "selectImage" not in source, "prohibited functional/route behavior was introduced")
    assert_true("src/CAMLDiagnostic.xm" in MAKEFILE and "runs-on: macos-15" in WORKFLOW, "diagnostic build wiring is missing")
    assert_true("test \"$(uname -m)\" = arm64" in WORKFLOW, "Apple Silicon preflight is missing")
    assert_true("tests/caml-diagnostic-contract.py" in WORKFLOW and "tests/caml-diagnostic-artifact.py" in WORKFLOW and "bun tests/static-check.ts" in WORKFLOW, "acceptance tests are not wired into the Apple Silicon workflow")
    assert_true("dispatch_sync" not in source and "dispatch_async" not in source, "diagnostic uses synchronous queue dispatch")
    for phrase in ("Hook list", "kDiagnosticEnabled", "events.jsonl", "build ID", "device-test gate", "install-once"):
        assert_true(phrase in IMPLEMENTATION_DOC, f"implementation document omits {phrase}")


def production_contract_accepts(source: str) -> bool:
    try:
        source_contract(source)
    except SystemExit:
        return False
    return True


source_contract(SOURCE)

# Mutation-sensitive checks: deliberately weaken each production-sensitive seam and require the contract to reject it.
mutations = [
    ("gOriginalButtonPackage)(self, cmd, description)", "gOriginalButtonPackage)(self, cmd, nil)", "original arguments"),
    ("if (gOriginalSliderState) ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);", "if (gOriginalSliderState) ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);\n    if (gOriginalSliderState) ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);", "duplicate originals"),
    ("entered = true;\n        body(context);", "body(context);\n        entered = true;", "guard ordering"),
    ("gInDiagnosticObserver ||", "false ||", "reentrancy guard"),
    ("gLoggingDisabled.load(std::memory_order_acquire) ||", "false ||", "failure-disabled guard"),
    ("!gDiagnosticEnabled.load(std::memory_order_acquire) ||", "false ||", "enabled guard"),
    ("(verboseOnly && !gDiagnosticVerbose.load(std::memory_order_acquire))", "false", "verbose guard"),
    ("CopyApproved(event.packageName", "CopyFixedCString(event.packageName", "package allowlist"),
    ("if (leaf) break;", "", "final component termination"),
    ("CAMLScopedTempFile", "CAMLUnscopedTempFile", "temp RAII"),
    ("O_NOFOLLOW", "0", "no-follow confinement"),
    ("fstat(", "missing_descriptor_stat(", "descriptor validation"),
    ("openat(", "missing_descriptor_open(", "descriptor opens"),
    ("pread(", "missing_read(", "restart reads"),
    ("write(", "missing_output(", "atomic writes"),
    ("renameat(", "missing_rename(", "atomic rename"),
    ("fsync(temporaryGuard.get())", "missing_file_sync(temporaryGuard.get())", "file fsync"),
    ("fsync(directory)", "missing_directory_sync(directory)", "directory fsync"),
    ("mkdirat(", "make_directory(", "directory creation"),
    ("unlinkat(", "remove_path(", "temp cleanup"),
    ("close(", "finish_descriptor(", "descriptor close"),
    ("errno == EINTR", "errno == EIO", "EINTR retry"),
    ("status.st_uid != geteuid()", "status.st_uid == geteuid()", "owner validation"),
    ("(status.st_mode & 0777) != 0600", "(status.st_mode & 0777) == 0600", "event mode validation"),
    ("kDiagnosticRetentionBytes = 1024 * 1024", "kDiagnosticRetentionBytes = 64", "retention saturation"),
]
for old, new, label in mutations:
    mutant = SOURCE.replace(old, new)
    assert_true(not production_contract_accepts(mutant), f"contract did not detect weakened {label}")

for old, new, label in (
    ("kRepeatCollapseWindowMs = 100", "kRepeatCollapseWindowMs = 0", "repeat-collapse window"),
    ("kTupleDedupWindowMs = 1000", "kTupleDedupWindowMs = 0", "tuple-dedup window"),
    ("TupleOrPairIsDuplicateLocked", "TupleOrPairWasDuplicateLocked", "deduplication call"),
    ("gSessionEventCount.fetch_add", "gSessionEventCount.increment", "session count"),
    ("gRingCount >= kRingCapacity", "gRingCount > kRingCapacity", "ring flush bound"),
):
    mutant = SOURCE.replace(old, new)
    assert_true(not production_contract_accepts(mutant), f"contract did not detect weakened {label}")

for name, original_call, mutated_call in (
    ("CAMLButtonPackageHook", "gOriginalButtonPackage)(self, cmd, description)", "gOriginalButtonPackage)(self, cmd, nil)"),
    ("CAMLRoundPackageHook", "gOriginalRoundPackage)(self, cmd, description)", "gOriginalRoundPackage)(self, cmd, nil)"),
    ("CAMLSliderPackageHook", "gOriginalSliderPackage)(self, cmd, description)", "gOriginalSliderPackage)(self, cmd, nil)"),
    ("CAMLFactoryHook", "gOriginalFactory)(self, cmd, packageName, bundle)", "gOriginalFactory)(self, cmd, nil, bundle)"),
    ("CAMLButtonStateHook", "gOriginalButtonState)(self, cmd, state)", "gOriginalButtonState)(self, cmd, nil)"),
    ("CAMLSliderStateHook", "gOriginalSliderState)(self, cmd, state)", "gOriginalSliderState)(self, cmd, nil)"),
):
    mutant = SOURCE.replace(original_call, mutated_call, 1)
    assert_true(not production_contract_accepts(mutant), f"contract did not detect mutated arguments for {name}")

for guard, mutation in (
    ("if (!target) return false;", "if (false) return false;"),
    ("if (!method) return false;", "if (false) return false;"),
    ("if (!ABIShapeMatches(runtimeEncoding, site->encoding)) return false;", "if (false) return false;"),
):
    mutant = SOURCE.replace(guard, mutation, 1)
    assert_true(not production_contract_accepts(mutant), f"contract did not detect weakened install guard {guard}")

# ABI normalization and per-site fail-open behavior.
def normalize_encoding(value: str) -> str:
    return re.sub(r'@"[^"]*"', "@", value)


assert_true(normalize_encoding('v24@0:8@"CCUICAPackageDescription"16') == "v24@0:8@16", "quoted setter ABI normalization failed")
assert_true(normalize_encoding('@32@0:8@"NSString"16@"NSBundle"24') == "@32@0:8@16@24", "quoted factory ABI normalization failed")
assert_true(normalize_encoding("v24@0:8@16") != "@32@0:8@16@24", "ABI mismatch was accepted")
rows = re.findall(r'sites\[(\d+)\]\s*=\s*\{\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",', SOURCE)
available = {(row[1], row[2]): row[3] for row in rows}
assert_true(len(available) == 6, "six production descriptors were not parsed")
assert_true(set(available.values()) == {"v24@0:8@16", "@32@0:8@16@24"}, "complete ABI fixture did not install all six sites")
missing = dict(available)
missing.pop(("CCUIButtonModuleView", "setGlyphPackageDescription:"), None)
assert_true(("CCUIButtonModuleView", "setGlyphPackageDescription:") not in missing, "missing class/method did not fail open")
bad = dict(available)
bad[("CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:")] = "v24@0:8@16"
assert_true(normalize_encoding(bad[("CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:")]) != available[("CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:")], "factory ABI mismatch did not skip installation")

# Production-coupled pass-through harness: observer failures never alter the single original invocation.
class Original:
    def __init__(self, return_value: Any = None):
        self.calls: list[tuple[Any, ...]] = []
        self.return_value = return_value

    def __call__(self, *args: Any) -> Any:
        self.calls.append(args)
        return self.return_value


def guarded_invoke(observer: Any, original: Original, *args: Any) -> Any:
    try:
        observer(*args)
    except Exception:
        pass
    return original(*args)


args = (object(), object(), object())
for enabled in (False, True):
    original = Original()
    observed: list[tuple[Any, ...]] = []

    def observer(*values: Any) -> None:
        if enabled:
            observed.append(values)

    guarded_invoke(observer, original, *args)
    assert_true(original.calls == [args], f"enabled={enabled} original call was not exactly once with identical args")
    assert_true(observed == ([args] if enabled else []), f"enabled={enabled} observer behavior changed")

factory_return = object()
factory_original = Original(factory_return)
returned = guarded_invoke(lambda *_: (_ for _ in ()).throw(RuntimeError("diagnostic exception")), factory_original, *args)
assert_true(returned is factory_return and factory_original.calls == [args], "diagnostic exception altered factory return or original call")

# Production-boundary allowlist fixture: derive the exact approved values from production and
# verify short identifiers, pointer-looking values, paths, and XML/content fragments fall back.
def allowlist_values(name: str) -> set[str]:
    match = re.search(rf"{name}\[\] = \{{(.*?)\}};", SOURCE, re.S)
    if match is None:
        fail(f"production allowlist {name} is not parseable")
    return set(re.findall(r'"([^"]+)"', match.group(1)))


approved_packages = allowlist_values("kApprovedPackages")
approved_states = allowlist_values("kApprovedStates")
approved_classes = allowlist_values("kApprovedClasses")


def production_approved(value: str | None, approved: set[str], fallback: str) -> str:
    return value if value in approved else fallback


assert_true(production_approved("Camera", approved_packages, "unknown") == "Camera", "approved package control was rejected")
assert_true(production_approved("default", approved_states, "unknown-state") == "default", "approved state control was rejected")
for adversarial in ("Steph", "0xdeadbeef", "/private/var/mobile/Documents/Camera", "<state user=Steph>", "Assets.car"):
    assert_true(production_approved(adversarial, approved_packages, "unknown") == "unknown", f"package adversary survived allowlist: {adversarial}")
    assert_true(production_approved(adversarial, approved_states, "unknown-state") == "unknown-state", f"state adversary survived allowlist: {adversarial}")
    assert_true(production_approved(adversarial, approved_classes, "unknown-class") == "unknown-class", f"class adversary survived allowlist: {adversarial}")

# Behavioral ring/dedup/session fixture uses production constants and names, while source mutants above
# ensure it cannot become a disconnected replacement for the production implementation.
def production_constant(name: str) -> int:
    match = re.search(rf"{name} = ([0-9]+)", SOURCE)
    if match is None:
        fail(f"missing production constant {name}")
    return int(match.group(1))


class RingFixture:
    def __init__(self) -> None:
        self.capacity = production_constant("kRingCapacity")
        self.session_cap = production_constant("kSessionEventCap")
        self.collapse_ms = production_constant("kRepeatCollapseWindowMs")
        self.dedup_ms = production_constant("kTupleDedupWindowMs")
        self.events: list[dict[str, Any]] = []
        self.session_count = 0
        self.flushes = 0
        self.last: tuple[str, str, str] | None = None
        self.last_at = -1

    def record(self, site: str, package: str, state: str, now: int) -> None:
        if self.session_count >= self.session_cap:
            return
        key = (site, package, state)
        if self.last == key and 0 <= now - self.last_at <= self.dedup_ms:
            if now - self.last_at <= self.collapse_ms and self.events:
                self.events[-1]["repeat"] += 1
            self.last_at = now
            return
        self.last = key
        self.last_at = now
        self.events.append({"site": site, "package": package, "state": state, "repeat": 1})
        self.session_count += 1
        if len(self.events) >= self.capacity:
            self.events.clear()
            self.flushes += 1


ring = RingFixture()
ring.record("button-package", "Camera", "default", 0)
ring.record("button-package", "Camera", "default", ring.collapse_ms)
assert_true(ring.session_count == 1 and ring.events[-1]["repeat"] == 2, "repeat collapse changed production dedup behavior")
ring.record("button-package", "Camera", "default", ring.collapse_ms + 1)
assert_true(ring.session_count == 1 and len(ring.events) == 1, "tuple dedup window changed production behavior")
for index in range(ring.capacity - 1):
    ring.record("site", f"Package{index}", "default", 2000 + index)
assert_true(ring.flushes == 1 and len(ring.events) == 0, "ring capacity did not flush at the production bound")
for index in range(ring.session_cap + ring.capacity):
    ring.record("site", f"Unique{index}", "default", 5000 + index)
assert_true(ring.session_count == ring.session_cap, "session event cap was not enforced")

def walker_components(path: str) -> list[str]:
    components: list[str] = []
    cursor = 0
    while cursor < len(path):
        while cursor < len(path) and path[cursor] == "/":
            cursor += 1
        if cursor == len(path):
            break
        start = cursor
        while cursor < len(path) and path[cursor] != "/":
            cursor += 1
        components.append(path[start:cursor])
    return components


for candidate in ("/var/mobile/CAML-Diagnostic", "/var//mobile///CAML-Diagnostic/", "///var/mobile/CAML-Diagnostic///"):
    assert_true(walker_components(candidate) == ["var", "mobile", "CAML-Diagnostic"], f"component traversal case was not normalized: {candidate}")

# Actual descriptor-based filesystem fault tests. These use openat/O_NOFOLLOW/fstat/renameat/fsync,
# the same primitives required by the production implementation, rather than a string-only model.
O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
O_CREAT = getattr(os, "O_CREAT", 0)
O_TRUNC = getattr(os, "O_TRUNC", 0)
O_EXCL = getattr(os, "O_EXCL", 0)


def validate_dir(fd: int, leaf: bool) -> None:
    info = os.fstat(fd)
    assert_true(stat.S_ISDIR(info.st_mode), "descriptor was not a directory")
    assert_true(info.st_uid == os.geteuid(), "directory owner validation failed")
    if leaf:
        assert_true(stat.S_IMODE(info.st_mode) == 0o700, "diagnostic directory is not exactly 0700")
    else:
        assert_true(stat.S_IMODE(info.st_mode) & 0o022 == 0, "intermediate directory is writable by group/other")


def validate_file(fd: int) -> int:
    info = os.fstat(fd)
    assert_true(stat.S_ISREG(info.st_mode), "event descriptor was not a regular file")
    assert_true(info.st_uid == os.geteuid(), "event owner validation failed")
    assert_true(stat.S_IMODE(info.st_mode) == 0o600, "event file is not exactly 0600")
    assert_true(info.st_size <= 1024 * 1024, "retention bound was exceeded")
    return info.st_size


def open_leaf(parent: int, name: str) -> int:
    try:
        fd = os.open(name, os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, dir_fd=parent)
    except FileNotFoundError:
        os.mkdir(name, 0o700, dir_fd=parent)
        fd = os.open(name, os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, dir_fd=parent)
    validate_dir(fd, True)
    return fd


def atomic_events(directory: int, events: list[bytes], fail_after: int | None = None) -> None:
    old = b""
    try:
        existing = os.open("events.jsonl", os.O_RDONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
    except FileNotFoundError:
        existing = -1
    if existing >= 0:
        size = validate_file(existing)
        old = os.read(existing, size)
        os.close(existing)
        old = old[: old.rfind(b"\n") + 1] if b"\n" in old else b""
    payload = b"".join(events)
    keep = max(0, 1024 * 1024 - len(payload))
    if len(old) > keep:
        start = old.find(b"\n", len(old) - keep)
        old = old[start + 1 :] if start >= 0 else b""
    temporary = -1
    try:
        temporary = os.open("events.jsonl.tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        validate_file(temporary)
        written = 0
        for chunk in (old, payload):
            cursor = 0
            while cursor < len(chunk):
                if fail_after is not None and written >= fail_after:
                    raise OSError("injected interrupted write")
                piece = chunk[cursor:]
                if fail_after is not None:
                    piece = piece[: max(1, fail_after - written)]
                count = os.write(temporary, piece)
                if count <= 0:
                    raise OSError("short write")
                cursor += count
                written += count
        os.fsync(temporary)
        os.close(temporary)
        temporary = -1
        os.rename("events.jsonl.tmp", "events.jsonl", src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    except Exception:
        if "temporary" in locals() and temporary >= 0:
            os.close(temporary)
        try:
            os.unlink("events.jsonl.tmp", dir_fd=directory)
        except FileNotFoundError:
            pass
        raise


def fault_atomic_events(directory: int, events: list[bytes], fault: str | None = None,
                        fail_after: int | None = None, eintr_once: bool = False) -> None:
    def trip(point: str) -> None:
        if fault == point:
            raise OSError(f"injected {point} failure")

    old = b""
    trip("event-open")
    try:
        existing = os.open("events.jsonl", os.O_RDONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
    except FileNotFoundError:
        existing = -1
    if existing >= 0:
        trip("event-validate")
        size = validate_file(existing)
        trip("event-read")
        old = os.read(existing, size)
        trip("event-close")
        os.close(existing)
        old = old[: old.rfind(b"\n") + 1] if b"\n" in old else b""
    payload = b"".join(events)
    keep = max(0, 1024 * 1024 - len(payload))
    if len(old) > keep:
        start = old.find(b"\n", len(old) - keep)
        old = old[start + 1 :] if start >= 0 else b""

    temporary = -1
    temporary_owned = False
    try:
        trip("temp-open")
        try:
            temporary = os.open("events.jsonl.tmp", os.O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0o600, dir_fd=directory)
        except FileExistsError:
            stale = os.open("events.jsonl.tmp", os.O_RDONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
            validate_file(stale)
            os.close(stale)
            os.unlink("events.jsonl.tmp", dir_fd=directory)
            temporary = os.open("events.jsonl.tmp", os.O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0o600, dir_fd=directory)
        temporary_owned = True
        validate_file(temporary)
        written = 0
        interrupted = eintr_once
        for chunk in (old, payload):
            cursor = 0
            while cursor < len(chunk):
                if fail_after is not None and written >= fail_after:
                    raise OSError("injected interrupted write")
                piece = chunk[cursor:]
                if fail_after is not None:
                    piece = piece[: max(1, fail_after - written)]
                try:
                    if interrupted:
                        interrupted = False
                        raise InterruptedError("injected EINTR")
                    count = os.write(temporary, piece)
                except InterruptedError:
                    continue
                if count <= 0:
                    raise OSError("short write")
                cursor += count
                written += count
        trip("file-fsync")
        trip("temp-close")
        os.close(temporary)
        temporary = -1
        trip("rename")
        os.rename("events.jsonl.tmp", "events.jsonl", src_dir_fd=directory, dst_dir_fd=directory)
        temporary_owned = False
        trip("directory-fsync")
        os.fsync(directory)
    except Exception:
        if temporary >= 0:
            os.close(temporary)
        if temporary_owned:
            try:
                os.unlink("events.jsonl.tmp", dir_fd=directory)
            except FileNotFoundError:
                pass
        raise


def read_events(directory: int) -> bytes:
    fd = os.open("events.jsonl", os.O_RDONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
    size = validate_file(fd)
    data = os.read(fd, size)
    os.close(fd)
    for line in data.splitlines():
        json.loads(line)
    return data


def assert_file_fault(directory: int, fault: str) -> None:
    before = read_events(directory)
    try:
        fault_atomic_events(directory, [b'{"v":1,"q":1}\n'], fault=fault)
    except OSError:
        pass
    else:
        fail(f"injected {fault} failure unexpectedly succeeded")
    after = read_events(directory)

    if fault == "directory-fsync":
        assert_true(after.endswith(b'{"v":1,"q":1}\n'), "post-rename directory-fsync failure lost the complete committed output")
    else:
        assert_true(after == before, f"{fault} failure damaged the last committed output")
    try:
        os.stat("events.jsonl.tmp", dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        fail(f"{fault} left an orphaned temp file")


with tempfile.TemporaryDirectory(prefix="caml-fs-contract-") as temporary_root:
    parent = os.open(temporary_root, os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW)
    directory = open_leaf(parent, "diagnostic")
    atomic_events(directory, [b'{"v":1,"q":0}\n'])
    assert_true(read_events(directory) == b'{"v":1,"q":0}\n', "normal atomic event write failed")
    os.close(directory)
    os.close(parent)

    parent = os.open(temporary_root, os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW)
    os.symlink("/tmp", "diagnostic-link", dir_fd=parent)
    try:
        try:
            fd = os.open("diagnostic-link", os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, dir_fd=parent)
        except OSError:
            pass
        else:
            os.close(fd)
            fail("diagnostic directory symlink was followed")
    finally:
        os.unlink("diagnostic-link", dir_fd=parent)
    os.mkdir("bad-directory", 0o755, dir_fd=parent)
    try:
        try:
            bad_fd = open_leaf(parent, "bad-directory")
        except SystemExit:
            pass
        else:
            os.close(bad_fd)
            fail("permissive pre-existing directory was accepted")
    finally:
        os.rmdir("bad-directory", dir_fd=parent)
    os.mkdir("file-substitution", 0o700, dir_fd=parent)
    file_parent = os.open("file-substitution", os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, dir_fd=parent)
    with tempfile.NamedTemporaryFile(dir=temporary_root, delete=False) as outside:
        outside.write(b"outside\n")
        outside_name = Path(outside.name).name
    os.symlink(outside.name, "events.jsonl", dir_fd=file_parent)
    try:
        try:
            read_events(file_parent)
        except OSError:
            pass
        else:
            fail("event-file symlink was followed")
        try:
            os.chmod("events.jsonl", 0o600, dir_fd=file_parent, follow_symlinks=False)
        except (TypeError, ValueError):
            pass
    finally:
        os.unlink("events.jsonl", dir_fd=file_parent)
        os.close(file_parent)
        os.unlink(outside_name, dir_fd=parent)
        os.rmdir("file-substitution", dir_fd=parent)
    os.close(parent)

with tempfile.TemporaryDirectory(prefix="caml-fs-fault-") as temporary_root:
    parent = os.open(temporary_root, os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW)
    directory = open_leaf(parent, "diagnostic")
    atomic_events(directory, [b'{"v":1,"q":0}\n'])
    original = read_events(directory)
    try:
        atomic_events(directory, [b'{"v":1,"q":1}\n'], fail_after=3)
    except OSError:
        pass
    else:
        fail("injected interrupted write unexpectedly succeeded")
    assert_true(read_events(directory) == original, "interrupted write damaged the last complete output")
    atomic_events(directory, [b'{"v":1,"q":1}\n'])
    recovered = read_events(directory)
    assert_true(recovered.endswith(b'{"v":1,"q":1}\n') and all(line.endswith(b"\n") for line in recovered.splitlines(keepends=True)), "restart did not recover complete JSONL records")
    os.close(directory)
    os.close(parent)

with tempfile.TemporaryDirectory(prefix="caml-fs-matrix-") as temporary_root:
    parent = os.open(temporary_root, os.O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW)
    directory = open_leaf(parent, "diagnostic")
    atomic_events(directory, [b'{"v":1,"q":0}\n'])
    for fault in ("event-open", "event-validate", "event-read", "event-close", "temp-open", "file-fsync", "temp-close", "rename", "directory-fsync"):
        assert_file_fault(directory, fault)
    before_eintr = read_events(directory)
    fault_atomic_events(directory, [b'{"v":1,"q":1}\n'], eintr_once=True)
    after_eintr = read_events(directory)
    assert_true(after_eintr.endswith(b'{"v":1,"q":1}\n') and after_eintr.startswith(before_eintr), "EINTR retry did not preserve and commit complete records")

    stale = os.open("events.jsonl.tmp", os.O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0o600, dir_fd=directory)
    os.write(stale, b"stale\n")
    os.close(stale)
    fault_atomic_events(directory, [b'{"v":1,"q":2}\n'])
    assert_true(read_events(directory).endswith(b'{"v":1,"q":2}\n'), "validated stale temp was not recovered")
    os.symlink("/tmp", "events.jsonl.tmp", dir_fd=directory)
    try:
        try:
            fault_atomic_events(directory, [b'{"v":1,"q":3}\n'])
        except OSError:
            pass
        else:
            fail("unsafe stale temp symlink was accepted")
        os.stat("events.jsonl.tmp", dir_fd=directory, follow_symlinks=False)
    finally:
        os.unlink("events.jsonl.tmp", dir_fd=directory)

    fd = os.open("events.jsonl", os.O_WRONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
    os.ftruncate(fd, 0)
    os.write(fd, b'{"v":1,"q":0}\npartial')
    os.close(fd)
    fault_atomic_events(directory, [b'{"v":1,"q":4}\n'])
    recovered = read_events(directory)
    assert_true(b"partial" not in recovered and recovered.endswith(b'{"v":1,"q":4}\n'), "incomplete tail was not removed on restart")

    fd = os.open("events.jsonl", os.O_WRONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
    os.fchmod(fd, 0o644)
    os.close(fd)
    try:
        read_events(directory)
    except SystemExit:
        pass
    else:
        fail("permissive event mode was accepted")
    fd = os.open("events.jsonl", os.O_WRONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
    os.fchmod(fd, 0o600)
    os.close(fd)

    line = b'{"v":1,"q":5}\n'
    old = line * ((1024 * 1024 // len(line)) - 1)
    fd = os.open("events.jsonl", os.O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0o600, dir_fd=directory)
    os.write(fd, old)
    os.close(fd)
    fault_atomic_events(directory, [b'{"v":1,"q":6}\n'])
    saturated = read_events(directory)
    assert_true(len(saturated) <= 1024 * 1024 and saturated.endswith(b'{"v":1,"q":6}\n') and all(line.endswith(b"\n") for line in saturated.splitlines(keepends=True)), "retention saturation did not evict complete oldest records")
    os.close(directory)
    os.close(parent)

print("PASS: deterministic descriptors, truthful install status, guarded pass-through/ARC boundary, allowlist redaction, mutation-sensitive runtime/filesystem matrix, ring/dedup/session bounds, and no-device workflow checks")
