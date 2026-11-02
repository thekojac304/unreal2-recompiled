@echo off
rem Focused test of the borderless fullscreen compositor (see test.c) on the pinned x64 DXVK D3D8/D3D9 pair.
rem x64; compiles out\dev-init\runtime\d3d8_borderless.inc with owned stubs. Output: experiments\xrt\build\borderless_composite\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\borderless_composite
if not exist "%OUT%" mkdir "%OUT%"
set XRT_D3D8_DIR=%HERE%..\..\..\..\third_party\graphics\dxvk-v3.1.1\dxvk-3.1.1\x64
for %%I in ("%XRT_D3D8_DIR%") do set XRT_D3D8_DIR=%%~fI
set DXVK_LOG_LEVEL=none
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /wd4505 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\borderless_composite.exe" "%HERE%test.c" user32.lib ole32.lib dinput8.lib dxguid.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\borderless_composite.exe"
