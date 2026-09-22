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
    has_exact_release_companion = (
        "make clean package FINALPACKAGE=1 STRIP=0" in workflow
        and "source_dylib=" in workflow
        and "source_preferences=" in workflow
        and "cp \"$symbol_binary\" \"dist/symbols/$arch/$target\"" in workflow
        and "strip -x \"$source_binary\"" in workflow
    )
    if not has_exact_release_companion:
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


def main() -> int:
    """Return zero only when the current tree passes and the historical tree fails."""
    current_failures = violations(None)
    if current_failures:
        raise SystemExit("ASSERT_CURRENT_ZERO failed: " + ", ".join(current_failures))
    rejected_failures = violations(REJECTED)
    if len(rejected_failures) < 4:
        raise SystemExit(
            f"ASSERT_REJECTED_FAILS failed: expected >=4 violations, got {rejected_failures}"
        )
    print(
        "PASS: ASSERT_CURRENT_ZERO and ASSERT_REJECTED_FAILS "
        "(" + ", ".join(rejected_failures) + ")"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
