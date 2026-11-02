@echo off
rem Measurement of the ALAudio ambient stop/play churn through the developer runtime's OpenAL adapter (see test.c).
rem x64, links hle_openal.c and xrt_mem.c (out\dev-init\runtime) and XAudio2 (muted); about 25 s.
rem Output: experiments\xrt\build\openal_churn\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\openal_churn
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\openal_churn.exe" "%HERE%test.c" "%RT%\hle_openal.c" "%RT%\xrt_mem.c" xaudio2.lib ole32.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\openal_churn.exe"
