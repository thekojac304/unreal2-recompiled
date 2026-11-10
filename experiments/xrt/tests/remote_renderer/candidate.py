"""Verified relink only. Fresh candidate with previously qualified renderer source.

No launcher, supervisor policy, breakpoint, authorization or original image edit.
"""
import shutil, struct, sys, uuid
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
def build():
    old=P.read(P.OLD/'build.json');source=Path(old['root'])
    assert P.core.tree(source)==old['outputs']
    assert P.core.tree(P.RT)==old['runtime']==P.core.tree(P.OLD/'runtime')
    assert P.core.tree(P.W/'experiments/xrt/gen')==old['generated']
    assert P.read(P.O/'contract-audit.json')['passed']
    target=P.W/'experiments/xrt/build/d3d8-remote-20261029-01'/(sys.argv[2]if len(sys.argv)>2 else 'client')
    target.mkdir(parents=True)
    copied={}
    for name,digest in old['outputs'].items():
        if name.endswith('.obj'):
            dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name,dest)
            assert P.core.sha(dest)==digest;copied[name]=digest
    assert len(copied)==279
    response=target/'link-objects.rsp'
    response.write_text((source/'link-objects.rsp').read_text().replace(str(source),str(target)))
    previous=next(c for c in old['commands']if Path(c['command'][0]).name.lower()=='link.exe')
    cmd=[s.replace(str(source),str(target))for s in previous['command']]
    # Exact original linker and flags, with only fresh output/object paths.
    helper=P.load('remote_link_environment',P.H.parent/'getobject_boundary/phase.py')
    helper.O=P.O/'link-environment';helper.O.mkdir()
    P.R.execute(cmd,target,'link',env=helper.env(),timeout=180,cwd=P.W/'experiments/xrt')
    sha=P.core.sha(target/'xrt_ucc.exe')
    assert sha!=old['binary_sha256']
    assert not any(r['kind']=='launch-claimed'and r['sha256']==sha for r in P.core.Ledger(P.core.HOME/'ledger.jsonl').rows)
    assert P.core.tree(source)==old['outputs']
    P.save('build.json',dict(passed=True,root=str(target),outputs=P.core.tree(target),
        binary_sha256=sha,pdb_sha256=P.core.sha(target/'xrt_ucc.pdb'),
        runtime_root=str(P.RT),runtime=P.core.tree(P.RT),generated=old['generated'],
        inherited_build=str((P.OLD/'build.json').relative_to(P.W)),inherited_build_sha256=P.core.sha(P.OLD/'build.json'),
        reused_objects=279,compiled_objects=0,reused_object_hashes=copied,
        source_equivalence_verified=True,commands=[P.read(target/'link.json')],
        qualified_operations=['SetMaterial exact 68-byte tuple','Clear bounded tuple','Present four NULLs',
          'SetRenderState (7,1),(9,2),(29,0),(26,1),(143,1),(48,0),(35,3),(136,1)'],
        new_native_operations_enabled=[],state_148_1_still_guarded=True,
        fresh_non_graphical_contract_audit=P.core.sha(P.O/'contract-audit.json'),
        game_qualified=False,execution_authorized=False,genuine_launches=0))
    print('FRESH VERIFIED RELINK',sha,flush=True)
def mapping():
    # Reuse offline PE/PDB mapping, without loading or starting the executable.
    mod=P.load('remote_material_mapping',P.H.parent/'d3d8_material/candidate.py')
    mod.W=P.W;mod.O=P.O;mod.RT=P.RT;mod.P=P
    mod.mapping()
def verify():
    import pefile
    b=P.read(P.O/'build.json');target=Path(b['root']);old=P.read(P.OLD/'build.json')
    assert P.core.tree(target)==b['outputs']
    assert P.core.tree(P.RT)==b['runtime']==old['runtime']
    assert P.core.tree(P.W/'experiments/xrt/gen')==b['generated']
    assert P.core.sha(P.OLD/'build.json')==b['inherited_build_sha256']
    origin=P.read(P.OLD/'object-lineage.json');assert len(origin)==279
    lineage={}
    for name,row in origin.items():
        assert '/fp:strict'in row['command']
        assert P.core.sha(Path(row['source']))==row['source_sha256']
        assert P.core.sha(target/name)==row['object_sha256']==b['reused_object_hashes'][name]==old['outputs'][name]
        assert struct.unpack('<H',(target/name).read_bytes()[:2])[0]==0x8664
        lineage[name]=dict(row,reused_in_this_candidate=True,inherited_from=str(P.OLD/'object-lineage.json'))
    rsp=[Path(s.strip().strip('"'))for s in (target/'link-objects.rsp').read_text().splitlines()if s.strip()]
    assert len(rsp)==279 and set(rsp)=={target/n for n in origin}
    exe=target/'xrt_ucc.exe';pe=pefile.PE(str(exe));assert pe.FILE_HEADER.Machine==0x8664
    rsds=[pe.get_data(d.struct.AddressOfRawData,d.struct.SizeOfData)for d in pe.DIRECTORY_ENTRY_DEBUG if d.struct.Type==2]
    assert len(rsds)==1 and rsds[0][:4]==b'RSDS'
    verifier=P.load('remote_pdb_reader',P.H.parent/'d3d8_material/verify.py')
    guid,age=verifier.pdb_identity(exe.with_suffix('.pdb'))
    assert guid==rsds[0][4:20]and age==struct.unpack_from('<I',rsds[0],20)[0]
    assert P.core.sha(exe)==b['binary_sha256']and P.core.sha(exe.with_suffix('.pdb'))==b['pdb_sha256']
    context=P.read(P.O/'mapping-context.json');instructions=context['context']
    immediate=next(i for i,x in enumerate(instructions)if x['operands']=='edi, 0x696f323')
    idx=next(i for i,x in enumerate(instructions)if x['bytes']=='897e44')
    assert immediate<idx and [(x['mnemonic'],x['operands'])for x in instructions[idx-2:idx-1]]==[('cmp','dword ptr [rsi + 0x40], edi')]
    assert instructions[idx-1]['mnemonic']=='jne'
    marker=instructions[idx]
    assert marker['bytes']=='897e44'and pe.get_data(marker['rva'],3).hex()==marker['bytes']
    assert not any(r.get('sha256')==b['binary_sha256']for r in P.core.Ledger(P.core.HOME/'ledger.jsonl').rows)
    P.save('object-lineage.json',lineage)
    P.save('candidate-verification.json',dict(passed=True,pe_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],
        rsds_guid=str(uuid.UUID(bytes_le=guid)),pdb_age=age,pe_pdb_identity_matched=True,
        runtime_tree_sha256=P.core.digest(b['runtime']),generated_tree_sha256=P.core.digest(b['generated']),
        original_compile_lineage_sha256=P.core.sha(P.OLD/'object-lineage.json'),
        source_object_and_link_input_lineage_verified=True,reused_objects=279,compiled_objects=0,
        offline_marker=dict(guest='0x0696f323',rva=hex(marker['rva']),bytes=marker['bytes']),
        marker_is_documentation_only=True,supervisor_or_breakpoint_changes=False,
        unconsumed=True,new_rendering_behavior_enabled=False,game_qualified=False,genuine_launches=0))
    print('INDEPENDENT SOURCE/279 OBJECTS/PE/PDB/LINK VERIFICATION PASS',flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
