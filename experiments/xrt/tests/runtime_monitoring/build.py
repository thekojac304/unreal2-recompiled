"""Fresh candidate; all runtime TUs rebuilt, unchanged generated objects verified."""
import sys,uuid,shutil,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    b=read(PRIOR/'build.json');origin=read(PRIOR/'object-lineage.json');previous=Path(b['root'])
    core.require(core.tree(previous)==b['outputs'] and core.tree(W/'experiments/xrt/gen')==b['generated'],'prior build/generated inventory')
    target=W/'experiments/xrt/build/runtime-monitoring-20261030-01'/str(uuid.uuid4());target.mkdir(parents=True)
    logs=O/('build-'+str(uuid.uuid4()));logs.mkdir();h=helper(logs);env=h.env();lineage={};commands=[]
    (target/'obj/rt').mkdir(parents=True)
    for rel,row in origin.items():
        core.require(core.sha(previous/rel)==row['object_sha256'] and core.sha(row['source'])==row['source_sha256'],'inherited object/source')
        for name,digest in row.get('verified_local_headers',{}).items():core.require(core.sha(name)==digest,'inherited header')
        if rel.startswith('obj/rt/'):continue
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest)
        lineage[rel]=dict(row,reused=True,reused_in_this_candidate=True,inherited_from=str(PRIOR/'object-lineage.json'))
    names=[Path(rel).stem for rel in origin if rel.startswith('obj/rt/')]+['monitor']
    for name in names:
        src=RT/(name+'.c');obj=target/('obj/rt/'+name+'.obj')
        cmd=['cl','/nologo','/c','/std:c11','/O2','/Zi','/fp:strict','/W4','/wd4100','/wd4201','/wd4127','/wd4324','/D_CRT_SECURE_NO_WARNINGS','/DXRT_WITH_UNREAL2','/showIncludes',f'/I{RT}',f'/Fo{obj}',f'/Fd{target}/obj/rt/runtime.pdb',src]
        h.run(cmd,name,environment=env,timeout=120);receipt=read(logs/(name+'.json'));commands.append(receipt)
        # Record exactly the workspace include files actually observed by compiler.
        text=(logs/(name+'.stdout.txt')).read_text();headers={}
        for line in text.splitlines():
            if 'including file:' in line:
                p=Path(line.split('including file:',1)[1].strip())
                if p.is_relative_to(W):headers[str(p)]=core.sha(p)
        lineage[obj.relative_to(target).as_posix()]=dict(source=str(src),source_sha256=core.sha(src),object_sha256=core.sha(obj),
            command=receipt['command'],verified_local_headers=headers,reused=False,reused_in_this_candidate=False,compile_receipt=str(logs/(name+'.json')))
    src=RT/'monitor.asm';obj=target/'obj/rt/monitor_asm.obj'
    h.run(['ml64','/nologo','/c','/Zi',f'/Fo{obj}',src],'monitor_asm',environment=env)
    receipt=read(logs/'monitor_asm.json');commands.append(receipt)
    lineage['obj/rt/monitor_asm.obj']=dict(source=str(src),source_sha256=core.sha(src),object_sha256=core.sha(obj),command=receipt['command'],
        reused=False,reused_in_this_candidate=False,verified_local_headers={})
    rsp='\n'.join('"'+str(target/p)+'"' for p in sorted(lineage))+'\n';(target/'link-objects.rsp').write_text(rsp)
    link=[s.replace(str(previous),str(target)) for s in b['commands'][-1]['command']]
    h.run(link,'link',environment=env,cwd=W/'experiments/xrt',timeout=180);commands.append(read(logs/'link.json'))
    toolchain=dict(b['toolchain']);toolchain[receipt['command'][0]]=core.sha(receipt['command'][0])
    save(O/'object-lineage.json',lineage)
    save(O/'build.json',dict(passed=True,root=str(target),outputs=core.tree(target),runtime_root=str(RT),runtime=core.tree(RT),
        generated=b['generated'],binary_sha256=core.sha(target/'xrt_ucc.exe'),pdb_sha256=core.sha(target/'xrt_ucc.pdb'),
        commands=commands,compiled_objects=len(names)+1,reused_objects=len(origin)-14,inherited_build=str(PRIOR/'build.json'),
        inherited_build_sha256=core.sha(PRIOR/'build.json'),toolchain=toolchain,gamma_profile=b['gamma_profile'],
        genuine_launches=0,execution_authorized=False))
    print('Fresh unlaunched candidate',target,flush=True)
if __name__=='__main__':main()
