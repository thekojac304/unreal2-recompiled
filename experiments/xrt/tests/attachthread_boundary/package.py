"""Prepare a new fixed owner package; never call its launch path."""
import json
from pathlib import Path
import shutil
import sys
import uuid
W=Path(__file__).resolve().parents[4]
SOURCE=W/'experiments/xrt/tests/setres_completion'
H=W/'experiments/xrt/tests/setres_import_continuation'
PRIOR=W/'out/recovery/attachthread-setres-20261029-01'
O=W/'out/recovery/setres-import-continuation-20261029-01'
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core
from supervisor.environment import load


def main():
    core.require(not H.exists() and not O.exists(),'preserve an existing continuation package')
    core.require(core.read_large(PRIOR/'diagnosis.json')['passed'] and core.read_large(PRIOR/'fixture-validation.json')['passed'],'diagnosis/fixture incomplete')
    b=core.read_large(PRIOR/'build.json');exe=Path(b['root'])/'xrt_ucc.exe';sha=b['binary_sha256'];pdb=b['pdb_sha256']
    import pefile
    with pefile.PE(str(exe)) as pe:
        record=next(pe.get_data(e.struct.AddressOfRawData,e.struct.SizeOfData) for e in pe.DIRECTORY_ENTRY_DEBUG if pe.get_data(e.struct.AddressOfRawData,4)==b'RSDS')
        guid=str(uuid.UUID(bytes_le=record[4:20]))
    shutil.copytree(SOURCE,H)
    common=(H/'common.py').read_text()
    common=common.replace('out/recovery/renderer-gamma-integration-20261029-01','out/recovery/attachthread-setres-20261029-01')
    common=common.replace('out/recovery/setres-completion-20261029-01','out/recovery/setres-import-continuation-20261029-01')
    oldexe="experiments/xrt/build/renderer-prerequisites-20261029-01/ba218809-88d7-40a6-b069-2125cbecd53c/xrt_ucc.exe"
    common=common.replace(oldexe,exe.relative_to(W).as_posix()).replace('d6071f6563300dc4ae04b77d35943625f5b4274bb58db4a04ed6aee22b58d158',sha)
    common=common.replace('9e571a4c30354a36e261f4263cd414e578c6d046ead554ae7f741f79891ced8b',pdb)
    common=common.replace("SCOPE = 'setres-completion-before-0696d2cd'","SCOPE = 'setres-import-continuation-before-0696d2cd'")
    common=common.replace('AUTHORIZE ONE SETRES COMPLETION D6071F6563300DC4', 'AUTHORIZE ONE IMPORT-FIXED SETRES '+sha[:16].upper())
    (H/'common.py').write_text(common)
    identity=(H/'identity.py').read_text().replace('555dc5e3-509e-4146-8554-63a3f440b1d1',guid)
    identity=identity.replace('reused == 265 and len(objects)-reused == 14','reused == 278 and len(objects)-reused == 1')
    identity=identity.replace("len(b['commands']) == 15","len(b['commands']) == 2")
    identity=identity.replace('reused_generated_objects=265, compiled_runtime_objects=14','reused_generated_objects=265, reused_runtime_objects=13, compiled_runtime_objects=1')
    identity=identity.replace("read(PRIOR/'candidate-verification.json')['dependencies']","read(W/'out/recovery/renderer-gamma-integration-20261029-01/candidate-verification.json')['dependencies']")
    identity=identity.replace("read(PRIOR/'physical-gamma-abi-audit.json')","read(W/'out/recovery/renderer-gamma-integration-20261029-01/physical-gamma-abi-audit.json')")
    identity=identity.replace("core.sha(PRIOR/'physical-gamma-audit.json')","core.sha(W/'out/recovery/renderer-gamma-integration-20261029-01/physical-gamma-audit.json')")
    (H/'identity.py').write_text(identity)
    prepare=(H/'prepare.py').read_text()
    prepare=prepare.replace("roots=[p for p in (W/'out/recovery').iterdir() if p.is_dir() and p!=O]", "roots=[PRIOR,W/'out/recovery/setres-completion-20261029-01',W/'out/recovery/renderer-gamma-integration-20261029-01']")
    (H/'prepare.py').write_text(prepare)
    qualify=(H/'qualify.py').read_text().replace('env=helper.env()','helper.O=out;env=helper.env()')
    (H/'qualify.py').write_text(qualify)
    # Discover the new RVA from the new PE/PDB; retain the identical guest stop.
    mapping=(H/'mapping.py').read_text()
    exact="stop.address-base==RVA and stop.bytes.hex()=='897b44'"
    core.require(exact in mapping,'fixed mapping check absent')
    (H/'mapping.py').write_text(mapping.replace(exact,"stop.bytes.hex()=='897b44'"))
    sys.path.insert(0,str(H))
    import mapping as m
    plan=m.resolve();rva=plan['stop_rva']
    (H/'mapping.py').write_text(mapping)
    (H/'common.py').write_text(common.replace('RVA = 0x05a7f813','RVA = '+hex(rva)))
    # The original hold is retained, with a strictly scoped, evidence-bound
    # resolution checked afresh by the later local owner command.
    owner=(H/'owner.py').read_text()
    start=owner.index('    transitions=[r for r in ledger.rows')
    end=owner.index('    from identity import consumed',start)
    owner=owner[:start]+'''    resolved=read(O/'resolved-hold.json')
    core.require(core.sha(ledger.path)==resolved['ledger_sha256'],'ledger changed since the diagnosed hold; prepare again')
    transitions=[r for r in ledger.rows if r['kind']=='operational-transition']
    core.require(transitions and transitions[-1]==resolved['transition'],'unrelated or changed hold; no reset')
    core.require(resolved['candidate_sha256']==SHA and resolved['guest_stop']==GUEST and resolved['hold_preserved'], 'wrong scoped resolution')
    for path,digest in resolved['evidence'].items():core.require(core.sha(path)==digest,'resolution evidence changed')
    core.require(read(PRIOR/'diagnosis.json')['exact_import']=='user32.dll!AttachThreadInput' and read(PRIOR/'fixture-validation.json')['passed'], 'import correction unverified')
'''+owner[end:]
    (H/'owner.py').write_text(owner)
    (H/'README.md').write_text('''# Import-fixed SetRes continuation preparation

This separate fixed package retains the guest endpoint before 0x0696D2CD.
The consumed candidate and diagnostic hold remain preserved. The new launcher
admits only the exact evidence-bound AttachThreadInput resolution; any ledger
change, unrelated hold, STOP file or identity difference rejects execution.
It never resets authorization or consumption and requires a fresh local phrase.

The runtime change calls real USER32 for the measured current self-thread pair.
Native FALSE / ERROR_INVALID_PARAMETER and the keyboard-state reset are retained.
Cross-thread queue attachment remains unsupported and guarded.

Preparation only. No genuine game launch is authorized or performed by the
preparation scripts. See the fresh REPORT.txt and seal-validation.json for status.
''')
    print(json.dumps(dict(package=str(H),candidate=sha,pdb=pdb,guest_stop=hex(0x696d2cd),rva=hex(rva),genuine_launches=0)),flush=True)


if __name__=='__main__':main()
