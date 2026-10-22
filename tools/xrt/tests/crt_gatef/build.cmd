@echo off
rem Build both sides of the gate-F CRT differential test into experiments\xrt\build\crt_gatef\.
rem   ref.exe  (x86): the real msvcr70.dll (loaded from a sandbox copy at run time)
rem   cand.exe (x64): the runtime's adapters (runtime\hle_msvcr70.c with xrt_fmt.c, xrt_mem.c, and the translated
rem                   _CIpow: xrt_msvcr70img.c + gen\msvcr70\pow_sse2.c from tools\xrt\lift_sse2.py)
rem Each side is built in its own cmd so the two vcvarsall environments do not mix.
setlocal
cd /d "%~dp0"
set OUT=..\..\..\..\experiments\xrt\build\crt_gatef
set RT=..\..\..\..\experiments\xrt\runtime
set GEN=..\..\..\..\experiments\xrt\gen
set STUBS=..\..\..\..\experiments\xrt\tests\common\xrt_test_stubs.c
set VCVARS="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
if "%1"=="x86" (
    call %VCVARS% x86 >nul || exit /b 1
    cl /nologo /O1 /W4 /wd4100 /D_CRT_SECURE_NO_WARNINGS /Fo%OUT%\ref\ /Fe%OUT%\ref.exe ref.c || exit /b 1
    exit /b 0
)
if "%1"=="x64" (
    call %VCVARS% x64 >nul || exit /b 1
    cl /nologo /O2 /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EH /DSTUB_EVENT /I%RT% /Fo%OUT%\cand\ /Fe%OUT%\cand.exe cand.c %RT%\hle_msvcr70.c %RT%\xrt_fmt.c %RT%\xrt_mem.c %RT%\xrt_msvcr70img.c %GEN%\msvcr70\pow_sse2.c %STUBS% bcrypt.lib || exit /b 1
    exit /b 0
)
if not exist %OUT%\ref mkdir %OUT%\ref
if not exist %OUT%\cand mkdir %OUT%\cand
cmd /c "%~f0" x86 || exit /b 1
cmd /c "%~f0" x64 || exit /b 1
echo built %OUT%\ref.exe %OUT%\cand.exe
