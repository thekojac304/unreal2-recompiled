@echo off
rem FGlobalMath sine table: hardware x87 (x86) vs the runtime's x87 model (x64), current source and, for comparison,
rem the previous xrt_cpu.c of a git revision (default HEAD~0's parent is not assumed: pass a revision, e.g. aae4923).
rem   build_and_run.cmd [old-revision]
rem Outputs to experiments\xrt\build\x87_sintab\ (git-ignored); compare with check_sintab.py.
setlocal
set HERE=%~dp0
set WS=%HERE%..\..\..\..
set OUT=%WS%\experiments\xrt\build\x87_sintab
set RT=%WS%\experiments\xrt\runtime
set VC="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
if not exist "%OUT%\x86" mkdir "%OUT%\x86"
if not exist "%OUT%\x64" mkdir "%OUT%\x64"
if not exist "%OUT%\old" mkdir "%OUT%\old"
setlocal
call %VC% x86 >nul || exit /b 1
cl /nologo /O2 /W3 /Fo"%OUT%\x86\\" /Fe"%OUT%\x86\hw_sintab.exe" "%HERE%hw_sintab.c" || exit /b 1
endlocal
setlocal
call %VC% x64 >nul || exit /b 1
cl /nologo /O2 /fp:strict /W3 /wd4100 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\x64\\" /Fe"%OUT%\x64\rt_sintab.exe" "%HERE%rt_sintab.c" "%RT%\xrt_cpu.c" || exit /b 1
if not "%1"=="" (
  git -C "%WS%" show %1:experiments/xrt/runtime/xrt_cpu.c > "%OUT%\old\xrt_cpu.c" || exit /b 1
  cl /nologo /O2 /fp:strict /W3 /wd4100 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\old\\" /Fe"%OUT%\old\rt_sintab_old.exe" "%HERE%rt_sintab.c" "%OUT%\old\xrt_cpu.c" || exit /b 1
)
endlocal
"%OUT%\x86\hw_sintab.exe" > "%OUT%\hw.txt" || exit /b 1
"%OUT%\x64\rt_sintab.exe" > "%OUT%\rt.txt" || exit /b 1
if not "%1"=="" "%OUT%\old\rt_sintab_old.exe" > "%OUT%\rt_old.txt"
echo ran: %OUT%
