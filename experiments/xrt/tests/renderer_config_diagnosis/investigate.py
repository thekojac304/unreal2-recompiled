"""Preserve and analyze saved evidence; never creates a game process."""
import json
import pathlib
import shutil
import struct
import subprocess
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def preserve():
    core.require(not O.exists(),'retain existing investigation')
    O.mkdir();b=read(LAST/'build.json');sandbox=W/'sandbox_cmp/setres-bfa1bae0-044b-42bc-aa73-30d1894c2a33'
    roots=[LAST,PRIOR,pathlib.Path(b['root']),sandbox,core.HOME,W/'tools/xrt',W/'experiments/xrt/runtime',W/'experiments/xrt/gen',H.parent/'setres_initial_completion']
    inventories={str(p):core.tree(p) for p in roots}
    shutil.copytree(ATTEMPT,O/'preserved/complete-consumed-attempt')
    for p in [EXE,EXE.with_suffix('.pdb'),core.HOME/'ledger.jsonl',LAST/'HALTED.json',LAST/'OWNER-ATTEMPT-CONSUMED.json']:
        dest=O/'preserved'/p.name;shutil.copy2(p,dest);core.require(core.sha(p)==core.sha(dest),'preservation copy mismatch')
    shutil.copytree(LAST/'preserved/strict-failures',O/'preserved/strict-failures')
    source={str(p):core.sha(p) for root in [W/'experiments/xrt/tests',W/'notes'] for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_relative_to(H)}
    source.update({str(p):core.sha(p) for p in W.glob('*.md')})
    for name,args in [('git-head',['rev-parse','HEAD']),('git-status',['status','--short']),('git-diff',['diff','--binary'])]:
        r=subprocess.run(['git',*args],capture_output=True,cwd=W,check=True);(O/(name+'.txt')).write_bytes(r.stdout)
    import asset_boundary
    save(O/'preservation.json',dict(trees=inventories,source_files=source,protected=asset_boundary.verify(),consumed_sha256=core.sha(EXE),genuine_launches=0))
    print('Consumed attempt/candidate/PDB/ledger copied; complete sandbox, history and source inventories preserved.',flush=True)


def analyze():
    rows=[json.loads(s) for s in (ATTEMPT/'debug-observations.jsonl').read_text().splitlines()]
    raw=(ATTEMPT/'runtime-events.raw.bin').read_bytes()
    core.require(raw==(ATTEMPT/'runtime-stream.raw.bin').read_bytes() and len(raw)%448==0,'raw stream integrity')
    events=[json.loads(raw[i:i+448].split(b'\0',1)[0]) for i in range(0,len(raw),448)]
    core.require(events==read(ATTEMPT/'runtime-events.json')['events'] and not any(e.get('truncated') for e in events),'raw event decoder')
    entry=next(r for r in rows if r['kind']=='setres_entry_raw')
    renderer_row=next(r for r in rows if r['kind']=='setres_renderer_raw')
    renderer=entry['renderer'];data=bytes.fromhex(renderer_row['raw'])
    core.require(renderer==renderer_row['address'] and len(data)==0x4700,'raw renderer identity/size')
    runtime_cpu=''.join(e['hex'] for e in events if e['kind']=='setres_raw' and e['phase']=='entry' and e['area']=='cpu')
    runtime_frame=next(e['hex'] for e in events if e['kind']=='setres_raw' and e['phase']=='entry' and e['area']=='frame')
    core.require(runtime_cpu==entry['cpu_raw'] and runtime_frame==entry['frame_raw'],'runtime/debugger entry CPU/frame differ')
    profile=read(PRIOR/'configuration-profile.json');fields=[]
    for offset,expected in profile['fields'].items():
        at=int(offset,0);b=data[at:at+4];observed=struct.unpack('<I',b)[0]
        fields.append(dict(offset=offset,width=4,expected=expected,expected_hex=f'0x{expected:08x}',observed_entry=observed,
            observed_hex=f'0x{observed:08x}',raw_le=b.hex(),match=observed==expected,
            failure_time_evidence=('not equal to 1; first failed short-circuit term; exact DWORD not saved' if at==0x40d0 else
                 'equal to expected: preceding complete capability-array assertion passed' if at in (0x41a0,0x41c8,0x41cc,0x41f0) else
                 'not read by the short-circuited aggregate assertion; exact failing-time DWORD unavailable'),
            expectation_source=dict(profile=str(PRIOR/'configuration-profile.json'),sha256=core.sha(PRIOR/'configuration-profile.json'),
             generator=str(H.parent/'renderer_prerequisites/phase.py'),line=95,
             origin='hardcoded canonical Boolean assumption' if at==0x40d0 else 'original field/config/capability model; see field-sources.json')))
    failed_cpu=next(r['cpu'] for r in reversed(rows) if r['kind']=='raw_boundary_stack' and r.get('tag')=='profile_entry')
    failure_frame=next(r for r in reversed(rows) if r['kind']=='raw_boundary_frame' and r.get('tag')=='profile_entry')
    save(O/'renderer-fields.json',dict(passed=True,renderer=renderer,renderer_hex=hex(renderer),viewport=entry['viewport'],
        raw_evidence_index=renderer_row['index'],phase='SetRes entry before guest prologue',fields=fields,
        failed_boundary=dict(cpu=failed_cpu,frame_raw=failure_frame['raw'],site=hex(failed_cpu['pc'])),
        evidence_limit='The failing profile_entry did not dump renderer fields. Exact DWORDs above are measured entry values; the failed short-circuit assertion proves its first field was not 1 then. No exact failing-time field dump is fabricated.'))
    summaries=[]
    for kind in ('native_return','render_native_return','state_native_return','state_bridge_return'):
        for r in rows:
            if r['kind']==kind:summaries.append({k:r[k] for k in ('index','kind','method','hresult','last_error','cpu') if k in r})
    save(O/'milestone.json',dict(passed=True,initial_frame=entry['frame'],initial_renderer=renderer,initial_viewport=entry['viewport'],
        actual_setres_guest_instructions_executed=True,stopped_site=failed_cpu['pc'],stopped_method='SetMaterial entry, before its native bridge/body',
        completed=dict(CreateDevice=1,Clear=1,Present=1,SetRenderState=8),last_completed='SetRenderState(136,1), native HRESULT=0/last-error=0 and checked guest return',
        SetMaterial_completed=False,configured_238_calls_started=False,SetRes_returned=False,evidence=summaries,
        cleanup=read(ATTEMPT/'cleanup.json'),genuine_launches=0))
    save(O/'raw-entry-verification.json',dict(passed=True,records=len(events),complete_cpu_bytes=416,runtime_debugger_cpu_equal=True,
         runtime_debugger_frame_equal=True,entry_frame=entry['frame'],entry_cpu=entry['cpu'],renderer=renderer,
         renderer_dump_index=renderer_row['index'],renderer_dump_sha256=core.digest(renderer_row['raw'])))
    print(json.dumps(fields,indent=2),flush=True)


def verify():
    p=read(O/'preservation.json')
    for root,tree in p['trees'].items():core.require(core.tree(pathlib.Path(root))==tree,'preserved tree changed: '+root)
    for path,digest in p['source_files'].items():core.require(core.sha(path)==digest,'source state changed: '+path)
    import asset_boundary
    core.require(asset_boundary.verify()==p['protected'],'protected installation/saves changed')
    core.require(core.tree(ATTEMPT)==core.tree(O/'preserved/complete-consumed-attempt'),'consumed attempt copy changed')
    save(O/'preservation-after.json',dict(passed=True,genuine_launches=0,global_ledger_unchanged=True,source_state_unchanged=True,
        sandbox_unchanged=True,original_installation_saves_unchanged=True,production_policy_breakpoints_unchanged=True))


if __name__=='__main__':
    core.require(sys.argv[1:] in (['preserve'],['analyze'],['verify']),'offline investigation command')
    globals()[sys.argv[1]]()
