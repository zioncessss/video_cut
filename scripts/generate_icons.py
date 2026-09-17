import struct
import zlib
from pathlib import Path

def create_png_icon(filepath: Path, width=256, height=256):
    # Create RGBA raw pixels: nice blue-purple gradient with white center
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # filter type None
        for x in range(width):
            # Gradient from blue to indigo
            r = int(37 + (99 - 37) * (x / width))
            g = int(99 + (102 - 99) * (y / height))
            b = int(235 + (241 - 235) * (x / width))
            a = 255
            # Draw a rounded rect / sparkle center
            dx = abs(x - width / 2)
            dy = abs(y - height / 2)
            if (dx < 30 and dy < 80) or (dx < 80 and dy < 30):
                r, g, b = 255, 255, 255
            raw_data.extend([r, g, b, a])

    compressed = zlib.compress(raw_data)
    
    png = bytearray(b'\x89PNG\r\n\x1a\n')
    
    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
    png.extend(struct.pack('>I', len(ihdr_data)))
    png.extend(b'IHDR')
    png.extend(ihdr_data)
    png.extend(struct.pack('>I', ihdr_crc))
    
    # IDAT
    idat_crc = zlib.crc32(b'IDAT' + compressed)
    png.extend(struct.pack('>I', len(compressed)))
    png.extend(b'IDAT')
    png.extend(compressed)
    png.extend(struct.pack('>I', idat_crc))
    
    # IEND
    iend_crc = zlib.crc32(b'IEND')
    png.extend(struct.pack('>I', 0))
    png.extend(b'IEND')
    png.extend(struct.pack('>I', iend_crc))
    
    filepath.write_bytes(png)
    return png

def create_ico(png_bytes: bytes, ico_path: Path):
    # ICO header: 0, 1 (icon), 1 (count)
    header = struct.pack('<HHH', 0, 1, 1)
    # Entry: width (0=256), height (0=256), colors (0), reserved (0), planes (1), bpp (32), size, offset
    entry = struct.pack('<BBBBHHII', 0, 0, 0, 0, 1, 32, len(png_bytes), 6 + 16)
    ico_path.write_bytes(header + entry + png_bytes)

def create_icns(png_bytes: bytes, icns_path: Path):
    # ICNS header: 'icns', total_length
    # Ostype for 256x256 PNG is 'ic08'
    chunk_type = b'ic08'
    chunk_len = 8 + len(png_bytes)
    total_len = 8 + chunk_len
    header = b'icns' + struct.pack('>I', total_len)
    chunk = chunk_type + struct.pack('>I', chunk_len) + png_bytes
    icns_path.write_bytes(header + chunk)

if __name__ == '__main__':
    res_dir = Path(__file__).resolve().parent.parent / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)
    png_bytes = create_png_icon(res_dir / "icon.png")
    create_ico(png_bytes, res_dir / "icon.ico")
    create_icns(png_bytes, res_dir / "icon.icns")
    print("Icons generated successfully in resources/")
