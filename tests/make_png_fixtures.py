from pathlib import Path
import struct
import zlib

out = Path(__file__).resolve().parents[1] / 'build/png-fixtures'
out.mkdir(parents=True, exist_ok=True)

def chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))

def png(name, width, height, depth, color_type, scanlines, extra=b''):
    head = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, color_type, 0, 0, 0))
    raw = head + extra + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b'')
    (out / name).write_bytes(raw)
    return raw

rgba = png('rgba.png', 2, 2, 8, 6, b'\0\xff\0\0\xff\0\xff\0\xff\0\0\0\xff\xff\x40\x80\xc0\x80')
png('rgb.png', 2, 1, 8, 2, b'\0\xff\0\0\0\xff\0')
png('gray.png', 2, 1, 8, 0, b'\0\0\xff')
png('gray-alpha.png', 2, 1, 8, 4, b'\0\x80\x40\xff\0')
png('gray1.png', 2, 1, 1, 0, b'\0\x40')
png('palette.png', 2, 1, 1, 3, b'\0\x40', chunk(b'PLTE', b'\xff\0\0\0\xff\0') + chunk(b'tRNS', b'\xff\x80'))
png('gray16.png', 2, 1, 16, 0, b'\0\0\0\xff\xff')
(out / 'truncated.png').write_bytes(rgba[:33])
(out / 'not-png.png').write_bytes(b'x' * 33)
wrong = bytearray(rgba); wrong[16:20] = struct.pack('>I', 4097)
(out / 'too-wide.png').write_bytes(wrong)
wrong = bytearray(rgba); wrong[20:24] = struct.pack('>I', 0)
(out / 'zero-height.png').write_bytes(wrong)
wrong = bytearray(rgba); wrong[16:24] = struct.pack('>II', 4096, 4096)
(out / 'pixel-budget.png').write_bytes(wrong)
# Valid container with corrupt compressed data reaches the platform codec failure path.
head = rgba[:33]
(out / 'bad-deflate.png').write_bytes(head + chunk(b'IDAT', b'not deflate') + chunk(b'IEND', b''))
print('PNG fixtures: RGBA/RGB/gray/alpha/palette/1-bit/16-bit and malformed/bounded cases')
