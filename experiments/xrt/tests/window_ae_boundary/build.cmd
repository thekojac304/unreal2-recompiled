@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
set OUT=experiments\xrt\build\window_ae_boundary_03
set RT=experiments\xrt\runtime
set HERE=experiments\xrt\tests\window_ae_boundary
if "%1"=="translated" goto translated
if exist "%OUT%" exit /b 2
for %%d in (x86 x64 gen) do mkdir "%OUT%\%%d"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
cl /nologo /c /O2 /GS- /W4 /Fo"%OUT%\x86\\" "%HERE%\aeprobe.c" || exit /b 1
link /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:0x12000000 /DYNAMICBASE:NO /OUT:"%OUT%\aeprobe.dll" "%OUT%\x86\aeprobe.obj" user32.lib kernel32.lib imm32.lib || exit /b 1
cl /nologo /O2 /W4 /Fo"%OUT%\x86\\" /Fe"%OUT%\native.exe" "%HERE%\native.c" user32.lib imm32.lib || exit /b 1
"%OUT%\native.exe" "%CD%\%OUT%\aeprobe.dll" positive > "%OUT%\native.txt" || exit /b 1
if "%1"=="native" exit /b 0
:translated
.venv\Scripts\python -I tools\xrt\xlift.py "%OUT%\aeprobe.dll" --out "%OUT%\gen" > "%OUT%\lift.txt" || exit /b 1
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O1 /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"%RT%" /Fo"%OUT%\x64\\" /Fe"%OUT%\translated.exe" "%HERE%\host.c" "%OUT%\gen\*.c" "%RT%\hle_kernel32.c" "%RT%\hle_misc.c" "%RT%\hle_msvcr70.c" "%RT%\xrt_cpu.c" "%RT%\xrt_diag.c" "%RT%\xrt_eh.c" "%RT%\xrt_events.c" "%RT%\xrt_fmt.c" "%RT%\xrt_loader.c" "%RT%\xrt_mem.c" "%RT%\xrt_thread.c" "%RT%\..\tests\common\xrt_test_stubs.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib imm32.lib /link /STACK:0x10000000 > "%OUT%\x64\build.txt" || (type "%OUT%\x64\build.txt" & exit /b 1)
.venv\Scripts\python -I "%HERE%\compare.py"
