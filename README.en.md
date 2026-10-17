# LX04 PC Bridge

[中文](README.md) · **English**

Turn a **Xiaomi LX04 touchscreen speaker** into a microphone, speaker and desktop status display for a Windows PC. Run the host application on your PC and the Android APK on the speaker, connected through USB, wireless ADB or LAN pairing.

## Features

### Two-way audio bridge

- **Speaker → PC microphone**: route captured audio into VB-CABLE, then select `CABLE Output` in your calling, meeting or voice-input application.
- **PC → speaker playback**: capture PC playback through Hi-Fi Cable and send it to the speaker.
- Mute the microphone and speaker independently, test speaker playback, view input levels and synchronize the PC master volume.
- USB and wireless ADB support hardware microphone capture and releasing the microphone from XiaoAi, depending on ROM capabilities and permissions. Direct LAN mode uses the app's audio capture instead.

### PC status display

The speaker's **800 × 480** display can show CPU / GPU utilization and available temperatures, memory, disks, network rates, uptime and connection status. Sensor availability depends on hardware, drivers and optional monitoring tools; unavailable readings are not replaced with invented values.

- Display up to **four disks** in a multi-disk card; tap to switch between disk IO activity and capacity usage.
- Show or hide the date, hours, minutes and seconds separately.
- Distinguish USB ADB, WiFi ADB and direct LAN connections in the status display.

### Customizable interface and synchronized styles

- Light and dark themes, editable card titles, primary metrics, secondary lines, font sizes and colors.
- Edit on the PC or long-press a card on the speaker; styles synchronize in both directions. The PC host includes a HUD preview.
- Upload up to **three background images** and adjust card and button opacity.
- Rotate the system display or flip only the bridge HUD for upside-down mounting. System rotation requires `WRITE_SETTINGS` permission.
- The PySide6 / QML host uses FluentWinUI3 styling and Lucide icons, with page widths and scrollbars adapted to the window layout.

### Screen mirroring and system notifications

- Mirror a selected PC monitor to the speaker, choose a quality preset and switch back to the status display.
- Forward supported Windows system notification titles, bodies and buttons. Tapping a button on the speaker attempts the corresponding action on the PC notification.
- Hide the bridge screen while keeping audio services running in the background, returning the display to the original XiaoAi interface.

### Connection and reliability improvements

Device refresh, connection setup and diagnostics run in the background to reduce UI blocking. Heartbeats and automatic retries improve connection recovery. Fixes cover partial-read timeouts, late callbacks after cancellation and old connections interfering with new sessions. Speaker-side fixes also improve client switching, disconnect cleanup and pairing-code invalidation.

## Three connection modes

### USB cable

Enable USB debugging, connect a data-capable cable and accept the debugging authorization on the speaker. Select USB in the host, refresh devices and connect. ADB supports APK installation, hardware microphone capture, releasing the microphone from XiaoAi and system controls.

### WiFi · wireless ADB

Connect over USB once, read the speaker's IP address and enable wireless ADB in the host, then connect using that IP. This keeps the ADB transport and supports the same bridge features as USB. After restarting the speaker, USB activation is normally required again.

### WiFi · direct LAN

Connect the PC and speaker to the same LAN. Enable WiFi pairing on the speaker, scan or enter its IP in the host, enter the **six-digit pairing code** shown on the speaker and connect. A successful pairing saves a token for subsequent connections without re-entering the code.

- No ADB dependency. Hardware microphone capture and releasing XiaoAi's microphone are unavailable; audio capture uses the app instead.
- Discovery broadcasts do not contain the pairing code. Codes expire when pairing ends, and repeated incorrect attempts trigger a cooldown.
- Use a trusted LAN. Pairing authentication does not provide transport encryption.
- Audio / control, mirroring and notifications use TCP **17890 / 17891 / 17892** respectively. Discovery and pairing use UDP **17893**.

## Requirements

- **PC**: 64-bit Windows 10 / 11.
- **Speaker**: LX04 running Android 8.1+ on firmware that permits third-party APK installation. Restricted stock firmware must meet that prerequisite first; this project does not provide firmware-flashing tools.
- **Microphone routing**: install official [VB-CABLE](https://vb-audio.com/Cable/).
- **PC playback on the speaker**: also install Hi-Fi Cable from the same official page. These serve different purposes; restart Windows as instructed after installation.
- **Initial USB / wireless ADB setup**: a data-capable Micro USB cable, working ADB drivers and USB debugging authorization.

The packaged host includes ADB and needs neither Android SDK nor Python to run. Install VB-Audio virtual audio devices separately. MSI Afterburner is optional for CPU temperature monitoring; installers for these tools are not bundled by this project.

## Quick start

1. Prepare the requirements above and connect the speaker to the PC over USB.
2. Run `host\adb\adb.exe devices -l` and confirm the device state is `device`. If it is `unauthorized`, accept debugging authorization on the speaker.
3. Run `host\install_apk.bat` to update the current APK, grant recording and system-settings permissions and start the background bridge service.
4. Double-click `启动上位机.bat` in the repository root, choose a connection mode and connect.
5. Select `CABLE Output` in applications that need the microphone. For PC playback, ensure Hi-Fi Cable is installed, then use the speaker test to check the playback path.

Installing an APK updates the application; it does not require reflashing the speaker's firmware. Update both the host and APK when an upgrade changes speaker-side functionality.

## Build and distribution

Run the host from source:

```powershell
python -m pip install -r host/requirements.txt
python host/pc_host.py
```

Build the host and APK. APK builds require JDK 17+, Android SDK and a working Gradle environment:

```powershell
python build_host_exe.py --no-commit
python build_apk.py --no-commit
```

- **Host**: `dist/LX04-PC-Bridge-Host/LX04-PC-Bridge-Host.exe`. Distribute the entire `LX04-PC-Bridge-Host` directory, including `_internal`, rather than the EXE alone.
- **Speaker APK**: `dist/LX04-PC-Bridge.apk`.
- Both build scripts attempt to create a local Git snapshot by default. The commands above use `--no-commit` to produce artifacts only.
- Maintainers can run `python pack_release.py --bump -m "release notes"` to build both applications and create a local version commit.

## Troubleshooting

- **USB device missing**: first check whether Windows detects the speaker, then check the ADB driver, debugging switch and authorization. A historical device entry does not mean it is currently connected; selecting MTP alone does not guarantee ADB availability.
- **Wireless ADB stops working after a restart**: reconnect USB and activate wireless ADB again.
- **Direct LAN pairing fails**: check network reachability, the pairing window, code validity and firewall access for the required ports.
- **Microphone is silent**: check recording permission, mute state and whether XiaoAi holds the microphone. Hardware capture support varies by ROM.
- **Missing temperatures**: some hardware does not expose readable sensors; unavailable readings are omitted.
- **Mirroring or notification compatibility**: these features depend on the Windows environment. See the changelog for known issues; interactive notifications are not supported for every application.

## Documentation and license

- [Changelog and known issues](CHANGELOG.md) (Chinese)
- [Communication protocol](protocol.md) (Chinese)
- [Preserved pre-merge project guide](README-UPSTREAM.md) (Chinese; historical reference, with current features and paths documented here)

Original code is licensed under [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for third-party notices and [host/assets/LUCIDE-LICENSE.txt](host/assets/LUCIDE-LICENSE.txt) for the Lucide icon license. VB-CABLE and Hi-Fi Cable are governed by VB-Audio's own licenses.

[切换到中文 / Switch to Chinese](README.md)
