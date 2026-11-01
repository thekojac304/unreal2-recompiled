@echo off
rem Focused test of the developer background mode (see test.c). x64; compiles tools\xrt\dev\dev_support.c (included by
rem test.c) against the developer runtime headers (out\dev-init\runtime) with owned stubs. Run it while another
rem application owns the foreground. Output: experiments\xrt\build\bg_input\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\bg_input
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /I"%HERE%..\..\..\..\tools\xrt\dev" /Fo"%OUT%\\" /Fe"%OUT%\bg_input.exe" "%HERE%test.c" winmm.lib user32.lib dbghelp.lib dinput8.lib dxguid.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\bg_input.exe"
