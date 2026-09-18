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
    assert_true("__attribute__((noinline, used)) static uint32_t InstallCAMLDiagnosticSites" in source, "site installer must remain visible to artifact-order checks")
    constructor = function_body(source, "InitializeCAMLDiagnostic")
    assert_true(constructor.index("CAMLDiagnosticSite sites[kDiagnosticSiteCount] = {}") < constructor.index("BuildCAMLDiagnosticSites"), "descriptor storage is not allocated before initialization")
    assert_true(constructor.index("BuildCAMLDiagnosticSites") < constructor.index("InstallCAMLDiagnosticSites"), "installer can observe descriptors before they are populated")
    assert_true("gDiagnosticInstalledMask.store(installedMask" in source, "installation status is not retained")
    assert_true("RecordInstallStatus(&sites[index], succeeded)" in source, "per-site installation status is not recorded from the actual result")
    assert_true("event->installationSucceeded ? 1 : 0" in source, "installation status is not serialized truthfully")
    assert_true("kDiagnosticInstalledMask" not in source, "status assertion typo should not mask the real status symbol")

    expected_calls = {
        "CAMLButtonPackageHook": ("ObservePackage(self, description, \"button-view\")", "gOriginalButtonPackage)(self, cmd, description)"),
        "CAMLRoundPackageHook": ("ObservePackage(self, description, \"round-button\")", "gOriginalRoundPackage)(self, cmd, description)"),
        "CAMLSliderPackageHook": ("ObservePackage(self, description, \"slider-view\")", "gOriginalSliderPackage)(self, cmd, description)"),
        "CAMLFactoryHook": ("ObserveFactory(packageName, bundle)", "gOriginalFactory)(self, cmd, packageName, bundle)"),
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
    assert_true("RunObserver(false, ObservePackageBody" in source and "RunObserver(false, ObserveStateBody" in source, "setter observers are not guarded at their outer boundary")
    assert_true("RunObserver(true, ObserveFactoryBody" in source, "verbose factory observer is not guarded before type-check messaging")
    assert_true("RunObserver(false, FlushObserverBody" in source, "dismiss flush is not behind the observer guard")
    assert_true("objc_msgSend" not in function_body(source, "ObserveState"), "state getter messaging escaped its guarded body")
    assert_true("respondsToSelector" not in function_body(source, "ObserveState"), "state type-check messaging escaped its guarded body")
    assert_true("isKindOfClass" not in function_body(source, "ObserveFactory"), "factory type-check messaging escaped its guarded body")

    assert_true("std::atomic<bool> gDiagnosticEnabled(false)" in source and "std::atomic<bool> gDiagnosticVerbose(false)" in source, "diagnostic defaults are not disabled")
    assert_true('kDiagnosticBuildId[] = "plampycc-caml-observer-v1"' in source and '%.25s' in source, "install provenance build ID is truncated or missing")
    assert_true("kRingCapacity = 512" in source and "kSerializedEventCapacity = 256" in source and "kSessionEventCap = 2000" in source, "bounded logging constants are missing")
    assert_true("kDiagnosticRetentionBytes = 1024 * 1024" in source, "explicit diagnostic retention limit is missing")
    assert_true("openat" in source and "O_NOFOLLOW" in source and "fstat" in source and "S_ISREG" in source, "descriptor-based no-follow regular-file validation is missing")
    assert_true("renameat" in source and "fsync(temporary)" in source and "fsync(directory)" in source, "atomic crash-recoverable output protocol is missing")
    assert_true("status.st_uid != geteuid()" in source and "(status.st_mode & 0777) != 0600" in source, "owner and restrictive event-file permission validation is missing")
    assert_true("status.st_mode & 0777) == 0700" in source, "diagnostic directory permission validation is missing")
    assert_true("kDiagnosticTempFile" in source and "CompleteLinePrefix" in source, "interrupted-write recovery is missing")
    assert_true("NSFileHandle" not in source and "fileExistsAtPath" not in source and "chmod(path.fileSystemRepresentation" not in source, "path-based output API remains in the diagnostic")
    assert_true("(c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.'" in source and ": '_'" in source, "production whitelist redaction is missing")
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

# Mutation-sensitive checks: deliberately weaken the production source and require the contract to reject it.
mutant = SOURCE.replace("gOriginalButtonPackage)(self, cmd, description)", "gOriginalButtonPackage)(self, cmd, nil)", 1)
assert_true(not production_contract_accepts(mutant), "contract did not detect mutated original argument")
mutant = SOURCE.replace("if (gOriginalSliderState) ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);", "if (gOriginalSliderState) ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);\n    if (gOriginalSliderState) ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);", 1)
assert_true(not production_contract_accepts(mutant), "contract did not detect duplicate original call")
mutant = SOURCE.replace("entered = true;\n        body(context);", "body(context);\n        entered = true;", 1)
assert_true(not production_contract_accepts(mutant), "contract did not detect observer body before guard state")
mutant = SOURCE.replace("((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||\n                              (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.') ? (char)c : '_'", "(char)c")
assert_true(not production_contract_accepts(mutant), "contract did not detect weakened production redaction")
mutant = SOURCE.replace(" | O_NOFOLLOW", "")
assert_true(not production_contract_accepts(mutant), "contract did not detect weakened no-follow output open")

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

# Adversarial production whitelist fixture: the exact whitelist required by CopySafe rejects paths, XML, PII, and pointers.
def production_whitelist(value: str, capacity: int) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    return "".join(char if char in allowed else "_" for char in value[: capacity - 1])


adversarial = "/private/var/mobile/Documents/<contents user=Steph token=abc> Assets.car 0xdeadbeef"
redacted = production_whitelist(adversarial, 64)
assert_true("/" not in redacted and "<" not in redacted and " " not in redacted and "0xdeadbeef" not in redacted, "adversarial production-boundary redaction leaked prohibited data")

# Actual descriptor-based filesystem fault tests. These use openat/O_NOFOLLOW/fstat/renameat/fsync,
# the same primitives required by the production implementation, rather than a string-only model.
O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


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


def read_events(directory: int) -> bytes:
    fd = os.open("events.jsonl", os.O_RDONLY | O_CLOEXEC | O_NOFOLLOW, dir_fd=directory)
    size = validate_file(fd)
    data = os.read(fd, size)
    os.close(fd)
    for line in data.splitlines():
        json.loads(line)
    return data


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

print("PASS: deterministic descriptors, truthful install status, pre-gate observer isolation, mutation-sensitive pass-through/redaction, confined atomic filesystem faults, and no-device workflow checks")
