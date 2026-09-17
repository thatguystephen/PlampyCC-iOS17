from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
source_root = ROOT / "assets"
layout_root = ROOT / "layout/var/mobile/Library/Application Support/PlampyCC"
reference_pattern = re.compile(r'src="([^"]+)"')
expected_prefix = "/var/jb/var/mobile/Library/Application Support/PlampyCC/"
references = []

for path in sorted(source_root.rglob("*.caml")):
    text = path.read_text()
    mirror = layout_root / path.relative_to(source_root)
    if not mirror.exists() or mirror.read_bytes() != path.read_bytes():
        raise SystemExit(f"source/staged CAML mirror differs: {path}")
    source_references = reference_pattern.findall(text)
    mirror_references = reference_pattern.findall(mirror.read_text())
    if source_references != mirror_references:
        raise SystemExit(f"source/staged CAML references differ: {path}")
    for reference in source_references:
        if not reference.startswith(expected_prefix) or "/var/jb/var/jb/" in reference:
            raise SystemExit(f"invalid or repeated CAML prefix: {path}: {reference}")
        staged = ROOT / ("layout" + reference.removeprefix("/var/jb"))
        if not staged.exists():
            raise SystemExit(f"missing CAML dependency: {path}: {reference}")
        references.append(reference)
if len(references) != 81:
    raise SystemExit(f"expected 81 CAML references, found {len(references)}")

staged_references = []
for path in sorted(layout_root.rglob("*.caml")):
    for reference in reference_pattern.findall(path.read_text()):
        if not reference.startswith(expected_prefix) or "/var/jb/var/jb/" in reference:
            raise SystemExit(f"invalid or repeated staged CAML prefix: {path}: {reference}")
        staged_references.append(reference)
if staged_references != references:
    raise SystemExit("source and staged CAML reference coverage differs")

binary_mismatches = []
for path in sorted(source_root.rglob("*")):
    if not path.is_file() or path.suffix == ".caml":
        continue
    mirror = layout_root / path.relative_to(source_root)
    if not mirror.exists() or mirror.read_bytes() != path.read_bytes():
        binary_mismatches.append(str(path.relative_to(ROOT)))
if binary_mismatches:
    raise SystemExit("binary asset mismatch: " + ", ".join(binary_mismatches))

print(f"PASS: {len(references)} CAML references have one /var/jb prefix and all staged dependencies; binary mirrors match")
