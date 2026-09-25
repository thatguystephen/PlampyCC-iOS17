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
REPLACEMENT = (ROOT / "src/CAMLReplacement.xm").read_text()
REPLACEMENT_HEADER = (ROOT / "src/CAMLReplacement.h").read_text()
REPLACEMENT_CORE = (ROOT / "src/CAMLReplacementCore.hpp").read_text()
VERIFIED_ABI = (ROOT / "src/CAMLVerifiedABI.h").read_text()


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
    "CAMLButtonPackageHook": ("ObservePackage(self, description, \"button-package\")", "gOriginalButtonPackage)(self, cmd, argument)"),
    "CAMLRoundPackageHook": ("ObservePackage(self, description, \"round-package\")", "gOriginalRoundPackage)(self, cmd, argument)"),
    "CAMLSliderPackageHook": ("ObservePackage(self, description, \"slider-package\")", "gOriginalSliderPackage)(self, cmd, argument)"),
    "CAMLFactoryHook": ("ObserveFactory(packageName)", "gOriginalFactory)(self, cmd, packageName, bundle)"),
    "CAMLButtonStateHook": ("ObserveState(self, state, \"button-state\")", "gOriginalButtonState)(self, cmd, state)"),
    "CAMLSliderStateHook": ("ObserveState(self, state, \"slider-state\")", "gOriginalSliderState)(self, cmd, state)"),
}
for name, (observer, original) in hooks.items():
    body = function_body(HOOKS, name)
    assert_true(body.count(observer) == 1, f"{name} observer call is not exactly once")
    assert_true(body.count(original) == 1, f"{name} original call is not exactly once")
    assert_true(body.index(observer) < body.index(original), f"{name} does not preserve observe-before-pass-through ordering")
    assert_true("@" not in body, f"{name} uses Objective-C ownership/message syntax before the boundary")

low_power_body = function_body(HOOKS, "CAMLLowPowerDescriptionHook")
assert_true(low_power_body.count("gOriginalLowPowerDescription") == 2, "Low Power getter does not guard and invoke its exact original slot")
assert_true(low_power_body.count("ObservePackage(self, description, \"controller\")") == 1, "Low Power getter observer is not exactly once")
assert_true("CAMLCreateReplacementDescription" not in low_power_body and "CAMLRecordPackageInstall" not in low_power_body,
            "Low Power diagnostic seam must remain observer-only")
assert_true(low_power_body.index("gOriginalLowPowerDescription") < low_power_body.index("ObservePackage"),
            "Low Power getter does not observe the exact stock result")
assert_true('"CCUILowPowerModuleViewController", "glyphPackageDescription"' in SOURCE,
            "verified 21D50 Low Power getter descriptor is absent")

# The three package setters run the verified construct-and-pass route between
# observation and the original call: the ARC-side factory returns a +1
# replacement or nil (fail-open), the original receives argument = replacement
# ?: description, the owned/applied recovery state is recorded after the
# original invocation, and the +1 result is released exactly once through the
# shared MRR release helper. The borrowed incoming description is never
# released.
replacement_hooks = {
    "CAMLButtonPackageHook": ("CAMLCreateReplacementDescription(self, description, false)",
                              "CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 0)"),
    "CAMLRoundPackageHook": ("CAMLCreateReplacementDescription(self, description, false)",
                             "CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 1)"),
    "CAMLSliderPackageHook": ("CAMLCreateReplacementDescription(self, description, true)",
                              "CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 2)"),
}
for name, (factory_call, record_call) in replacement_hooks.items():
    body = function_body(HOOKS, name)
    observer, original = hooks[name]
    assert_true(body.count(factory_call) == 1, f"{name} does not call the CAML replacement factory exactly once")
    assert_true(body.count("argument = replacement ? replacement : description") == 1, f"{name} does not select replacement-or-original exactly once")
    assert_true(body.count(record_call) == 1, f"{name} does not record the owned/applied recovery state exactly once")
    assert_true(body.count("CAMLReleaseReplacement(replacement)") == 1, f"{name} does not release the +1 replacement exactly once")
    assert_true("CAMLReleaseReplacement(description)" not in body, f"{name} releases the borrowed incoming description")
    assert_true("objc_release" not in body, f"{name} depends on the unverified runtime release declaration")
    assert_true(body.index(observer) < body.index(factory_call) < body.index(original) < body.index(record_call)
                < body.index("CAMLReleaseReplacement(replacement)"),
                f"{name} does not preserve observe → replace → original → record → single-release ordering")
for name in ("CAMLFactoryHook", "CAMLButtonStateHook", "CAMLSliderStateHook"):
    assert_true("CAMLCreateReplacementDescription" not in function_body(HOOKS, name),
                f"{name} must not construct replacements")

# The pinned-SDK release declaration risk is resolved with the MRR message
# release form, centralized in exactly one shim helper whose declarations come
# from Foundation; the runtime's release entry-point is never named.
assert_true("objc_release" not in HOOKS, "the shim still depends on the unverified runtime release declaration")
assert_true(HOOKS.count("[replacement release]") == 1, "the MRR release form is not centralized in exactly one helper body")
assert_true("#import <Foundation/Foundation.h>" in HOOKS, "the MRR release form lacks its NSObject protocol declaration")
release_body = function_body(HOOKS, "CAMLReleaseReplacement")
assert_true(release_body.count("[replacement release]") == 1 and "description" not in release_body,
            "the release helper does not release exactly one replacement and nothing else")

# Reconcile-time invocations go through the shim's original-IMP slots, never
# the intercepted hooks, so restoration cannot overwrite recovery state.
invoke_body = function_body(HOOKS, "CAMLInvokeOriginalPackage")
for slot in ("gOriginalButtonPackage", "gOriginalRoundPackage", "gOriginalSliderPackage"):
    assert_true(slot in invoke_body, f"reconcile-time invoker omits the {slot} original slot")
assert_true("sel_registerName(\"setGlyphPackageDescription:\")" in invoke_body, "reconcile-time invoker does not use the verified setter selector")
assert_true(invoke_body.count(")(consumer, sel_registerName") == 1, "reconcile-time invoker performs more than one indirect call")

# The functional replacement boundary is ARC-owned, fail-open, and limited to
# the machine-verified declarations in CAMLVerifiedABI.h.
assert_true("ns_returns_retained" in REPLACEMENT_HEADER and "__unsafe_unretained id description" in REPLACEMENT_HEADER,
            "replacement factory does not declare the +1 borrowed-argument boundary")
assert_true("ns_returns_retained" in REPLACEMENT and "@try" in REPLACEMENT and "@catch (...)" in REPLACEMENT,
            "replacement factory lacks the guarded fail-open boundary")
assert_true(10 <= REPLACEMENT.count("return nil"), "replacement factory does not fail open on every miss")
assert_true("initWithPackageName:name inBundle:bundle" in REPLACEMENT, "replacement factory does not use the verified initializer route")
assert_true("ROOT_PATH_NS(@\"/Library/Application Support/PlampyCC\")" in REPLACEMENT
            and "ROOT_PATH_NS(@\"/var/mobile/Library/Application Support/PlampyCC\")" in REPLACEMENT,
            "replacement factory does not use the primary rooted theme path with bounded legacy fallback")
assert_true("CAMLVerifiedABI.h" in REPLACEMENT and "initWithPackageName:inBundle:" in VERIFIED_ABI
            and "packageURL" in VERIFIED_ABI and "0x1d308a228" in VERIFIED_ABI,
            "verified ABI declarations are missing or unreferenced")
assert_true("/var/jb" not in REPLACEMENT + REPLACEMENT_CORE, "replacement sources embed a hand-written rootless prefix")
assert_true("objc_msgSend" not in REPLACEMENT_CORE and "#import" not in REPLACEMENT_CORE,
            "replacement core is not a pure policy header")
for needle in ("BundleDirectoryForPackage", "\"timer\", \"TimerModule.bundle\"", "themeType == 1",
               "\"DisplayModule.bundle\"", "\"MediaControls.framework\"", "HearingAidsModule.bundle"):
    assert_true(needle in REPLACEMENT_CORE, f"replacement routing core omits {needle}")
assert_true("CAMLReplacementCore.hpp" in (ROOT / "tests/native-caml-diagnostic.cpp").read_text(),
            "native test does not exercise the production replacement routing core")

# SP1 live preference reconciliation: owned/applied recovery state, weak
# consumer lifetime tracking, main-thread reconcile from the preference reload
# seam, newest-stock preservation, and production-coupled transition tests
# across all three verified setter seams. SP1-R1/SP1-R2: the ARC adapter must
# DELEGATE every classification/record/reconcile transition to the shared
# production policy (no local transition reimplementation), mark its own
# constructions so owned inputs are never taken for stock, and the native
# suite must exercise those exact transitions with identity assertions and an
# honest weak-lifetime limitation.
TWEAK = (ROOT / "src/Tweak.xm").read_text()
native_test = (ROOT / "tests/native-caml-diagnostic.cpp").read_text()
for token in ("ClassifyInstall", "DecideReconcile", "ClassifyIncoming", "PlanConstruction",
              "RecordInstall", "ObserveReconcile", "PlanReconcileAction",
              "Seam::ButtonPackage", "Seam::RoundPackage", "Seam::SliderPackage"):
    assert_true(token in native_test, f"native transition tests do not cover the production reconcile policy: {token}")
for transition in ("ClassifyIncoming", "PlanConstruction", "RecordInstall", "ObserveReconcile", "PlanReconcileAction"):
    assert_true(f"caml_replacement::{transition}(" in REPLACEMENT,
                f"adapter does not delegate to the production transition {transition}")
    assert_true(transition in REPLACEMENT_CORE, f"shared policy does not define the production transition {transition}")
assert_true("weakObjectsHashTable" in REPLACEMENT and "allObjects" in REPLACEMENT,
            "package consumers are not tracked weakly for their lifetimes")
for key in ('@"identifier"', '@"original"', '@"applied"', '@"appliedTheme"'):
    assert_true(key in REPLACEMENT, f"package recovery state is not identity-aware: missing {key}")
assert_true("plampy.packageOverride" in REPLACEMENT and "plampy.packageSeam" in REPLACEMENT,
            "package recovery state is not association-scoped to the consumer")
assert_true("plampy.packageOwnedReplacement" in REPLACEMENT
            and "objc_setAssociatedObject(replacement, kPackageOwnedKey" in REPLACEMENT
            and "ObjCDescriptionOwned" in REPLACEMENT,
            "constructed replacements are not marked owned for incoming classification")
assert_true("CAMLRecordPackageInstall" in REPLACEMENT and "CAMLReconcilePackageConsumers" in REPLACEMENT,
            "ARC module does not own the install record and reconcile pass")
assert_true("ReadInstalledDescription(consumer, &probe)" in REPLACEMENT,
            "factory does not require a verified recovery read-back before taking ownership of stock")
assert_true("SameDescription" in REPLACEMENT and "ClassifyInstall" in REPLACEMENT_CORE
            and "DecideReconcile" in REPLACEMENT_CORE,
            "reconcile does not run the production classification and decision policy")
assert_true("kind == IncomingKind::NewStock" in REPLACEMENT_CORE and "input.prior.original" in REPLACEMENT_CORE,
            "recording does not limit stock adoption to genuinely newer stock")
assert_true("RecoveryState{base.original, nullptr, -1}" in REPLACEMENT_CORE,
            "restoration does not preserve the stock recovery record for stale owned reassignment")
assert_true("SP1-R3" in native_test,
            "native transition tests do not cover restore -> stale-owned reassignment -> reconcile/re-enable recovery")
assert_true("weak-lifetime" in native_test and "not executed on this host" in native_test,
            "native tests overclaim Foundation weak-lifetime proof for consumer destruction")
assert_true("CAMLInvokeOriginalPackage(seam, consumer" in REPLACEMENT,
            "reconcile does not invoke setters through the original-IMP slots")
assert_true("NSThread isMainThread" in REPLACEMENT and "dispatch_async(dispatch_get_main_queue()" in REPLACEMENT,
            "reconcile and record updates do not stay on the main thread")
assert_true("ReconcileWallpaper(overlay);\n        CAMLReconcilePackageConsumers();" in TWEAK,
            "preference reloads do not reconcile package consumers alongside the static state")
assert_true("valueForKey" not in REPLACEMENT and "setValue" not in REPLACEMENT,
            "the replacement route mutates private description state")
assert_true("glyphPackageDescription" in REPLACEMENT and "glyphPackageDescription" in VERIFIED_ABI,
            "the recovery read-back is not limited to the verified ABI declarations")
assert_true("CAML-REPLACEMENT-IMPLEMENTATION.md" not in REPLACEMENT and "CAML-ROUTING-BLOCKER.md" in REPLACEMENT,
            "the replacement module still points at the stale documentation")

assert_true("return gOriginalFactory ? ((id(*)(__unsafe_unretained id, SEL, __unsafe_unretained id, __unsafe_unretained id))gOriginalFactory)(self, cmd, packageName, bundle) : nil;" in HOOKS, "factory does not return the original result")
for name in hooks:
    assert_true(not re.search(rf"\b{name}\s*\([^;]*\)\s*\{{", SOURCE), f"legacy hook implementation remains in CAMLDiagnostic.xm: {name}")
    assert_true(name in SOURCE, f"hook declaration is not visible to installer integration: {name}")

class_defs = re.findall(r"\b(?:static\s+)?(?:id|void)\s+(CAML\w+Hook)\s*\([^;]*\)\s*\{", SOURCE)
assert_true(not class_defs, "CAMLDiagnostic.xm still owns replacement IMP bodies")


# The guarded observer is an ARC-owned body boundary. Only it may message
# objects, catch Objective-C exceptions, and touch the diagnostic ring.
primitive = function_body(SOURCE, "CAMLDiagnosticPrimitiveAdmission")
for predicate in ("gInDiagnosticObserver", "gLoggingDisabled", "kDiagnosticCompileEnabled", "gDiagnosticVerbose"):
    assert_true(predicate in primitive, f"primitive admission omits {predicate}")
assert_true("gDiagnosticEnabled" not in primitive, "runtime diagnostic preference can enable recording in a release build")
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
assert_true(len(rows) == 7, "deterministic seven-site descriptor table is incomplete")
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
directory_walk = function_body(IO, "OpenDirectoryUnderTrustedPrefix")
assert_true("O_RDONLY | O_DIRECTORY | O_CLOEXEC, 0" in directory_walk,
            "trusted platform prefix is not acquired once with normal symlink resolution")
assert_true(directory_walk.count("O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW") == 2
            and "makeDirectoryAt(adapter.context, current, component, 0700)" in directory_walk,
            "tweak-owned suffix does not retain no-follow open/retry plus mkdir 0700")
assert_true("ValidateDirectoryDescriptor(adapter, next, leaf, effectiveUser)" in directory_walk
            and "status.st_uid != effectiveUser" in IO
            and "(status.st_mode & 0777) == 0700" in IO,
            "tweak-owned suffix no longer enforces descriptor uid/mode validation")
assert_true("ValidatePlatformPrefixDescriptor(adapter, current, effectiveUser)" in directory_walk,
            "trusted prefix is not validated under the stated platform prefix policy")
platform_policy = function_body(IO, "ValidatePlatformPrefixDescriptor")
assert_true("status.st_uid == effectiveUser" in platform_policy
            and "(status.st_mode & 0002) == 0" in platform_policy
            and "status.st_uid == 0" in platform_policy
            and "(status.st_mode & 0022) == 0" in platform_policy,
            "platform prefix policy must admit the observed mobile 0755/0775 chains and reject world-writable or foreign-owned prefixes")
production_walk = function_body(SOURCE, "OpenDiagnosticDirectory")
assert_true("caml_diag::OpenDirectoryUnderTrustedPrefix" in production_walk
            and "DiagnosticTrustedPrefix()" in production_walk
            and "kDiagnosticOwnedSuffix" in production_walk,
            "production does not use the shared trusted-prefix directory walk")

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
output_directory = function_body(SOURCE, "DiagnosticOutputDirectory")
assert_true('ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic")' in output_directory,
            "diagnostic output must stay under the mobile-writable root")
assert_true('ROOT_PATH_NS(@"/Library/Application Support/PlampyCC/CAML-Diagnostic")' not in output_directory,
            "diagnostic output must not use the root-owned system asset root")
assert_true("return @\"/" not in output_directory and "/var/jb" not in output_directory,
            "diagnostic output must route through the rootless macro, never an unwrapped literal or hardcoded jailbreak root")
assert_true(re.search(r'kDiagnosticOwnedSuffix\s*=\s*"PlampyCC/CAML-Diagnostic"', SOURCE) is not None,
            "owned suffix must be exactly the tweak-owned PlampyCC/CAML-Diagnostic chain")
trusted_prefix = function_body(SOURCE, "DiagnosticTrustedPrefix")
assert_true('ROOT_PATH_NS(@"/var/mobile/Library/Application Support")' in trusted_prefix
            and 'ROOT_PATH_NS(@"/var/jb' not in trusted_prefix,
            "trusted platform prefix must preserve exactly one ROOT_PATH_NS rootless prefix")
output_test_source = (ROOT / "tests/caml-diagnostic-output.py").read_text()
walk_test_source = (ROOT / "tests/native-caml-directory-walk.cpp").read_text()
assert_true("OUTPUT_SUFFIX" in output_test_source and 'symlink_to("private/var"' in output_test_source
            and 'symlink_to("../../relocated-root"' in output_test_source,
            "output regression does not drive the fixture from OUTPUT_SUFFIX with rootless symlink topology")
assert_true("OpenDirectoryUnderTrustedPrefix" in walk_test_source
            and "legacy all-component no-follow walk" in walk_test_source
            and "events.jsonl" in walk_test_source,
            "executable regression does not run the shared production walk and baseline failure")
assert_true("policy-matrix" in walk_test_source and "expect-fail" in walk_test_source
            and "unwrapped" in output_test_source,
            "regression suite does not cover the observed chains, adversarial topologies, and path selection")
assert_true("CAML-Diagnostic" in DOC and "/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/events.jsonl" in DOC,
            "implementation document does not name the mobile-writable diagnostic output path")
assert_true("ValidatePlatformPrefixDescriptor" in DOC and "PlampyCC/CAML-Diagnostic" in DOC,
            "implementation document does not state the corrected trusted-prefix and owned-suffix contract")
FLASH = (ROOT / "docs/FLASHLIGHT-DIAGNOSTIC.md").read_text()
assert_true("Proven path-admission failure" in FLASH and "ValidatePlatformPrefixDescriptor" in FLASH
            and "/var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic/events.jsonl" in FLASH,
            "Flashlight diagnostic note does not record the proven failure and corrected path contract")
assert_true("plampycc-caml-observer-v2" in DOC and "plampycc-caml-observer-v2-diag" in DOC and "plampycc-caml-observer-v1" not in DOC,
            "implementation document has stale diagnostic build ID")
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

output_test = subprocess.run(
    ["python3", "tests/caml-diagnostic-output.py"],
    cwd=ROOT, text=True, capture_output=True,
)
assert_true(output_test.returncode == 0, f"mobile-writable diagnostic output contract failed:\n{output_test.stderr}")

assert_true("runs-on: macos-15" in WORKFLOW and "test \"$(uname -m)\" = arm64" in WORKFLOW, "Apple Silicon rootless build preflight is missing")
assert_true("tests/caml-diagnostic-contract.py" in WORKFLOW and "tests/caml-diagnostic-artifact.py" in WORKFLOW, "contract tests are not wired into CI")
assert_true("make clean package FINALPACKAGE=1 STRIP=0" in WORKFLOW and "source_preferences=" in WORKFLOW and "strip -x \"$source_binary\"" in WORKFLOW, "exact release companion workflow is missing")
assert_true("dpkg-deb -R" in WORKFLOW and "dpkg-deb -b" in WORKFLOW and "SHA256SUMS" in WORKFLOW, "package extraction/repack/checksum path is missing")
assert_true("pass_gate(12" in (ROOT / "tests/caml-diagnostic-artifact.py").read_text(), "twelve artifact gates are not declared")
for phrase in ("Hook list", "kDiagnosticEnabled", "events.jsonl", "build ID", "device-test gate", "install-once"):
    assert_true(phrase in DOC, f"implementation document omits {phrase}")

# Post-strip signing contract: strip -x invalidates the build-time ldid -S
# signature (the pinned Theos signs every linked binary through
# _THEOS_CODESIGN_COMMANDLINE), so every final staged Mach-O must be re-signed
# after stripping and before dpkg-deb -b, the shipped bytes must be proven
# unchanged since signing, and the final signatures must be verified from
# CodeDirectory hash coverage rather than tool exit codes.
strip_index = WORKFLOW.index("strip -x \"$source_binary\"")
resign_index = WORKFLOW.index("ldid -S \"$staged_file\"")
pack_index = WORKFLOW.index("dpkg-deb -b \"$RUNNER_TEMP/plampycc-package\"")
assert_true(strip_index < resign_index < pack_index,
            "final packaged Mach-Os are not re-signed after stripping and before packing")
assert_true("python3 -B tests/signature-contract.py" in WORKFLOW
            and "tests/signature-contract.py --package" in WORKFLOW,
            "signature self-test/package assertion is not wired into CI")
assert_true("cmp \"$packaged_file\" \"$RUNNER_TEMP/plampycc-package$relative\"" in WORKFLOW,
            "packaged bytes are not proven unchanged since signing")
assert_true("TARGET_CODESIGN_FLAGS ?= -S" in WORKFLOW and "TARGET_CODESIGN = ldid" in WORKFLOW,
            "workflow does not verify the pinned Theos signing step")
artifact_text = (ROOT / "tests/caml-diagnostic-artifact.py").read_text()
assert_true("signature_contract" in artifact_text and "extract_packaged_binaries" in artifact_text,
            "artifact gates do not verify the final packaged signatures")
signature_text = (ROOT / "tests/signature-contract.py").read_text()
assert_true("LC_CODE_SIGNATURE" in signature_text and "CodeDirectory" in signature_text
            and "hash mismatch" in signature_text and "self_test" in signature_text,
            "final-signature assertion is not a CodeDirectory hash-coverage check with fixtures")
assert_true("ldid -S" in DOC and "ldid -S" in (ROOT / "PROVENANCE.md").read_text(),
            "the pinned signing step is not documented")
assert_true("dispatch_sync" not in SOURCE and "dispatch_async" not in SOURCE, "diagnostic introduced queue dispatch")

print("PASS: redesigned non-ARC hook shim, guarded observer boundary, shared native policies, injected syscall adapter, atomic fault state, rootless verification contract, and post-strip ldid -S re-sign with final-signature and no-mutation assertions")
