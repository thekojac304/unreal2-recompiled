@echo off
rem Focused test of the developer frame limiter (see test.c). x64; compiles tools\xrt\dev\dev_support.c (included by
rem test.c) against the developer runtime headers (out\dev-init\runtime) with owned stubs. Output: experiments\xrt\build\fps_cap\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\fps_cap
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /I"%HERE%..\..\..\..\tools\xrt\dev" /Fo"%OUT%\\" /Fe"%OUT%\fps_cap.exe" "%HERE%test.c" winmm.lib user32.lib dbghelp.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\fps_cap.exe"
