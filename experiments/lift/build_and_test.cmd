@echo off
rem Lifting experiment: original Core.dll (x86) vs lifted C (x64). Requires the sandbox System copy.
setlocal
cd /d "%~dp0"
if not exist build mkdir build
set VCVARS="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
call %VCVARS% x86 >nul || exit /b 1
cl /nologo /O2 /W3 /Fobuild\ /Febuild\harness_original_x86.exe harness_original.c || exit /b 1
endlocal & setlocal
cd /d "%~dp0"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /wd4102 /fp:strict /Fobuild\ /Febuild\harness_lifted_x64.exe harness_lifted.c lifted_core.c || exit /b 1
set SYS=%~dp0..\..\sandbox\System
build\harness_original_x86.exe "%SYS%" > build\original_x86.txt || exit /b 1
build\harness_lifted_x64.exe "%SYS%\Core.dll" > build\lifted_x64.txt || exit /b 1
fc /b build\original_x86.txt build\lifted_x64.txt >nul && (echo IDENTICAL: original x86 vs lifted x64) || (echo DIFFERENT: original x86 vs lifted x64)
