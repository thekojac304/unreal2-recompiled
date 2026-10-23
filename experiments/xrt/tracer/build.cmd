@echo off
rem Build the original-execution tracer (x86, it debugs the 32-bit UCC.exe).
setlocal
cd /d "%~dp0"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
if not exist ..\build\tracer mkdir ..\build\tracer
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /Fo..\build\tracer\ /Fe..\build\tracer\uctrace.exe uctrace.c user32.lib gdi32.lib dwmapi.lib uuid.lib || exit /b 1
