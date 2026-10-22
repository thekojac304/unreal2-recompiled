@echo off
rem Build uvm with MSVC. Usage: build_msvc.cmd [x64|x86|arm64]
setlocal
set ARCH=%1
if "%ARCH%"=="" set ARCH=x64
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" %ARCH% >nul || exit /b 1
cd /d "%~dp0"
if not exist build\%ARCH% mkdir build\%ARCH%
cl /nologo /std:c++17 /O2 /EHsc /W4 /permissive- /Fobuild\%ARCH%\ /Febuild\%ARCH%\uvm.exe src\package.cpp src\vm.cpp src\natives_core.cpp src\main.cpp
