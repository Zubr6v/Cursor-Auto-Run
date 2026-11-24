"""Build a small Windows icon without third-party image libraries."""

from __future__ import annotations

import struct
from pathlib import Path


def _inside(x: int, y: int, size: int) -> bool:
    margin = max(1, int(size * 0.08))
    radius = max(2, int(size * 0.22))
    left, top = margin, margin
    right, bottom = size - margin - 1, size - margin - 1
    if x < left or y < top or x > right or y > bottom:
        return False
    corner_x = left + radius if x < left + radius else right - radius if x > right - radius else None
    corner_y = top + radius if y < top + radius else bottom - radius if y > bottom - radius else None
    if corner_x is None or corner_y is None:
        return True
    return (x - corner_x) ** 2 + (y - corner_y) ** 2 <= radius ** 2


def _triangle(x: int, y: int, size: int) -> bool:
    left = size * 0.38
    right = size * 0.68
    mid = (size - 1) / 2
    half = (x - left) / max(1, right - left) * (size * 0.24)
    return left <= x <= right and abs(y - mid) <= half


def _pixels(size: int) -> bytes:
    rows = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            if not _inside(x, y, size):
                rows += bytes((0, 0, 0, 0))
            elif _triangle(x, y, size):
                rows += bytes((20, 20, 20, 255))
            else:
                rows += bytes((236, 236, 236, 255))
    return bytes(rows)


def _and_mask(size: int) -> bytes:
    stride = ((size + 31) // 32) * 4
    return bytes(stride * size)


def _dib(size: int) -> bytes:
    pixels = _pixels(size)
    header = struct.pack(
        "<IiiHHIIiiII",
        40,
        size,
        size * 2,
        1,
        32,
        0,
        len(pixels),
        0,
        0,
        0,
        0,
    )
    return header + pixels + _and_mask(size)


def write_icon(path: Path) -> None:
    images = [(16, _dib(16)), (32, _dib(32)), (48, _dib(48))]
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    offset = 6 + 16 * len(images)
    payload = bytearray()
    for size, dib in images:
        stored = size if size < 256 else 0
        entries += struct.pack("<BBBBHHII", stored, stored, 0, 0, 1, 32, len(dib), offset)
        offset += len(dib)
        payload += dib
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + bytes(entries) + bytes(payload))


if __name__ == "__main__":
    destination = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    write_icon(destination)
    print(destination)
