@echo off
rem F3 validation: builds the real runtime/hle_kernel32.c (same flags as build_xrt.cmd) + stubs + test, x64.
rem   build.cmd   -> experiments\xrt\build\f3_sandbox_guard\f3_test.exe
setlocal
cd /d "%~dp0\..\.."
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
set OUT=build\f3_sandbox_guard
if not exist %OUT% mkdir %OUT%
cl /nologo /c /O2 /Zi /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /Iruntime /Fo%OUT%\hle_kernel32.obj /Fd%OUT%\ runtime\hle_kernel32.c || exit /b 1
cl /nologo /c /O2 /Zi /W3 /wd4100 /D_CRT_SECURE_NO_WARNINGS /Iruntime /Fo%OUT%\ /Fd%OUT%\ /DSTUB_EVENT /DSTUB_JSTR /DSTUB_LOADLIB /DSTUB_K32EXTRA tests\f3_sandbox_guard\stubs.c tests\f3_sandbox_guard\f3_test.c tests\common\xrt_test_stubs.c || exit /b 1
link /nologo /DEBUG /OUT:%OUT%\f3_test.exe %OUT%\f3_test.obj %OUT%\stubs.obj %OUT%\xrt_test_stubs.obj %OUT%\hle_kernel32.obj || exit /b 1
echo built %OUT%\f3_test.exe
