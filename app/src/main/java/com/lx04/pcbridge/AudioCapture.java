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
    private String sourceName = "mic";
    private boolean lastOpenWasSilent;

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
        int[] rates = new int[] {48000, 44100, 16000};
        // XiaoAi often opens VOICE_RECOGNITION first and returns silence for normal speech.
        int[] sources = new int[] {
                MediaRecorder.AudioSource.UNPROCESSED,
                MediaRecorder.AudioSource.MIC,
                MediaRecorder.AudioSource.CAMCORDER,
                MediaRecorder.AudioSource.DEFAULT,
                MediaRecorder.AudioSource.VOICE_RECOGNITION
        };
        for (int source : sources) {
            for (int rate : rates) {
                record = tryOpen(source, rate, AudioFormat.CHANNEL_IN_MONO, true);
                if (record != null) {
                    return beginCapture(source, rate);
                }
                if (lastOpenWasSilent) {
                    break;
                }
            }
        }
        record = tryOpen(MediaRecorder.AudioSource.MIC, 48000, AudioFormat.CHANNEL_IN_MONO, false);
        if (record != null) {
            Log.w("lx04-mic", "all sources were digital-silent; keeping MIC anyway");
            return beginCapture(MediaRecorder.AudioSource.MIC, 48000);
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

    private boolean beginCapture(int source, int rate) {
        sampleRate = rate;
        channels = 1;
        sourceName = sourceLabel(source);
        running = true;
        thread = new Thread(this::loop, "lx04-mic");
        thread.start();
        return true;
    }

    private AudioRecord tryOpen(int source, int rate, int channelMask, boolean requireSignal) {
        lastOpenWasSilent = false;
        int min = AudioRecord.getMinBufferSize(rate, channelMask, AudioFormat.ENCODING_PCM_16BIT);
        if (min <= 0) {
            return null;
        }
        int buffer = Math.max(min, rate / 50 * 2 * 8);
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
                lastOpenWasSilent = false;
                return null;
            }
            if (requireSignal && !hasDigitalSignal(rec, rate)) {
                Log.w("lx04-mic", "skip silent source " + sourceLabel(source) + " @ " + rate);
                try {
                    rec.stop();
                } catch (Exception ignored) {
                }
                rec.release();
                lastOpenWasSilent = true;
                return null;
            }
            lastOpenWasSilent = false;
            return rec;
        } catch (Exception e) {
            lastOpenWasSilent = false;
            return null;
        }
    }

    private void loop() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO);
        AudioRecord rec = record;
        if (rec == null) {
            return;
        }
        int chunk = Math.max(sampleRate / 50, 320) * 2;
        byte[] buf = new byte[chunk];
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
            listener.onAudio(buf, n, peak(buf, n));
        }
    }

    private static boolean hasDigitalSignal(AudioRecord rec, int rate) {
        int chunk = Math.max(rate / 50, 320) * 2;
        byte[] buf = new byte[chunk];
        float maxPeak = 0f;
        long deadline = SystemClock.elapsedRealtime() + 220;
        while (SystemClock.elapsedRealtime() < deadline) {
            int n;
            try {
                n = rec.read(buf, 0, buf.length);
            } catch (Exception e) {
                return false;
            }
            if (n <= 0) {
                continue;
            }
            maxPeak = Math.max(maxPeak, peak(buf, n));
            if (maxPeak >= 0.004f) {
                return true;
            }
        }
        return maxPeak >= 0.002f;
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
            default:
                return "default";
        }
    }
}
