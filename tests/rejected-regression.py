from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REJECTED = "97eabba5d671005187011e518d9c6624e5298810"


def git_show(commit: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def violations(commit: str | None) -> list[str]:
    def read(path: str) -> str:
        return git_show(commit, path) if commit else (ROOT / path).read_text()

    source = read("src/Tweak.xm")
    workflow = read(".github/workflows/build-rootless.yml")
    caml = read("assets/Plampy/Assets/AppearanceModule.bundle/StyleMode.ca/main.caml")
    checks = read("tests/static-check.ts")
    failures = []
    if "THEOS_COMMIT: 5280bd038207e14f8bd76f5417aa2fe641c03228" not in workflow:
        failures.append("immutable rootless Theos pin")
    if "make clean stage FINALPACKAGE=0 STRIP=0" not in workflow:
        failures.append("pre-strip symbol collection")
    if "ReconcileGlyphView" not in source:
        failures.append("live glyph reconciliation")
    if "plampy.originalGlyph" in source:
        failures.append("owned glyph recovery state")
    if "wall.alpha = 0; [background insertSubview:wall" in source:
        failures.append("visible wallpaper transition")
    if "/var/jb/var/jb/" in caml:
        failures.append("repeated CAML prefix")
    if "source.includes(`@\\\"${identifier}\\\"`)" in checks:
        failures.append("token-only mapping checks")
    return failures


current_failures = violations(None)
if current_failures:
    raise SystemExit("current candidate still violates: " + ", ".join(current_failures))
rejected_failures = violations(REJECTED)
if len(rejected_failures) < 4:
    raise SystemExit(f"rejected candidate was not rejected by enough structural checks: {rejected_failures}")
print("PASS: current candidate clears structural regressions; rejected 97eabba fails " + ", ".join(rejected_failures))
