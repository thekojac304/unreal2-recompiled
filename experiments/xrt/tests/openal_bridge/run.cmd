@echo off
rem Focused test of the developer runtime's OpenAL 1.0 adapter (see test.c). x64, links the developer runtime's
rem hle_openal.c and xrt_mem.c (out/dev-init/runtime) and XAudio2 (muted). Output: experiments\xrt\build\openal_bridge\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\openal_bridge
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\openal_bridge.exe" "%HERE%test.c" "%RT%\hle_openal.c" "%RT%\xrt_mem.c" xaudio2.lib ole32.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\openal_bridge.exe"
