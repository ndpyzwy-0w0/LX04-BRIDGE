package com.lx04.pcbridge;

import android.os.SystemClock;

import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

final class TcpToastServer {
    interface Callback {
        void onControl(JSONObject json);
    }

    private final Callback callback;
    private final AtomicInteger seq = new AtomicInteger();
    private final Object outLock = new Object();
    private volatile boolean running;
    private ServerSocket server;
    private Thread acceptThread;
    private volatile Socket client;
    private volatile OutputStream out;

    TcpToastServer(Callback callback) {
        this.callback = callback;
    }

    synchronized void start() {
        if (running) {
            return;
        }
        running = true;
        acceptThread = new Thread(this::acceptLoop, "lx04-toast");
        acceptThread.start();
    }

    synchronized void stop() {
        running = false;
        closeQuietly(client);
        client = null;
        synchronized (outLock) {
            out = null;
        }
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
    }

    boolean connected() {
        return client != null && out != null;
    }

    boolean sendEvent(JSONObject json) {
        if (json == null) {
            return false;
        }
        byte[] payload = json.toString().getBytes(StandardCharsets.UTF_8);
        byte[] frame = Protocol.encode(Protocol.EVENT, (byte) 0, seq.incrementAndGet(),
                SystemClock.elapsedRealtime(), payload);
        try {
            synchronized (outLock) {
                OutputStream stream = out;
                if (stream == null) {
                    return false;
                }
                stream.write(frame);
                stream.flush();
            }
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    private void acceptLoop() {
        try {
            server = new ServerSocket(Protocol.TOAST_PORT, 1, InetAddress.getByName("0.0.0.0"));
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
                synchronized (outLock) {
                    out = null;
                }
            }
        } catch (Exception ignored) {
        }
    }

    private void handleClient(Socket socket) {
        try {
            socket.setTcpNoDelay(true);
            socket.setSoTimeout(0);
            try {
                socket.setReceiveBufferSize(8 * 1024);
                socket.setSendBufferSize(8 * 1024);
            } catch (Exception ignored) {
            }
            InputStream in = socket.getInputStream();
            OutputStream stream = socket.getOutputStream();
            synchronized (outLock) {
                out = stream;
            }
            byte[] header = new byte[Protocol.HEADER_SIZE];
            while (running && client == socket && !socket.isClosed()) {
                if (!readFully(in, header)) {
                    break;
                }
                Protocol.Frame frame = Protocol.decodeHeader(header);
                if (frame == null) {
                    break;
                }
                byte[] payload = new byte[frame.payloadLength];
                if (frame.payloadLength > 0 && !readFully(in, payload)) {
                    break;
                }
                if (frame.type == Protocol.PING) {
                    byte[] pong = Protocol.encode(Protocol.PONG, (byte) 0, frame.seq,
                            SystemClock.elapsedRealtime(), new byte[0]);
                    synchronized (outLock) {
                        if (out != null) {
                            out.write(pong);
                            out.flush();
                        }
                    }
                    continue;
                }
                if (frame.type != Protocol.CONTROL || payload.length == 0) {
                    continue;
                }
                try {
                    callback.onControl(new JSONObject(new String(payload, StandardCharsets.UTF_8)));
                } catch (Exception ignored) {
                }
            }
        } catch (Exception ignored) {
        } finally {
            synchronized (outLock) {
                if (client == socket) {
                    out = null;
                }
            }
            closeQuietly(socket);
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
