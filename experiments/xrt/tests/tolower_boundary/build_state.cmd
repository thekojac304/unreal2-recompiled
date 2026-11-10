@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
set RT=experiments\xrt\runtime
set OUT=experiments\xrt\build\tolower_state
if not exist %OUT% mkdir %OUT%
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EH /DSTUB_EVENT /DSTUB_JSTR /DSTUB_CRTDEPS /DSTUB_POW /I%RT% /Fo%OUT%\ /Fe%OUT%\guest_state.exe experiments\xrt\tests\tolower_boundary\guest_state.c %RT%\hle_msvcr70.c %RT%\xrt_cpu.c %RT%\xrt_fmt.c %RT%\xrt_mem.c experiments\xrt\tests\common\xrt_test_stubs.c bcrypt.lib || exit /b 1
%OUT%\guest_state.exe
