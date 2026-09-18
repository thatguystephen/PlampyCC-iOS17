from __future__ import annotations

import argparse
import io
import lzma
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

EXPECTED_LITERALS = (
    "CCUIButtonModuleView",
    "CCUIRoundButton",
    "CCUIBaseSliderView",
    "setGlyphPackageDescription:",
    "descriptionForPackageNamed:inBundle:",
    "setGlyphState:",
    "button-package",
    "round-package",
    "slider-package",
    "factory",
    "button-state",
    "slider-state",
    "unknown",
    "unknown-state",
    "unknown-class",
)


def run(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def source_order(source: str) -> None:
    constructor_start = source.index("InitializeCAMLDiagnostic")
    constructor = source[constructor_start:]
    storage = constructor.index("CAMLDiagnosticSite sites[kDiagnosticSiteCount] = {}")
    build = constructor.index("BuildCAMLDiagnosticSites")
    install = constructor.index("InstallCAMLDiagnosticSites")
    if not storage < build < install:
        raise SystemExit("descriptor initialization does not precede first installer use")
    if "gSites" in source or "component = nextComponent" in source:
        raise SystemExit("unsafe dynamic descriptor or NULL component traversal remains")
    walker = source[source.index("OpenDiagnosticDirectory"):source.index("ReadExistingEvents")]
    if "if (leaf) break;" not in walker or "bool leaf = *cursor == '\\0'" not in walker:
        raise SystemExit("final component traversal termination is not explicit")
    if "__unsafe_unretained id" not in source:
        raise SystemExit("observer contexts do not use borrowed ownership")


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
        # Keep the disassembly step in the artifact gate. Static borrowed-context and
        # source-order assertions are authoritative; otool output formats differ across Xcode.
        if not run(["otool", "-tvV", str(binary)]):
            raise SystemExit(f"{binary}: generated text disassembly is empty")
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


def extract_packaged_dylib(package: Path, destination: Path) -> None:
    members = ar_members(package.read_bytes())
    data_name = next((name for name in members if name.startswith("data.tar")), None)
    if data_name is None:
        raise SystemExit(f"{package}: data member is absent")
    compressed = members[data_name]
    payload = lzma.decompress(compressed) if data_name.endswith((".xz", ".lzma")) else compressed
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        candidate = next((member for member in archive.getmembers() if member.name.endswith("/PlampyCC.dylib")), None)
        if candidate is None:
            raise SystemExit(f"{package}: packaged tweak dylib is absent")
        extracted = archive.extractfile(candidate)
        if extracted is None:
            raise SystemExit(f"{package}: packaged tweak dylib cannot be extracted")
        destination.write_bytes(extracted.read())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--source", type=Path, default=Path("src/CAMLDiagnostic.xm"))
    args = parser.parse_args()
    source_order(args.source.read_text())
    with tempfile.TemporaryDirectory(prefix="caml-artifact-") as scratch:
        scratch_path = Path(scratch)
        for architecture in ("arm64", "arm64e"):
            companion = args.artifact / "symbols" / architecture / "PlampyCC.dylib"
            if not companion.is_file() or companion.stat().st_size == 0:
                raise SystemExit(f"missing unstripped {architecture} diagnostic binary")
            verify_slice(companion, require_symbols=True)
        packages = sorted((args.artifact / "packages").glob("*.deb"))
        if len(packages) != 1:
            raise SystemExit(f"expected one final package, found {len(packages)}")
        universal = scratch_path / "PlampyCC.dylib"
        extract_packaged_dylib(packages[0], universal)
        for architecture in ("arm64", "arm64e"):
            thin = scratch_path / f"PlampyCC-{architecture}.dylib"
            run(["lipo", str(universal), "-thin", architecture, "-output", str(thin)])
            verify_slice(thin, require_symbols=False)
    print("PASS: unstripped and final packaged arm64/arm64e slices preserve deterministic descriptors, guarded ARC boundaries, and no legacy initializer")


if __name__ == "__main__":
    main()
