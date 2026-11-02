@echo off
rem Owned cache/footprint microbenchmark (no game code). Usage: see cache_sweep.c.
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 "%~dp0cache_sweep.c" /Fe:"%~dp0cache_sweep.exe" /Fo:"%TEMP%\\"
