"""Copy an independent regression workspace; never overwrite historical outputs."""
import sys,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import preserve as P
H=P.W/'sandbox_d3d8_create_20261025_02'
previous=P.O/'harness.json'
if previous.exists():shutil.copy2(previous,P.O/'harness-01-preserved.json')
P.F.P.H=H;P.F.P.O=P.O;P.F.P.harness()
b=P.F.read(P.O/'harness.json')
for p in (P.W/'experiments/xrt/runtime').iterdir():
    if p.is_file():
        rel=p.relative_to(P.W);dest=H/rel;shutil.copy2(p,dest);b['files'][rel.as_posix()]=P.sha(dest)
(H/'tmp').mkdir()
P.save('harness.json',b)
print('CURRENT RUNTIME COPIED',len(b['files']),flush=True)
