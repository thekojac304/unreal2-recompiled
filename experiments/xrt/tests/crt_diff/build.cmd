@echo off
rem Build both sides of the msvcr70 differential test into experiments\xrt\build\crt_diff\.
rem   ref.exe  (x86): calls the real msvcr70.dll (loaded from a sandbox copy at run time)
rem   cand.exe (x64): calls the runtime's adapters (runtime\xrt_fmt.c, hle_msvcr70.c, xrt_mem.c)
rem Each side is built in its own cmd so the two vcvarsall environments do not mix (no labels: LF file).
setlocal
cd /d "%~dp0"
set OUT=..\..\build\crt_diff
set VCVARS="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
if "%1"=="x86" (
    call %VCVARS% x86 >nul || exit /b 1
    cl /nologo /O1 /W4 /wd4100 /D_CRT_SECURE_NO_WARNINGS /Fo%OUT%\ref\ /Fe%OUT%\ref.exe ref.c || exit /b 1
    exit /b 0
)
if "%1"=="x64" (
    call %VCVARS% x64 >nul || exit /b 1
    cl /nologo /O2 /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /I..\..\runtime /Fo%OUT%\cand\ /Fe%OUT%\cand.exe cand.c ..\..\runtime\xrt_fmt.c ..\..\runtime\hle_msvcr70.c ..\..\runtime\xrt_mem.c /DSTUB_EH ..\common\xrt_test_stubs.c || exit /b 1
    exit /b 0
)
if not exist %OUT%\ref mkdir %OUT%\ref
if not exist %OUT%\cand mkdir %OUT%\cand
cmd /c "%~f0" x86 || exit /b 1
cmd /c "%~f0" x64 || exit /b 1
echo built %OUT%\ref.exe %OUT%\cand.exe
