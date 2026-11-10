"""Freeze a validated additive package; never launches fixtures or graphics."""
import difflib, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
import prepare_evidence as E
P=E.P

def main():
    results=P.core.read_large(E.O/'validation-results.json')
    assert results['passed'] and results['failures']==results['errors']==0
    final=P.core.read_large(E.O/'collector-final-validation.json')
    assert final['passed'] and final['final_focused_tests']==23 and final['contract_summaries_unchanged']
    for path,digest in final['final_source_hashes'].items():assert P.core.sha(Path(path))==digest
    old=P.core.read_large(P.O/'contract-results.json')
    new=P.core.read_large(E.O/'contract-results.json')
    assert len(new)==28
    for row in new:
        prior=[r['summary'] for r in old if r['group']==row['group'] and r['arch']==row['arch'] and r['translated']==row['translated']]
        assert len(prior)==1 and prior[0]=={k:row[k] for k in prior[0]},('original assertion/result discrepancy',row['group'],row['arch'],row['translated'])
    patch=''
    for name,original in [('fixture.c',P.H/'fixture.c'),('support.inc',P.H/'support.inc'),('preflight.c',P.H.parent/'d3d8_state/native.c')]:
        patch+=''.join(difflib.unified_diff(original.read_text().splitlines(True),(E.O/'sources'/name).read_text().splitlines(True),fromfile=str(original),tofile='instrumented/'+name))
    (E.O/'instrumentation.patch').write_text(patch)
    E.preserve()
    P.core.atomic(E.O/'preparation.json',dict(prepared=True,physical_batch_executed=False,genuine_launches=0,
        validation=results,original_contract_summaries_identical=True,original_physical_run_and_audit_unchanged=True,
        module_identity_final_validation=final,
        original_assertions_and_expected_results_unchanged=True,production_runtime_and_supervisor_unchanged=True,
        expected_fixture_processes=23,expected_group_calls=13392,expected_group_readbacks=13392,
        expected_preflight_calls=8,strict_x87='FAILED',strict_wndproc='FAILED',strict_native_x86='FAILED',production_accepted=False,
        module_identity_policy='kernel mapped path + read-only file pin + file ID/SHA/PE/mapping recheck; explicit unresolved failures; bounded unload-race proof',
        development_repairs=[
            'Corrected duplicate Python summary-key merge in preparation reporting; no renderer effect.',
            'Used DXVK LUID/vendor/device for the physical adapter join; retained emulated zero subsystem/revision fields and actual DXGI PCI fields separately.',
            'Built disposable executables with the Windows subsystem and CRT main entry to avoid hidden console hosts; kept strict single-process job membership.',
            'Resolved WOW64 loader aliases from the live kernel mapping, preserving raw snapshots and fail-closed unresolved identities.',
            'Retained unproven off-list mappings across retries; the negative test exposed and now prevents retry-based evidence loss.',
            'Unified evidence timestamps on the precise Windows clock after a retained coarse-clock exit-order failure; exact inequalities remain enforced.',
        ],owner_command=(E.O/'owner-command.ps1').read_text()))
    E.freeze()
    print(json.dumps(dict(prepared=True,tests=results['tests'],contract_fixtures=len(new),original_summaries_identical=True,graphics_executed=False),indent=2))

if __name__=='__main__':main()
