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
for %%F in ("%~dp0..\app\build\outputs\apk\debug\*.apk") do set "APK=%%~fF"
if not defined APK (
  for %%F in ("%~dp0..\app\build\outputs\apk\release\*.apk") do set "APK=%%~fF"
)
if not defined APK (
  echo 还没有编译出 APK。请用 Android Studio 打开本仓库，执行 Build ^> Build APK^(s^)。
  exit /b 1
)

"%SDK%\platform-tools\adb.exe" install -r -t "%APK%"
"%SDK%\platform-tools\adb.exe" shell pm grant com.lx04.pcbridge android.permission.RECORD_AUDIO
"%SDK%\platform-tools\adb.exe" shell am start -n com.lx04.pcbridge/.MainActivity
echo 安装完成。
