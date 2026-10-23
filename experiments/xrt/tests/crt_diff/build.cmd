@echo off
rem Build both sides of the msvcr70 differential test into experiments\xrt\build\crt_diff\.
rem   ref.exe  (x86): calls the real msvcr70.dll (loaded from a sandbox copy at run time)
rem   cand.exe (x64): calls the runtime's adapters (runtime\xrt_fmt.c, hle_msvcr70.c, xrt_mem.c, with hle_kernel32.c
rem                   for its handle table and sandbox guard and xrt_msvcr70img.c for the DLL's tables; the translated
rem                   _CIpow core gen\msvcr70\pow_sse2.c comes from build_xrt.cmd and is linked, never committed)
rem Each side is built in its own cmd so the two vcvarsall environments do not mix (no labels: LF file). The
rem outputs are deleted first and checked afterwards, so a failed compile or link can never leave an old exe behind.
setlocal
cd /d "%~dp0"
set OUT=..\..\build\crt_diff
if not "%XRT_CRT_BUILD_DIR%"=="" set OUT=%XRT_CRT_BUILD_DIR%
set VCVARS="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
set R=..\..\runtime
if "%1"=="x86" (
    call %VCVARS% x86 >nul || exit /b 1
    cl /nologo /O1 /W4 /wd4100 /D_CRT_SECURE_NO_WARNINGS /Fo%OUT%\ref\ /Fe%OUT%\ref.exe ref.c || exit /b 1
    exit /b 0
)
if "%1"=="x64" (
    call %VCVARS% x64 >nul || exit /b 1
    cl /nologo /O2 /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EH /DSTUB_JSTR /DSTUB_LOADLIB /DSTUB_K32DEPS /I%R% /Fo%OUT%\cand\ /Fe%OUT%\cand.exe cand.c %R%\xrt_fmt.c %R%\hle_msvcr70.c %R%\xrt_mem.c %R%\hle_kernel32.c %R%\xrt_msvcr70img.c ..\..\gen\msvcr70\pow_sse2.c ..\common\xrt_test_stubs.c bcrypt.lib winmm.lib advapi32.lib || exit /b 1
    exit /b 0
)
if not exist ..\..\gen\msvcr70\pow_sse2.c (
    echo missing experiments\xrt\gen\msvcr70\pow_sse2.c: run experiments\xrt\build_xrt.cmd first
    exit /b 1
)
if not exist %OUT%\ref mkdir %OUT%\ref
if not exist %OUT%\cand mkdir %OUT%\cand
if exist %OUT%\ref.exe del %OUT%\ref.exe
if exist %OUT%\cand.exe del %OUT%\cand.exe
if exist %OUT%\ref.exe (
    echo BUILD FAILED: cannot delete the old ref.exe - is it running?
    exit /b 1
)
if exist %OUT%\cand.exe (
    echo BUILD FAILED: cannot delete the old cand.exe - is it running?
    exit /b 1
)
cmd /c "%~f0" x86 || exit /b 1
cmd /c "%~f0" x64 || exit /b 1
if not exist %OUT%\ref.exe (
    echo BUILD FAILED: ref.exe
    exit /b 1
)
if not exist %OUT%\cand.exe (
    echo BUILD FAILED: cand.exe
    exit /b 1
)
echo built %OUT%\ref.exe %OUT%\cand.exe
exit /b 0
