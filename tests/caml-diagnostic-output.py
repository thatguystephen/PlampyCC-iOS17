from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/CAMLDiagnostic.xm").read_text()

OUTPUT_SUFFIX = Path("var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic")
EVENTS_NAME = "events.jsonl"


def fail(message: str) -> None:
    raise SystemExit(message)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def can_writer_modify(*, writer_uid: int, owner_uid: int, owner_gid: int, mode: int) -> bool:
    """Evaluate write permission bits for the simulated mobile writer."""
    if writer_uid == owner_uid:
        return bool(mode & 0o200)
    if writer_uid == owner_gid:
        return bool(mode & 0o020)
    return bool(mode & 0o002)


def validate_directory_fd(path: Path, *, effective_uid: int, leaf: bool) -> bool:
    """Mirror ValidateDirectoryFD's owner/mode checks for a real test directory."""
    status = path.stat()
    if not stat.S_ISDIR(status.st_mode):
        return False
    if leaf:
        return status.st_uid == effective_uid and stat.S_IMODE(status.st_mode) == 0o700
    return not (stat.S_IMODE(status.st_mode) & 0o022)


def main() -> None:
    diagnostic_start = SOURCE.index("static NSString *DiagnosticOutputDirectory")
    diagnostic_end = SOURCE.index("static bool ValidateDirectoryFD", diagnostic_start)
    output_function = SOURCE[diagnostic_start:diagnostic_end]
    expected_literal = 'ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic")'
    assert_true(expected_literal in output_function, "production output path is not the mobile-writable ROOT_PATH_NS path")
    assert_true('ROOT_PATH_NS(@"/Library/Application Support/PlampyCC/CAML-Diagnostic")' not in output_function,
                "production output path still targets the root-owned system asset root")

    # The process below stands in for SpringBoard's mobile uid. The normalized
    # package asset tree is modeled as uid/gid 0, mode 0755; the test does not
    # require root or mutate real ownership on the host.
    simulated_mobile_uid = 501
    normalized_owner_uid = 0
    normalized_owner_gid = 0
    normalized_mode = 0o755
    assert_true(not can_writer_modify(writer_uid=simulated_mobile_uid,
                                      owner_uid=normalized_owner_uid,
                                      owner_gid=normalized_owner_gid,
                                      mode=normalized_mode),
                "simulated mobile writer can modify the normalized root:wheel asset tree")

    with tempfile.TemporaryDirectory(prefix="plampycc-diagnostic-output-") as directory:
        sandbox = Path(directory)
        asset_root = sandbox / "var/jb/Library/Application Support/PlampyCC"
        asset_leaf = asset_root / "Plampy"
        asset_leaf.mkdir(parents=True)
        asset_root.chmod(0o755)
        asset_leaf.chmod(0o755)
        (asset_leaf / "wallpaper.jpeg").write_bytes(b"asset")
        (asset_leaf / "wallpaper.jpeg").chmod(0o644)
        assert_true(stat.S_IMODE(asset_root.stat().st_mode) == 0o755,
                    "normalized asset root is not mode 0755")
        assert_true(stat.S_IMODE(asset_leaf.stat().st_mode) == 0o755,
                    "normalized asset leaf is not mode 0755")

        # This is the mobile-writable counterpart, not a packaged directory.
        mobile_parent = sandbox / "var/jb/var/mobile/Library/Application Support/PlampyCC"
        mobile_parent.mkdir(parents=True)
        for parent in mobile_parent.parents:
            if parent != sandbox and sandbox in parent.parents:
                parent.chmod(0o755)
        assert_true(can_writer_modify(writer_uid=simulated_mobile_uid,
                                      owner_uid=simulated_mobile_uid,
                                      owner_gid=simulated_mobile_uid,
                                      mode=0o755),
                    "simulated mobile writer cannot create the mobile-writable output leaf")

        output = mobile_parent / "CAML-Diagnostic"
        output.mkdir(mode=0o700)
        output.chmod(0o700)
        effective_uid = os.geteuid()
        assert_true(validate_directory_fd(output, effective_uid=effective_uid, leaf=True),
                    "created diagnostic leaf fails ValidateDirectoryFD owner/mode checks")

        events = output / EVENTS_NAME
        events.write_text('{"v":1}\n')
        events.chmod(0o600)
        event_status = events.stat()
        assert_true(stat.S_IMODE(event_status.st_mode) == 0o600,
                    "events file is not restricted to mode 0600")
        assert_true(event_status.st_uid == effective_uid,
                    "events file is not owned by the mobile writer")
        assert_true(events.read_text() == '{"v":1}\n', "events file was not created with its payload")

    print("PASS: simulated mobile writer rejects root:wheel assets and creates/validates mobile CAML-Diagnostic/events.jsonl")


if __name__ == "__main__":
    main()
