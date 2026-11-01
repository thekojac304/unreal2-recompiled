"""Mutation check for test.c: each mutated copy of tools/xrt/dev/native/glm_xform.c must FAIL the differential test.
Usage: mutate.py OUT_DIR (after run.cmd has built OUT_DIR/translated.c). Needs the MSVC environment (run from run.cmd's
vcvarsall) - see run.cmd: `run.cmd mutate`."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[3]
out = Path(sys.argv[1])
src = (WS / 'tools/xrt/dev/native/glm_xform.c').read_text()
# Equivalent in practice, so not used: reassociating a translation sum (v0..v2 are rounded to float right after, which
# erases the last double bit except at rounding ties) and `test`-style exit flags (equal to the add's for any stack
# address that does not wrap).
MUTATIONS = {
    'reassociated rotation sum (double kept in an x87 slot)':
        ('r[7] = f64(a[8]) * f64(pf[7]) + f64(a[7]) * f64(pf[4]); r[7] = r[7] + f64(a[6]) * f64(pf[1]);',
         'r[7] = f64(a[8]) * f64(pf[7]) + f64(a[6]) * f64(pf[1]); r[7] = r[7] + f64(a[7]) * f64(pf[4]);'),
    'stale x87 slots swapped': ('c->st[(t + 7u) & 7u] = s1;   c->st[(t + 6u) & 7u] = s0;',
                                'c->st[(t + 7u) & 7u] = s0;   c->st[(t + 6u) & 7u] = s1;'),
    'exit flags not updated': ('fl_add(c, sp, 0xc0u, res, 32);', '(void)sp;'),
    'translation not rounded before the offset': ('w0 = f64((float)v0) + f64(pf[9]);', 'w0 = v0 + f64(pf[9]);'),
    'final x87 slot not written': ('c->st[(c->top + 7u) & 7u] = r0;', '(void)0;'),
    'scale product rounded early': ('s0 = f64(a[12]) * f64(pf[12]);', 's0 = (float)(f64(a[12]) * f64(pf[12]));'),
}
failed = 0
for name, (old, new) in MUTATIONS.items():
    assert src.count(old) == 1, name
    m = out / 'mutant.c'
    m.write_text(src.replace(old, new))
    exe = out / 'mutant.exe'
    b = subprocess.run(['cl', '/nologo', '/O2', '/fp:strict', '/W3', '/std:c11', '/wd4102', '/wd4146', '/D_CRT_SECURE_NO_WARNINGS',
                        f'/I{WS / "out/dev-init/runtime"}', f'/Fo{out}\\', f'/Fe{exe}', str(HERE / 'test.c'),
                        str(out / 'translated.c'), str(m)], capture_output=True, text=True)
    if b.returncode:
        print(b.stdout, b.stderr); sys.exit(2)
    r = subprocess.run([str(exe), '300'], capture_output=True, text=True)
    detected = r.returncode != 0 and 'FAIL' in r.stdout
    failed += not detected
    print(('detected  ' if detected else 'MISSED    ') + name)
print('mutations: %d/%d detected' % (len(MUTATIONS) - failed, len(MUTATIONS)))
sys.exit(1 if failed else 0)
