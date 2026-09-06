"""Small adapter for the bundled Resolve 20 DRP's Qt/protobuf containers.

This is an offline asset builder, not a general Resolve project-file editor.
Unknown archive members and the original generator remain byte-for-byte intact.
"""

import re
import struct
import zlib

import zstandard


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError("Invalid protobuf varint")


def varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("Negative varint")
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def fields(data: bytes) -> list[tuple[int, int, bytes]]:
    """Return number, wire type, and raw value (without its size prefix)."""
    result = []
    offset = 0
    while offset < len(data):
        key, offset = read_varint(data, offset)
        wire = key & 7
        if wire == 2:
            length, offset = read_varint(data, offset)
            end = offset + length
        elif wire == 0:
            _, end = read_varint(data, offset)
        elif wire in (1, 5):
            end = offset + (8 if wire == 1 else 4)
        else:
            raise ValueError(f"Unsupported protobuf wire type: {wire}")
        if end > len(data):
            raise ValueError("Truncated protobuf field")
        result.append((key >> 3, wire, data[offset:end]))
        offset = end
    return result


def encode_fields(values: list[tuple[int, int, bytes]]) -> bytes:
    return b"".join(
        varint(number << 3 | wire) + (varint(len(value)) if wire == 2 else b"") + value
        for number, wire, value in values
    )


def renamed_generator_fields(hex_blob: str, name: str) -> str:
    blob = bytes.fromhex(hex_blob)
    if blob[:4] != b"\0\0\0\2" or blob[8:13] != b"\x81\x28\xb5\x2f\xfd":
        raise ValueError("Unexpected generator FieldsBlob encoding")
    if struct.unpack(">I", blob[4:8])[0] != len(blob) - 8:
        raise ValueError("Generator FieldsBlob length mismatch")
    data = zstandard.ZstdDecompressor().decompress(blob[9:])
    outer = fields(data)
    if [n for n, w, v in outer].count(1) != 1:
        raise ValueError("Missing generator metadata")

    def rename(value: bytes) -> bytes:
        # Field 3 contains Edit-page PTZR overrides. New assets use Fusion
        # coordinates instead, so do not inherit the old title's Y offset.
        inner = [
            (n, w, name.encode() if n == 2 else v)
            for n, w, v in fields(value)
            if n != 3
        ]
        if not any(n == 2 and w == 2 for n, w, _ in inner):
            raise ValueError("Missing native generator name")
        return encode_fields(inner)

    # Keep generator type, frame rate and source duration unchanged.
    updated = encode_fields([(n, w, rename(v) if n == 1 else v) for n, w, v in outer])
    packed = b"\x81" + zstandard.ZstdCompressor(level=3).compress(updated)
    return (b"\0\0\0\2" + struct.pack(">I", len(packed)) + packed).hex()


def qt_string(text: str) -> bytes:
    data = text.encode("utf-16-be")
    return struct.pack(">I", len(data)) + data


def pack_composition(tools: str) -> str:
    # Match the native Qt QVariant map and nested Fusion compressed stream.
    header = (
        b"Composition { CurrentTime = 0, RenderRange = { 0, 299 }, "
        b"GlobalRange = { 0, 299 }, CurrentID = 1, HiQ = true, "
        b'Version = "DaVinci Resolve 20.2.1.0006", '
        b"Prefs = { Comp = { FrameFormat = { Rate = 60, Width = 1920, "
        b"Height = 1080, }, Unsorted = { GlobalEnd = 299 }, } }, "
        b"Compressed = true, }\0"
    )
    graph = tools.encode("utf-8")
    comp = header + struct.pack("<I", len(graph)) + zlib.compress(graph)
    qt_map = (
        struct.pack(">II", 1, 3)
        + qt_string("count")
        + struct.pack(">IBI", 2, 0, 1)
        + qt_string("0_name")
        + struct.pack(">IB", 10, 0)
        + qt_string("Composition 1")
        + qt_string("0_data")
        + struct.pack(">IBI", 12, 0, len(comp))
        + comp
    )
    return (struct.pack(">I", len(qt_map)) + zlib.compress(qt_map)).hex()


def unpack_composition(hex_blob: str) -> str:
    blob = bytes.fromhex(hex_blob)
    data = zlib.decompress(blob[4:])
    if len(data) != struct.unpack(">I", blob[:4])[0]:
        raise ValueError("Composition container length mismatch")
    marker = data.index(b"Composition {")
    end = data.index(b"\0", marker)
    graph = zlib.decompress(data[end + 5 :])
    if len(graph) != struct.unpack("<I", data[end + 1 : end + 5])[0]:
        raise ValueError("Fusion graph length mismatch")
    return graph.decode("utf-8").rstrip("\0")


def generator_blocks(xml: str) -> list[str]:
    return re.findall(
        r"  <Element>\s*<Sm2MpGenerator\b.*?</Sm2MpGenerator>\s*</Element>\r?\n",
        xml,
        re.DOTALL,
    )


def extract_composition(xml: str, name: str) -> str:
    matching = [
        block for block in generator_blocks(xml) if f"<Name>{name}</Name>" in block
    ]
    if len(matching) != 1:
        raise ValueError(
            f"Expected one generator named {name!r}, found {len(matching)}"
        )
    match = re.search(r"<CompositionBA>(.*?)</CompositionBA>", matching[0])
    if not match:
        raise ValueError("Generator has no composition")
    return unpack_composition(match[1])
