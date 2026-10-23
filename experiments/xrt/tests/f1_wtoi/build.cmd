@echo off
rem Build and run the F1 _wtoi check into experiments\xrt\build\f1_wtoi\.
setlocal
cd /d "%~dp0"
set OUT=..\..\build\f1_wtoi
set VCVARS="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
set DLL=..\..\..\..\sandbox_ref\hellofull\System\msvcr70.dll
if "%1"=="ref" goto ref
if "%1"=="cand" goto cand
if not exist %OUT%\ref mkdir %OUT%\ref
if not exist %OUT%\cand mkdir %OUT%\cand
cmd /c "%~f0" ref || exit /b 1
cmd /c "%~f0" cand || exit /b 1
%OUT%\ref_wtoi.exe %DLL% > %OUT%\ref.txt || exit /b 1
%OUT%\cand_wtoi.exe > %OUT%\cand.txt || exit /b 1
echo built and ran: %OUT%\ref.txt %OUT%\cand.txt
exit /b 0
:ref
call %VCVARS% x86 >nul || exit /b 1
cl /nologo /O1 /W4 /D_CRT_SECURE_NO_WARNINGS /Fo%OUT%\ref\ /Fe%OUT%\ref_wtoi.exe ref_wtoi.c || exit /b 1
exit /b 0
:cand
call %VCVARS% x64 >nul || exit /b 1
cl /nologo /O2 /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EVENT /DSTUB_EH /DSTUB_POW /DSTUB_JSTR /DSTUB_CRTDEPS /I..\..\runtime /Fo%OUT%\cand\ /Fe%OUT%\cand_wtoi.exe cand_wtoi.c ..\..\runtime\xrt_fmt.c ..\..\runtime\hle_msvcr70.c ..\..\runtime\xrt_mem.c ..\common\xrt_test_stubs.c || exit /b 1
exit /b 0
