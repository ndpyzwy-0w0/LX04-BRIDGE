@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

where adb >nul 2>nul
if %errorlevel%==0 (
  set "ADB=adb"
  goto :have_adb
)

if defined ANDROID_HOME (
  set "SDK=%ANDROID_HOME%"
) else if defined ANDROID_SDK_ROOT (
  set "SDK=%ANDROID_SDK_ROOT%"
) else (
  set "SDK=%LOCALAPPDATA%\Android\Sdk"
)

if not exist "%SDK%\platform-tools\adb.exe" (
  echo 未找到 adb。请安装 Android SDK Platform-Tools，或把 adb 加入 PATH。
  exit /b 1
)
set "ADB=%SDK%\platform-tools\adb.exe"

:have_adb
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

"%ADB%" install -r -t "%APK%"
"%ADB%" shell pm grant com.lx04.pcbridge android.permission.RECORD_AUDIO
"%ADB%" shell am start -n com.lx04.pcbridge/.MainActivity
echo 安装完成。
