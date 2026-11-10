"""Independent lineage + PE/PDB and inert endpoint mapping; never launches PE."""
import sys,re,ctypes as C
from ctypes import wintypes as T
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    b=read(O/'build.json');lines=read(O/'object-lineage.json');exe,sha,pdb=identity()
    for folder,root in [('outputs',exe.parent),('runtime',RT),('generated',W/'experiments/xrt/gen')]:
        core.require(core.tree(root)==b[folder],'inventory changed: '+folder)
    objects={p for p in b['outputs'] if p.endswith('.obj')}
    core.require(set(lines)==objects and len(objects)==281,'complete object lineage')
    inherited=set();seen_objects=set()
    def check(rel,row,trail=frozenset()):
        core.require(core.sha(row['source'])==row['source_sha256'],'source changed')
        for name,digest in row.get('verified_local_headers',{}).items():core.require(core.sha(name)==digest,'header changed')
        cmd=row['command'];obj=next(s[3:] for s in cmd if s.startswith('/Fo'))
        core.require(core.sha(obj)==row['object_sha256'],'original compile output changed')
        if Path(row['source']).suffix=='.c':core.require('/fp:strict' in cmd and '/c' in cmd,'compile semantics')
        parent=row.get('inherited_from')
        if parent:
            core.require(parent not in trail,'lineage cycle');inherited.add(parent);old=read(parent)[rel]
            core.require(old['source_sha256']==row['source_sha256'] and old['object_sha256']==row['object_sha256'],'inherited lineage mismatch')
            check(rel,old,trail|{parent})
    for rel,row in lines.items():
        core.require(core.sha(exe.parent/rel)==row['object_sha256'],'linked object mismatch');check(rel,row)
    inputs=re.findall(r'"([^"]+\.obj)"',(exe.parent/'link-objects.rsp').read_text())
    core.require(len(inputs)==281 and {Path(p).relative_to(exe.parent).as_posix() for p in inputs}==objects,'exact link inputs')
    core.require(sum(bool(r.get('reused_in_this_candidate')) for r in lines.values())==265,'reuse counts')
    core.require(len(b['commands'])==17 and all(r['exit']==0 for r in b['commands']),'build commands')
    for p,digest in b['toolchain'].items():core.require(core.sha(p)==digest,'toolchain changed')
    core.require(core.sha(exe)==sha and core.sha(exe.with_suffix('.pdb'))==pdb,'PE/PDB hashes')
    m=load('monitor_identity',H.parent/'surface_transfer/identity.py');m.EXE=exe;m.SHA=sha;m.PDB=pdb;m.O=O
    deps=read(W/'out/recovery/renderer-gamma-integration-20261029-01/candidate-verification.json')['dependencies']
    for name,digest in deps.items():core.require(core.sha(core.independent(name))==digest,'dependency changed')
    save(O/'candidate-identity.json',dict(passed=True,executable=str(exe),sha256=sha,pdb_sha256=pdb,pe_pdb=m.pdb_identity(),
        objects=281,reused_generated_objects=265,compiled_runtime_objects=15,assembled_probe_objects=1,
        build_record_sha256=core.sha(O/'build.json'),object_lineage_sha256=core.sha(O/'object-lineage.json'),
        transitive_records={p:core.sha(p) for p in inherited},consumption=m.consumed(),dependencies=deps,toolchain=b['toolchain'],genuine_launches=0))
    # Reuse independent original-PE/translated-callsite disassembly, redirected.
    mapping=load('monitor_mapping',H.parent/'surface_transfer/mapping.py');mapping.H=H.parent/'surface_transfer';mapping.O=O;mapping.RT=RT
    mapping.identity=identity;mapping.legacy=legacy;mapping.main()
    l=legacy();api=l.D.api;dll=C.WinDLL('dbghelp',use_last_error=True);h=api(l.D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(dll,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202);core.require(api(dll,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(exe.parent),False),'symbols init')
    symbols={}
    try:
        base=api(dll,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(exe),None,0x140000000,0,None,0)
        core.require(base,'symbols load')
        for name in ('xm_probe','xm_emit','xm_pending','xm_committed','xm_failure','xm_init','xm_scope','xm_mark','xm_restore','xm_unwind','xm_current_cpu','xrt_fatal','d8_CreateDevice'):
            s=l.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            core.require(api(dll,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(l.D.Symbol)])(h,name.encode(),C.byref(s)),'monitor symbol '+name)
            symbols[name]=dict(rva=s.Address-base,size=s.Size)
    finally:api(dll,'SymCleanup',[T.HANDLE])(h)
    save(O/'monitor-linked.json',dict(passed=True,sha256=sha,pdb_sha256=pdb,symbols=symbols,
        typed_descriptor_sha256=core.sha(O/'typed-methods.json'),wrapper_source_sha256=core.sha(RT/'monitor_com.inc')))
    print('Independent 281-object lineage, PE/PDB, endpoint and linked monitoring PASS',flush=True)
if __name__=='__main__':main()
