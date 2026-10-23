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
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /MP /Iruntime /Fo"%XRT_CLIENT_BUILD%\obj\client\\" gen\unreal2\*.c gen\windrv\*.c gen\d3ddrv\*.c gen\particlesystems\*.c gen\legend\*.c gen\ui\*.c gen\u2\*.c gen\u2dialog\*.c || exit /b 1
cl /nologo /c /O2 /Zi /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DXRT_WITH_UNREAL2 /MP /Iruntime /Fo"%XRT_CLIENT_BUILD%\obj\rt\\" /Fd"%XRT_CLIENT_BUILD%\obj\rt\\" runtime\*.c || exit /b 1
link /nologo /DEBUG /STACK:0x10000000 /OUT:"%XRT_CLIENT_BUILD%\xrt_ucc.exe" "%XRT_BASE_BUILD%\obj\gen\*.obj" "%XRT_CLIENT_BUILD%\obj\client\*.obj" "%XRT_CLIENT_BUILD%\obj\rt\*.obj" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib || exit /b 1
..\..\.venv\Scripts\python -I ..\..\tools\xrt\client_identity.py --base "%XRT_BASE_BUILD%" --out "%XRT_CLIENT_BUILD%" --record || exit /b 1
