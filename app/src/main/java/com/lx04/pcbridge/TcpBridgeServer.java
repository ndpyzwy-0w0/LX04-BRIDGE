package com.lx04.pcbridge;

import android.os.Build;
import android.os.SystemClock;

import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.atomic.AtomicInteger;

final class TcpBridgeServer {
    interface Callbacks {
        void prepareForClient();
        void onClient(boolean connected, String helloAckName);
        void onControl(JSONObject json);
    }

    private final BridgeState state;
    private final Callbacks callbacks;
    private final ArrayBlockingQueue<byte[]> outbound = new ArrayBlockingQueue<>(12);
    private final AtomicInteger seq = new AtomicInteger();
    private volatile boolean running;
    private ServerSocket server;
    private Thread acceptThread;
    private volatile Socket client;
    private volatile long dropped;

    TcpBridgeServer(BridgeState state, Callbacks callbacks) {
        this.state = state;
        this.callbacks = callbacks;
    }

    long getDropped() {
        return dropped;
    }

    synchronized void start() {
        if (running) {
            return;
        }
        running = true;
        dropped = 0;
        acceptThread = new Thread(this::acceptLoop, "lx04-tcp");
        acceptThread.start();
    }

    synchronized void stop() {
        running = false;
        closeQuietly(client);
        client = null;
        if (server != null) {
            try {
                server.close();
            } catch (Exception ignored) {
            }
            server = null;
        }
        if (acceptThread != null) {
            acceptThread.interrupt();
        }
        outbound.clear();
    }

    void sendAudio(byte[] pcm, int length, boolean muted) {
        if (client == null) {
            return;
        }
        byte[] payload = new byte[length];
        System.arraycopy(pcm, 0, payload, 0, length);
        enqueue(Protocol.AUDIO, muted ? Protocol.FLAG_MUTED : 0, payload);
    }

    void sendStatus() {
        try {
            JSONObject o = new JSONObject();
            o.put("usbConnected", state.usbConnected);
            o.put("usbAdb", state.usbAdb);
            o.put("recording", state.recording);
            o.put("muted", state.muted);
            o.put("level", state.level);
            o.put("frames", state.frames);
            o.put("dropped", dropped);
            o.put("sampleRate", state.sampleRate);
            o.put("channels", state.channels);
            enqueue(Protocol.STATUS, (byte) 0, o.toString().getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    private void enqueue(byte type, int flags, byte[] payload) {
        byte[] frame = Protocol.encode(type, (byte) flags, seq.incrementAndGet(),
                SystemClock.elapsedRealtime(), payload);
        if (!outbound.offer(frame)) {
            outbound.poll();
            outbound.offer(frame);
            dropped++;
            state.dropped = dropped;
        }
    }

    private void acceptLoop() {
        try {
            server = new ServerSocket(Protocol.PORT, 1, InetAddress.getByName("0.0.0.0"));
            server.setReuseAddress(true);
            while (running) {
                Socket socket;
                try {
                    socket = server.accept();
                } catch (Exception e) {
                    if (!running) {
                        break;
                    }
                    continue;
                }
                closeQuietly(client);
                client = socket;
                handleClient(socket);
                if (client == socket) {
                    client = null;
                }
                callbacks.onClient(false, "");
            }
        } catch (Exception ignored) {
        }
    }

    private void handleClient(Socket socket) {
        try {
            socket.setTcpNoDelay(true);
            socket.setSoTimeout(15000);
            callbacks.prepareForClient();
            OutputStream out = socket.getOutputStream();
            InputStream in = socket.getInputStream();
            out.write(Protocol.encode(Protocol.HELLO, (byte) 0, seq.incrementAndGet(),
                    SystemClock.elapsedRealtime(), helloPayload()));
            out.flush();
            callbacks.onClient(true, "");
            Thread reader = new Thread(() -> readLoop(in), "lx04-tcp-in");
            reader.start();
            long lastStatus = 0;
            while (running && client == socket && !socket.isClosed()) {
                byte[] frame = outbound.poll();
                if (frame != null) {
                    out.write(frame);
                } else {
                    Thread.sleep(4);
                }
                long now = SystemClock.elapsedRealtime();
                if (now - lastStatus > 250) {
                    lastStatus = now;
                    sendStatus();
                }
            }
            reader.interrupt();
        } catch (Exception ignored) {
        } finally {
            closeQuietly(socket);
        }
    }

    private void readLoop(InputStream in) {
        byte[] header = new byte[Protocol.HEADER_SIZE];
        try {
            while (running) {
                try {
                    if (!readFully(in, header)) {
                        break;
                    }
                } catch (SocketTimeoutException timeout) {
                    enqueue(Protocol.PING, 0, new byte[0]);
                    continue;
                }
                Protocol.Frame frame = Protocol.decodeHeader(header);
                if (frame == null) {
                    break;
                }
                byte[] payload = new byte[frame.payloadLength];
                if (frame.payloadLength > 0 && !readFully(in, payload)) {
                    break;
                }
                frame.payload = payload;
                dispatch(frame);
            }
        } catch (Exception ignored) {
        }
    }

    private void dispatch(Protocol.Frame frame) {
        try {
            if (frame.type == Protocol.PING) {
                enqueue(Protocol.PONG, 0, new byte[0]);
                return;
            }
            if (frame.type == Protocol.HELLO_ACK) {
                String name = "";
                if (frame.payload != null && frame.payload.length > 0) {
                    JSONObject o = new JSONObject(new String(frame.payload, StandardCharsets.UTF_8));
                    name = o.optString("name", o.optString("pc", ""));
                }
                callbacks.onClient(true, name);
                return;
            }
            if (frame.type == Protocol.CONTROL && frame.payload != null && frame.payload.length > 0) {
                callbacks.onControl(new JSONObject(new String(frame.payload, StandardCharsets.UTF_8)));
            }
        } catch (Exception ignored) {
        }
    }

    private byte[] helloPayload() {
        try {
            JSONObject o = new JSONObject();
            o.put("device", "LX04");
            o.put("model", Build.MODEL);
            o.put("android", Build.VERSION.RELEASE);
            o.put("sampleRate", state.sampleRate);
            o.put("channels", state.channels);
            o.put("audioSource", state.audioSource);
            o.put("apkVersion", state.apkVersion);
            o.put("bits", 16);
            o.put("encoding", "pcm_s16le");
            o.put("port", Protocol.PORT);
            return o.toString().getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "{}".getBytes(StandardCharsets.UTF_8);
        }
    }

    private static boolean readFully(InputStream in, byte[] dest) throws Exception {
        int off = 0;
        while (off < dest.length) {
            int n = in.read(dest, off, dest.length - off);
            if (n < 0) {
                return false;
            }
            off += n;
        }
        return true;
    }

    private static void closeQuietly(Socket socket) {
        if (socket == null) {
            return;
        }
        try {
            socket.close();
        } catch (Exception ignored) {
        }
    }
}
