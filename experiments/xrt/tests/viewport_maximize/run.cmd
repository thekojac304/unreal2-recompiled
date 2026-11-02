@echo off
rem Focused test of the developer runtime's windowed maximize (see test.c). x64; compiles the developer runtime's
rem viewport_window.inc (out\dev-init\runtime) with owned stubs. Shows a test window for about a second on the last
rem monitor. Output: experiments\xrt\build\viewport_maximize\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\viewport_maximize
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /wd4505 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\viewport_maximize.exe" "%HERE%test.c" user32.lib imm32.lib ole32.lib gdi32.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\viewport_maximize.exe"
