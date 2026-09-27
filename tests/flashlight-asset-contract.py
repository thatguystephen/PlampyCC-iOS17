from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOTS = (
    ROOT / "assets/Plampy/Icon",
    ROOT / "layout/Library/Application Support/PlampyCC/Plampy/Icon",
)
NAMES = ("FlashlightOn.png", "FlashlightOff.png")


def fail(message: str) -> None:
    raise SystemExit(message)


def assert_true(value: bool, message: str) -> None:
    if not value:
        fail(message)


def rgba_alpha_bbox(path: Path) -> tuple[int, int, tuple[int, int, int, int]]:
    raw = path.read_bytes()
    assert_true(raw[:8] == b"\x89PNG\r\n\x1a\n", f"{path}: not a PNG")
    width = height = None
    bit_depth = color_type = interlace = None
    compressed = bytearray()
    offset = 8
    while offset < len(raw):
        size = struct.unpack(">I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        payload = raw[offset + 8 : offset + 8 + size]
        offset += 12 + size
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    assert_true(
        (width, height, bit_depth, color_type, interlace) == (80, 144, 8, 6, 0),
        f"{path}: expected non-interlaced 80x144 RGBA8 canvas",
    )
    assert width is not None and height is not None
    decoded = zlib.decompress(bytes(compressed))
    stride = width * 4
    rows: list[bytearray] = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = decoded[cursor]
        cursor += 1
        row = bytearray(decoded[cursor : cursor + stride])
        cursor += stride
        for i in range(stride):
            left = row[i - 4] if i >= 4 else 0
            above = previous[i]
            upper_left = previous[i - 4] if i >= 4 else 0
            if filter_type == 1:
                row[i] = (row[i] + left) & 0xFF
            elif filter_type == 2:
                row[i] = (row[i] + above) & 0xFF
            elif filter_type == 3:
                row[i] = (row[i] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
                row[i] = (row[i] + predictor) & 0xFF
            elif filter_type != 0:
                fail(f"{path}: unsupported PNG filter {filter_type}")
        rows.append(row)
        previous = row
    points = [
        (x, y)
        for y, row in enumerate(rows)
        for x in range(width)
        if row[x * 4 + 3] != 0
    ]
    assert_true(bool(points), f"{path}: normalized asset is fully transparent")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return width, height, (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


metrics: dict[str, tuple[int, int, tuple[int, int, int, int]]] = {}
for root in ASSET_ROOTS:
    for name in NAMES:
        path = root / name
        assert_true(path.is_file(), f"missing asset: {path}")
        metrics[str(path)] = rgba_alpha_bbox(path)
        _, _, bbox = metrics[str(path)]
        assert_true(bbox == (12, 32, 68, 112),
                    f"{path}: theme art geometry drift (expected original 56x80 content at (12,32)-(68,112), got {bbox})")

for name in NAMES:
    source = (ASSET_ROOTS[0] / name).read_bytes()
    staged = (ASSET_ROOTS[1] / name).read_bytes()
    assert_true(source == staged, f"source and staged {name} assets differ")

print("PASS: Flashlight on/off theme art keeps the original 80x144 canvas and 56x80 content geometry in both source and staged trees and remains byte-identical across packaging inputs; render sizing is owned by the SizedGlyphArt peer-canvas normalization, not pixel padding")
