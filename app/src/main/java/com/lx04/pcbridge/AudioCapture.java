package com.lx04.pcbridge;

import android.content.Context;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;

final class AudioCapture {
    interface Listener {
        void onAudio(byte[] pcm, int length, float peak);
    }

    private final Listener listener;
    private volatile boolean running;
    private Thread thread;
    private AudioRecord record;
    private int sampleRate = 48000;
    private int channels = 1;
    private int captureChannels = 1;
    private String sourceName = "mic";

    AudioCapture(Listener listener) {
        this.listener = listener;
    }

    int getSampleRate() {
        return sampleRate;
    }

    int getChannels() {
        return channels;
    }

    String getSourceName() {
        return sourceName;
    }

    synchronized boolean start() {
        stop();
        int[] sources = new int[] {
                MediaRecorder.AudioSource.MIC,
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                MediaRecorder.AudioSource.CAMCORDER,
                MediaRecorder.AudioSource.DEFAULT,
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                MediaRecorder.AudioSource.UNPROCESSED
        };
        int[] rates = new int[] {48000, 16000, 44100};
        int[] masks = new int[] {AudioFormat.CHANNEL_IN_MONO, AudioFormat.CHANNEL_IN_STEREO};
        for (int source : sources) {
            for (int rate : rates) {
                for (int mask : masks) {
                    record = tryOpen(source, rate, mask);
                    if (record != null) {
                        return beginCapture(source, rate, mask);
                    }
                }
            }
        }
        return false;
    }

    synchronized void stop() {
        running = false;
        if (thread != null) {
            thread.interrupt();
            try {
                thread.join(400);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            thread = null;
        }
        if (record != null) {
            try {
                record.stop();
            } catch (Exception ignored) {
            }
            record.release();
            record = null;
        }
    }

    private boolean beginCapture(int source, int rate, int mask) {
        sampleRate = rate;
        captureChannels = mask == AudioFormat.CHANNEL_IN_STEREO ? 2 : 1;
        channels = 1;
        sourceName = sourceLabel(source) + (captureChannels == 2 ? "-stereo" : "");
        running = true;
        thread = new Thread(this::loop, "lx04-mic");
        thread.start();
        Log.i("lx04-mic", "using " + sourceName + " @ " + rate);
        return true;
    }

    private AudioRecord tryOpen(int source, int rate, int channelMask) {
        int min = AudioRecord.getMinBufferSize(rate, channelMask, AudioFormat.ENCODING_PCM_16BIT);
        if (min <= 0) {
            return null;
        }
        int ch = channelMask == AudioFormat.CHANNEL_IN_STEREO ? 2 : 1;
        int buffer = min * 2;
        try {
            AudioRecord rec = new AudioRecord(source, rate, channelMask,
                    AudioFormat.ENCODING_PCM_16BIT, buffer);
            if (rec.getState() != AudioRecord.STATE_INITIALIZED) {
                rec.release();
                return null;
            }
            rec.startRecording();
            if (rec.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) {
                rec.release();
                return null;
            }
            if (!hasRealSignal(rec, rate, ch)) {
                Log.w("lx04-mic", "skip empty " + sourceLabel(source)
                        + (ch == 2 ? "-stereo" : "") + " @ " + rate);
                try {
                    rec.stop();
                } catch (Exception ignored) {
                }
                rec.release();
                return null;
            }
            try {
                rec.stop();
            } catch (Exception ignored) {
            }
            rec.release();
            AudioRecord live = new AudioRecord(source, rate, channelMask,
                    AudioFormat.ENCODING_PCM_16BIT, buffer);
            if (live.getState() != AudioRecord.STATE_INITIALIZED) {
                live.release();
                return null;
            }
            live.startRecording();
            if (live.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) {
                live.release();
                return null;
            }
            return live;
        } catch (Exception e) {
            return null;
        }
    }

    private void loop() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO);
        AudioRecord rec = record;
        if (rec == null) {
            return;
        }
        int frameBytes = Math.max(sampleRate / 100, 160) * 2 * captureChannels;
        byte[] buf = new byte[frameBytes];
        byte[] mono = captureChannels == 2 ? new byte[frameBytes / 2] : buf;
        while (running) {
            int n;
            try {
                n = rec.read(buf, 0, buf.length);
            } catch (Exception e) {
                break;
            }
            if (n <= 0) {
                continue;
            }
            int outLen = n;
            byte[] out = buf;
            if (captureChannels == 2) {
                outLen = mixToMono(buf, n, mono);
                out = mono;
            }
            listener.onAudio(out, outLen, peak(out, outLen));
        }
    }

    private static boolean hasRealSignal(AudioRecord rec, int rate, int ch) {
        int chunk = Math.max(rate / 100, 160) * 2 * ch;
        byte[] buf = new byte[chunk];
        long sumSq = 0;
        long zeros = 0;
        long samples = 0;
        int peak = 0;
        long deadline = SystemClock.elapsedRealtime() + 280;
        while (SystemClock.elapsedRealtime() < deadline) {
            int n;
            try {
                n = rec.read(buf, 0, buf.length);
            } catch (Exception e) {
                return false;
            }
            if (n <= 1) {
                continue;
            }
            for (int i = 0; i + 1 < n; i += 2) {
                int sample = (buf[i] & 0xFF) | (buf[i + 1] << 8);
                if (sample > 32767) {
                    sample -= 65536;
                }
                int abs = sample < 0 ? -sample : sample;
                if (abs > peak) {
                    peak = abs;
                }
                sumSq += (long) sample * sample;
                if (sample == 0) {
                    zeros++;
                }
                samples++;
            }
        }
        if (samples < 200) {
            return false;
        }
        float rms = (float) Math.sqrt(sumSq / (double) samples) / 32768f;
        float zeroFrac = zeros / (float) samples;
        boolean ok = rms >= 0.004f && zeroFrac < 0.35f;
        Log.i("lx04-mic", "probe rms=" + rms + " zero=" + zeroFrac + " peak=" + peak + " ok=" + ok);
        return ok;
    }

    private static int mixToMono(byte[] stereo, int length, byte[] mono) {
        int frames = length / 4;
        int out = 0;
        for (int i = 0; i < frames; i++) {
            int left = (stereo[i * 4] & 0xFF) | (stereo[i * 4 + 1] << 8);
            int right = (stereo[i * 4 + 2] & 0xFF) | (stereo[i * 4 + 3] << 8);
            if (left > 32767) {
                left -= 65536;
            }
            if (right > 32767) {
                right -= 65536;
            }
            int mixed = (left + right) / 2;
            mono[out] = (byte) (mixed & 0xFF);
            mono[out + 1] = (byte) ((mixed >> 8) & 0xFF);
            out += 2;
        }
        return out;
    }

    private static float peak(byte[] pcm, int length) {
        int max = 0;
        for (int i = 0; i + 1 < length; i += 2) {
            int sample = (pcm[i] & 0xFF) | (pcm[i + 1] << 8);
            if (sample > 32767) {
                sample -= 65536;
            }
            int abs = sample < 0 ? -sample : sample;
            if (abs > max) {
                max = abs;
            }
        }
        return max / 32768f;
    }

    static boolean hasMicPermission(Context context) {
        return context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }

    private static String sourceLabel(int source) {
        switch (source) {
            case MediaRecorder.AudioSource.MIC:
                return "mic";
            case MediaRecorder.AudioSource.UNPROCESSED:
                return "unprocessed";
            case MediaRecorder.AudioSource.CAMCORDER:
                return "camcorder";
            case MediaRecorder.AudioSource.VOICE_RECOGNITION:
                return "voice_recognition";
            case MediaRecorder.AudioSource.VOICE_COMMUNICATION:
                return "voice_communication";
            default:
                return "default";
        }
    }
}
