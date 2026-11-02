@echo off
rem Owned fragmentation test of the guest VirtualAlloc pool and guest heap (see test.c), one fresh process per phase.
rem x64, links the developer runtime's xrt_mem.c (out/dev-init/runtime). With "reference", also builds the test against
rem the round-4 xrt_mem.c (out/dev-init-savepoints/perf-r4d-20261102/runtime) to show which phases the old allocator fails
rem (informational; the old allocator is expected to die "bounded client pool exhausted").
rem Output: experiments\xrt\build\pool_fragmentation\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OLD=%HERE%..\..\..\..\out\dev-init-savepoints\perf-r4d-20261102\runtime
set OUT=%HERE%..\..\build\pool_fragmentation
if not exist "%OUT%\ref" mkdir "%OUT%\ref"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\pool_fragmentation.exe" "%HERE%test.c" "%RT%\xrt_mem.c" >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
set FAILED=0
for %%p in (split "churn 150" "churn 400" levels invalid staging segments heap) do (
  "%OUT%\pool_fragmentation.exe" %%~p || set FAILED=1
)
if "%1"=="reference" (
  cl /nologo /O2 /W3 /DREFERENCE /D_CRT_SECURE_NO_WARNINGS /I"%OLD%" /Fo"%OUT%\ref\\" /Fe"%OUT%\pool_fragmentation_ref.exe" "%HERE%test.c" "%OLD%\xrt_mem.c" >"%OUT%\build-ref.txt" || (type "%OUT%\build-ref.txt" & exit /b 1)
  echo --- reference: round-4 allocator ---
  for %%p in (split churn levels invalid staging heap) do (
    "%OUT%\pool_fragmentation_ref.exe" %%p >"%OUT%\ref-%%p.txt" 2>&1 && (echo reference %%p: passes) || (echo reference %%p: FAILS & findstr /b "xrt_fatal FAIL" "%OUT%\ref-%%p.txt")
  )
)
if %FAILED%==1 (echo FAIL & exit /b 1)
echo PASS
