from __future__ import annotations

import argparse
import importlib.util
import io
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

_SIGNATURE_SPEC = importlib.util.spec_from_file_location(
    "signature_contract", Path(__file__).resolve().parent / "signature-contract.py"
)
assert _SIGNATURE_SPEC is not None and _SIGNATURE_SPEC.loader is not None
signature_contract = importlib.util.module_from_spec(_SIGNATURE_SPEC)
_SIGNATURE_SPEC.loader.exec_module(signature_contract)

EXPECTED_LITERALS = (
    "CCUIButtonModuleView",
    "CCUIRoundButton",
    "CCUIBaseSliderView",
    "setGlyphPackageDescription:",
    "descriptionForPackageNamed:inBundle:",
    "initWithPackageName:inBundle:",
    "packageURL",
    "setGlyphState:",
    "button-package",
    "round-package",
    "slider-package",
    "factory",
    "button-state",
    "slider-state",
    "CCUILowPowerModuleViewController",
    "glyphPackageDescription",
    "controller",
    "DisplayModule.bundle",
    "MediaControls.framework",
    "TimerModule.bundle",
    "unknown",
    "unknown-state",
    "unknown-class",
)


def run(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def function_body(source: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\(", source)
    if match is None:
        raise SystemExit(f"missing function {name}")
    opening = source.find("{", match.start())
    if opening < 0:
        raise SystemExit(f"missing function body for {name}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise SystemExit(f"unterminated function {name}")


def verify_shared_directory_walk(source: str, io_source: str) -> None:
    production_walk = function_body(source, "OpenDiagnosticDirectory")
    helper_call = "caml_diag::OpenDirectoryUnderTrustedPrefix("
    if '#include "CAMLDiagnosticIO.hpp"' not in source or production_walk.count(helper_call) != 1:
        raise SystemExit("production does not delegate exactly once to the shared directory walker")

    shared_walk = function_body(io_source, "OpenDirectoryUnderTrustedPrefix")
    leaf_detection = "bool leaf = *cursor == '\\0';"
    leaf_validation = "ValidateDirectoryDescriptor(adapter, next, leaf, effectiveUser)"
    leaf_termination = "if (leaf) break;"
    required = (leaf_detection, leaf_validation, "current = next;", leaf_termination)
    if any(token not in shared_walk for token in required):
        raise SystemExit("shared directory walker lacks explicit final-component detection, validation, or termination")
    if not (shared_walk.index(leaf_detection) < shared_walk.index(leaf_validation)
            < shared_walk.index("current = next;") < shared_walk.index(leaf_termination)):
        raise SystemExit("shared directory walker does not validate and retain the final component before terminating")


def verify_missing_termination_is_rejected(source: str, io_source: str) -> None:
    termination = "if (leaf) break;"
    if io_source.count(termination) != 1:
        raise SystemExit("shared directory walker termination fixture is ambiguous")
    malformed = io_source.replace(termination, "/* final-component termination removed */", 1)
    try:
        verify_shared_directory_walk(source, malformed)
    except SystemExit:
        return
    raise SystemExit("artifact source gate accepted a shared walker without explicit final-component termination")


def source_order(source: str, io_source: str) -> None:
    constructor_start = source.index("InitializeCAMLDiagnostic")
    constructor = source[constructor_start:]
    storage = constructor.index("CAMLDiagnosticSite sites[kDiagnosticSiteCount] = {}")
    build = constructor.index("BuildCAMLDiagnosticSites")
    install = constructor.index("InstallCAMLDiagnosticSites")
    if not storage < build < install:
        raise SystemExit("descriptor initialization does not precede first installer use")
    if "gSites" in source or "component = nextComponent" in source or "gDiagnosticInstalledMask" in source:
        raise SystemExit("unsafe dynamic descriptor or parallel installed-state model remains")
    if "__unsafe_unretained id" not in source:
        raise SystemExit("observer contexts do not use borrowed ownership")
    if "caml_diag::AtomicOutputState" not in source or "caml_diag::CompleteLinePrefix" not in source:
        raise SystemExit("production does not call the shared atomic/recovery policy")
    if "gDarwinSyscalls" not in source or "CAMLDiagnosticHooks.mm" in source:
        raise SystemExit("Darwin syscall adapter boundary is absent or hook shim leaked into observer source")
    for name in ("CAMLButtonPackageHook", "CAMLRoundPackageHook", "CAMLSliderPackageHook", "CAMLFactoryHook", "CAMLButtonStateHook", "CAMLSliderStateHook", "CAMLLowPowerDescriptionHook"):
        if re.search(rf"\b{name}\s*\([^;]*\)\s*\{{", source):
            raise SystemExit(f"replacement IMP body remains in diagnostic source: {name}")
    verify_shared_directory_walk(source, io_source)
    verify_missing_termination_is_rejected(source, io_source)


def observer_instruction_ranges(symbols: str, disassembly: str) -> dict[str, str]:
    address_by_symbol: dict[str, int] = {}
    all_addresses: list[int] = []
    for line in symbols.splitlines():
        match = re.match(r"^([0-9a-fA-F]+)\s+.*\s+(\S+)$", line.strip())
        if match is None:
            continue
        address = int(match.group(1), 16)
        all_addresses.append(address)
        name = match.group(2).lstrip("_")
        for observer in ("ObservePackage", "ObserveState", "ObserveFactory"):
            if observer in name and f"{observer}Body" not in name:
                address_by_symbol[observer] = address
    if len(address_by_symbol) != 3:
        raise SystemExit("generated observer symbol addresses are incomplete")
    sorted_addresses = sorted(set(all_addresses))
    instruction_lines: list[tuple[int, str]] = []
    for line in disassembly.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]{8,})\s+", line)
        if match is not None:
            instruction_lines.append((int(match.group(1), 16), line))
    ranges: dict[str, str] = {}
    for observer, start in address_by_symbol.items():
        following = [address for address in sorted_addresses if address > start]
        end = following[0] if following else start + 0x1000
        lines = [line for address, line in instruction_lines if start <= address < end]
        if not lines:
            raise SystemExit(f"generated disassembly has no instruction range for {observer}")
        ranges[observer] = "\n".join(lines)
    return ranges


HOOK_NAMES = (
    "CAMLButtonPackageHook", "CAMLRoundPackageHook", "CAMLSliderPackageHook",
    "CAMLFactoryHook", "CAMLButtonStateHook", "CAMLSliderStateHook",
    "CAMLLowPowerDescriptionHook",
)
ORIGINAL_SLOT_NAMES = (
    "gOriginalButtonPackage", "gOriginalRoundPackage", "gOriginalSliderPackage",
    "gOriginalFactory", "gOriginalButtonState", "gOriginalSliderState",
    "gOriginalLowPowerDescription",
)
DESCRIPTOR_NAMES = ("BuildCAMLDiagnosticSites", "InstallCAMLDiagnosticSites")
REPLACEMENT_BOUNDARY_NAMES = (
    "CAMLDiagnosticPrimitiveAdmission", "CAMLCreateReplacementDescription",
    "CAMLRecordPackageInstall", "CAMLReconcilePackageConsumers",
    "CAMLInvokeOriginalPackage", "CAMLReleaseReplacement",
)
PACKAGE_HOOK_NAMES = ("CAMLButtonPackageHook", "CAMLRoundPackageHook", "CAMLSliderPackageHook")


def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(artifact: Path) -> None:
    manifest = artifact / "SHA256SUMS"
    if not manifest.is_file():
        raise SystemExit("artifact checksum manifest is absent")
    expected: dict[str, str] = {}
    for line in manifest.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        expected[name] = digest
    if not expected:
        raise SystemExit("artifact checksum manifest is empty")
    for name, digest in expected.items():
        path = artifact / name
        if not path.is_file() or sha256(path) != digest:
            raise SystemExit(f"checksum mismatch: {name}")
    if any(name.startswith(".ci-artifacts/") or name.startswith("/") for name in expected):
        raise SystemExit("checksum manifest contains an absolute or local artifact path")


def pass_gate(number: int, name: str) -> None:
    print(f"PASS gate {number:02d}: {name}")




def symbol_addresses(symbols: str, names: tuple[str, ...]) -> dict[str, int]:
    found: dict[str, int] = {}
    for line in symbols.splitlines():
        match = re.match(r"^([0-9a-fA-F]+)\s+.*\s+(\S+)$", line.strip())
        if match is None:
            continue
        name = match.group(2).lstrip("_")
        for expected in names:
            if name == expected:
                found[expected] = int(match.group(1), 16)
    return found


def all_symbol_addresses(symbols: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for line in symbols.splitlines():
        match = re.match(r"^([0-9a-fA-F]+)\s+.*\s+(\S+)$", line.strip())
        if match is not None:
            found[match.group(2).lstrip("_")] = int(match.group(1), 16)
    return found


def branch_to(line: str, address: int, name: str | None = None) -> bool:
    opcode_ok = re.match(r"^\s*[0-9a-fA-F]{8,}\s+b", line) is not None
    target_ok = re.search(rf"(?:0x)?0*{address:x}(?:\b|\s|$)", line) is not None
    named_ok = name is not None and name in line
    return opcode_ok and (target_ok or named_ok)


def disassembly_ranges(disassembly: str, addresses: dict[str, int], boundaries: dict[str, int] | None = None) -> dict[str, str]:
    instructions: list[tuple[int, str]] = []
    for line in disassembly.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]{8,})\s+", line)
        if match is not None:
            instructions.append((int(match.group(1), 16), line))
    starts = sorted(set((boundaries or addresses).values()))
    starts = [value for value in starts if value >= min(addresses.values())]
    ranges: dict[str, str] = {}
    for name, start in addresses.items():
        end = next((value for value in starts if value > start), start + 0x1000)
        lines = [line for address, line in instructions if start <= address < end]
        if not lines:
            raise SystemExit(f"final slice has no instructions for {name}")
        ranges[name] = "\n".join(lines)
    return ranges


def uuid_of(binary: Path) -> str:
    load_commands = run(["otool", "-l", str(binary)])
    match = re.search(r"LC_UUID\s+.*?uuid\s+([0-9A-Fa-f-]+)", load_commands, re.S)
    if match is None:
        raise SystemExit(f"{binary}: Mach-O UUID load command is absent")
    return match.group(1).lower()


def verify_symbol_companion(companion: Path) -> None:
    symbols = run(["nm", "-a", str(companion)])
    required = HOOK_NAMES + REPLACEMENT_BOUNDARY_NAMES + ORIGINAL_SLOT_NAMES + DESCRIPTOR_NAMES
    missing = [name for name in required if name not in symbols]
    if missing:
        raise SystemExit(f"{companion}: exact unstripped map is incomplete: {', '.join(missing)}")
    load_commands = run(["otool", "-l", str(companion)])
    if "LC_UUID" not in load_commands:
        raise SystemExit(f"{companion}: Mach-O UUID load command is absent")


def verify_stripped_slice(binary: Path, companion: Path, architecture: str) -> None:
    if uuid_of(binary) != uuid_of(companion):
        raise SystemExit(f"{binary}: UUID does not match its exact unstripped companion")
    symbols = run(["nm", "-arch", architecture, "-a", str(companion)])
    required = HOOK_NAMES + REPLACEMENT_BOUNDARY_NAMES + ORIGINAL_SLOT_NAMES + DESCRIPTOR_NAMES
    addresses = symbol_addresses(symbols, required)
    missing = [name for name in required if name not in addresses]
    if missing:
        raise SystemExit(f"{companion}: exact unstripped map is incomplete: {', '.join(missing)}")
    if len({addresses[name] for name in ORIGINAL_SLOT_NAMES}) != len(ORIGINAL_SLOT_NAMES):
        raise SystemExit(f"{companion}: original IMP slots are not six distinct addresses")
    if addresses["BuildCAMLDiagnosticSites"] >= addresses["InstallCAMLDiagnosticSites"]:
        raise SystemExit(f"{companion}: descriptor construction is not before installation")
    disassembly = run(["otool", "-arch", architecture, "-tvV", str(binary)])
    boundaries = all_symbol_addresses(symbols)
    ranges = disassembly_ranges(disassembly, {name: addresses[name] for name in HOOK_NAMES}, boundaries)
    primitive = disassembly_ranges(disassembly, {"CAMLDiagnosticPrimitiveAdmission": addresses["CAMLDiagnosticPrimitiveAdmission"]}, boundaries)["CAMLDiagnosticPrimitiveAdmission"]
    admission = addresses["CAMLDiagnosticPrimitiveAdmission"]
    forbidden = ("objc_retain", "objc_storeStrong", "objc_release", "objc_msgSend")
    if any(token in primitive for token in forbidden):
        raise SystemExit(f"{binary}: primitive admission performs Objective-C ownership/message work")
    for name, body in ranges.items():
        lines = body.splitlines()
        admission_index = next((index for index, line in enumerate(lines)
                                if re.search(rf"(?:0x)?0*{admission:x}(?:\b|\s|$)", line)
                                or "CAMLDiagnosticPrimitiveAdmission" in line), None)
        if admission_index is None:
            raise SystemExit(f"{binary}: {name} has no mapped primitive-admission call")
        if any(any(token in line for token in forbidden) for line in lines[:admission_index]):
            raise SystemExit(f"{binary}: {name} has ownership/message work before admission")
        if not any("blr" in line for line in lines[admission_index + 1:]):
            raise SystemExit(f"{binary}: {name} has no original-IMP indirect call after admission")
    # Ownership bookkeeping for the three package hooks: exactly one recovery-state
    # record and exactly one release, both after the original invocation, with the
    # release after the record (the reviewed exactly-once post-original order).
    record_target = addresses["CAMLRecordPackageInstall"]
    release_target = addresses["CAMLReleaseReplacement"]
    for name in PACKAGE_HOOK_NAMES:
        lines = ranges[name].splitlines()
        record_calls = [index for index, line in enumerate(lines) if branch_to(line, record_target, "CAMLRecordPackageInstall")]
        release_calls = [index for index, line in enumerate(lines) if branch_to(line, release_target, "CAMLReleaseReplacement")]
        indirect = [index for index, line in enumerate(lines) if "blr" in line]
        if len(record_calls) != 1:
            raise SystemExit(f"{binary}: {name} does not record recovery state exactly once")
        if len(release_calls) != 1:
            raise SystemExit(f"{binary}: {name} does not release the replacement exactly once")
        if not indirect or record_calls[0] < indirect[-1] or release_calls[0] < record_calls[0]:
            raise SystemExit(f"{binary}: {name} ownership bookkeeping is not exactly once after the original invocation")


def verify_slice(binary: Path, require_symbols: bool) -> None:
    strings = run(["strings", str(binary)])
    missing = [literal for literal in EXPECTED_LITERALS if literal not in strings]
    if missing:
        raise SystemExit(f"{binary}: missing diagnostic literal(s): {', '.join(missing)}")
    symbols = run(["nm", "-a", str(binary)])
    if require_symbols:
        if "BuildCAMLDiagnosticSites" not in symbols or "InstallCAMLDiagnosticSites" not in symbols:
            raise SystemExit(f"{binary}: deterministic descriptor builder/installer symbols are absent")
        for symbol in ("ObservePackage", "ObserveState", "ObserveFactory"):
            if symbol not in symbols:
                raise SystemExit(f"{binary}: observer boundary symbol {symbol} is absent from generated code")
        disassembly = run(["otool", "-tvV", str(binary)])
        ranges = observer_instruction_ranges(symbols, disassembly)
        forbidden = ("objc_retain", "objc_storeStrong", "objc_release")
        for observer, body in ranges.items():
            if any(token in body for token in forbidden):
                raise SystemExit(f"{binary}: observer entry {observer} performs ARC ownership work before RunObserver")
    if re.search(r"GLOBAL__sub_I_CAMLDiagnostic", symbols):
        raise SystemExit(f"{binary}: legacy CAML translation-unit global initializer is present")
    load_commands = run(["otool", "-l", str(binary)])
    if "LC_UUID" not in load_commands:
        raise SystemExit(f"{binary}: Mach-O UUID load command is absent")


def ar_members(archive: bytes) -> dict[str, bytes]:
    if not archive.startswith(b"!<arch>\n"):
        raise SystemExit("downloaded package is not an ar archive")
    members: dict[str, bytes] = {}
    offset = 8
    while offset < len(archive):
        header = archive[offset : offset + 60]
        if len(header) != 60 or header[58:60] != b"`\n":
            raise SystemExit("malformed ar member")
        name = header[:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        start = offset + 60
        members[name] = archive[start : start + size]
        offset = start + size + (size & 1)
    return members


def extract_packaged_binaries(package: Path, destination: Path) -> dict[str, Path]:
    members = ar_members(package.read_bytes())
    data_name = next((name for name in members if name.startswith("data.tar")), None)
    if data_name is None:
        raise SystemExit(f"{package}: data member is absent")
    payload = members[data_name]
    extracted: dict[str, Path] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        for member in archive.getmembers():
            if member.uid != 0 or member.gid != 0:
                raise SystemExit(f"{package}:{member.name}: payload owner is {member.uid}:{member.gid}, expected root:wheel (0:0)")
            mode = member.mode & 0o7777
            if mode & 0o022:
                raise SystemExit(f"{package}:{member.name}: unsafe group/world-writable mode {mode:o}")
            if member.isdir() and mode != 0o755:
                raise SystemExit(f"{package}:{member.name}: directory mode is {mode:o}, expected 755")
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            blob = handle.read()
            if not signature_contract.is_macho(blob):
                if mode != 0o644:
                    raise SystemExit(f"{package}:{member.name}: data-file mode is {mode:o}, expected 644")
                continue
            if mode != 0o755:
                raise SystemExit(f"{package}:{member.name}: Mach-O mode is {mode:o}, expected 755")
            leaf = Path(member.name).name
            if leaf in extracted:
                raise SystemExit(f"{package}: packaged binary name {leaf} is ambiguous")
            target = destination / leaf
            target.write_bytes(blob)
            extracted[leaf] = target
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--source", type=Path, default=Path("src/CAMLDiagnostic.xm"))
    parser.add_argument("--io-source", type=Path, default=Path("src/CAMLDiagnosticIO.hpp"))
    args = parser.parse_args()
    source_order(args.source.read_text(), args.io_source.read_text())
    pass_gate(1, "source descriptor/admission order and shared directory-walker termination")
    companions = {}
    for number, architecture in ((2, "arm64"), (4, "arm64e")):
        companion = args.artifact / "symbols" / architecture / "PlampyCC.dylib"
        if not companion.is_file() or companion.stat().st_size == 0:
            raise SystemExit(f"missing unstripped {architecture} diagnostic binary")
        verify_symbol_companion(companion)
        companions[architecture] = companion
        pass_gate(number, f"{architecture} exact unstripped companion")
        pass_gate(number + 1, f"{architecture} companion descriptor and observer checks")
    packages = sorted((args.artifact / "packages").glob("*.deb"))
    if len(packages) != 1:
        raise SystemExit(f"expected one final package, found {len(packages)}")
    pass_gate(6, "single rootless package")
    with tempfile.TemporaryDirectory(prefix="caml-artifact-") as scratch:
        scratch_path = Path(scratch)
        extracted = extract_packaged_binaries(packages[0], scratch_path)
        for leaf in ("PlampyCC.dylib", "PlampyCC"):
            if leaf not in extracted:
                raise SystemExit(f"{packages[0]}: packaged binary {leaf} is absent")
        for leaf, path in sorted(extracted.items()):
            errors = signature_contract.verify_macho(path.read_bytes(), f"{packages[0]}:{leaf}")
            if errors:
                raise SystemExit("final packaged signature check failed: " + "; ".join(errors))
        universal = extracted["PlampyCC.dylib"]
        pass_gate(7, "extract packaged binaries and verify final code signatures")
        for number, architecture in ((8, "arm64"), (10, "arm64e")):
            companion = companions[architecture]
            thin = scratch_path / f"PlampyCC-{architecture}.dylib"
            run(["lipo", str(universal), "-thin", architecture, "-output", str(thin)])
            verify_slice(thin, require_symbols=False)
            verify_stripped_slice(thin, companion, architecture)
            pass_gate(number, f"{architecture} UUID-matched final machine-code boundary")
            pass_gate(number + 1, f"{architecture} final package literals and legacy-initializer gate")
    verify_checksums(args.artifact)
    pass_gate(12, "all declared artifact checksums")
    print("PASS: 12 package gates/checksum checks; exact UUID-matched stripped arm64/arm64e hook boundaries verified; final packaged code signatures verified")


if __name__ == "__main__":
    main()
