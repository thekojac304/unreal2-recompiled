@echo off
rem Focused test of the Walking Speed wrapper tools\xrt\dev\native\walk_speed.c (see test.c). x64, developer runtime
rem headers (out\dev-init\runtime), owned stubs. Output: experiments\xrt\build\walk_speed\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\walk_speed
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /std:c11 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\walk_speed.exe" "%HERE%test.c" >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\walk_speed.exe"
