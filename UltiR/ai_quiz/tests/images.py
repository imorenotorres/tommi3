"""Build small synthetic images for the tests. Standard library only."""

import struct
import zlib


def png(width: int, height: int, rgb: tuple[int, int, int] = (40, 90, 140)) -> bytes:
    """A valid PNG of one colour."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\x00" + bytes(rgb) * width
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height, 9))
            + chunk(b"IEND", b""))


def jpeg_start() -> bytes:
    """The first bytes of a JPEG file. Enough to be recognised as one; not a picture a browser can show."""
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64


SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
