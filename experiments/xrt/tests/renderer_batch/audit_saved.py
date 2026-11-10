"""Independent read-only audit of a saved batch; never runs a fixture or game.

Writes exclusively to a fresh audit directory. Numerical agreement alone does
not promote groups whose required execution-environment evidence is absent.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
sys.path.insert(0, str(H))
import desktop_batch as D
P = D.P
core = P.core


def raw(directory):
    record = core.read_large(directory/'result.json')
    stdout = (directory/'stdout.txt').read_text()
    lines = stdout.splitlines()
    assert lines and all(line.startswith('{') for line in lines), directory
    # Reject duplicate fields/nonfinite values independently of the saved parser.
    rows = [core.loads(line.encode()) for line in lines]
    assert rows == record['rows'] and record['exit'] == 0, directory
    assert (directory/'stderr.txt').read_bytes() == b'', directory
    exe = Path(record['executable'])
    assert core.sha(exe) == record['sha256']
    return record, rows


def fpu(call):
    pre, post = [bytes.fromhex(call[k]) for k in ['pre', 'post']]
    assert len(pre) == len(post) == 512
    assert pre[:2] == b'\x7f\x02'
    for a, b in [(0, 5), (24, 28), (32, 42), (48, 58)]:
        assert pre[a:b] == post[a:b], (a, b)


def main(batch, out):
    assert not sys.flags.optimize
    batch, out = batch.resolve(), out.resolve()
    assert batch.is_relative_to(W/'out/recovery') and out.is_relative_to(W/'out/recovery')
    out.mkdir()
    original = core.tree(batch)
    preserved = {str(p): core.tree(p) for p in [W/'experiments/xrt/runtime', W/'experiments/xrt/gen',
                W/'tools/xrt/supervisor', core.HOME]}
    core.atomic(out/'preservation.json', dict(batch_root=str(batch), batch=original, trees=preserved,
                delivery_sha256=core.sha(P.O/'delivery.json'), protected=P.A.verify()))
    delivery = D.verify_bundle()
    cases = core.read_large(P.O/'cases.json')['cases']
    expected_dirs = {'preflight-x86', 'preflight-x64'}
    groups, executables = [], {}
    total = 0
    for group in range(1, 8):
        name = P.GROUPS[group]
        profiles = [c for c in cases if c['group'] == group]
        outcomes = []
        for arch, variant in [('x86','native'), ('x64','native'), ('x64','translated')]:
            dirname = f'{name}-{arch}-{variant}'; expected_dirs.add(dirname)
            directory = batch/dirname
            record, rows = raw(directory)
            exe = P.O/'fixtures'/dirname/'fixture.exe'
            assert Path(record['executable']) == exe
            assert record['args'] == ['--physical', str(P.G.verified_pair(arch))]
            build = core.read_large(exe.parent/'build-record.json')
            rt = P.O/'snapshots'/name/'runtime'
            inputs = [H/'fixture.c', H/'support.inc', H/'resize32.asm', *rt.glob('*')]
            assert build['inputs'] == core.digest({str(p):core.sha(p) for p in inputs if p.is_file()})
            for path, digest in build['outputs'].items(): assert core.sha(Path(path)) == digest
            assert struct.unpack_from('<H', (exe.parent/'fixture.obj').read_bytes())[0] == (0x14c if arch=='x86' else 0x8664)
            assert build['fp'] == '/fp:strict'
            assert core.tree(rt) == core.read_large(rt.parent/'snapshot.json')['runtime']
            assert rows[0] == dict(kind='create', hr=0, nonnull=True)
            assert rows[-1] == dict(kind='summary',passed=True,calls=len(profiles)*8,
                                    graphics=True,translated=variant=='translated')
            assert len(rows) == 2 + len(profiles)*16
            observations = []
            pos = 1
            for case in profiles:
                for seed in [18,0,0x13572468,0xffffffff]:
                    for repeat in range(2):
                        call, readback = rows[pos:pos+2]; pos += 2
                        assert call['kind']=='call' and readback['kind']=='readback'
                        assert all(call[k]==case[k] for k in ['group','site','config','slot','a','b','c'])
                        assert call['seed']==call['error']==seed and call['hr']==0 and call['stack_delta']==0
                        assert call['fpu_preserved'] is True; fpu(call)
                        assert readback['slot']==case['slot'] and readback['hr']==0 and readback['equal'] is True
                        if case['slot']==50: assert readback['value']==case['b']
                        if case['slot']==63: assert readback['value']==case['c']
                        if case['slot']==76: assert readback['value']==2
                        if case['slot'] in [83,85]: assert readback['extra']==0
                        observations.append(tuple(call[k] for k in ['group','site','config','slot','a','b','c','seed','error','hr'])+
                                            tuple(readback[k] for k in ['slot','hr','equal','value','extra']))
            assert pos==len(rows)-1
            log=(directory/'fixture_d3d9.log').read_text()
            assert 'DXVK: v3.1.1' in log and 'NVIDIA GeForce RTX 5090:' in log and 'Driver   : NVIDIA 621.1.0' in log
            assert not any(line.startswith(('err:', 'warn:')) for line in log.splitlines())
            # Cross-check the original audit without using it for independent expected rows.
            assert len(D.audit(rows,group))==len(observations)
            outcomes.append(observations); total += len(observations)
            executables[dirname]=dict(path=str(exe),sha256=core.sha(exe),build_record_sha256=core.sha(exe.parent/'build-record.json'),
                                      dxvk_log_sha256=core.sha(directory/'fixture_d3d9.log'))
        assert outcomes[0]==outcomes[1]==outcomes[2]
        groups.append(dict(group=group,name=name,profiles=len(profiles),calls_per_variant=len(outcomes[0]),
            numerical_differential_passed=True,raw_FPU_protected_fields_passed=True,production_accepted=False))
    preflights=[]
    for arch in ['x86','x64']:
        record, rows = raw(batch/('preflight-'+arch))
        assert Path(record['executable'])==P.PRIOR/'state-fixtures'/arch/'native.exe'
        assert record['args']==[str(P.G.verified_pair(arch)),'148','1','18','0']
        assert rows[0]['kind']=='create' and rows[0]['hr']==0 and rows[0]['device']
        assert Counter(r['kind'] for r in rows)==dict(create=1,state=5,call=4,identity=1,cleanup=1)
        states=[r for r in rows if r['kind']=='state']
        assert [r['ordinal'] for r in states]==list(range(5))
        for i, call in enumerate(r for r in rows if r['kind']=='call'):
            assert call['ordinal']==i and call['hr']==0 and call['last_error']==18 and call['delta']==0
            fpu(call)
            expected=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else [int(str(j)*8+f'{0x12345678+(j-1)*0x11111111:08x}',16) for j in range(1,9)]
            assert call['regs']==expected
            if arch=='x64': assert bytes.fromhex(call['xmm'])==bytes.fromhex('78563412896745239a785634ab896745')*10
            assert states[i+1]['values'][148]==[0,1]
            assert all(states[i]['values'][k]==states[i+1]['values'][k] for k in range(256) if k!=148)
        identity=next(r for r in rows if r['kind']=='identity')
        assert identity==dict(kind='identity',parent_hr=0,same_parent=True,add=2,balance=1,parent_release=2,creation_hr=0,same_window=True,flags=66)
        assert rows[-1]==dict(kind='cleanup',device_release=0,parent_release=0,window_valid=False,d3d8_loaded=False,d3d9_loaded=False,callbacks=0,foreign_callbacks=0)
        preflights.append(dict(arch=arch,passed=True,executable_sha256=record['sha256']))
    assert {p.name for p in batch.iterdir() if p.is_dir()}==expected_dirs and len(expected_dirs)==23
    completed=core.read_large(batch/'result.json'); progress=core.read_large(batch/'progress.json')
    assert completed['passed'] and completed['groups']==progress and completed['genuine_launches']==0
    assert [(r['group'],r['name']) for r in progress]==[(g['group'],g['name']) for g in groups]
    strict=core.read_large(P.O/'strict-failures.json')
    assert strict['x87']==strict['wndproc_equality']==strict['strict_native_x86_compatibility']=='FAILED'
    assert core.sha(Path(strict['historical_source']))==strict['historical_source_sha256']
    result=dict(promotion_status='HELD_MISSING_REQUIRED_EVIDENCE',groups=groups,group_calls=total,group_readbacks=total,
        saved_process_result_sets=23,preflights=preflights,raw_stdout_equals_saved_rows=True,ordered_call_readback_stream_complete=True,
        verified_delivery_files=len(delivery['files']),executables=executables,dxvk_hashes=P.G.HASHES,
        observed_GPU='NVIDIA GeForce RTX 5090',observed_driver_log='NVIDIA 621.1.0',
        blockers=['No batch-time session/active-console/window-station/desktop/input-desktop/display-topology observation was saved.',
                  'No batch-time adapter PCI/LUID and driver-binary identity observation was saved; logs contain model and driver version only.'],
        evidence_limits=['21 group processes assert GPR/XMM preservation and zero device/parent Release counts in the hash-matched fixture, but do not emit those raw values.',
                         'No group PID/process-tree receipt or post-DestroyWindow/module-unload observation was saved.',
                         'xrt_event is deliberately a no-op in the fixture; complete call/readback stdout is verified, but there is no runtime event stream or dropped-event counter.'],
        runtime_integrated=False,new_game_candidate=None,genuine_launches=0,supervisor_mutations=0,
        strict_x87='FAILED',strict_wndproc='FAILED',strict_native_x86='FAILED')
    assert core.tree(batch)==original
    for path, files in preserved.items(): assert core.tree(Path(path))==files
    assert P.A.verify()==core.read_large(out/'preservation.json')['protected']
    result['preservation_passed']=True
    core.atomic(out/'audit.json',result)
    print(json.dumps({k:result[k] for k in ['promotion_status','saved_process_result_sets','group_calls','group_readbacks','blockers','preservation_passed']},indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--batch',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args(); main(args.batch,args.out)
