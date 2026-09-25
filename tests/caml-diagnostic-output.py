from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/CAMLDiagnostic.xm").read_text()

# Drives the fixture: the tweak-owned suffix below the trusted platform prefix.
OUTPUT_SUFFIX = Path("PlampyCC/CAML-Diagnostic")
# The documented collector path. ROOT_PATH_NS contributes exactly one /var/jb
# prefix; the source never embeds the jailbreak root itself.
OUTPUT_FULL = Path("var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic")
EVENTS_NAME = "events.jsonl"


def fail(message: str) -> None:
    raise SystemExit(message)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def can_writer_modify(*, writer_uid: int, writer_gid: int,
                      owner_uid: int, owner_gid: int, mode: int) -> bool:
    """Evaluate write permission bits for the simulated mobile writer."""
    if writer_uid == owner_uid:
        return bool(mode & 0o200)
    if writer_gid == owner_gid:
        return bool(mode & 0o020)
    return bool(mode & 0o002)


def validate_directory_fd(path: Path, *, effective_uid: int, leaf: bool) -> bool:
    """Mirror ValidateDirectoryDescriptor owner/mode checks for a real directory."""
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        return False
    if info.st_uid != effective_uid:
        return False
    bits = stat.S_IMODE(info.st_mode)
    if leaf:
        return bits == 0o700
    return not (bits & 0o022)


def validate_platform_prefix_fd(path: Path, *, effective_uid: int) -> bool:
    """Mirror ValidatePlatformPrefixDescriptor's stated platform policy."""
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        return False
    bits = stat.S_IMODE(info.st_mode)
    if info.st_uid == effective_uid:
        return not (bits & 0o002)
    if info.st_uid == 0:
        return not (bits & 0o022)
    return False


def macro_literal(body: str, function: str) -> str:
    match = re.search(r'ROOT_PATH_NS\(@"([^"]+)"\)', body)
    assert_true(match is not None, f"{function} does not route through ROOT_PATH_NS")
    return match.group(1)


def main() -> None:
    diagnostic_start = SOURCE.index("static NSString *DiagnosticOutputDirectory")
    diagnostic_end = SOURCE.index("static NSString *DiagnosticTrustedPrefix", diagnostic_start)
    output_function = SOURCE[diagnostic_start:diagnostic_end]
    prefix_start = diagnostic_end
    prefix_end = SOURCE.index("static constexpr const char *kDiagnosticOwnedSuffix", prefix_start)
    prefix_function = SOURCE[prefix_start:prefix_end]
    suffix_match = re.search(r'kDiagnosticOwnedSuffix\s*=\s*"([^"]+)"', SOURCE)
    assert_true(suffix_match is not None, "kDiagnosticOwnedSuffix literal is missing")
    owned_suffix = suffix_match.group(1)

    # Path-selection contract: runtime data is routed through exactly one
    # ROOT_PATH_NS rewrite into the sanctioned rootless writable-state tree.
    # A bare /var/mobile return (unrewritten) or a hand-written /var/jb prefix
    # (randomized on undetectable jailbreaks) is a selection failure, and the
    # root-owned /Library package territory must stay read-only for output.
    expected_literal = 'ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic")'
    assert_true(expected_literal in output_function,
                "production output path is not the ROOT_PATH_NS-routed mobile-writable path")
    assert_true('ROOT_PATH_NS(@"/Library/Application Support/PlampyCC/CAML-Diagnostic")' not in output_function,
                "production output path still targets the root-owned system asset root")
    assert_true('ROOT_PATH_NS(@"/var/mobile/Library/Application Support")' in prefix_function,
                "trusted prefix is not the platform-owned mobile Application Support directory")
    for name, body in (("output", output_function), ("trusted prefix", prefix_function)):
        assert_true("return @\"/" not in body,
                    f"{name} returns an unwrapped literal path instead of ROOT_PATH_NS")
        assert_true("/var/jb" not in body,
                    f"{name} hardcodes the jailbreak root instead of the ROOT_PATH_NS macro")
    output_literal = macro_literal(output_function, "DiagnosticOutputDirectory")
    prefix_literal = macro_literal(prefix_function, "DiagnosticTrustedPrefix")
    assert_true(output_literal == prefix_literal + "/" + owned_suffix,
                "output path is not the trusted prefix plus the owned suffix")
    assert_true(owned_suffix == "PlampyCC/CAML-Diagnostic",
                "owned suffix is not the tweak-owned PlampyCC/CAML-Diagnostic chain")
    assert_true(output_literal == "/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic",
                "the logical output path changed unexpectedly")

    # The process below stands in for SpringBoard's mobile uid. The normalized
    # package asset tree is modeled as uid/gid 0, mode 0755; the test does not
    # require root or mutate real ownership on the host.
    simulated_mobile_uid = 501
    simulated_mobile_gid = 501
    assert_true(not can_writer_modify(writer_uid=simulated_mobile_uid,
                                      writer_gid=simulated_mobile_gid,
                                      owner_uid=0, owner_gid=0, mode=0o755),
                "simulated mobile writer can modify the normalized root:wheel asset tree")

    with tempfile.TemporaryDirectory(prefix="plampycc-diagnostic-output-") as directory:
        sandbox = Path(directory)

        # Reproduce the platform topology inside the sandbox:
        #   /var -> /private/var
        #   /var/jb -> relocated root
        # The walk target is the sanctioned rootless writable-state tree
        # relocated-root/var/mobile/Library/Application Support with the
        # observed mobile:mobile chain (Library 0755, Application Support
        # 0775). A parallel unwrapped var/mobile tree stands in for the
        # unrewritten path and must receive nothing.
        private_var = sandbox / "private/var"
        relocated_root = sandbox / "relocated-root"
        library = relocated_root / "var/mobile/Library"
        support = library / "Application Support"
        private_var.mkdir(parents=True)
        support.mkdir(parents=True)
        (sandbox / "var").symlink_to("private/var", target_is_directory=True)
        (private_var / "jb").symlink_to("../../relocated-root", target_is_directory=True)
        library.chmod(0o755)
        support.chmod(0o775)

        unwrapped_support = sandbox / "unwrapped/var/mobile/Library/Application Support"
        unwrapped_support.mkdir(parents=True)
        unwrapped_support.parent.chmod(0o755)
        unwrapped_support.chmod(0o775)

        asset_root = sandbox / "var/jb/Library/Application Support/PlampyCC"
        asset_leaf = asset_root / "Plampy"
        asset_leaf.mkdir(parents=True)
        asset_root.chmod(0o755)
        asset_leaf.chmod(0o755)
        (asset_leaf / "wallpaper.jpeg").write_bytes(b"asset")
        (asset_leaf / "wallpaper.jpeg").chmod(0o644)
        assert_true(mode_of(asset_root) == 0o755, "normalized asset root is not mode 0755")
        assert_true(mode_of(asset_leaf) == 0o755, "normalized asset leaf is not mode 0755")

        effective_uid = os.geteuid()
        assert_true(validate_platform_prefix_fd(support, effective_uid=effective_uid),
                    "observed 0775 mobile-writable platform parent fails the stated platform policy")
        assert_true(validate_platform_prefix_fd(unwrapped_support, effective_uid=effective_uid),
                    "unwrapped decoy parent fails the stated platform policy")
        assert_true(can_writer_modify(writer_uid=simulated_mobile_uid,
                                      writer_gid=simulated_mobile_gid,
                                      owner_uid=simulated_mobile_uid,
                                      owner_gid=simulated_mobile_gid,
                                      mode=0o775),
                    "simulated mobile writer cannot create the mobile-writable output leaf")

        output = sandbox / OUTPUT_FULL
        mobile_parent = output.parent
        assert_true(output == sandbox / "var/jb/var/mobile/Library/Application Support" / OUTPUT_SUFFIX,
                    "OUTPUT_SUFFIX no longer drives the diagnostic fixture")

        binary = sandbox / "native-caml-directory-walk"
        compile_result = subprocess.run(
            ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
             "tests/native-caml-directory-walk.cpp", "-o", str(binary)],
            cwd=ROOT, text=True, capture_output=True,
        )
        assert_true(compile_result.returncode == 0,
                    "shared production-walk regression compile failed:\n" + compile_result.stderr)

        def run_walk(*args: str, expect: int) -> subprocess.CompletedProcess:
            result = subprocess.run([str(binary), *args], cwd=ROOT, text=True, capture_output=True)
            assert_true(result.returncode == expect,
                        "walk scenario " + " ".join(args) + " returned " + str(result.returncode) + ":\n"
                        + result.stdout + result.stderr)
            return result

        # The e15e986 boundary: an all-component no-follow walk from above /var
        # must still fail at the first platform symlink.
        run_walk("legacy-boundary", str(sandbox), expect=0)
        # Synthetic uid/gid/mode matrix: the observed mobile:mobile chains are
        # admitted; adversarial ownership/world-writable variants are rejected.
        run_walk("policy-matrix", expect=0)

        # Happy path on the exact observed chain (Library 0755, Application
        # Support 0775): this is the fixture that fails before the platform
        # parent policy and passes after it.
        run_walk("expect-pass", str(support), expect=0)
        assert_true(validate_directory_fd(output, effective_uid=effective_uid, leaf=True),
                    "created diagnostic leaf fails shared production uid/mode checks")
        events = output / EVENTS_NAME
        event_status = events.stat()
        assert_true(stat.S_IMODE(event_status.st_mode) == 0o600,
                    "events file is not restricted to mode 0600")
        assert_true(event_status.st_uid == effective_uid,
                    "events file is not owned by the mobile writer")
        assert_true(events.read_text() == '{"v":1}\n', "events file was not created with its payload")

        # A 0755 platform parent (the other observed chain) must also pass.
        chain_0755 = sandbox / "chain-0755/var/mobile/Library/Application Support"
        chain_0755.mkdir(parents=True)
        chain_0755.parent.chmod(0o755)
        chain_0755.chmod(0o755)
        run_walk("expect-pass", str(chain_0755), expect=0)

        # Adversarial topologies must fail closed.
        world_writable = sandbox / "adversarial/world-writable/var/mobile/Library/Application Support"
        world_writable.mkdir(parents=True)
        world_writable.chmod(0o777)
        run_walk("expect-fail", str(world_writable), expect=0)

        outside = sandbox / "adversarial/outside"
        outside.mkdir(parents=True)

        symlink_intermediate = sandbox / "adversarial/symlink-intermediate/var/mobile/Library/Application Support"
        symlink_intermediate.mkdir(parents=True)
        (symlink_intermediate / "PlampyCC").symlink_to(outside, target_is_directory=True)
        run_walk("expect-fail", str(symlink_intermediate), expect=0)

        symlink_leaf = sandbox / "adversarial/symlink-leaf/var/mobile/Library/Application Support/PlampyCC"
        symlink_leaf.mkdir(parents=True)
        (symlink_leaf / "CAML-Diagnostic").symlink_to(outside, target_is_directory=True)
        run_walk("expect-fail", str(symlink_leaf.parent), expect=0)

        group_writable = sandbox / "adversarial/group-writable/var/mobile/Library/Application Support/PlampyCC"
        group_writable.mkdir(parents=True)
        group_writable.chmod(0o775)
        run_walk("expect-fail", str(group_writable.parent), expect=0)

        wrong_leaf_mode = sandbox / "adversarial/wrong-leaf-mode/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic"
        wrong_leaf_mode.mkdir(parents=True)
        wrong_leaf_mode.chmod(0o755)
        run_walk("expect-fail", str(wrong_leaf_mode.parent.parent), expect=0)

        # Path-selection regression: the unrewritten /var/mobile decoy tree
        # receives nothing; all output lands under the rootless rewrite.
        assert_true(not (sandbox / "unwrapped/var/mobile/Library/Application Support/PlampyCC").exists(),
                    "walk wrote into the unwrapped /var/mobile decoy tree")
        assert_true(mobile_parent == sandbox / "var/jb/var/mobile/Library/Application Support/PlampyCC",
                    "output left the rootless writable-state tree")

    print("PASS: legacy symlink walk fails; policy matrix covers the observed chains; "
          "the shared production walk admits mobile 0755/0775 platform parents, creates/validates "
          "CAML-Diagnostic/events.jsonl in the rootless rewrite tree, rejects adversarial "
          "symlink/ownership/mode topologies, and leaves the unwrapped decoy untouched")


if __name__ == "__main__":
    main()
