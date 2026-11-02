@echo off
rem Owned reproduction of the DirectMusic helper exit on performance close/release (see test.c). x86 like the helper;
rem drives out\dev-init\build\dmusic_helper.exe (or %1) with a staging sandbox (System + Music from the snapshot).
rem Output: experiments\xrt\build\dmusic_heartbeat\  (about 30 s)
setlocal
set HERE=%~dp0
set WS=%HERE%..\..\..\..
set OUT=%HERE%..\..\build\dmusic_heartbeat
set HELPER=%~1
if "%HELPER%"=="" set HELPER=%WS%\out\dev-init\build\dmusic_helper.exe
set SB=%WS%\sandbox_cmp\dmusic-heartbeat
if not exist "%OUT%" mkdir "%OUT%"
if not exist "%SB%\System" mkdir "%SB%\System"
if not exist "%SB%\Music" mkdir "%SB%\Music"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /I"%WS%\out\dev-init\runtime" /Fo"%OUT%\\" /Fe"%OUT%\dmusic_heartbeat.exe" "%HERE%test.c" ole32.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\dmusic_heartbeat.exe" "%HELPER%" "%SB%"
