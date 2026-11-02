@echo off
rem Focused test of the developer runtime's PostQuitMessage adapter (see test.c). x64; compiles the developer runtime's
rem message_pump.inc and window_transitions.inc (out\dev-init\runtime) with owned stubs. Output: experiments\xrt\build\quit_message\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\quit_message
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /wd4505 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\quit_message.exe" "%HERE%test.c" user32.lib imm32.lib ole32.lib gdi32.lib >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\quit_message.exe"
