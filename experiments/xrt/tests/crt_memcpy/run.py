"""crt_memcpy driver: lift ogg.dll at 0x10010000 (tools/xrt/xlift.py, plain), write its rebased image, build the x64
harness with the lifted C, run it on the lifted memcpy. Needs sandbox_cmp/level/System/ogg.dll (game file, read as data
and translated; never executed natively) and Visual Studio 18. Output: experiments/xrt/build/crt_memcpy/.
Usage: .venv/Scripts/python.exe -I experiments/xrt/tests/crt_memcpy/run.py"""
import os, subprocess, sys
WS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(WS, 'tools', 'xrt'))
from peimage import PEImage
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(WS, 'experiments', 'xrt', 'build', 'crt_memcpy')
RT = os.path.join(WS, 'out', 'dev-init', 'runtime')
VCVARS = r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat'
DLL = os.path.join(WS, 'sandbox_cmp', 'level', 'System', 'ogg.dll')
BASE, MEMCPY = 0x10010000, 0x10012660
os.makedirs(OUT, exist_ok=True)
lift = os.path.join(OUT, 'lift')
subprocess.run([sys.executable, '-I', os.path.join(WS, 'tools', 'xrt', 'xlift.py'), DLL, '--out', lift, '--base', hex(BASE)], check=True)
open(os.path.join(OUT, 'image.bin'), 'wb').write(bytes(PEImage(DLL, BASE).image))
srcs = ' '.join(f'"{os.path.join(lift, n)}"' for n in sorted(os.listdir(lift)) if n.endswith('.c'))
cmd = (f'call "{VCVARS}" x64 >nul && cl /nologo /O2 /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS '
       f'/I"{RT}" /Fo"{OUT}\\\\" /Fe"{os.path.join(OUT, "harness.exe")}" {srcs} "{os.path.join(HERE, "harness.c")}" >"{os.path.join(OUT, "build.txt")}"')
if subprocess.run(cmd, shell=True).returncode:
    print(open(os.path.join(OUT, 'build.txt')).read()); sys.exit(1)
sys.exit(subprocess.run([os.path.join(OUT, 'harness.exe'), os.path.join(OUT, 'image.bin'), hex(BASE), hex(MEMCPY)]).returncode)
