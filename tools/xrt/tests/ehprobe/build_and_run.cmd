@echo off
rem C++ exception probe: build ehprobe.dll (x86, EH tables patched to VC7 and bound to the game's msvcr70.dll), the
rem native x86 host, and - from the lifted DLL - the translated x64 host; then run_probe.py runs both and compares.
rem Outputs in experiments\xrt\build\ehprobe\ (git-ignored).
setlocal
set HERE=%~dp0
set WS=%HERE%..\..\..\..
set OUT=%WS%\experiments\xrt\build\ehprobe
set RT=%WS%\experiments\xrt\runtime
set PY=%WS%\.venv\Scripts\python.exe
set VC="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
for %%d in (x86 x64 gen) do if not exist "%OUT%\%%d" mkdir "%OUT%\%%d"

setlocal
call %VC% x86 >nul || exit /b 1
cl /nologo /c /O2 /Oy- /EHs /GS- /GR- /arch:IA32 /Zc:threadSafeInit- /W3 /Fo"%OUT%\x86\\" "%HERE%ehprobe.cpp" || exit /b 1
lib /nologo /def:"%HERE%msvcr70_probe.def" /machine:x86 /out:"%OUT%\x86\msvcr70_probe.lib" >nul || exit /b 1
> "%OUT%\x86\vt.c" echo const void* probe_type_info_vtable[2];
>> "%OUT%\x86\vt.c" echo int _fltused = 1;
cl /nologo /c /Fo"%OUT%\x86\vt.obj" "%OUT%\x86\vt.c" || exit /b 1
link /nologo /DLL /NOENTRY /NODEFAULTLIB /SAFESEH:NO /BASE:0x11000000 /DYNAMICBASE:NO /OUT:"%OUT%\ehprobe.dll" "%OUT%\x86\ehprobe.obj" "%OUT%\x86\vt.obj" "%OUT%\x86\msvcr70_probe.lib" /ALTERNATENAME:??_7type_info@@6B@=_probe_type_info_vtable || exit /b 1
cl /nologo /O2 /W3 /Fo"%OUT%\x86\\" /Fe"%OUT%\native_host.exe" "%HERE%native_host.c" || exit /b 1
endlocal
"%PY%" -I "%HERE%patch_probe.py" "%OUT%\ehprobe.dll" > "%OUT%\patch.txt" || exit /b 1
"%PY%" -I "%WS%\tools\xrt\xlift.py" "%OUT%\ehprobe.dll" --out "%OUT%\gen" > "%OUT%\lift.txt" || exit /b 1

setlocal
call %VC% x64 >nul || exit /b 1
cl /nologo /O1 /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"%RT%" /Fo"%OUT%\x64\\" /Fe"%OUT%\xrt_probe_host.exe" "%HERE%xrt_probe_host.c" "%OUT%\gen\*.c" "%RT%\hle_kernel32.c" "%RT%\hle_misc.c" "%RT%\hle_msvcr70.c" "%RT%\xrt_cpu.c" "%RT%\xrt_diag.c" "%RT%\xrt_eh.c" "%RT%\xrt_events.c" "%RT%\xrt_fmt.c" "%RT%\xrt_loader.c" "%RT%\xrt_mem.c" "%RT%\xrt_thread.c" "%RT%\..\tests\common\xrt_test_stubs.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib /link /STACK:0x10000000 >"%OUT%\x64\build.txt" || (type "%OUT%\x64\build.txt" & exit /b 1)
endlocal

"%PY%" -I "%HERE%run_probe.py" || exit /b 1
