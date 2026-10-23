@echo off
rem Build the translated host program (Windows x64): UCC.exe/Core.dll plus Engine, GlmLib, Editor, Window, UnrImp and Fire (loaded on demand).
rem   build_xrt.cmd [lifted|runtime|link]   (default: all)
rem Lifted C must already be in gen\ (tools\xrt\xlift.py); it is machine-translated proprietary code: never commit it.
setlocal
cd /d "%~dp0"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
if "%XRT_BUILD_DIR%"=="" set XRT_BUILD_DIR=build
if not exist "%XRT_BUILD_DIR%\obj\gen" mkdir "%XRT_BUILD_DIR%\obj\gen"
if not exist "%XRT_BUILD_DIR%\obj\rt" mkdir "%XRT_BUILD_DIR%\obj\rt"
set WHAT=%1
if "%WHAT%"=="" set WHAT=all
if "%WHAT%"=="all" goto lifted
if "%WHAT%"=="lifted" goto lifted
if "%WHAT%"=="runtime" goto runtime
goto link
:lifted
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /MP /Iruntime /Fo"%XRT_BUILD_DIR%\obj\gen\\" gen\ucc\*.c gen\core\*.c gen\engine\*.c gen\glmlib\*.c gen\editor\*.c gen\window\*.c gen\unrimp\*.c gen\fire\*.c gen\msvcr70\*.c || exit /b 1
if "%WHAT%"=="lifted" goto link
:runtime
cl /nologo /c /O2 /Zi /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /MP /Iruntime /Fo"%XRT_BUILD_DIR%\obj\rt\\" /Fd"%XRT_BUILD_DIR%\obj\rt\\" runtime\*.c || exit /b 1
:link
link /nologo /DEBUG /STACK:0x10000000 /OUT:"%XRT_BUILD_DIR%\xrt_ucc.exe" "%XRT_BUILD_DIR%\obj\gen\*.obj" "%XRT_BUILD_DIR%\obj\rt\*.obj" winmm.lib advapi32.lib ole32.lib bcrypt.lib || exit /b 1
echo built %XRT_BUILD_DIR%\xrt_ucc.exe
