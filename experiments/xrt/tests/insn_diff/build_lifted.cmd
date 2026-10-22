@echo off
rem Rebuilds only the lifted harness from another generated C file (used by mutation_check.py).
rem   build_lifted.cmd <lifted .c> <output .exe>      (build.cmd must have run once: it builds obj64\*.obj)
setlocal
set HERE=%~dp0
for %%I in ("%HERE%..\..\..\..") do set WS=%%~fI
set OUT=%WS%\experiments\xrt\build\insn_diff
set RT=%WS%\experiments\xrt\runtime
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /I"%RT%" /Fo"%~dpn2.obj" "%~1" >nul || exit /b 1
link /nologo /OUT:"%~2" "%~dpn2.obj" "%OUT%\obj64\xrt_cpu.obj" "%OUT%\obj64\xrt_mem.obj" "%OUT%\obj64\lifted_x64.obj" || exit /b 1
