"""Independent staged candidate/source/object/PE/PDB verifier. No execution."""
import json,math,re,struct,sys,uuid
from pathlib import Path
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parents[4];O=W/'out/recovery/d3d8-material-20261029-01'
sys.path.insert(0,str(O/'enforcement'))
from supervisor import core,service

def pdb_identity(path):
    data=path.read_bytes();assert data[:32]==b'Microsoft C/C++ MSF 7.00\r\n\x1aDS\0\0\0'
    block,_,count,dbytes,_,mapblock=struct.unpack_from('<6I',data,32)
    n=math.ceil(dbytes/block);indices=struct.unpack_from('<'+'I'*n,data,mapblock*block)
    directory=b''.join(data[i*block:(i+1)*block]for i in indices)[:dbytes]
    ns=struct.unpack_from('<I',directory)[0];sizes=struct.unpack_from('<'+'I'*ns,directory,4);at=4+ns*4;streams=[]
    for size in sizes:
        n=0 if size==0xffffffff else math.ceil(size/block);ids=struct.unpack_from('<'+'I'*n,directory,at);at+=n*4
        streams.append(b''.join(data[i*block:(i+1)*block]for i in ids)[:size])
    info=streams[1];return info[12:28],struct.unpack_from('<I',info,8)[0]

def main():
    import pefile
    b=core.read_large(O/'build.json');target=Path(b['root']);exe=target/'xrt_ucc.exe'
    assert core.tree(target)==b['outputs']and core.tree(O/'runtime')==b['runtime']and core.tree(W/'experiments/xrt/gen')==b['generated']
    old=core.read_large(W/b['inherited_build']);assert core.sha(W/b['inherited_build'])==b['inherited_build_sha256']and core.tree(Path(old['root']))==old['outputs']
    origin=core.read_large(W/'out/recovery/viewport-getobject-20261028-01/build.json');lineage={}
    for source_build,reuse in [(origin,True),(b,False)]:
        for row in source_build['commands']:
            cmd=row['command'];assert row['exit']==0
            if Path(cmd[0]).name.lower()=='link.exe':continue
            obj=Path(next(x[3:]for x in cmd if x.startswith('/Fo')));root=Path(source_build['root']);rel=obj.relative_to(root).as_posix()
            if reuse and rel.startswith('obj/rt/'):continue
            assert rel not in lineage and '/fp:strict'in cmd
            sources=[Path(x)if Path(x).is_absolute()else W/'experiments/xrt'/x for x in cmd if x.lower().endswith('.c')];assert len(sources)==1
            actual=target/rel;assert struct.unpack('<H',actual.read_bytes()[:2])[0]==0x8664
            if reuse:assert core.sha(actual)==b['reused_object_hashes'][rel]==old['outputs'][rel]==origin['outputs'][rel]
            lineage[rel]=dict(source=str(sources[0]),source_sha256=core.sha(sources[0]),object_sha256=core.sha(actual),reused=reuse,command=cmd)
    assert len(lineage)==279 and sum(x['reused']for x in lineage.values())==265
    assert core.tree(W/'experiments/xrt/runtime')==core.read_large(O/'preservation.json')['production_runtime']
    assert {n:h for n,h in b['runtime'].items()if n not in ['d3d8_device_abi.h','d3d8_device_slots.inc','hle_d3d8_device.inc']}=={n:h for n,h in core.read_large(O/'preservation.json')['production_runtime'].items()if n not in ['d3d8_device_abi.h','d3d8_device_slots.inc','hle_d3d8_device.inc']}
    links=[x['command']for x in b['commands']if Path(x['command'][0]).name.lower()=='link.exe'];assert len(links)==1
    rsp=Path(next(x[1:]for x in links[0]if x.startswith('@')));objects=[Path(x.strip().strip('"'))for x in rsp.read_text().splitlines()if x.strip()]
    assert len(objects)==279 and set(objects)=={target/n for n in lineage}
    pe=pefile.PE(str(exe));assert pe.FILE_HEADER.Machine==0x8664
    rsds=[pe.get_data(x.struct.AddressOfRawData,x.struct.SizeOfData)for x in pe.DIRECTORY_ENTRY_DEBUG if x.struct.Type==2];assert len(rsds)==1 and rsds[0][:4]==b'RSDS'
    guid,age=pdb_identity(exe.with_suffix('.pdb'));assert guid==rsds[0][4:20]and age==struct.unpack_from('<I',rsds[0],20)[0]
    assert core.sha(exe)==b['binary_sha256']and core.sha(exe.with_suffix('.pdb'))==b['pdb_sha256']
    q=core.read_large(core.HOME/'qualification.json');service.verify_seal(q)
    plan=core.read_large(Path(q['evidence'])/'candidate-debugger-plan.json');assert plan['sha256']==b['binary_sha256']and plan['pdb_sha256']==b['pdb_sha256']and plan['guest_stop']==0x696f323
    assert pe.get_data(plan['stop_rva'],3).hex()==plan['stop_bytes']=='897e44'
    manifest=dict(version=1,kind='genuine',executable=exe.relative_to(W).as_posix(),sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],
        build_record=(O/'build.json').relative_to(W).as_posix(),build_record_sha256=core.sha(O/'build.json'),fixture_case=None,dependencies=q['candidate_dependencies'],
        sources={(O/'runtime'/n).relative_to(W).as_posix():h for n,h in b['runtime'].items()})
    core.validate_manifest(manifest,dict(scope=core.SCOPE))
    ledger=core.Ledger(W/'out/desktop-supervisor/ledger.jsonl');assert not any(x.get('sha256')==b['binary_sha256']for x in ledger.rows)
    core.atomic(O/'candidate-preview.json',manifest);core.atomic(O/'object-lineage.json',lineage);core.atomic(O/'debugger-plan.json',plan)
    core.atomic(O/'candidate-verification.json',dict(passed=True,compiled_runtime_objects=14,verified_unchanged_generated_objects=265,
        complete_source_object_link_lineage=True,pe_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],
        rsds_guid=str(uuid.UUID(bytes_le=guid)),pdb_age=age,pe_pdb_identity_matched=True,guest_stop='0x0696f323',native_stop_rva=hex(plan['stop_rva']),
        native_stop_preferred_va=hex(pe.OPTIONAL_HEADER.ImageBase+plan['stop_rva']),stop_bytes=plan['stop_bytes'],unconsumed=True,
        qualification_digest=core.digest(q),production_runtime_unchanged=True,genuine_launches=0))
    print('INDEPENDENT CANDIDATE/PE/PDB/LINEAGE VERIFICATION PASS',flush=True)

if __name__=='__main__':main()
