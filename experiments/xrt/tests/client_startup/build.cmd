@echo off
setlocal
set HERE=%~dp0
set XRT=%HERE%..\..
set OUT=%XRT%\build\client_startup
set VC="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
if not exist "%OUT%\x86" mkdir "%OUT%\x86"
if not exist "%OUT%\x64" mkdir "%OUT%\x64"
call %VC% x86 >nul || exit /b 1
cl /nologo /W4 /O2 /Fo"%OUT%\x86\\" /Fe"%OUT%\x86\native.exe" "%HERE%native.c" /link /BASE:0x10900000 /DYNAMICBASE:NO || exit /b 1
"%OUT%\x86\native.exe" "%HERE%..\..\..\..\sandbox_cmp\level\System\msvcr70.dll" || exit /b 1
cl /nologo /W4 /O2 /DORIGINAL /Fo"%OUT%\x86\\" /Fe"%OUT%\x86\memory.exe" "%HERE%memory.c" || exit /b 1
"%OUT%\x86\memory.exe" || exit /b 1
rem Build the HAL-availability diagnostic separately from the adapter regressions. Run it explicitly;
rem exit 1 is the currently observed original startup blocker, not a passing graphics test.
cl /nologo /W4 /O2 /Fo"%OUT%\x86\\" /Fe"%OUT%\x86\graphics_boundary.exe" "%HERE%graphics_boundary.c" user32.lib || exit /b 1
call %VC% x64 >nul || exit /b 1
cl /nologo /W4 /O2 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EVENT /DSTUB_JSTR /DSTUB_LOADLIB /DSTUB_K32EXTRA /I"%XRT%\runtime" /Fo"%OUT%\x64\\" /Fe"%OUT%\x64\adapter.exe" "%HERE%adapter.c" "%XRT%\runtime\hle_kernel32.c" "%XRT%\runtime\hle_misc.c" "%HERE%..\common\xrt_test_stubs.c" winmm.lib advapi32.lib ole32.lib user32.lib || exit /b 1
"%OUT%\x64\adapter.exe" || exit /b 1
cl /nologo /W4 /O2 /D_CRT_SECURE_NO_WARNINGS /I"%XRT%\runtime" /Fo"%OUT%\x64\\" /Fe"%OUT%\x64\memory.exe" "%HERE%memory.c" "%XRT%\runtime\xrt_mem.c" || exit /b 1
"%OUT%\x64\memory.exe" || exit /b 1
