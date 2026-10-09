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
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

final class TcpBridgeServer {
    interface Callbacks {
        void prepareForClient();
        void onClient(boolean connected, String helloAckName);
        void onControl(JSONObject json);
        void onPlay(byte[] pcm, boolean muted);
        void onFile(int slot, byte[] jpeg);

        /**
         * 局域网客户端的首帧鉴权（USB / adb forward 的回环客户端不会走到这里）。
         * 返回 true 放行。
         */
        boolean authorize(Socket socket, InputStream in, OutputStream out);
    }

    private final BridgeState state;
    private final Callbacks callbacks;
    private final ArrayBlockingQueue<byte[]> outbound = new ArrayBlockingQueue<>(6);
    private final ArrayBlockingQueue<byte[]> events = new ArrayBlockingQueue<>(8);
    private final AtomicInteger seq = new AtomicInteger();
    private volatile boolean running;
    private ServerSocket server;
    private Thread acceptThread;
    private volatile Socket client;
    private final Object clientLock = new Object();
    private volatile long dropped;
    private final AtomicInteger lanClients = new AtomicInteger();
    /** 局域网鉴权线程上限，避免被同网段的连接把线程数撑爆。 */
    private static final int MAX_LAN_CLIENTS = 2;

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
        synchronized (clientLock) {
            closeQuietly(client);
            client = null;
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
        outbound.clear();
        events.clear();
    }

    void sendAudio(byte[] pcm, int length, boolean muted) {
        if (client == null) {
            return;
        }
        byte[] payload = new byte[length];
        System.arraycopy(pcm, 0, payload, 0, length);
        enqueue(Protocol.AUDIO, muted ? Protocol.FLAG_MUTED : 0, payload);
    }

    void sendEvent(JSONObject json) {
        if (client == null || json == null) {
            return;
        }
        byte[] frame = Protocol.encode(Protocol.EVENT, (byte) 0, seq.incrementAndGet(),
                SystemClock.elapsedRealtime(), json.toString().getBytes(StandardCharsets.UTF_8));
        if (!events.offer(frame)) {
            events.poll();
            events.offer(frame);
        }
    }

    void sendStatus() {
        try {
            JSONObject o = new JSONObject();
            o.put("usbConnected", state.usbConnected);
            o.put("usbAdb", state.usbAdb);
            o.put("recording", state.recording);
            o.put("muted", state.micMuted);
            o.put("micMuted", state.micMuted);
            o.put("spkMuted", state.spkMuted);
            o.put("level", state.level);
            o.put("frames", state.frames);
            o.put("dropped", dropped);
            o.put("sampleRate", state.sampleRate);
            o.put("channels", state.channels);
            o.put("playLevel", state.playLevel);
            o.put("volume", BridgeService.musicVolume());
            o.put("lightTheme", state.lightTheme);
            o.put("sysRotation", state.sysRotation);
            o.put("uiHidden", state.uiHidden);
            o.put("screenMirror", state.screenMirror);
            o.put("toastOverlay", state.toastOverlay);
            o.put("clientIsLan", state.clientIsLan);
            o.put("wifiOn", state.wifiOn);
            o.put("wifiPairing", state.wifiPairing);
            o.put("wifiPaired", state.wifiPaired);
            o.put("wifiIp", state.wifiIp);
            o.put("wifiPort", Protocol.WIFI_PAIR_PORT);
            o.put("wifiPairCode", state.wifiPairCode);
            o.put("hudStyle", state.hudStyle.toStatusJson());
            JSONObject bg = new JSONObject();
            bg.put("sel", HudBackground.INSTANCE.selected());
            bg.put("alpha", HudBackground.INSTANCE.alpha());
            org.json.JSONArray used = new org.json.JSONArray();
            for (int i = 0; i < HudBackground.SLOTS; i++) {
                used.put(HudBackground.INSTANCE.used(i));
            }
            bg.put("used", used);
            o.put("hudBg", bg);
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
            ServerSocket bound = new ServerSocket();
            bound.setReuseAddress(true);
            bound.bind(new java.net.InetSocketAddress(InetAddress.getByName("0.0.0.0"), Protocol.PORT), 1);
            server = bound;
            if (!running) {
                closeQuietly(bound);
                return;
            }
            while (running) {
                Socket socket;
                try {
                    socket = bound.accept();
                } catch (Exception e) {
                    if (!running) {
                        break;
                    }
                    continue;
                }
                if (socket.getInetAddress().isLoopbackAddress()) {
                    // USB / adb forward：串行处理，保持原有语义。
                    // 注意不要把 client 先赋成 socket：handleClient 内部会先
                    // closeQuietly(client) 关掉"上一个客户端"，此时若它已经等于
                    // 本连接，就会把正在服务的 socket 自己关掉（表现为只收到
                    // HELLO、之后 STATUS 与控制全断）。
                    handleClient(socket);
                    continue;
                }
                // 局域网：鉴权最多可能耗掉几秒，放到独立线程去做，
                // 否则任意一台局域网主机连上来就能把 USB 客户端挡在门外。
                if (lanClients.incrementAndGet() > MAX_LAN_CLIENTS) {
                    lanClients.decrementAndGet();
                    closeQuietly(socket);
                    continue;
                }
                Thread worker = new Thread(() -> {
                    try {
                        handleClient(socket);
                    } finally {
                        lanClients.decrementAndGet();
                    }
                }, "lx04-tcp-lan");
                worker.setDaemon(true);
                worker.start();
            }
        } catch (Exception ignored) {
        } finally {
            // 绑定失败（端口被占等）时必须复位，否则 running 永远为 true，
            // 后续 start() 直接 return，桥接再也起不来且没有任何日志。
            running = false;
        }
    }

    private void handleClient(Socket socket) {
        try {
            socket.setTcpNoDelay(true);
            socket.setSoTimeout(15000);
            try {
                socket.setReceiveBufferSize(64 * 1024);
                socket.setSendBufferSize(64 * 1024);
            } catch (Exception ignored) {
            }
            callbacks.prepareForClient();
            OutputStream out = socket.getOutputStream();
            InputStream in = socket.getInputStream();
            out.write(Protocol.encode(Protocol.HELLO, (byte) 0, seq.incrementAndGet(),
                    SystemClock.elapsedRealtime(), helloPayload()));
            out.flush();
            // USB（adb forward）来的客户端地址是回环；局域网客户端必须先通过鉴权，
            // 通过之后才让它成为"当前客户端"。
            if (!socket.getInetAddress().isLoopbackAddress()
                    && !callbacks.authorize(socket, in, out)) {
                closeQuietly(socket);
                return;
            }
            synchronized (clientLock) {
                if (!running) {
                    return;
                }
                closeQuietly(client);
                client = socket;
                state.clientIsLan = !socket.getInetAddress().isLoopbackAddress();
                callbacks.onClient(true, "");
            }
            Thread reader = new Thread(() -> readLoop(socket, in), "lx04-tcp-in");
            reader.start();
            long lastStatus = 0;
            while (running && client == socket && !socket.isClosed()) {
                if (state.flushStatus) {
                    state.flushStatus = false;
                    lastStatus = SystemClock.elapsedRealtime();
                    sendStatus();
                }
                byte[] frame = events.poll();
                if (frame == null) {
                    try {
                        frame = outbound.poll(1, TimeUnit.MILLISECONDS);
                    } catch (InterruptedException e) {
                        break;
                    }
                }
                if (frame != null) {
                    out.write(frame);
                    if (frame.length >= Protocol.HEADER_SIZE && frame[4] == Protocol.EVENT) {
                        out.flush();
                    }
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
            disconnectClient(socket);
        }
    }

    private void readLoop(Socket socket, InputStream in) {
        // 用带进度的 Reader：读超时打断在帧中间时不会丢已读字节，避免帧错位。
        Protocol.Reader reader = new Protocol.Reader(in);
        try {
            while (running && client == socket) {
                Protocol.Frame frame;
                try {
                    frame = reader.next();
                } catch (SocketTimeoutException timeout) {
                    enqueue(Protocol.PING, 0, new byte[0]);
                    continue;
                }
                if (frame == null) {
                    break;
                }
                synchronized (clientLock) {
                    if (client == socket) {
                        dispatch(frame);
                    }
                }
            }
        } catch (Exception ignored) {
        } finally {
            // 读线程死了必须收尾：以前只退出循环，socket 不关、client 不清，
            // 音箱侧还以为"已连接"，实际已经收不到任何控制指令。
            disconnectClient(socket);
        }
    }

    private void disconnectClient(Socket socket) {
        synchronized (clientLock) {
            if (client == socket) {
                closeQuietly(socket);
                client = null;
                callbacks.onClient(false, "");
            }
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
                return;
            }
            if (frame.type == Protocol.FILE && frame.payload != null) {
                callbacks.onFile(frame.flags & 0xFF, frame.payload);
                return;
            }
            if (frame.type == Protocol.PLAY && frame.payload != null) {
                callbacks.onPlay(frame.payload, (frame.flags & Protocol.FLAG_MUTED) != 0);
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
            o.put("videoPort", Protocol.VIDEO_PORT);
            o.put("toastPort", Protocol.TOAST_PORT);
            return o.toString().getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "{}".getBytes(StandardCharsets.UTF_8);
        }
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

    private static void closeQuietly(ServerSocket socket) {
        if (socket == null) {
            return;
        }
        try {
            socket.close();
        } catch (Exception ignored) {
        }
    }
}
