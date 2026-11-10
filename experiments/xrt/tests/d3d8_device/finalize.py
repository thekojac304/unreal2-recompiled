"""Seal new artifact hashes and record process/scope audit after characterization."""
import json,subprocess
from pathlib import Path
from run import W,HERE,sha,write
O=W/'out/recovery/d3d8-device-20261025-01'
assert json.loads((O/'final-integrity.json').read_text())['passed']
assert json.loads((O/'measurement.json').read_text())['passed']
roots=[p for p in(W/'experiments/xrt/build').iterdir()if p.name.startswith('d3d8-device-')]
for root in roots:
    p=root/'source-snapshot/verified/verified.json'
    if p.exists():
        data=json.loads(p.read_text());assert data['passed']
        for path,h in data['source_sha256'].items():assert sha(p.parent/Path(path).name)==h
query="@(Get-Process native,translated,xrt_ucc,dmusic_helper -ErrorAction SilentlyContinue | Select-Object Id,Name,Path) | ConvertTo-Json -Compress"
r=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,text=True)
processes=json.loads(r.stdout)if r.stdout.strip()else[]
assert not processes,processes
write(O/'completion.json',dict(passed=True,processes_remaining=processes,genuine_client_sessions=0,production_runtime_changed=False,generated_game_code_changed=False,
    CreateDevice_production_guard=True,Clear_Present_production_supported=False,rendering_host_calls=0,recommendation='CONDITIONAL GO for captured path only; general creation/retry NO-GO pending backend failure cleanup',
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()))
paths=[p for root in [O,HERE,*roots]for p in root.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name!='phase-artifacts.json']
paths += [W/'experiments/xrt/D3D8_DEVICE_CHARACTERIZATION.md',W/'experiments/xrt/results/compare/d3d8_device_characterization.json']
write(O/'phase-artifacts.json',{str(p.relative_to(W)):sha(p)for p in paths})
print('COMPLETION PASS:',len(paths),'new/preserved artifact hashes; no native/translated/client/helper processes remain; characterization stops here')
