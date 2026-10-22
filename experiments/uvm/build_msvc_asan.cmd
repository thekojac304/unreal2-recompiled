@echo off
rem Debug + AddressSanitizer build of uvm (x64).
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cd /d "%~dp0"
if not exist build\asan mkdir build\asan
cl /nologo /std:c++17 /Od /Zi /EHsc /W4 /fsanitize=address /Fobuild\asan\ /Fdbuild\asan\ /Febuild\asan\uvm.exe src\package.cpp src\vm.cpp src\natives_core.cpp src\main.cpp
for /f "delims=" %%d in ('where clang_rt.asan_dynamic-x86_64.dll 2^>nul') do copy /y "%%d" build\asan\ >nul
