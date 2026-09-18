from __future__ import annotations

import argparse
import re
import subprocess
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
    if "gSites" in source:
        raise SystemExit("global dynamically initialized descriptor table remains")


def verify_slice(binary: Path) -> None:
    strings = run(["strings", str(binary)])
    missing = [literal for literal in EXPECTED_LITERALS if literal not in strings]
    if missing:
        raise SystemExit(f"{binary}: missing descriptor literal(s): {', '.join(missing)}")
    symbols = run(["nm", "-a", str(binary)])
    if "BuildCAMLDiagnosticSites" not in symbols or "InstallCAMLDiagnosticSites" not in symbols:
        raise SystemExit(f"{binary}: deterministic descriptor builder/installer symbols are absent")
    if re.search(r"GLOBAL__sub_I_CAMLDiagnostic", symbols):
        raise SystemExit(f"{binary}: legacy CAML translation-unit global initializer is present")
    load_commands = run(["otool", "-l", str(binary)])
    if "LC_UUID" not in load_commands:
        raise SystemExit(f"{binary}: Mach-O UUID load command is absent")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--source", type=Path, default=Path("src/CAMLDiagnostic.xm"))
    args = parser.parse_args()
    source_order(args.source.read_text())
    for architecture in ("arm64", "arm64e"):
        binary = args.artifact / "symbols" / architecture / "PlampyCC.dylib"
        if not binary.is_file() or binary.stat().st_size == 0:
            raise SystemExit(f"missing unstripped {architecture} diagnostic binary")
        verify_slice(binary)
    print("PASS: both arm64 and arm64e artifacts contain deterministic initialized descriptors before installer use")


if __name__ == "__main__":
    main()
