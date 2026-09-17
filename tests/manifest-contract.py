from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EMITTER = ROOT / ".github/workflows/emit-manifest.py"
THEOS = "5280bd038207e14f8bd76f5417aa2fe641c03228"
SDK = "146e41ff2c292168388929e43c9b4de2f00e36b3"
REJECTED = "97eabba5d671005187011e518d9c6624e5298810"
EXPECTED = {
    "symbols/arm64/PlampyCC.dylib": "tweak",
    "symbols/arm64/PlampyCC": "preferences",
    "symbols/arm64e/PlampyCC.dylib": "tweak",
    "symbols/arm64e/PlampyCC": "preferences",
}


def run_emitter(workspace: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", ".github/workflows/emit-manifest.py"],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def make_fixture(workspace: Path, symbols: tuple[str, ...]) -> None:
    (workspace / ".github/workflows").mkdir(parents=True)
    (workspace / "dist/packages").mkdir(parents=True)
    for arch in ("arm64", "arm64e"):
        (workspace / f"dist/symbols/{arch}").mkdir(parents=True)
    shutil.copy2(EMITTER, workspace / ".github/workflows/emit-manifest.py")
    (workspace / "dist/packages/plampycc.deb").write_bytes(b"package")
    for relative in symbols:
        path = workspace / "dist" / relative
        path.write_bytes(relative.encode())
    (workspace / "dist/source-commit.txt").write_text(REJECTED + "\n")
    (workspace / "dist/xcode-version.txt").write_text("Xcode fixture\n")


with tempfile.TemporaryDirectory(prefix="plampycc-manifest-") as temp:
    workspace = Path(temp)
    full = tuple(EXPECTED)
    make_fixture(workspace, full)
    env = {
        **os.environ,
        "GITHUB_REPOSITORY": "fixture/plampycc",
        "THEOS_COMMIT": THEOS,
        "SDK_COMMIT": SDK,
        "SDK_NAME": "iPhoneOS16.5.sdk",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "fixture",
    }
    result = run_emitter(workspace, env)
    if result.returncode != 0:
        raise SystemExit(f"full manifest producer failed: {result.stderr}")
    manifest = json.loads((workspace / "dist/build-manifest.json").read_text())
    if len(manifest["packages"]) != 1 or len(manifest["unstrippedBinaries"]) != 4:
        raise SystemExit("manifest coverage is not complete")
    for entry in manifest["unstrippedBinaries"]:
        filename = entry["filename"]
        if EXPECTED.get(filename) != entry.get("target"):
            raise SystemExit(f"manifest target mismatch: {filename}")
        if entry.get("architectures") != [filename.split("/")[1]]:
            raise SystemExit(f"manifest architecture mismatch: {filename}")
        digest = sha256((workspace / "dist" / filename).read_bytes()).hexdigest()
        if entry.get("sha256") != digest:
            raise SystemExit(f"manifest hash mismatch: {filename}")

with tempfile.TemporaryDirectory(prefix="plampycc-manifest-incomplete-") as temp:
    workspace = Path(temp)
    make_fixture(workspace, ("symbols/arm64/PlampyCC.dylib", "symbols/arm64e/PlampyCC.dylib", "symbols/arm64/PlampyCC"))
    if run_emitter(workspace, env).returncode == 0:
        raise SystemExit("manifest producer accepted incomplete target coverage")

print("PASS: manifest producer emitted and consumer-checked all four target/architecture entries; incomplete coverage rejected")
