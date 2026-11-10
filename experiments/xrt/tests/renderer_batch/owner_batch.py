"""Evidence-complete extension of desktop_batch; preserves the historical delivery.

Only 'run' may create graphics devices. 'verify', 'plan' and 'audit' are read-only.
"""
import argparse, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
import prepare_evidence as E
from evidence_capture import Collector, save
import evidence_check as A
P=E.P

def verify():
    E.D.verify_bundle();manifest=A.read(E.O/'evidence-delivery.json')
    for path,digest in manifest['files'].items():A.need(P.core.sha(Path(path))==digest,'evidence delivery identity '+path)
    for arch in ['x86','x64']:P.G.verified_pair(arch)
    E.preserve()
    return manifest

def plan():
    return dict(schema=2,fixture_processes=23,collector_helper_processes=0,graphics_create_devices=23,
        groups=[P.GROUPS[g] for g in range(1,8)],variants=['native x86','native x64','translated x64'],
        preflights='unchanged state-148 oracle assertions, rebuilt with checkpoints',group_calls=13392,group_readbacks=13392,
        gates=['verify frozen historical and evidence deliveries','require owner active physical console on WinSta0/Default',
               'create suspended child; assign kill-on-close job before resume','capture owner and child identity, topology, LUID, loaded backend and vendor ICD hashes',
               'capture raw ABI, ownership, destroy/unload, synchronous runtime events separately from stdout',
               'independently reject incomplete evidence after every process; stop at first failure','independently audit entire saved batch'],
        production_accepted=False,genuine_game_launch=False,gamma=False,resize=False)

def run(out):
    verify();out=out.resolve();A.need(out.is_relative_to(P.W/'out/recovery'),'output must be under out/recovery');out.mkdir()
    save(out/'plan.json',plan());collector=Collector();progress=[]
    try:
        for arch in ['x86','x64']:
            exe=E.O/'build'/('preflight-'+arch)/'fixture.exe';pair=P.G.verified_pair(arch);d=out/('preflight-'+arch)
            collector.capture(exe,[pair,148,1,18,0],d,build_record=exe.parent/'build-record.json',backend=[pair/'d3d8.dll',pair/'d3d9.dll'],physical=True)
            A.preflight(d,arch)
        for g in range(1,8):
            observations=[]
            for arch,translated in [('x86',False),('x64',False),('x64',True)]:
                name=f'{P.GROUPS[g]}-{arch}-{"translated" if translated else "native"}'
                exe=E.O/'build'/name/'fixture.exe';pair=P.G.verified_pair(arch);d=out/name
                collector.capture(exe,['--physical',pair],d,build_record=exe.parent/'build-record.json',backend=[pair/'d3d8.dll',pair/'d3d9.dll'],physical=True)
                values,report=A.group(d,g,arch,translated);observations.append(values);progress.append(report);save(out/'progress.json',progress)
            A.need(observations[0]==observations[1]==observations[2],'functional native/translated differential discrepancy')
            print('Complete physical evidence and matching differential:',P.GROUPS[g],flush=True)
        result=A.batch(out);E.preserve();save(out/'assessment.json',result)
        save(out/'evidence-index.json',{str(p.relative_to(out)):P.core.sha(p) for p in out.rglob('*') if p.is_file()})
        print(json.dumps({k:result[k] for k in ['functional_differential','physical_evidence_completeness','production_assessment','production_accepted','process_count','group_calls']},indent=2))
    except BaseException as error:
        save(out/'REJECTED.json',dict(physical_evidence_completeness='REJECTED',production_accepted=False,error=str(error),strict_x87='FAILED',strict_wndproc='FAILED',strict_native_x86='FAILED'))
        raise

if __name__=='__main__':
    A.need(not sys.flags.optimize,'optimized Python cannot run acceptance assertions')
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['plan','verify','run','audit']);ap.add_argument('--out',type=Path);ap.add_argument('--batch',type=Path);v=ap.parse_args()
    if v.action=='plan':print(json.dumps(plan(),indent=2))
    elif v.action=='verify':verify();print('Historical and evidence deliveries verified; no graphics executed')
    elif v.action=='run':
        if v.out is None:ap.error('--out requires a fresh directory')
        run(v.out)
    else:
        if v.batch is None or v.out is None:ap.error('audit requires --batch and fresh --out')
        verify();v.out.mkdir();save(v.out/'assessment.json',A.batch(v.batch.resolve()));E.preserve()
