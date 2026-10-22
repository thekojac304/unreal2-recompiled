@echo off
rem Build the x87 differential harnesses into experiments\xrt\build\x87 (git-ignored).
rem   x87_hw32.exe  32-bit native x87 reference (inline __asm)
rem   x87_rt64.exe  x64: runtime\xrt_cpu.c (same flags as build_xrt.cmd) + lifted Core.dll helpers
rem Usage: build_x87.cmd [xrt_cpu.c to test] [exe suffix]
rem   e.g. build_x87.cmd experiments\xrt\build\x87\snap\xrt_cpu_head.c _head  ->  x87_rt64_head.exe
rem Requires build\x87\gen\Core_000.c from:
rem   python -I tools\xrt\xlift.py sandbox_ref\hellofull\System\Core.dll --out experiments\xrt\build\x87\gen
rem          --only 0x10116f60,0x10116f80,0x10116fa0,0x10116fc0,0x10116fe0,0x10116ff0,0x10117000,0x10117010,0x1015d510
setlocal
set T=%~dp0
set X=%T%..\..
set B=%X%\build\x87
set RTSRC=%~1
if "%RTSRC%"=="" set RTSRC=%X%\runtime\xrt_cpu.c
set SUF=%~2
set VS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%B%\obj32" mkdir "%B%\obj32"
if not exist "%B%\obj64" mkdir "%B%\obj64"
if not exist "%B%\gen\Core_000.c" (echo missing %B%\gen\Core_000.c - run xlift --only first & exit /b 1)

rem ---------------------------------------------------------------- 32-bit reference
setlocal
call "%VS%" x86 >nul || exit /b 1
cl /nologo /O1 /W3 /D_CRT_SECURE_NO_WARNINGS /Fo"%B%\obj32\\" /Fe"%B%\x87_hw32.exe" "%T%x87_hw32.c" || exit /b 1
endlocal

rem ---------------------------------------------------------------- x64 runtime harness
call "%VS%" x64 >nul || exit /b 1
rem runtime helpers: exactly the flags of build_xrt.cmd's runtime step
cl /nologo /c /O2 /Zi /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /I"%X%\runtime" /Fo"%B%\obj64\xrt_cpu%SUF%.obj" /Fd"%B%\obj64\\" "%RTSRC%" || exit /b 1
rem lifted functions: flags of build_xrt.cmd's lifted step; compiled four times with the x87 helpers
rem renamed, to evaluate the same translated code under alternative helper models (x87_alt.c)
set REN=/Df_10116f60=MDL_f_10116f60 /Df_10116f80=MDL_f_10116f80 /Df_10116fa0=MDL_f_10116fa0 /Df_10116fc0=MDL_f_10116fc0 /Df_10116fe0=MDL_f_10116fe0 /Df_10116ff0=MDL_f_10116ff0 /Df_10117000=MDL_f_10117000 /Df_10117010=MDL_f_10117010 /Df_1015d510=MDL_f_1015d510 /Dxrt_fsin=MDL_fsin /Dxrt_fcos=MDL_fcos /Dxrt_fptan=MDL_fptan /Dxrt_fpatan=MDL_fpatan /Dxrt_fyl2x=MDL_fyl2x /Dxrt_f2xm1=MDL_f2xm1 /Dxrt_fscale=MDL_fscale /Dxrt_fsqrt=MDL_fsqrt
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /I"%X%\runtime" /Fo"%B%\obj64\gen_rt.obj" "%B%\gen\Core_000.c" || exit /b 1
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /I"%X%\runtime" %REN:MDL=hx% /Fo"%B%\obj64\gen_hx.obj" "%B%\gen\Core_000.c" || exit /b 1
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /I"%X%\runtime" %REN:MDL=p66% /Fo"%B%\obj64\gen_p66.obj" "%B%\gen\Core_000.c" || exit /b 1
cl /nologo /c /O1 /fp:strict /W3 /wd4102 /wd4146 /I"%X%\runtime" %REN:MDL=pfix% /Fo"%B%\obj64\gen_pfix.obj" "%B%\gen\Core_000.c" || exit /b 1
ml64 /nologo /c /Fo"%B%\obj64\x87_hw64.obj" "%T%x87_hw64.asm" || exit /b 1
cl /nologo /c /O2 /fp:strict /W3 /D_CRT_SECURE_NO_WARNINGS /I"%X%\runtime" /Fo"%B%\obj64\\" "%T%x87_rt64.c" "%T%x87_alt.c" || exit /b 1
link /nologo /OUT:"%B%\x87_rt64%SUF%.exe" "%B%\obj64\x87_rt64.obj" "%B%\obj64\x87_alt.obj" "%B%\obj64\xrt_cpu%SUF%.obj" "%B%\obj64\gen_rt.obj" "%B%\obj64\gen_hx.obj" "%B%\obj64\gen_p66.obj" "%B%\obj64\gen_pfix.obj" "%B%\obj64\x87_hw64.obj" || exit /b 1
echo built %B%\x87_hw32.exe %B%\x87_rt64%SUF%.exe from %RTSRC%
