@echo off
rem Focused test of the guard staging mode pool functions (see test.c), then the strict-versus-guard differential test
rem (see diff.c; round 4): two seeds, each run once per mode in its own process; the traces must be identical. x64,
rem links the developer runtime's xrt_mem.c (out/dev-init/runtime). Output: experiments\xrt\build\staging_guard\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\staging_guard
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\staging_guard.exe" "%HERE%test.c" "%RT%\xrt_mem.c" >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\staging_guard.exe" || exit /b 1
if not exist "%OUT%\diff" mkdir "%OUT%\diff"
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\diff\\" /Fe"%OUT%\staging_diff.exe" "%HERE%diff.c" "%RT%\xrt_mem.c" >"%OUT%\build-diff.txt" || (type "%OUT%\build-diff.txt" & exit /b 1)
for %%s in (1 2) do (
  "%OUT%\staging_diff.exe" strict 60000 %%s > "%OUT%\trace-strict-%%s.txt" || (echo strict run %%s failed & exit /b 1)
  "%OUT%\staging_diff.exe" guard 60000 %%s > "%OUT%\trace-guard-%%s.txt" || (echo guard run %%s failed & exit /b 1)
  fc /b "%OUT%\trace-strict-%%s.txt" "%OUT%\trace-guard-%%s.txt" >nul || (echo DIFFERENT: strict and guard traces of seed %%s & exit /b 1)
  echo seed %%s: strict and guard traces identical
)
echo PASS
