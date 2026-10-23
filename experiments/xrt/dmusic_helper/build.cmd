@echo off
setlocal
cd /d "%~dp0\..\..\.."
set OUT=experiments\xrt\build\dmusic-ipc
if not exist "%OUT%\x86" mkdir "%OUT%\x86"
if not exist "%OUT%\x64" mkdir "%OUT%\x64"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
cl /nologo /O2 /W4 /D_CRT_SECURE_NO_WARNINGS /Fo"%OUT%\x86\\" /Fe"%OUT%\dmusic_helper.exe" experiments\xrt\dmusic_helper\main.c ole32.lib uuid.lib || exit /b 1
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W4 /D_CRT_SECURE_NO_WARNINGS /Fo"%OUT%\x64\\" /Fe"%OUT%\ipc_session.exe" experiments\xrt\tests\directmusic_boundary\ipc_session.c ole32.lib uuid.lib
