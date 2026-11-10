@echo off
rem Link the real client EXE translation against an identified full-checkpoint object's set.
rem The baseline's generated objects are read only. All client/runtime outputs go in a separate directory.
rem XRT_BASE_BUILD and XRT_CLIENT_BUILD must be absolute paths; the latter should be a fresh build directory.
setlocal
cd /d "%~dp0"
if "%XRT_BASE_BUILD%"=="" exit /b 2
if "%XRT_CLIENT_BUILD%"=="" exit /b 2
if not exist "%XRT_BASE_BUILD%\identity.json" exit /b 2
..\..\.venv\Scripts\python -I ..\..\tools\xrt\client_identity.py --base "%XRT_BASE_BUILD%" --out "%XRT_CLIENT_BUILD%" || exit /b 1
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
if not exist "%XRT_CLIENT_BUILD%\obj\client" mkdir "%XRT_CLIENT_BUILD%\obj\client"
if not exist "%XRT_CLIENT_BUILD%\obj\rt" mkdir "%XRT_CLIENT_BUILD%\obj\rt"
if not exist "%XRT_CLIENT_BUILD%\obj\engine" mkdir "%XRT_CLIENT_BUILD%\obj\engine"
rem Serial compiler processes: earlier C1001/D8040 findings remain unresolved.
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /errorReport:none /Iruntime /FIworld_observer.h /Fo"%XRT_CLIENT_BUILD%\obj\engine\\" @"%XRT_CLIENT_BUILD%\engine-sources.rsp" || exit /b 1
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /errorReport:none /Iruntime /Fo"%XRT_CLIENT_BUILD%\obj\client\\" @"%XRT_CLIENT_BUILD%\client-sources.rsp" || exit /b 1
rem The isolated /O1 compilation passed after a parallel MSVC C1001 for this unit.
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /errorReport:none /Iruntime /Fo"%XRT_CLIENT_BUILD%\obj\client\\" gen\particlesystems\ParticleSystems_001.c || exit /b 1
cl /nologo /c /O2 /Zi /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DXRT_WITH_UNREAL2 /errorReport:none /Iruntime /Fo"%XRT_CLIENT_BUILD%\obj\rt\\" /Fd"%XRT_CLIENT_BUILD%\obj\rt\\" runtime\*.c || exit /b 1
link /nologo /DEBUG /STACK:0x10000000 /OUT:"%XRT_CLIENT_BUILD%\xrt_ucc.exe" @"%XRT_CLIENT_BUILD%\base-objects.rsp" "%XRT_CLIENT_BUILD%\obj\engine\*.obj" "%XRT_CLIENT_BUILD%\obj\client\*.obj" "%XRT_CLIENT_BUILD%\obj\rt\*.obj" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib || exit /b 1
..\..\.venv\Scripts\python -I ..\..\tools\xrt\client_identity.py --base "%XRT_BASE_BUILD%" --out "%XRT_CLIENT_BUILD%" --record || exit /b 1
