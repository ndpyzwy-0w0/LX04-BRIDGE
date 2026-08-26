package com.lx04.pcbridge;

import android.os.SystemClock;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;

final class TcpVideoServer {
    interface Callback {
        void onVideo(byte[] jpeg);
    }

    private final Callback callback;
    private volatile boolean running;
    private ServerSocket server;
    private Thread acceptThread;
    private volatile Socket client;
    private final Object outLock = new Object();

    TcpVideoServer(Callback callback) {
        this.callback = callback;
    }

    synchronized void start() {
        if (running) {
            return;
        }
        running = true;
        acceptThread = new Thread(this::acceptLoop, "lx04-video");
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
    }

    private void acceptLoop() {
        try {
            server = new ServerSocket(Protocol.VIDEO_PORT, 1, InetAddress.getByName("0.0.0.0"));
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
            }
        } catch (Exception ignored) {
        }
    }

    private void handleClient(Socket socket) {
        try {
            socket.setTcpNoDelay(true);
            socket.setSoTimeout(0);
            try {
                socket.setReceiveBufferSize(24 * 1024);
                socket.setSendBufferSize(8 * 1024);
            } catch (Exception ignored) {
            }
            InputStream in = socket.getInputStream();
            OutputStream out = socket.getOutputStream();
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
                if (frame.type != Protocol.VIDEO || payload.length < 24) {
                    continue;
                }
                byte[] ack = Protocol.encode(Protocol.VIDEO_ACK, (byte) 0, frame.seq,
                        SystemClock.elapsedRealtime(), new byte[0]);
                synchronized (outLock) {
                    out.write(ack);
                    out.flush();
                }
                callback.onVideo(payload);
            }
        } catch (Exception ignored) {
        } finally {
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
