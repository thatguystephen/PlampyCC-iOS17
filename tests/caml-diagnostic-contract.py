from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/CAMLDiagnostic.xm").read_text()
HOOKS = (ROOT / "src/CAMLDiagnosticHooks.mm").read_text()
CORE = (ROOT / "src/CAMLDiagnosticCore.hpp").read_text()
IO = (ROOT / "src/CAMLDiagnosticIO.hpp").read_text()
MAKEFILE = (ROOT / "Makefile").read_text()
WORKFLOW = (ROOT / ".github/workflows/build-rootless.yml").read_text()
DOC = (ROOT / "docs/CAML-DIAGNOSTIC-IMPLEMENTATION.md").read_text()


def fail(message: str) -> None:
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


# The hook ABI is now a separately compiled, non-ARC boundary. It must never
# become an observer implementation or a second pass-through model.
assert_true("-fno-objc-arc" in MAKEFILE, "dedicated hook translation unit is not explicitly non-ARC")
assert_true("CAMLDiagnosticHooks.mm" in MAKEFILE and "src/CAMLDiagnosticHooks.mm" in MAKEFILE, "hook shim is not wired into the tweak")
assert_true("__has_feature(objc_arc)" in HOOKS and "must be compiled with ARC disabled" in HOOKS, "non-ARC compile guard is missing")
assert_true("@try" not in HOOKS and "objc_msgSend" not in HOOKS and "respondsToSelector" not in HOOKS, "hook shim performs guarded-body work before admission")
assert_true("CAMLDiagnosticPrimitiveAdmission(false)" in HOOKS and "CAMLDiagnosticPrimitiveAdmission(true)" in HOOKS, "hooks do not use primitive admission")

hooks = {
    "CAMLButtonPackageHook": ("ObservePackage(self, description, \"button-view\")", "gOriginalButtonPackage)(self, cmd, description)"),
    "CAMLRoundPackageHook": ("ObservePackage(self, description, \"round-button\")", "gOriginalRoundPackage)(self, cmd, description)"),
    "CAMLSliderPackageHook": ("ObservePackage(self, description, \"slider-view\")", "gOriginalSliderPackage)(self, cmd, description)"),
    "CAMLFactoryHook": ("ObserveFactory(packageName)", "gOriginalFactory)(self, cmd, packageName, bundle)"),
    "CAMLButtonStateHook": ("ObserveState(self, state, \"glyph-state\")", "gOriginalButtonState)(self, cmd, state)"),
    "CAMLSliderStateHook": ("ObserveState(self, state, \"glyph-state\")", "gOriginalSliderState)(self, cmd, state)"),
}
for name, (observer, original) in hooks.items():
    body = function_body(HOOKS, name)
    assert_true(body.count(observer) == 1, f"{name} observer call is not exactly once")
    assert_true(body.count(original) == 1, f"{name} original call is not exactly once")
    assert_true(body.index(observer) < body.index(original), f"{name} does not preserve observe-before-pass-through ordering")
    assert_true("@" not in body, f"{name} uses Objective-C ownership/message syntax before the boundary")

assert_true("return gOriginalFactory ? ((id(*)(__unsafe_unretained id, SEL, __unsafe_unretained id, __unsafe_unretained id))gOriginalFactory)(self, cmd, packageName, bundle) : nil;" in HOOKS, "factory does not return the original result")
for name in hooks:
    assert_true(not re.search(rf"\b{name}\s*\([^;]*\)\s*\{{", SOURCE), f"legacy hook implementation remains in CAMLDiagnostic.xm: {name}")
    assert_true(name in SOURCE, f"hook declaration is not visible to installer integration: {name}")

class_defs = re.findall(r"\b(?:static\s+)?(?:id|void)\s+(CAML\w+Hook)\s*\([^;]*\)\s*\{", SOURCE)
assert_true(not class_defs, "CAMLDiagnostic.xm still owns replacement IMP bodies")


# The guarded observer is an ARC-owned body boundary. Only it may message
# objects, catch Objective-C exceptions, and touch the diagnostic ring.
primitive = function_body(SOURCE, "CAMLDiagnosticPrimitiveAdmission")
for predicate in ("gInDiagnosticObserver", "gLoggingDisabled", "gDiagnosticEnabled", "gDiagnosticVerbose"):
    assert_true(predicate in primitive, f"primitive admission omits {predicate}")
assert_true("no message send, retain, allocation, logging, or filesystem operation" in SOURCE, "primitive boundary is undocumented")
run = function_body(SOURCE, "RunObserver")
assert_true(run.index("BeginObserver(verboseOnly)") < run.index("entered = true") < run.index("body(context)"), "observer body can run before admission")
assert_true("@catch (...)" in run and "@finally" in run and "EndObserver()" in run, "guarded observer boundary is not exception-safe")
assert_true("DisableLoggingForSession();" in run, "observer failures do not fail closed")
for name in ("ObservePackage", "ObserveState", "ObserveFactory"):
    assert_true(re.search(rf"extern \"C\"[^\n]*\b{name}\s*\(", SOURCE) is not None, f"{name} is not exported across the hook boundary")
assert_true("__unsafe_unretained id" in SOURCE and "CAMLPackageContext" in SOURCE, "observer arguments are not explicitly borrowed")

# Descriptor installation stays POD and deterministic, while replacements are
# supplied by the new shim rather than dynamically initialized hook storage.
rows = re.findall(r'sites\[(\d+)\]\s*=\s*\{\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*\(IMP\)(\w+),\s*&\w+,\s*(true|false)', SOURCE)
assert_true(len(rows) == 6, "deterministic six-site descriptor table is incomplete")
assert_true("gSites" not in SOURCE and "gDiagnosticInstalledMask" not in SOURCE, "legacy dynamic descriptor state remains")
assert_true("RecordInstallStatus(&sites[index], succeeded)" in SOURCE, "installation truth is not recorded from the actual result")
assert_true("MSHookMessageEx" in function_body(SOURCE, "InstallSite"), "runtime installer does not use the declared hook boundary")
for guard in ("RuntimeInstallDecision::MissingClass", "RuntimeInstallDecision::MissingMethod", "RuntimeInstallDecision::WrongEncoding", "RuntimeInstallDecision::OriginalUnavailable"):
    assert_true(guard in CORE or guard in function_body(SOURCE, "InstallSite"), f"runtime installer decision is missing: {guard}")
assert_true("DecideRuntimeInstall" in function_body(SOURCE, "InstallSite"), "production installer does not use the shared runtime decision helper")
assert_true("RuntimeInstallDecision::Installed" in function_body(SOURCE, "InstallSite"), "runtime installer does not require the installed decision")
assert_true("DecideRuntimeInstall" in (ROOT / "tests/native-caml-diagnostic.cpp").read_text(), "native runtime metadata decision coverage is missing")
assert_true("makeDirectoryAt" in IO and "stat" in IO, "directory creation/stat operations are outside the injected adapter")
assert_true("DarwinMakeDirectoryAt" in SOURCE and "DarwinStat" in SOURCE, "production directory/stat adapter callbacks are missing")

# All non-ObjC policies are single-source production helpers. The host test
# compiles those exact headers; it is not a Python behavioral reimplementation.
for needle in ("caml_diag::ApprovedValue", "caml_diag::RingPolicy", "caml_diag::DedupPolicy", "caml_diag::CompleteLinePrefix", "caml_diag::AtomicOutputState", "caml_diag::WriteAll"):
    assert_true(needle in SOURCE, f"production does not call shared helper {needle}")
assert_true("kApprovedPackages" in CORE and "kApprovedStates" in CORE and "kApprovedClasses" in CORE, "approved-value policy is not centralized")
assert_true("AtomicOperation" in CORE and "AtomicPhase" in CORE, "atomic fault state machine is not centralized")
assert_true("struct SyscallAdapter" in IO and "AdapterReady" in IO and "EINTR" in SOURCE, "Darwin syscall adapter boundary is missing")
assert_true("gDarwinSyscalls" in SOURCE and "DarwinOpenAt" in SOURCE and "DarwinRenameAt" in SOURCE, "production adapter is not defined")
assert_true("O_NOFOLLOW" in SOURCE and "openat(" in SOURCE and "fstat(" in SOURCE and "S_ISREG" in SOURCE, "descriptor confinement is missing")
assert_true("renameAt" in SOURCE and "sync" in SOURCE and "CAMLScopedTempFile" in SOURCE, "atomic commit ownership boundary is missing")
assert_true("status.st_uid != geteuid()" in SOURCE and "(status.st_mode & 0777) != 0600" in SOURCE, "owner/mode validation is missing")
assert_true("CompleteLinePrefix" in SOURCE and "events.jsonl.tmp" in SOURCE, "restart tail/temp recovery boundary is missing")
assert_true("NSFileHandle" not in SOURCE and "fileExistsAtPath" not in SOURCE, "path-based diagnostic output API remains")

# Build the production helper test and run it from this contract.
with tempfile.TemporaryDirectory(prefix="caml-contract-") as directory:
    binary = Path(directory) / "native-caml-diagnostic"
    result = subprocess.run(
        ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "tests/native-caml-diagnostic.cpp", "-o", str(binary)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert_true(result.returncode == 0, f"native production-helper compile failed:\n{result.stderr}")
    result = subprocess.run([str(binary)], cwd=ROOT, text=True, capture_output=True)
    assert_true(result.returncode == 0, f"native production-helper contract failed:\n{result.stderr}")

assert_true("runs-on: macos-15" in WORKFLOW and "test \"$(uname -m)\" = arm64" in WORKFLOW, "Apple Silicon rootless build preflight is missing")
assert_true("tests/caml-diagnostic-contract.py" in WORKFLOW and "tests/caml-diagnostic-artifact.py" in WORKFLOW, "contract tests are not wired into CI")
assert_true("make clean package FINALPACKAGE=1 STRIP=0" in WORKFLOW and "source_preferences=" in WORKFLOW and "strip -x \"$source_binary\"" in WORKFLOW, "exact release companion workflow is missing")
assert_true("dpkg-deb -R" in WORKFLOW and "dpkg-deb -b" in WORKFLOW and "SHA256SUMS" in WORKFLOW, "package extraction/repack/checksum path is missing")
assert_true("pass_gate(12" in (ROOT / "tests/caml-diagnostic-artifact.py").read_text(), "twelve artifact gates are not declared")
for phrase in ("Hook list", "kDiagnosticEnabled", "events.jsonl", "build ID", "device-test gate", "install-once"):
    assert_true(phrase in DOC, f"implementation document omits {phrase}")
assert_true("dispatch_sync" not in SOURCE and "dispatch_async" not in SOURCE, "diagnostic introduced queue dispatch")

print("PASS: redesigned non-ARC hook shim, guarded observer boundary, shared native policies, injected syscall adapter, atomic fault state, and rootless verification contract")
