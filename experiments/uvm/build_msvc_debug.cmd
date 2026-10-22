@echo off
rem Debug build of uvm (x64) with symbolic crash traces.
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cd /d "%~dp0"
if not exist build\debug mkdir build\debug
cl /nologo /std:c++17 /Od /Zi /EHsc /W4 /MDd /DUVM_CRASH_TRACE /Fobuild\debug\ /Fdbuild\debug\ /Febuild\debug\uvm.exe src\package.cpp src\vm.cpp src\natives_core.cpp src\main.cpp /link /DEBUG
