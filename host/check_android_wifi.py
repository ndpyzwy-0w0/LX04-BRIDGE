"""Run real WiFi/server Java classes on the JVM with small Android API stubs.

Requires an org.json jar and either javac or an Eclipse ECJ jar. No APK/device
installation. The TCP check briefly binds the bridge port on this PC.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-jar", required=True)
    parser.add_argument("--ecj-jar")
    parser.add_argument("--java", default="java")
    parser.add_argument("--javac", default="javac")
    parser.add_argument("--ip", required=True, help="A non-loopback IPv4 address of this PC")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    java_src = root / "app/src/main/java/com/lx04/pcbridge"
    stubs = {
        "android/content/Context.java": """package android.content;
public class Context { public Context getApplicationContext() { return this; } }""",
        "android/os/Build.java": """package android.os;
public class Build { public static final String MODEL = "Test";
public static class VERSION { public static final String RELEASE = "8.1"; } }""",
        "android/os/SystemClock.java": """package android.os;
public class SystemClock { public static long elapsedRealtime() {
return System.nanoTime() / 1000000L; } }""",
    }
    with tempfile.TemporaryDirectory(prefix="lx04-wifi-check-") as temp:
        output = Path(temp)
        sources = [java_src / (name + ".java")
                   for name in ("Protocol", "WifiPairServer", "TcpBridgeServer")]
        sources.append(root / "host/checks/WifiServerCheck.java")
        for name, text in stubs.items():
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            sources.append(path)
        compiler = ([args.java, "-jar", args.ecj_jar, "-1.8", "-proc:none"]
                    if args.ecj_jar else [args.javac, "-source", "8", "-target", "8"])
        subprocess.run(compiler + ["-encoding", "UTF-8", "-cp", args.json_jar,
                                  "-d", temp] + list(map(str, sources)), check=True)
        subprocess.run([args.java, "-cp", temp + os.pathsep + args.json_jar,
                        "com.lx04.pcbridge.WifiServerCheck", args.ip], check=True)


if __name__ == "__main__":
    main()
