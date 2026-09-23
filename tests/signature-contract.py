"""Final-signature contract for the release package.

The pinned Theos build signs every linked binary at build time with `ldid -S`
(makefiles/instance/rules.mk `_THEOS_CODESIGN_COMMANDLINE`, driven by
`TARGET_CODESIGN = ldid` and `TARGET_CODESIGN_FLAGS ?= -S` from
makefiles/targets/_common/darwin_head.mk). The release repack then runs
`strip -x`, which mutates code bytes and stale-invalidates that build-time
signature, so the workflow re-signs every final packaged Mach-O with `ldid -S`
after stripping and before `dpkg-deb -b`.

This module is the automated assertion that the final package binaries really
carry valid code signatures afterwards: it parses each Mach-O slice's
LC_CODE_SIGNATURE embedded signature and recomputes the CodeDirectory page
hashes and any non-empty special-slot hashes against the actual shipped bytes.
A missing, stale, truncated, or partially hashed signature fails the build.
Tool exit codes are never trusted as proof of validity.

Run without arguments for the host-runnable fixture self test (synthetic thin
and universal signed Mach-Os must validate; unsigned, tampered-code,
tampered-hash, truncated-signature, and per-slice-tampered universal fixtures
must be rejected). Run with --package <deb> to validate a real package.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import struct
import tarfile
from pathlib import Path
from typing import NoReturn

CSMAGIC_EMBEDDED_SIGNATURE = 0xFADE0CC0
CSMAGIC_CODEDIRECTORY = 0xFADE0C02
CSSLOT_CODEDIRECTORY = 0
CSSLOT_ALTERNATE_CODEDIRECTORIES = 0x1000
CSSLOT_INFO_PLIST = 1
LC_CODE_SIGNATURE = 0x1D
FAT_MAGIC = 0xCAFEBABE
FAT_MAGIC_64 = 0xCAFEBABF
MH_MAGIC_64_LE = b"\xcf\xfa\xed\xfe"
MH_MAGIC_32_LE = b"\xce\xfa\xed\xfe"
FAT_BYTES = (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf")
PAGE = 4096
IDENT = b"plampycc-selftest\x00"


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def digest_of(hash_type: int, data: bytes) -> bytes:
    if hash_type == 1:
        return hashlib.sha1(data).digest()
    return hashlib.sha256(data).digest()[: {2: 32, 3: 20}[hash_type]]


HASH_SIZE = {1: 20, 2: 32, 3: 20}


def is_macho(data: bytes) -> bool:
    return data[:4] in FAT_BYTES or data[:4] in (MH_MAGIC_64_LE, MH_MAGIC_32_LE)


def macho_slices(data: bytes, label: str) -> list[tuple[str, bytes, int, int]]:
    """Return (label, slice-bytes, cputype, cpusubtype) for every architecture slice."""
    magic = data[:4]
    if magic == MH_MAGIC_64_LE:
        cputype, cpusubtype = struct.unpack_from("<II", data, 4)
        return [(label, data, cputype, cpusubtype)]
    if magic in FAT_BYTES:
        slices: list[tuple[str, bytes, int, int]] = []
        wide = magic == FAT_BYTES[1]
        count = struct.unpack_from(">I", data, 4)[0]
        entry_size = 32 if wide else 20
        if 8 + count * entry_size > len(data):
            fail(f"{label}: fat header runs past the file")
        for index in range(count):
            base = 8 + index * entry_size
            if wide:
                cputype, cpusubtype, offset, size = struct.unpack_from(">IIQQ", data, base)
            else:
                cputype, cpusubtype, offset, size = struct.unpack_from(">IIII", data, base)
            if size <= 0 or offset + size > len(data):
                fail(f"{label}: fat slice {index} runs past the file")
            slices.append((f"{label}[{index}]", data[offset : offset + size], cputype, cpusubtype))
        return slices
    fail(f"{label}: not a supported Mach-O container")


def verify_code_directory(
    label: str,
    block: bytes,
    offset: int,
    length: int,
    slice_bytes: bytes,
    dataoff: int,
    slots: list[tuple[int, int, int]],
) -> tuple[list[str], int | None]:
    """Validate one CodeDirectory against the slice bytes; return (errors, hash_type-if-valid)."""
    cd = block[offset : offset + length]
    errors: list[str] = []
    if len(cd) < 44:
        return [f"{label}: CodeDirectory header is truncated"], None
    (
        _magic,
        cd_length,
        _version,
        _flags,
        hash_offset,
        ident_offset,
        n_special_slots,
        n_code_slots,
        code_limit,
    ) = struct.unpack_from(">IIIIIIIII", cd, 0)
    hash_size, hash_type, _platform, page_size_log2 = struct.unpack_from(">BBBB", cd, 36)
    if cd_length != length:
        errors.append(f"{label}: CodeDirectory length field is inconsistent")
    if hash_type not in HASH_SIZE or hash_size != HASH_SIZE[hash_type]:
        return errors + [f"{label}: unsupported CodeDirectory hash type {hash_type}/{hash_size}"], None
    if page_size_log2 > 31:
        return errors + [f"{label}: unsupported CodeDirectory page size {page_size_log2}"], None
    page_size = (1 << page_size_log2) if page_size_log2 else max(code_limit, 1)
    if not (44 <= ident_offset < cd_length):
        errors.append(f"{label}: CodeDirectory identifier is out of bounds")
    # A valid signature hashes exactly the bytes that precede the signature
    # block. Anything else is stale (e.g. strip -x after signing) or partial.
    if code_limit != dataoff:
        errors.append(
            f"{label}: hashed code region ({code_limit}) does not end at the "
            f"signature ({dataoff}); the signature is stale or partial"
        )
    if code_limit > len(slice_bytes):
        errors.append(f"{label}: hashed code region runs past the slice")
    if errors:
        # Structural failures (stale or partial signature) make per-page hash
        # results redundant; report the root cause instead of its symptoms.
        return errors, None
    expected_slots = (code_limit + page_size - 1) // page_size if code_limit else 0
    if n_code_slots != expected_slots:
        errors.append(
            f"{label}: CodeDirectory covers {n_code_slots} code slots, "
            f"expected {expected_slots} for codeLimit {code_limit}"
        )
    hashes_end = hash_offset + n_code_slots * hash_size
    special_begin = hash_offset - n_special_slots * hash_size
    if special_begin < 44 or hashes_end > cd_length:
        return errors + [f"{label}: CodeDirectory hash storage is out of bounds"], None
    for index in range(n_code_slots):
        start = index * page_size
        end = min(start + page_size, code_limit)
        want = cd[hash_offset + index * hash_size : hash_offset + (index + 1) * hash_size]
        if digest_of(hash_type, slice_bytes[start:end]) != want:
            errors.append(f"{label}: code page {index} hash mismatch")
    for special in range(1, n_special_slots + 1):
        want = cd[hash_offset - special * hash_size : hash_offset - (special - 1) * hash_size]
        if want == b"\x00" * hash_size:
            continue  # empty special slot
        entry = next((slot for slot in slots if slot[0] == special), None)
        if entry is None:
            errors.append(f"{label}: special slot {special} has a hash but no signature slot")
            continue
        blob = block[entry[1] : entry[1] + entry[2]]
        if digest_of(hash_type, blob) != want:
            errors.append(f"{label}: special slot {special} hash mismatch")
    return errors, (hash_type if not errors else None)


def verify_signature_block(
    label: str, slice_bytes: bytes, dataoff: int, datasize: int
) -> list[str]:
    block = slice_bytes[dataoff : dataoff + datasize]
    if len(block) < 12 or datasize < 12:
        return [f"{label}: code signature block is truncated"]
    magic, length, count = struct.unpack_from(">III", block, 0)
    if magic != CSMAGIC_EMBEDDED_SIGNATURE:
        return [f"{label}: embedded signature superblob has magic {magic:#x}"]
    if length > datasize or 12 + 8 * count > length:
        return [f"{label}: code signature block is truncated"]
    slots: list[tuple[int, int, int]] = []
    for index in range(count):
        slot_type, offset = struct.unpack_from(">II", block, 12 + 8 * index)
        if offset + 8 > length:
            return [f"{label}: signature slot {slot_type:#x} is out of bounds"]
        _blob_magic, blob_length = struct.unpack_from(">II", block, offset)
        if blob_length < 8 or offset + blob_length > length:
            return [f"{label}: signature slot {slot_type:#x} has an out-of-bounds blob"]
        slots.append((slot_type, offset, blob_length))
    errors: list[str] = []
    valid_directories = 0
    valid_sha256_directories = 0
    for slot_type, offset, blob_length in slots:
        blob_magic = struct.unpack_from(">I", block, offset)[0]
        if blob_magic != CSMAGIC_CODEDIRECTORY:
            continue
        slot_errors, valid_type = verify_code_directory(
            label, block, offset, blob_length, slice_bytes, dataoff, slots
        )
        errors.extend(slot_errors)
        if valid_type is not None:
            valid_directories += 1
            if valid_type == 2:
                valid_sha256_directories += 1
    if valid_directories == 0 and not errors:
        errors.append(f"{label}: signature contains no CodeDirectory")
    if valid_sha256_directories == 0 and not errors:
        errors.append(f"{label}: no valid SHA-256 CodeDirectory")
    return errors


def verify_slice(label: str, slice_bytes: bytes) -> list[str]:
    if slice_bytes[:4] != MH_MAGIC_64_LE:
        return [f"{label}: slice is not a little-endian 64-bit Mach-O"]
    if len(slice_bytes) < 32:
        return [f"{label}: Mach-O header is truncated"]
    ncmds = struct.unpack_from("<I", slice_bytes, 16)[0]
    sizeofcmds = struct.unpack_from("<I", slice_bytes, 20)[0]
    if 32 + sizeofcmds > len(slice_bytes):
        return [f"{label}: load commands run past the slice"]
    signature: tuple[int, int] | None = None
    command_offset = 32
    for _ in range(ncmds):
        if command_offset + 8 > len(slice_bytes):
            return [f"{label}: load commands run past the slice"]
        cmd, cmdsize = struct.unpack_from("<II", slice_bytes, command_offset)
        if cmdsize < 8 or command_offset + cmdsize > len(slice_bytes):
            return [f"{label}: malformed load command size"]
        if cmd == LC_CODE_SIGNATURE:
            if cmdsize < 16:
                return [f"{label}: LC_CODE_SIGNATURE load command is malformed"]
            signature = struct.unpack_from("<II", slice_bytes, command_offset + 8)
        command_offset += cmdsize
    if signature is None:
        return [f"{label}: LC_CODE_SIGNATURE is absent; the slice is unsigned"]
    dataoff, datasize = signature
    if datasize < 12 or dataoff + datasize > len(slice_bytes):
        return [f"{label}: code signature block is truncated"]
    return verify_signature_block(label, slice_bytes, dataoff, datasize)


def verify_macho(data: bytes, label: str) -> list[str]:
    """Return a list of signature-validity errors for one (possibly fat) Mach-O."""
    if not is_macho(data):
        return [f"{label}: not a Mach-O"]
    errors: list[str] = []
    for slice_label, slice_bytes, _cputype, _cpusubtype in macho_slices(data, label):
        errors.extend(verify_slice(slice_label, slice_bytes))
    return errors


def ar_members(archive: bytes) -> dict[str, bytes]:
    if not archive.startswith(b"!<arch>\n"):
        fail("downloaded package is not an ar archive")
    members: dict[str, bytes] = {}
    offset = 8
    while offset < len(archive):
        header = archive[offset : offset + 60]
        if len(header) != 60 or header[58:60] != b"`\n":
            fail("malformed ar member")
        name = header[:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        start = offset + 60
        members[name] = archive[start : start + size]
        offset = start + size + (size & 1)
    return members


def package_macho_members(package: Path) -> dict[str, bytes]:
    members = ar_members(package.read_bytes())
    data_name = next((name for name in members if name.startswith("data.tar")), None)
    if data_name is None:
        fail(f"{package}: data member is absent")
    payload = members[data_name]
    found: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            blob = handle.read()
            if is_macho(blob):
                found[member.name] = blob
    return found


def verify_package(package: Path) -> None:
    members = package_macho_members(package)
    if not members:
        fail(f"{package}: no packaged Mach-O found")
    failures: list[str] = []
    for name, blob in sorted(members.items()):
        errors = verify_macho(blob, f"{package}:{name}")
        if errors:
            failures.extend(errors)
        else:
            print(f"signature ok: {name} ({len(macho_slices(blob, name))} slice(s))")
    if failures:
        fail("final packaged signature check failed:\n  " + "\n  ".join(dict.fromkeys(failures)))


# --- Host-runnable fixtures -------------------------------------------------

def _digest(hash_type: int, data: bytes) -> bytes:
    return digest_of(hash_type, data)


def _special_blob() -> bytes:
    payload = b"selftest-info-plist"
    return struct.pack(">II", 0xFADE0C00, 8 + len(payload)) + payload


def _build_code_directory(code: bytes, hash_type: int, special: bytes | None) -> bytes:
    hash_size = HASH_SIZE[hash_type]
    n_special = 1 if special is not None else 0
    n_code = (len(code) + PAGE - 1) // PAGE
    ident_offset = 48
    hash_offset = ident_offset + len(IDENT) + n_special * hash_size
    code_hashes = b"".join(_digest(hash_type, code[i * PAGE : (i + 1) * PAGE]) for i in range(n_code))
    special_hashes = _digest(hash_type, special) if special is not None else b""
    cd = bytearray(
        struct.pack(
            ">IIIIIIIII",
            CSMAGIC_CODEDIRECTORY,
            0,
            0x20100,
            0,
            hash_offset,
            ident_offset,
            n_special,
            n_code,
            len(code),
        )
    )
    cd += struct.pack(">BBBB", hash_size, hash_type, 0, 12)  # hashSize/hashType/platform/pageSize
    cd += struct.pack(">I", 0)  # spare2
    cd += struct.pack(">I", 0)  # scatterOffset (version 0x20100)
    cd += IDENT + special_hashes + code_hashes
    struct.pack_into(">I", cd, 4, len(cd))
    return bytes(cd)


def _superblob(entries: list[tuple[int, bytes]]) -> bytes:
    header_size = 12 + 8 * len(entries)
    offsets: list[int] = []
    cursor = header_size
    for _, blob in entries:
        offsets.append(cursor)
        cursor += len(blob)
    out = bytearray(struct.pack(">III", CSMAGIC_EMBEDDED_SIGNATURE, cursor, len(entries)))
    for (slot_type, _blob), offset in zip(entries, offsets):
        out += struct.pack(">II", slot_type, offset)
    for _, blob in entries:
        out += blob
    return bytes(out)


def _build_code(target: int, dataoff: int, datasize: int) -> bytes:
    code = bytearray(struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 1, 16, 0, 0))
    code += struct.pack("<IIII", LC_CODE_SIGNATURE, 16, dataoff, datasize)
    while len(code) < target:
        code.append((len(code) * 31 + 7) & 0xFF)
    return bytes(code)


def _build_signature(code: bytes, with_special: bool, hash_types: tuple[int, ...], dataoff: int) -> bytes:
    special = _special_blob() if with_special else None
    entries: list[tuple[int, bytes]] = []
    for index, hash_type in enumerate(hash_types):
        slot = CSSLOT_CODEDIRECTORY if index == 0 else CSSLOT_ALTERNATE_CODEDIRECTORIES + index - 1
        entries.append((slot, _build_code_directory(code, hash_type, special)))
    if special is not None:
        entries.append((CSSLOT_INFO_PLIST, special))
    return _superblob(entries)


def _signed_fixture(with_special: bool, hash_types: tuple[int, ...]) -> bytes:
    target = PAGE + 104  # one full code page plus a partial page
    signature_size = len(_build_signature(bytes(target), with_special, hash_types, target))
    code = _build_code(target, target, signature_size)
    signature = _build_signature(code, with_special, hash_types, target)
    if len(signature) != signature_size:
        fail("fixture builder produced an inconsistent signature size")
    return code + signature


def _unsigned_fixture() -> bytes:
    header = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 0, 0, 0, 0)
    return header + b"\x5a" * 256


def _fat_fixture() -> bytes:
    thin = _signed_fixture(False, (2,))
    slices = ((0x0100000C, 0, thin), (0x0100000C, 2, thin))
    header_size = 8 + 20 * len(slices)
    cursor = PAGE
    header = struct.pack(">II", FAT_MAGIC, len(slices))
    entries = b""
    body = b""
    for cputype, cpusubtype, blob in slices:
        entries += struct.pack(">IIIII", cputype, cpusubtype, cursor, len(blob), 12)
        padded = len(blob) + (-len(blob) % PAGE)
        body += blob + b"\x00" * (padded - len(blob))
        cursor += padded
    return header + entries + b"\x00" * (PAGE - header_size) + body


def expect_valid(label: str, data: bytes) -> None:
    errors = verify_macho(data, label)
    if errors:
        fail(f"self test {label}: expected a valid signature, got: {errors}")


def expect_invalid(label: str, data: bytes, needle: str) -> None:
    errors = verify_macho(data, label)
    if not errors:
        fail(f"self test {label}: expected rejection, but the signature validated")
    if not any(needle in error for error in errors):
        fail(f"self test {label}: expected {needle!r} in {errors}")


def self_test() -> None:
    full = _signed_fixture(True, (2, 1))
    expect_valid("thin fixture with special slot and two hash types", full)
    expect_valid("thin fixture with single SHA-256 directory", _signed_fixture(False, (2,)))
    expect_valid("universal fixture", _fat_fixture())

    expect_invalid("unsigned fixture", _unsigned_fixture(), "LC_CODE_SIGNATURE is absent")
    expect_invalid("signature dropped", full[: PAGE + 104], "truncated")

    tampered_code = bytearray(full)
    tampered_code[100] ^= 0xFF  # strip -x style mutation inside the hashed region
    expect_invalid("tampered code bytes", bytes(tampered_code), "hash mismatch")

    tampered_hash = bytearray(full)
    tampered_hash[len(full) - 8] ^= 0xFF  # corrupt the shared special-slot blob payload
    expect_invalid("tampered special-slot blob", bytes(tampered_hash), "hash mismatch")

    fat = _fat_fixture()
    fat_tampered = bytearray(fat)
    fat_tampered[PAGE + 64] ^= 0xFF  # first slice
    errors = verify_macho(bytes(fat_tampered), "universal tampered")
    if not errors or not any("[0]" in error and "hash mismatch" in error for error in errors):
        fail(f"self test universal tampered: expected slice [0] hash mismatch, got {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Final packaged Mach-O signature contract")
    parser.add_argument("--package", type=Path, action="append", default=[])
    args = parser.parse_args()
    self_test()
    print("PASS: signature-contract fixtures (valid thin/universal signatures accepted; unsigned, stale, tampered-code, tampered-hash, and truncated signatures rejected)")
    for package in args.package:
        verify_package(package)
        print(f"PASS: final packaged code signatures in {package}")


if __name__ == "__main__":
    main()
