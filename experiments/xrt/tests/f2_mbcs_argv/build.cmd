@echo off
rem Build the F2 MBCS argv check into experiments\xrt\build\f2_mbcs_argv\ (run run_f2.py afterwards).
setlocal
cd /d "%~dp0"
set OUT=..\..\build\f2_mbcs_argv
set VCVARS="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
if "%1"=="ref" goto ref
if "%1"=="cand" goto cand
if not exist %OUT%\ref mkdir %OUT%\ref
if not exist %OUT%\ref932 mkdir %OUT%\ref932
if not exist %OUT%\cand mkdir %OUT%\cand
cmd /c "%~f0" ref || exit /b 1
cmd /c "%~f0" cand || exit /b 1
echo built: %OUT%
exit /b 0
:ref
call %VCVARS% x86 >nul || exit /b 1
cl /nologo /O1 /W4 /MT /D_CRT_SECURE_NO_WARNINGS /Fo%OUT%\ref\ /Fe%OUT%\ref_argv.exe ref_argv.c || exit /b 1
cl /nologo /O1 /W4 /MT /D_CRT_SECURE_NO_WARNINGS /Fo%OUT%\ref932\ /Fe%OUT%\ref_argv_acp932.exe ref_argv.c /link /MANIFEST:EMBED /MANIFESTINPUT:acp932.manifest || exit /b 1
exit /b 0
:cand
call %VCVARS% x64 >nul || exit /b 1
cl /nologo /O2 /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EVENT /DSTUB_EH /DSTUB_POW /I..\..\runtime /Fo%OUT%\cand\ /Fe%OUT%\cand_argv.exe cand_argv.c ..\..\runtime\xrt_fmt.c ..\..\runtime\hle_msvcr70.c ..\..\runtime\xrt_mem.c ..\common\xrt_test_stubs.c || exit /b 1
exit /b 0
