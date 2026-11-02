@echo off
rem Developer-runtime variant of the C++ exception probe (round 4): ehprobe.dll (built as in build_and_run.cmd) is lifted
rem with the developer option set of out/dev-init/generated, plus ehframe for argument "frames" (the default) or without
rem it for "setjmp", and compiled with the developer runtime out/dev-init/runtime and the defines dev.py uses
rem (XRT_RV_ABI, XRT_PCLINES, XRT_EH_FRAMES); run_probe.py then compares the translated event logs with the native ones.
rem Outputs in experiments\xrt\build\ehprobe-dev-<mode>\ (git-ignored).
setlocal
set MODE=%1
if "%MODE%"=="" set MODE=frames
set HERE=%~dp0
set WS=%HERE%..\..\..\..
set OUT=%WS%\experiments\xrt\build\ehprobe-dev-%MODE%
set RT=%WS%\out\dev-init\runtime
set PY=%WS%\.venv\Scripts\python.exe
set VC="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
set OPTS=addr64,base,cflags,flags,icall,iflags,lazypc,pc,rdtsc,regcache,regs,restrict,rv,sse,x87,x87v,x87w
set DEFS=/DXRT_RV_ABI /DXRT_PCLINES
set LAND=
if "%MODE%"=="frames" (
  set OPTS=%OPTS%,ehframe
  set DEFS=/DXRT_RV_ABI /DXRT_PCLINES /DXRT_EH_FRAMES
  set LAND="%OUT%\x64\xrt_eh_land.obj"
)
for %%d in (x86 x64 gen) do if not exist "%OUT%\%%d" mkdir "%OUT%\%%d"
if exist "%OUT%\gen\*.c" del /q "%OUT%\gen\*.*"

setlocal
call %VC% x86 >nul 2>nul || exit /b 1
cl /nologo /c /O2 /Oy- /EHs /GS- /GR- /arch:IA32 /Zc:threadSafeInit- /W3 /Fo"%OUT%\x86\\" "%HERE%ehprobe.cpp" || exit /b 1
lib /nologo /def:"%HERE%msvcr70_probe.def" /machine:x86 /out:"%OUT%\x86\msvcr70_probe.lib" >nul || exit /b 1
> "%OUT%\x86\vt.c" echo const void* probe_type_info_vtable[2];
>> "%OUT%\x86\vt.c" echo int _fltused = 1;
cl /nologo /c /Fo"%OUT%\x86\vt.obj" "%OUT%\x86\vt.c" || exit /b 1
link /nologo /DLL /NOENTRY /NODEFAULTLIB /SAFESEH:NO /BASE:0x11000000 /DYNAMICBASE:NO /OUT:"%OUT%\ehprobe.dll" "%OUT%\x86\ehprobe.obj" "%OUT%\x86\vt.obj" "%OUT%\x86\msvcr70_probe.lib" /ALTERNATENAME:??_7type_info@@6B@=_probe_type_info_vtable || exit /b 1
cl /nologo /O2 /W3 /Fo"%OUT%\x86\\" /Fe"%OUT%\native_host.exe" "%HERE%native_host.c" || exit /b 1
endlocal
"%PY%" -I "%HERE%patch_probe.py" "%OUT%\ehprobe.dll" > "%OUT%\patch.txt" || exit /b 1
"%PY%" -I "%WS%\tools\xrt\xlift.py" "%OUT%\ehprobe.dll" --out "%OUT%\gen" --opt %OPTS% > "%OUT%\lift.txt" || exit /b 1

setlocal
call %VC% x64 >nul 2>nul || exit /b 1
ml64 /nologo /c /Fo"%OUT%\x64\monitor_asm.obj" "%RT%\monitor.asm" >nul || exit /b 1
if "%MODE%"=="frames" ml64 /nologo /c /Fo"%OUT%\x64\xrt_eh_land.obj" "%RT%\xrt_eh_land.asm" >nul || exit /b 1
cl /nologo /O2 /fp:strict /std:c11 /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS %DEFS% /DSTUB_LOADLIB /DSTUB_POW /I"%RT%" /I"%WS%\tools\xrt\dev" /Fo"%OUT%\x64\\" /Fe"%OUT%\xrt_probe_host.exe" "%HERE%xrt_probe_host.c" "%HERE%dev_host_stubs.c" "%OUT%\gen\*.c" "%RT%\hle_kernel32.c" "%RT%\hle_misc.c" "%RT%\hle_gui.c" "%RT%\hle_msvcr70.c" "%RT%\monitor.c" "%RT%\xrt_cpu.c" "%RT%\xrt_diag.c" "%RT%\xrt_eh.c" "%RT%\xrt_events.c" "%RT%\xrt_fmt.c" "%RT%\xrt_loader.c" "%RT%\xrt_mem.c" "%RT%\xrt_msvcr70img.c" "%RT%\xrt_thread.c" "%RT%\port_settings.c" "%RT%\hle_openal.c" "%WS%\tools\xrt\dev\dev_support.c" "%WS%\experiments\xrt\gen\msvcr70\pow_sse2.c" "%OUT%\x64\monitor_asm.obj" %LAND% winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib dbghelp.lib xaudio2.lib /link /STACK:0x10000000 >"%OUT%\x64\build.txt" || (type "%OUT%\x64\build.txt" & exit /b 1)
endlocal

set EHPROBE_OUT=%OUT%
"%PY%" -I "%HERE%run_probe.py" || exit /b 1
