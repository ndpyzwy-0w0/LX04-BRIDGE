"""LX04 binary framing — must match app/.../Protocol.java."""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass

MAGIC = b"LXB1"
HEADER = struct.Struct("<4sBBHII")
PORT = 17890
VIDEO_PORT = 17891

HELLO = 0x01
HELLO_ACK = 0x02
AUDIO = 0x03
STATUS = 0x04
CONTROL = 0x05
PING = 0x06
PONG = 0x07
PLAY = 0x08
VIDEO = 0x09
VIDEO_ACK = 0x0A
FLAG_MUTED = 0x01
MAX_PAYLOAD = 256 * 1024


@dataclass
class Frame:
    type: int
    flags: int
    seq: int
    timestamp_ms: int
    payload: bytes

    @property
    def muted(self) -> bool:
        return bool(self.flags & FLAG_MUTED)

    def json(self) -> dict:
        if not self.payload:
            return {}
        return json.loads(self.payload.decode("utf-8"))


def encode(msg_type: int, payload: bytes = b"", flags: int = 0, seq: int = 0, timestamp_ms: int = 0) -> bytes:
    payload = payload or b""
    return HEADER.pack(MAGIC, msg_type, flags, seq & 0xFFFF, timestamp_ms & 0xFFFFFFFF, len(payload)) + payload


def encode_json(msg_type: int, obj: dict, flags: int = 0, seq: int = 0) -> bytes:
    return encode(msg_type, json.dumps(obj, ensure_ascii=False).encode("utf-8"), flags, seq)


def try_decode_header(header: bytes) -> tuple[int, int, int, int, int] | None:
    if len(header) < HEADER.size:
        return None
    magic, msg_type, flags, seq, timestamp_ms, length = HEADER.unpack(header)
    if magic != MAGIC or length < 0 or length > MAX_PAYLOAD:
        return None
    return msg_type, flags, seq, timestamp_ms, length
