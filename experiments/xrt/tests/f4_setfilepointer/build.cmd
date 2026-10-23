@echo off
rem Build and run the F4 checks. Products go to experiments\xrt\build\f4_setfilepointer\ (git-ignored).
rem The scratch files are sparse (no disk space allocated) and FILE_FLAG_DELETE_ON_CLOSE removes them.
setlocal
set HERE=%~dp0
set XRT=%HERE%..\..
set OUT=%XRT%\build\f4_setfilepointer
set VC="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
if not exist "%OUT%\x86" mkdir "%OUT%\x86"
if not exist "%OUT%\x64" mkdir "%OUT%\x64"
setlocal
call %VC% x86 >nul || exit /b 1
cl /nologo /W4 /O2 /Fo"%OUT%\x86\\" /Fe"%OUT%\x86\host_api.exe" "%HERE%host_api.c" || exit /b 1
endlocal
setlocal
call %VC% x64 >nul || exit /b 1
cl /nologo /W4 /O2 /Fo"%OUT%\x64\\" /Fe"%OUT%\x64\host_api.exe" "%HERE%host_api.c" || exit /b 1
cl /nologo /W4 /O2 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DSTUB_EVENT /DSTUB_JSTR /DSTUB_LOADLIB /DSTUB_K32EXTRA /I"%XRT%\runtime" /Fo"%OUT%\x64\\" /Fe"%OUT%\x64\adapter.exe" "%HERE%adapter.c" "%XRT%\runtime\hle_kernel32.c" "%HERE%..\common\xrt_test_stubs.c" winmm.lib advapi32.lib || exit /b 1
endlocal
"%OUT%\x86\host_api.exe" "%OUT%\scratch_x86.bin" || exit /b 1
"%OUT%\x64\host_api.exe" "%OUT%\scratch_x64.bin" || exit /b 1
"%OUT%\x64\adapter.exe" "%OUT%\scratch_adapter.bin" || exit /b 1
