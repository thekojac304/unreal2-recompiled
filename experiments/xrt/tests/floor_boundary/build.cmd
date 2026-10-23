@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
set HERE=experiments\xrt\tests\floor_boundary
set OUT=experiments\xrt\build\floor_boundary
if not exist %OUT%\native mkdir %OUT%\native
if not exist %OUT%\cand mkdir %OUT%\cand
if "%1"=="x64" goto x64
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
cl /nologo /O1 /fp:strict /W4 /D_CRT_SECURE_NO_WARNINGS /Fo%OUT%\native\ /Fe%OUT%\native.exe %HERE%\native.c || exit /b 1
if "%1"=="native" exit /b 0
cmd /d /c "%~f0" x64
exit /b %errorlevel%
:x64
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
set RT=experiments\xrt\runtime
cl /nologo /O2 /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EH /DSTUB_EVENT /DSTUB_JSTR /DSTUB_CRTDEPS /DSTUB_POW /I%RT% /Fo%OUT%\cand\ /Fe%OUT%\cand.exe %HERE%\cand.c %RT%\hle_msvcr70.c %RT%\xrt_cpu.c %RT%\xrt_fmt.c %RT%\xrt_mem.c experiments\xrt\tests\common\xrt_test_stubs.c bcrypt.lib
