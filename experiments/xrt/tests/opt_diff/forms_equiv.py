"""Builds and runs forms_equiv.c (the xlift --opt sse helper twins against the helpers they replace) with the game
build's flags against out/dev-init/runtime/xrt.h. --mutations also rebuilds once per deliberately broken twin
(sse_mutants.h), each of which must be reported. Exit 0 when the twins agree and every mutation is detected.

  .venv\\Scripts\\python.exe -I experiments\\xrt\\tests\\opt_diff\\forms_equiv.py [--mutations]"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(WS, "experiments", "xrt", "build", "opt_diff")
RT = os.path.join(WS, "out", "dev-init", "runtime")
VCVARS = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
# each mutation points one TWIN_* of forms_equiv.c at a broken variant from sse_mutants.h
MUTATIONS = {"store-wide": "/DTWIN_WR32=wrf32s_mut_wide", "store-narrow": "/DTWIN_WR64=wrf64s_mut_narrow",
             "compare-no-unordered": "/DTWIN_CMP=fcompareo_mut_nan", "xcompare-equal-as-less": "/DTWIN_XCMP=XFCOMPAREO_mut_le"}


def run(mut=None):
    os.makedirs(OUT, exist_ok=True)
    exe = os.path.join(OUT, f"forms_equiv{'_' + mut if mut else ''}.exe")
    extra = MUTATIONS[mut] if mut else ""
    cmd = (f'call "{VCVARS}" x64 >nul && cl /nologo /O2 /fp:strict /W3 /wd4102 /wd4146 /I"{RT}" /I"{HERE}" {extra} '
           f'/Fo"{OUT}\\\\" /Fe"{exe}" "{os.path.join(HERE, "forms_equiv.c")}"')
    r = subprocess.run(cmd, shell=True, cwd=OUT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"build failed:\n{r.stdout}{r.stderr}")
    r = subprocess.run([exe], capture_output=True, text=True)
    print(r.stdout.strip())
    if mut:
        print(f"mutation {mut}: {'DETECTED' if r.returncode else 'NOT DETECTED'}")
        return 0 if r.returncode else 1
    return r.returncode


def main():
    bad = run()
    if "--mutations" in sys.argv[1:]:
        bad += sum(run(m) for m in MUTATIONS)
    print("PASS" if not bad else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
