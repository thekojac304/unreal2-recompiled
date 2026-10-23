@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
set OUT=experiments\xrt\build\gui_boundary
set RT=experiments\xrt\runtime
set HERE=experiments\xrt\tests\gui_boundary
for %%d in (x86 x64 gen) do if not exist "%OUT%\%%d" mkdir "%OUT%\%%d"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
cl /nologo /c /O2 /GS- /W4 /Fo"%OUT%\x86\\" "%HERE%\guiprobe.c" || exit /b 1
rc /nologo /fo "%OUT%\x86\guiprobe.res" "%HERE%\guiprobe.rc" || exit /b 1
link /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:0x12000000 /DYNAMICBASE:NO /OUT:"%OUT%\guiprobe.dll" "%OUT%\x86\guiprobe.obj" "%OUT%\x86\guiprobe.res" user32.lib gdi32.lib kernel32.lib comctl32.lib || exit /b 1
cl /nologo /O2 /Fo"%OUT%\x86\\" /Fe"%OUT%\native.exe" tools\xrt\tests\ehprobe\native_host.c || exit /b 1
.venv\Scripts\python -I tools\xrt\xlift.py "%OUT%\guiprobe.dll" --out "%OUT%\gen" > "%OUT%\lift.txt" || exit /b 1
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O1 /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"%RT%" /Fo"%OUT%\x64\\" /Fe"%OUT%\translated.exe" "%HERE%\host.c" "%OUT%\gen\*.c" "%RT%\hle_kernel32.c" "%RT%\hle_misc.c" "%RT%\hle_gui.c" "%RT%\hle_msvcr70.c" "%RT%\xrt_cpu.c" "%RT%\xrt_diag.c" "%RT%\xrt_eh.c" "%RT%\xrt_events.c" "%RT%\xrt_fmt.c" "%RT%\xrt_loader.c" "%RT%\xrt_mem.c" "%RT%\xrt_thread.c" "%RT%\..\tests\common\xrt_test_stubs.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib /link /STACK:0x10000000 > "%OUT%\x64\build.txt" || (type "%OUT%\x64\build.txt" & exit /b 1)
.venv\Scripts\python -I "%HERE%\compare.py"
