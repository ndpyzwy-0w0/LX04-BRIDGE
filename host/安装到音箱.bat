@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if defined ANDROID_HOME (
  set "SDK=%ANDROID_HOME%"
) else if defined ANDROID_SDK_ROOT (
  set "SDK=%ANDROID_SDK_ROOT%"
) else (
  set "SDK=%LOCALAPPDATA%\Android\Sdk"
)

if not exist "%SDK%\platform-tools\adb.exe" (
  echo 未找到 adb: %SDK%\platform-tools\adb.exe
  echo 请安装 Android SDK Platform-Tools，或把 adb 加入 PATH。
  exit /b 1
)

set "APK="
for %%F in ("%~dp0..\dist\LX04-PC-Bridge.apk") do set "APK=%%~fF"
if not defined APK (
  for %%F in ("%~dp0..\app\build\outputs\apk\debug\*.apk") do set "APK=%%~fF"
)
if not defined APK (
  for %%F in ("%~dp0..\app\build\outputs\apk\release\*.apk") do set "APK=%%~fF"
)
if not defined APK (
  echo 还没有 APK。请先运行 python build_apk.py，或在 Android Studio 里 Build APK。
  exit /b 1
)

"%SDK%\platform-tools\adb.exe" install -r -t "%APK%"
"%SDK%\platform-tools\adb.exe" shell pm grant com.lx04.pcbridge android.permission.RECORD_AUDIO
"%SDK%\platform-tools\adb.exe" shell am start-foreground-service -n com.lx04.pcbridge/.BridgeService
echo 安装完成。后台服务已启动，音箱上不必打开窗口。
