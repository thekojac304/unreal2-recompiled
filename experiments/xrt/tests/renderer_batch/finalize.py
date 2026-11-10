"""Audit the preparation bundle and write its readiness matrix. Never run graphics."""
import json,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
import prepare as P
import desktop_batch as D

def main():
    results=P.read(P.O/'contract-results.json');assert len(results)==36
    grouped=[]
    for group,name in P.GROUPS.items():
        rows=[r for r in results if r['group']==group];assert len(rows)==4
        assert {(r['arch'],r['translated']) for r in rows}=={('x86',False),('x64',False),('x86',True),('x64',True)}
        assert len({r['summary']['observations_hash'] for r in rows})==1,('boundary differential',name)
        for row in rows:
            d=Path(row['directory']);record=P.read(d/'build-record.json')
            rt=P.O/'snapshots'/name/'runtime'
            inputs=[P.H/'fixture.c',P.H/'support.inc',P.H/'resize32.asm',*rt.glob('*')]
            assert record['inputs']==P.core.digest({str(p):P.core.sha(p) for p in inputs if p.is_file()})
            for file,digest in record['outputs'].items():assert P.core.sha(Path(file))==digest
            machine=struct.unpack_from('<H',Path(d/'fixture.obj').read_bytes())[0]
            assert machine==(0x14c if row['arch']=='x86' else 0x8664)
            assert record['fp']=='/fp:strict'
        snapshot=P.read(P.O/'snapshots'/name/'snapshot.json')
        assert P.core.tree(P.O/'snapshots'/name/'runtime')==snapshot['runtime']
        grouped.append(dict(group=group,name=name,static_contract_verified=True,
            abi_memory_guards_tested=True,scope='guest/host callback protocol only; real Windows effects pending' if group==9 else 'provisional boundary, explicit COM doubles; no GPU compatibility claim',
            native_gpu_differential='N/A for method; real Windows differential PENDING' if group==9 else 'PENDING',
            production_implementation='PROVISIONAL source snapshot; accepted runtime unchanged',
            physical_desktop_test_required=True,checks=sum(r['summary']['checks'] for r in rows),
            abi_calls=sum(r['summary']['calls'] for r in rows)))
    gamma=P.read(P.O/'gamma-input-audit.json');assert gamma['passed']
    # Independently pin the GPU gamma fixture's ramp to the first original-PE CPU case.
    ramp=json.loads((P.O/'gamma-input/x86/run.stdout.txt').read_text().splitlines()[0])['ramp']
    assert bytes.fromhex(ramp)==struct.pack('<768H',*[i%256*257 for i in range(768)])
    P.save('readiness.json',dict(preparation_completed=True,groups=grouped,
        native_gpu_tests_executed=0,graphics_create_attempts=0,genuine_launches=0,
        gamma_input_cpu_differential=gamma,strict_x87='FAILED',strict_wndproc='FAILED',strict_native_x86='FAILED'))
    P.save('physical-batch-plan.json',D.plan())
    P.save('strict-failures.json',P.read(P.O/'preservation.json')['strict_failures'])
    P.save('development-repairs.json',dict(unexplained_discrepancies=0,repairs=[
        dict(kind='fixture import setup',cause='reused static analyzer imported its sibling phase module; explicitly bind the preserved analyzer module',production_effect=False),
        dict(kind='snapshot staging',cause='SetTexture prefix regex also matched SetTextureStageState; anchor opening parenthesis',retained='snapshots-stage-failed01',production_effect=False),
        dict(kind='fixture negative dispatch',cause='NULL-profile negative test dereferenced the profile in its fixture-only method selector; dispatch using separately saved slot so adapter rejects it',original_exit='0xc0000005',production_effect=False),
        dict(kind='fixture expected resize frame',cause='expected CPU subtracted an extra DWORD after already accounting for three stacked thiscall arguments; corrected expected ESP, then added native MASM ret-12 probe',production_effect=False)
    ]))
    P.verify()
    checks=sum(r['checks'] for r in grouped);calls=sum(r['abi_calls'] for r in grouped)
    table='| Group | Static contract | ABI / guards | Native GPU / Windows differential | Production | Physical test |\n|---|---|---|---|---|---|\n'
    for r in grouped:
        table+=f"| {r['group']}. {r['name']} | Verified | Passed x86/x64 | {'Windows pending' if r['group']==9 else 'Pending'} | Provisional | Required |\n"
    report=f'''# Unreal II renderer batch preparation

Nine independent source snapshots and 36 native/translated boundary fixtures are prepared.
No genuine game execution, graphics CreateDevice attempt, display/session change,
supervisor policy/authorization/breakpoint change, original/save modification, push or release occurred.
The accepted material package, historical evidence, production sources, generated sources,
consumed identities and fresh combined candidate remain byte-for-byte unchanged.

{table}

Validation: {checks:,} boundary assertions across {calls:,} assembly-trampolined calls.
All nine groups have native x86/x64 and translated x86/x64 executables. Nine changed
runtime integration units compiled independently under /fp:strict. Fixtures compile
one changed C unit and link the hash-verified prior ABI trampoline; all source/object/
executable hashes and PE object architectures were checked. No new game candidate was linked.
Ten evidence-parser tests reject missing/duplicate cases, bad HRESULT/readback/stack,
forged FPU flags, wrong readback slots, void gamma HRESULT claims and missing restoration.
Parser sample rows and COM doubles are explicitly not native graphics evidence.

Static verification re-read the original PEs and matched all 4,134 generated instruction
markers, all 38 cache state call sites (39 configuration cases because state 52 has both
boolean inputs), 11 identity transform sites, 15 cache stage sites, five initial sampler
sites, NULL bindings, FVF and gamma. Vtable ownership was independently re-read from
the PEs; Core's exported FMatrix::Identity is exactly the fixture's 64 input bytes.
The complete original/generated callback call contexts and thiscall argument frame are
in callback-contracts.json. Each snapshot has its own runtime file map and reviewable patch.

The initial sampler samples use raw LOD bits 0, +0.5, -0.5, filters 2/3, mip modes
0/1/2 and anisotropy 1/2, over stages 0..7. Cache samples preserve the independent
_ftol(+/-0.5)=0 input contract and address-mode samples 1/3. These are measurement
profiles, not assertions about the current game's actual configuration or caps and
not production allowlists. Streams cover 0..15; NULL pointer, stride/base zero and FVF 2
are guarded separately. A production profile must first be bound to measured native
caps and captured renderer fields. No non-NULL texture/buffer/shader support was added.

Boundary tests verify full guest CPU/frame/input preservation; HRESULT and all four
last-error seeds; native stdcall stack, integer nonvolatiles, x64 XMM6..15, x87 control,
status/TOP/two live values and MXCSR; dead/unknown identities; method/profile sealing;
bad stack ranges; reentry and Release in callbacks; and exact tuple rejection. Matrix
and gamma tests copy to typed host locals and cover readonly and cross-page inputs,
NULL/overflow/uncommitted/guard/inaccessible-tail ranges and wrong bytes. Host callback
services are explicit test doubles. They prove adapter protocol only.

Gamma input arithmetic: five complete 1,536-byte ramps (3,840 WORDs) agree between
relocated original x86 PE arithmetic plus original Core appPow/appRound/ftol and the
generated x64 loop. The x86 oracle loads only the pinned original MSVCR70 math runtime;
no game module entry point executes. The first case, gamma=1, brightness=.5, contrast=.5,
is byte-identical to the staged GPU fixture ramp. SetGammaRamp is VOID: EAX is not an
HRESULT and is excluded from differential outcome comparison. Its provisional guest
policy preserves EAX; native volatile register behavior remains a measured gate.
Native DXVK return effects, ramp readback, restore behavior and physical desktop effects
remain pending. The native fixture restores its saved ramp before reporting ordinary
ABI/readback assertion failures; no gamma mutation occurred during this preparation.

ResizeViewport: ECX is the guest viewport; stack is [return,flags,width,height], ret 12,
EAX is UBOOL. The SetRes call supplies flags 0x10 or 0x11 and signed X/Y. The original
method also handles dimension -1; that path remains outside the fixture's captured
1540x945 sample and stays guarded. The native x86 MASM probe validates ECX/stack/ret 12;
x64 and translated protocol probes check zero and nonzero callback result propagation,
viewport/vtable/target identities and suspended CPU preservation. The actual generated
WinDrv method remains unchanged. This fixture does NOT emulate its window operations
or synthesize a resize success. Real Windows callback sequencing, focus, styles, client
rectangle and original/generated message equality require a separate physical-desktop
measurement of the real ResizeViewport body. That full Win32 harness is not claimed
ready or qualified by the protocol executable. Its complete static call/argument
inventory is prepared for that gate. Existing strict WNDPROC failure is not waived.

## Ordered physical-desktop batch

One invocation runs the already compiled fixtures serially and needs no per-operation
owner interaction. The runner rejects RDP before loading graphics. It first verifies
all delivery/executable hashes and both pinned DXVK pairs, then runs the unchanged
single-state (148,1) x86/x64 fixtures with the captured CreateDevice tuple. Any failure
stops the batch. It then measures groups 1..7 in native x86, native x64 and translated
x64 processes: four error seeds, two calls per exact case, typed readbacks, ABI/FPU,
cleanup and exact ordered native/translated result comparison. This is 23 disposable
processes by default, with one graphics CreateDevice per process; no game launch.

From E:\\Unreal2-Port-Investigation, only when physically present:

```powershell
.\\.venv\\Scripts\\python.exe -B experiments/xrt/tests/renderer_batch/desktop_batch.py run --out out/recovery/renderer-physical-batch-01
```

Add `--include-gamma` for the saved/restoring gamma sample after the preceding gates pass.
That adds three disposable processes. The output directory must be new. The runner
stops on CreateDevice, oracle, ABI, readback, restoration or differential failure;
it never changes a production allowlist or supervisor endpoint. It does not qualify
actual ResizeViewport/Win32 behavior. That remaining window gate must complete before
building a combined accepted renderer or seeking a bounded genuine SetRes attempt.

GPU results still required for every D3D group: real HRESULT/last-error effects;
native x86/x64/translated readback agreement; native CPU/FPU/nonvolatile behavior;
repeat/order behavior; real device lifetime; gamma restoration where applicable.
No mock or parser test is counted as any of these. Rendered pixels, genuine material
return, full SetRes return and outer engine initialization remain unverified.

STRICT X87: **FAILED**. COMPLETE WNDPROC EQUALITY: **FAILED**.
STRICT NATIVE X86 COMPATIBILITY: **FAILED**. Focused ABI and gamma input agreement
do not reclassify these historical failures.

Reproduction drivers: prepare.py preserve/static/stage/build/extended_static/integration,
gamma_input.py, test_audit.py, finalize.py. Use fresh paths for a new phase; preservation,
snapshot staging, gamma extraction and integration outputs are exclusive. Build reuse
requires exact current source/object hashes. All fixture repairs are explained in
development-repairs.json; no unexplained correctness or integrity discrepancy remains.
'''
    (P.O/'REPORT.md').write_text(report)
    # Freeze all new sources/results and the two immutable preflight fixture executables.
    files={str(p.relative_to(P.W)):P.core.sha(p) for root in [P.O,P.H] for p in root.rglob('*') if p.is_file() and p.name!='delivery.json'}
    for arch in ['x86','x64']:
        p=P.PRIOR/'state-fixtures'/arch/'native.exe';files[str(p.relative_to(P.W))]=P.core.sha(p)
    P.save('delivery.json',dict(files=files,total_boundary_assertions=checks,abi_calls=calls,
        source_snapshot_count=9,fixture_executable_count=36,graphics_executed=False,
        strict_x87='FAILED',strict_wndproc='FAILED'))
    print('Preparation audited:',checks,'assertions,',calls,'ABI calls, nine snapshots, 36 executables',flush=True)
if __name__=='__main__':main()
