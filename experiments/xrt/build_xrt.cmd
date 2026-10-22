@echo off
rem Build the translated UCC.exe + Core.dll host program (Windows x64).
rem   build_xrt.cmd [lifted|runtime|link]   (default: all)
rem Lifted C must already be in gen\ (tools\xrt\xlift.py); it is machine-translated proprietary code: never commit it.
setlocal
cd /d "%~dp0"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
if not exist build\obj\gen mkdir build\obj\gen
if not exist build\obj\rt mkdir build\obj\rt
set WHAT=%1
if "%WHAT%"=="" set WHAT=all
if "%WHAT%"=="all" goto lifted
if "%WHAT%"=="lifted" goto lifted
if "%WHAT%"=="runtime" goto runtime
goto link
:lifted
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /MP /Iruntime /Fobuild\obj\gen\ gen\ucc\*.c gen\core\*.c || exit /b 1
if "%WHAT%"=="lifted" goto link
:runtime
cl /nologo /c /O2 /Zi /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /MP /Iruntime /Fobuild\obj\rt\ /Fdbuild\obj\rt\ runtime\*.c || exit /b 1
:link
link /nologo /DEBUG /STACK:0x10000000 /OUT:build\xrt_ucc.exe build\obj\gen\*.obj build\obj\rt\*.obj winmm.lib advapi32.lib bcrypt.lib || exit /b 1
echo built build\xrt_ucc.exe
