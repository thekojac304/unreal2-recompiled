@echo off
rem Builds both harnesses of the differential instruction test into experiments\xrt\build\insn_diff\.
rem   native_x86.exe : 32-bit, executes the snippets on the CPU (native_run.asm + native_x86.c)
rem   lifted_x64.exe : 64-bit, runs the lifted snippets (generated id_lifted.c) on runtime\xrt_cpu.c + xrt_mem.c
rem gen.py must have written build\insn_diff\id_lifted.c first (run.py does both).
setlocal
set HERE=%~dp0
for %%I in ("%HERE%..\..\..\..") do set WS=%%~fI
set OUT=%WS%\experiments\xrt\build\insn_diff
set RT=%WS%\experiments\xrt\runtime
set VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%OUT%\obj32" mkdir "%OUT%\obj32"
if not exist "%OUT%\obj64" mkdir "%OUT%\obj64"

setlocal
call "%VCVARS%" x86 >nul || exit /b 1
ml /nologo /c /safeseh /Fo"%OUT%\obj32\native_run.obj" "%HERE%native_run.asm" || exit /b 1
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /I"%HERE%." /Fo"%OUT%\obj32\\" /Fe"%OUT%\native_x86.exe" "%HERE%native_x86.c" "%OUT%\obj32\native_run.obj" || exit /b 1
endlocal

setlocal
call "%VCVARS%" x64 >nul || exit /b 1
rem lifted code: same flags as experiments\xrt\build_xrt.cmd uses for gen\*.c
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /I"%RT%" /Fo"%OUT%\obj64\id_lifted.obj" "%OUT%\id_lifted.c" || exit /b 1
rem runtime parts: same flags as build_xrt.cmd uses for runtime\*.c
cl /nologo /c /O2 /fp:strict /W3 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /I"%HERE%." /Fo"%OUT%\obj64\\" "%RT%\xrt_cpu.c" "%RT%\xrt_mem.c" "%HERE%lifted_x64.c" || exit /b 1
link /nologo /OUT:"%OUT%\lifted_x64.exe" "%OUT%\obj64\id_lifted.obj" "%OUT%\obj64\xrt_cpu.obj" "%OUT%\obj64\xrt_mem.obj" "%OUT%\obj64\lifted_x64.obj" || exit /b 1
endlocal
echo built %OUT%\native_x86.exe and %OUT%\lifted_x64.exe
