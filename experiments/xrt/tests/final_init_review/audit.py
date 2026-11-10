"""Read-only independent consumer/identity audit, writes only this review."""
from pathlib import Path
import sys,re,json
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
import review as R
from review import W,O,BASE,core,read,save,C

def main():
    R.configure();b,lineage=R.verify()
    before=read(BASE/'preservation.json');changed=[]
    for root,tree in before['trees'].items():
        if core.tree(Path(root))!=tree:changed.append(root)
    for name,d in before['state'].items():
        p=Path(name)
        if (core.sha(p) if p.exists() else None)!=d:changed.append(name)
    protected=C.A.verify()
    core.require(not changed and protected==before['protected'],'preservation '+str(changed))
    save(O/'preservation-review.json',dict(passed=True,protected=protected,changed=changed,baseline_seal_sha256=core.sha(BASE/'seal.json'),candidate_unconsumed=True,production_policy_changed=False))
    sys.path.insert(0,str(H.parent/'functional_assessment'))
    import audit as retained
    original=retained.original_code()
    save(O/'d3ddrv-consumers.json',original)
    inventory=[];files={}
    for mod in ('unreal2','core','engine','windrv','window','d3ddrv'):
        for p in sorted((W/'experiments/xrt/gen'/mod).glob('*.c')):
            files[str(p)]=core.sha(p);lines=p.read_text().splitlines();fn=None
            for j,s in enumerate(lines):
                m=re.match(r'void (f_[0-9a-f]+)\(CPU\* c\)',s)
                if m:fn=m[1]
                if ('!GetLastError */' in s or re.search(r'/\* (?:fnstsw|fstsw|fnstenv|fstenv|fnsave|fsave|fxsave|stmxcsr)',s)
                    or ('c->fs_base + 0x34' in s)):
                    inventory.append(dict(module=mod,file=str(p),line=j+1,function=fn,context=lines[max(0,j-2):j+7]))
    init=W/'experiments/xrt/gen/engine/Engine_018.c';text=init.read_text()
    body=text.split('void f_1038f460(CPU* c) {',1)[1].split('\nvoid f_',1)[0]
    save(O/'init-consumer-inventory.json',dict(generated_files=files,sites=inventory,
        direct_init=dict(function='f_1038f460',guest='0x1038f460',file=str(init),sha256=core.sha(init),
            calls=[s.strip() for s in body.splitlines() if 'CALL(' in s],
            fpu_status_lines=[s.strip() for s in body.splitlines() if 'c->fsw' in s or 'fnstsw' in s]),
        reachability='Static inventory and direct Init calls only. Indirect COM/virtual/script/native callback edges are unresolved; presence does not prove dynamic reachability and absence in one caller does not prove noninterference.',
        error_monitor='xrt_loader.c wraps actual HLE dispatcher entry/return, including kernel32.dll!GetLastError. Direct guest TEB reads and inline x87 consumers have no dedicated live consumer stop.',
        beyond_endpoint=['0x1090ED5C call 0x10901370','0x1090ED61 fsub [ebp-0x38]'],
        whole_program_noninterference_proven=False))
    baseline=read(BASE/'strict-failures.json')
    wnd_source=W/'out/recovery/owner-color-verified-20261027-01/strict-limitations.json'
    wnd=read(wnd_source)
    core.require(wnd['wndproc']['original_complete_state_equality_passed'] is False,'strict WNDPROC verdict')
    save(O/'wndproc-source-review.json',dict(source=str(wnd_source),sha256=core.sha(wnd_source),finding=wnd['wndproc'],strict='FAILED',current_candidate_equivalence_proven=False))
    save(O/'strict-differences-review.json',dict(state='PROPOSED_NOT_APPROVED',historical_verdict='FAILED',baseline=baseline,
        differences=[
          dict(id='historical-x87',strict='FAILED',reachable='FPU arithmetic is reachable within Init and its callees; native graphics stack/status effects are reachable when CreateDevice/clear/present is reached.',known_consumers='Generated FNSTSW/comparison branches; real arithmetic, formatting and timing. The retained no-reader proof covers only 0x0696F0D1..0x0696F28C, not the full Init interval.',unknown='Native historical x87 occupancy/tags, live 80-bit values, interleaved logging and later consumer graph are not established.',proposal='Explicitly accept unresolved bounded compatibility risk only after owner review; do not describe it as PE-only or repair the state.'),
          dict(id='complete-WNDPROC-equality',strict='FAILED',reachable='Window procedure dispatch is reachable during window/renderer initialization. First Present can occur before Init returns; it was reached in prior renderer evidence.',known_consumers='Historical raw states change native window_proc 1410848 to 1474753616; translated window_proc 140702122140088 to 140722699353408 at first Present, resolving from the owned EXE +156088 to system opengl32.dll +48448. OS message dispatch and procedure queries/chaining can consume the new identity. Other sampled device/window fields were unchanged.',unknown='The historical physical fixture does not prove identical subclass behavior or message/order/reentry consequences in the current candidate. Module provenance is evidence, not a waiver.',proposal='Preserve raw procedure/module identities and callback state. A separately reviewed module-identified native subclass change may be accepted as bounded uncertainty; unknown module/procedure, unsupported message, reentry or state/identity corruption stops. Do not reduce complete equality to a message-only test.'),
          dict(id='DirectInput-Acquire-last-error',strict='FAILED',reachable='Acquire is implemented and reachable from input/window initialization; no proof excludes it from the proposed interval.',known_consumers='HRESULT is consumed by initialization/input handling. Independent sample 7 returns HRESULT 0 in both cases, native last-error 0 vs translated 5; actual inner native transfer agrees. GetLastError consumers can observe it.',unknown='No full path-sensitive overwrite-before-read proof exists; direct guest TEB reads are possible.',proposal='Preserve actual HRESULT/error. Permit only this documented diagnostic difference if separately accepted; any reached error consumer is a flagged analysis boundary, not evidence of parity.'),
          dict(id='CreateTexture-last-error',strict='FAILED',reachable='Texture allocation is possible in renderer/resource initialization within Init; the three known sites are static possibilities, not a current dynamic path.',known_consumers='D3DDrv at 0x0697AFC3, 0x0697B51B, 0x0697B806 tests EAX/HRESULT immediately. No D3DDrv GetLastError import; native x86 last-error 0 vs native/translated x64 seeded 0x13572468, with equal HRESULT/output.',unknown='Caller/callback/other-module error use or direct TEB access remains possible; no whole-program noninterference proof.',proposal='Keep error unchanged and compare actual native transfer. Permit only documented successful call discrepancy under separately approved bounded risk.'),
          dict(id='native-precision-status',strict='FAILED',reachable='Native depth creation, Clear, DrawPrimitive and Present may be reached during Init; operation reachability does not prove identical input state.',known_consumers='Observed MXCSR 0x3F80 to 0x3FA0 on measured calls; native x86 depth creation FSW 0x3000 to 0x3020. Nineteen local D3DDrv FNSTSW readers test AH comparison bits, not low-byte PE. No local full status/environment reader was found by the retained audit.',unknown='Other modules, native callbacks, exception/control modes and untraced code may observe status. Historical x87 failures also include tags/value loss and cannot be reduced to these PE changes.',proposal='Accept only explicitly enumerated observed sticky PE effects if approved; stop on control/rounding/masks/TOP/live value changes or additional exception effects. No FPU clearing/restoration added.')],
        approval=False,policy_activated=False))
    perf=read(BASE/'performance.json')
    save(O/'time-budget-review.json',dict(limit_seconds=60,changed=False,normal_record_ceiling=131072,
        records_per_second=perf['development_median_records_per_second'],nominal_ceiling_seconds=131072/perf['development_median_records_per_second'],
        decision='Retain 60 seconds as containment ceiling, not a demonstrated Init completion budget.',
        limits='Owned workloads omit real Init event count, loading/driver/helper latency and debugger overhead. Capacity may exhaust long before 60 seconds. Watchdog can kill without a stopped-tail capture; that outcome is incomplete evidence and must fail. No 120-second change is proposed or activated.'))
    print('Consumer review, exact candidate/object identities, historical preservation and unchanged 60-second budget audited.',flush=True)

if __name__=='__main__':main()
