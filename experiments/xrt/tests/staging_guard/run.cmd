@echo off
rem Focused test of the guard staging mode pool functions (see test.c). x64, links the developer
rem runtime's xrt_mem.c (out/dev-init/runtime). Output: experiments\xrt\build\staging_guard\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\staging_guard
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\staging_guard.exe" "%HERE%test.c" "%RT%\xrt_mem.c" >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\staging_guard.exe"
