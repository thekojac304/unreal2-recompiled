@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
set OUT=experiments\xrt\build\d3d8_boundary
set HERE=experiments\xrt\tests\d3d8_boundary
call :build x86 || exit /b 1
call :build x64 || exit /b 1
exit /b 0
:build
if not exist "%OUT%\%1" mkdir "%OUT%\%1"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" %1 >nul || exit /b 1
set MACHINE=%1
if "%1"=="x86" set MACHINE=X86
if "%1"=="x64" set MACHINE=X64
set BASE=0x12000000
if "%1"=="x64" set BASE=0x180000000
set ALIAS=
if "%1"=="x86" set ALIAS=/alternatename:__imp__Direct3DCreate8@4=__imp__Direct3DCreate8
lib /nologo /def:"%HERE%\d3d8.def" /machine:%MACHINE% /out:"%OUT%\%1\d3d8.lib" || exit /b 1
cl /nologo /c /O2 /GS- /W4 /Fo"%OUT%\%1\\" "%HERE%\probe.c" || exit /b 1
link /nologo /DLL /NOENTRY /NODEFAULTLIB %ALIAS% /BASE:%BASE% /DYNAMICBASE:NO /OUT:"%OUT%\%1\d3dprobe.dll" "%OUT%\%1\probe.obj" "%OUT%\%1\d3d8.lib" || exit /b 1
cl /nologo /O2 /W4 /Fo"%OUT%\%1\\" /Fe"%OUT%\%1\native.exe" "%HERE%\native.c" || exit /b 1
exit /b 0
