"""Supplementary raw GPU comparison. Never overrides the physical collector.

CLI accepts three saved stdout files, in x86/native, x64/native, x64/translated
order. This checks numerical/CPU/outer ABI evidence only. Physical process,
desktop, backend/module identity and watchdog acceptance remain separate.
"""
import sys,json,struct
from pathlib import Path
SLOTS=[3,40,41]+[34,72,35,34,73,35,34,73,35]+[35,34,34,35]
NARGS={3:1,34:1,35:1,40:2,41:2,72:5,73:9}
class Invalid(ValueError):pass
def need(ok,why):
    if not ok:raise Invalid(why)
def one(rows,kind):
    rs=[r for r in rows if r.get('kind')==kind];need(len(rs)==1,'missing/duplicate '+kind);return rs[0]
def abi(row,arch):
    regs=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else [
        0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,
        0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
    need(row['regs']==regs and row['stack_delta']==0,'outer native GPR/stack')
    xmm=bytes.fromhex(row['xmm'])
    need(xmm==(bytes(160) if arch=='x86' else struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10),'outer XMM')
    pre,post=[bytes.fromhex(row[k]) for k in ('pre','post')]
    need(len(pre)==len(post)==512,'FXSAVE size')
    need(pre[:2]==b'\x7f\x02' and pre[24:28]==struct.pack('<I',0x3f80),'FPU seed')
    for start,end in ((0,5),(24,28),(32,42),(48,58)):
        need(pre[start:end]==post[start:end],'strict outer x87/MXCSR difference')
def audit(rows,arch,translated):
    create=one(rows,'semantic-create')
    need(create['hr']<0x80000000 and (create['width'],create['height'])==(800,600),'device create')
    own=one(rows,'semantic-ownership')
    need(own['same_parent'] and own['same_window'] and own['parent_hr']<0x80000000 and
        own['creation_hr']<0x80000000 and own['add']==own['balance']+1 and own['flags']==0x42,'ownership')
    calls=[r for r in rows if r.get('kind')=='bringup-scene-call']
    need([r['slot'] for r in calls]==SLOTS,'scene sequence/count')
    for i,row in enumerate(calls):
        abi(row,arch)
        # Duplicate End/Begin deliberately measure the real native return.
        if i not in (12,14):need(row['hr']<0x80000000,'expected successful scene operation')
        before,after=[bytes.fromhex(row[k]) for k in ('cpu_before','cpu_after')]
        need(len(before)==len(after)==416,'full CPU observation')
        expected=bytearray(before)
        if translated:
            struct.pack_into('<I',expected,0,row['hr'])
            struct.pack_into('<I',expected,16,struct.unpack_from('<I',before,16)[0]+4*(NARGS[row['slot']]+1))
            struct.pack_into('<I',expected,64,0x98765432)
        need(after==expected,'guest CPU/return preservation')
    viewport=one(rows,'bringup-viewport')
    need(bytes.fromhex(viewport['bytes'])==struct.pack('<6I',0,0,800,600,0,0x3f800000),'viewport round trip')
    pixels=[r for r in rows if r.get('kind')=='bringup-pixels']
    presents=[r for r in rows if r.get('kind')=='bringup-present']
    need([r['mode'] for r in pixels]==[0,1,2] and [r['mode'] for r in presents]==[0,1,2],'three draw/readback modes')
    for row in pixels:
        need(all(row[k]<0x80000000 for k in ('get_hr','lock_hr','unlock_hr')) and
            100<row['changed_pixels']<480000,'actual non-clear readback')
    need(all(r['hr']<0x80000000 for r in presents),'Present')
    cleanup=one(rows,'semantic-cleanup')
    need(cleanup['device_release']==cleanup['parent_release']==0,'COM release')
    need(all(cleanup[k] for k in ('destroyed','unregistered','free_d3d8','free_d3d9','guest_freed')) and
        not any(cleanup[k] for k in ('window_valid','d3d8_loaded','d3d9_loaded')),'owned cleanup')
    summary=one(rows,'semantic-summary')
    need(summary['calls']==16 and summary['translated'] is translated,'summary')
    return dict(results=[(r['slot'],r['hr'],r['last_error']) for r in calls],
        pixels=[(r['mode'],r['changed_pixels'],r['rgb_hash']) for r in pixels],viewport=viewport['bytes'])
def compare(groups):
    measured=[audit(rows,arch,t) for rows,arch,t in zip(groups,('x86','x64','x64'),(False,False,True))]
    need(measured[0]==measured[1]==measured[2],'strict native/translated numerical difference')
    return dict(raw_comparison_passed=True,formal_physical_acceptance=False,measurements=measured,
        limitation='Outer wrapper ABI only; also require unchanged collector process/desktop/module/backend evidence.')
if __name__=='__main__':
    need(len(sys.argv)==4,'three saved stdout paths required')
    groups=[[json.loads(line) for line in Path(p).read_bytes().splitlines() if line.startswith(b'{')] for p in sys.argv[1:]]
    print(json.dumps(compare(groups),indent=2))
