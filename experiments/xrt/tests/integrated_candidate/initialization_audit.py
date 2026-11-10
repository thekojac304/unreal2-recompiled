"""Evidence-indexed initialization sequence; no inferred dynamic completion."""
import sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import pefile,capstone
def main():
    previous=read(PRIOR/'resource-path-audit.json');current=read(O/'resource-path-audit.json')
    source=A.source()/'System/D3DDrv.dll';pe=pefile.PE(str(source));pe.relocate_image(0x6960000)
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    # The device field and vtable register are adjacent in these original bodies.
    proven={0x696d619:('GetBackBuffer','ReadPixels; not asserted to occur in initial frame'),
            0x697b5d7:('CreateDepthStencilSurface','resource-cache branch, loop bounded by comparison with 4'),
            0x696fbcc:('GetRenderTarget','first renderer Lock helper'),
            0x696fbfb:('GetDepthStencilSurface','first renderer Lock helper')}
    for r in current['calls']:
        site=int(r['site'],16);r['interface_proven_for_this_audit']=site in proven
        r['classification']=proven[site][1] if site in proven else 'Unresolved interface: slot-offset match alone is not D3D8 device evidence.'
        if site in proven:assert proven[site][0]==r['method']
        text=Path(r['generated']).read_text();pos=text.index(f'P(0x{site:x}u)')
        entries=list(re.finditer(r'void (f_[0-9a-f]+)\(CPU\* c\)',text[:pos]));r['generated_function']=entries[-1][1] if entries else None
    save(O/'resource-path-audit.json',current)
    original_checks=[]
    for addr,raw,label in [(0x696d619,'ff5140','backbuffer vtable call'),(0x697b5d7,'ff5268','depth creation vtable call')]:
        actual=pe.get_data(addr-0x6960000,len(bytes.fromhex(raw)));assert actual==bytes.fromhex(raw)
        original_checks.append(dict(site=hex(addr),bytes=actual.hex(),meaning=label))
    stat=read(O/'static-audit.json');assert stat['passed']
    conditional=[dict(function=f['address'],**c) for f in stat['functions'] for c in f['calls'] if c.get('symbol') in ('SetWindowLongA','SetWindowLongW','SetMenu','PostMessageA','PostMessageW')]
    assert len(conditional)==9 and all(c['adapter_name_present'] for c in conditional)
    engine=next(f for f in stat['functions'] if f['address']=='0x1038f460')
    checkpoints=[c for c in engine['calls'] if int(c['address'],16)>=0x1038fb16 and int(c['address'],16)<=0x1038fb42]
    assert [c['address'] for c in checkpoints]==['0x1038fb16','0x1038fb2b','0x1038fb33','0x1038fb42']
    assert checkpoints[2]['target']=='0x10383950'
    save(O/'initialization-path.json',dict(passed=True,original_sha256=core.sha(source),original_checks=original_checks,
        resource_cache_create_depth_context=next(r for r in current['calls'] if r['site']=='0x697b5d7'),
        resource_coverage_prior=previous,conditional_windows=conditional,engine_tail=checkpoints,
        sequence=[
          dict(stage='LoadMap/actor initialization',status='historical accepted evidence only; not rerun'),
          dict(stage='OpenWindow -> TryRenderDevice -> SetRes',status='saved SetRes evidence independently paired: 250 calls, EAX=1, stop at 11104BF8'),
          dict(stage='remaining OpenWindow and UGameEngine::Init tail',status='static only; original virtual calls retained, including 1038FB16, 1038FB2B and conditional 1038FB42'),
          dict(stage='InitAudio at 1038FB33 -> 10383950',status='original body retained; no -nosound skip assumption'),
          dict(stage='Init return to 1090ED5C',status='offline linked mapping and owned non-game stop tests only; no genuine completion'),
          dict(stage='renderer Lock/cache/scene/draw/Unlock/Present',status='resource and scene adapter fixtures only; genuine scene unverified')],
        limits=['No path-sensitive proof that every resource branch executes in the first frame.',
                'ReadPixels GetBackBuffer is a readback path, not an initial-frame requirement.',
                'CopyRects and standalone image/render-target creation are subsystem support; no genuine callsite is asserted here.',
                'Offset collisions in unresolved COM calls are preserved, not mislabeled as supported device calls.'],
        genuine_launches=0,engine_initialization_bypassed=False,supervisor_authorization_changed=False))
    print('Original PE checks, 9 conditional Windows imports and Init-tail sequence audited',flush=True)
if __name__=='__main__':main()
