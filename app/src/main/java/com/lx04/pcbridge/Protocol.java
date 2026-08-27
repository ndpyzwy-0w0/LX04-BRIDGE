package com.lx04.pcbridge;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

final class Protocol {
    static final String MAGIC = "LXB1";
    static final int HEADER_SIZE = 16;
    static final int PORT = 17890;
    static final int VIDEO_PORT = 17891;
    static final int TOAST_PORT = 17892;
    static final int MAX_PAYLOAD = 256 * 1024;

    static final byte HELLO = 0x01;
    static final byte HELLO_ACK = 0x02;
    static final byte AUDIO = 0x03;
    static final byte STATUS = 0x04;
    static final byte CONTROL = 0x05;
    static final byte PING = 0x06;
    static final byte PONG = 0x07;
    static final byte PLAY = 0x08;
    static final byte VIDEO = 0x09;
    static final byte VIDEO_ACK = 0x0A;
    static final byte FILE = 0x0B;
    static final byte EVENT = 0x0C;

    static final byte FLAG_MUTED = 0x01;

    static byte[] encode(byte type, byte flags, int seq, long timestampMs, byte[] payload) {
        if (payload == null) {
            payload = new byte[0];
        }
        ByteBuffer buf = ByteBuffer.allocate(HEADER_SIZE + payload.length);
        buf.order(ByteOrder.LITTLE_ENDIAN);
        buf.put(MAGIC.getBytes(StandardCharsets.US_ASCII));
        buf.put(type);
        buf.put(flags);
        buf.putShort((short) (seq & 0xFFFF));
        buf.putInt((int) (timestampMs & 0xFFFFFFFFL));
        buf.putInt(payload.length);
        buf.put(payload);
        return buf.array();
    }

    static Frame decodeHeader(byte[] header) {
        if (header == null || header.length < HEADER_SIZE) {
            return null;
        }
        ByteBuffer buf = ByteBuffer.wrap(header);
        buf.order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic = new byte[4];
        buf.get(magic);
        if (magic[0] != 'L' || magic[1] != 'X' || magic[2] != 'B' || magic[3] != '1') {
            return null;
        }
        Frame frame = new Frame();
        frame.type = buf.get();
        frame.flags = buf.get();
        frame.seq = buf.getShort() & 0xFFFF;
        frame.timestampMs = buf.getInt() & 0xFFFFFFFFL;
        frame.payloadLength = buf.getInt();
        if (frame.payloadLength < 0 || frame.payloadLength > MAX_PAYLOAD) {
            return null;
        }
        return frame;
    }

    static final class Frame {
        byte type;
        byte flags;
        int seq;
        long timestampMs;
        int payloadLength;
        byte[] payload;
    }

    private Protocol() {}
}
