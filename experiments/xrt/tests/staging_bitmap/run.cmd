@echo off
rem Owned test of the D3D8 buffer validity bitmap (out/dev-init/runtime/d8_valid_bits.h) against the former byte map;
rem see staging_bitmap.c. Output: experiments\xrt\build\staging_bitmap\
setlocal
set HERE=%~dp0
set RT=%HERE%..\..\..\..\out\dev-init\runtime
set OUT=%HERE%..\..\build\staging_bitmap
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul || exit /b 1
cl /nologo /O2 /W3 /I"%RT%" /Fo"%OUT%\\" /Fe"%OUT%\staging_bitmap.exe" "%HERE%staging_bitmap.c" >"%OUT%\build.txt" || (type "%OUT%\build.txt" & exit /b 1)
"%OUT%\staging_bitmap.exe"
