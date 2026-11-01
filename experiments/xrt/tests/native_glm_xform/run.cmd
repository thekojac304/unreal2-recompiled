@echo off
rem Differential test of the native GlmLib transform query against the translated function (see test.c). x64, /O2
rem /fp:strict as dev.py builds both. Output: experiments\xrt\build\native_glm_xform\  Usage: run.cmd [cases per MXCSR]
setlocal
set HERE=%~dp0
set WS=%HERE%..\..\..\..
set RT=%WS%\out\dev-init\runtime
set OUT=%HERE%..\..\build\native_glm_xform
if not exist "%OUT%" mkdir "%OUT%"
"%WS%\.venv\Scripts\python.exe" -B -I "%HERE%extract.py" "%WS%\out\dev-init\generated" "%OUT%\translated.c" || exit /b 1
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /fp:strict /W3 /std:c11 /wd4102 /wd4146 /D_CRT_SECURE_NO_WARNINGS /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\native_glm_xform.exe" ^
   "%HERE%test.c" "%OUT%\translated.c" "%WS%\tools\xrt\dev\native\glm_xform.c" >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
if /i "%1"=="mutate" ("%WS%\.venv\Scripts\python.exe" -B -I "%HERE%mutate.py" "%OUT%" & exit /b)
"%OUT%\native_glm_xform.exe" %1
