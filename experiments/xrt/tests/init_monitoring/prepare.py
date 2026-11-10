"""Preserve inputs and independently verify the unchanged sealed candidate."""
import sys, shutil, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def preserved_roots():
    return [SEALED, W/'out/recovery/resource-functional-assessment-20261030-01',
            W/'out/recovery/physical-integrated-20261030-01',
            W/'out/recovery/surface-transfer-20261030-01',
            W/'tools/xrt/supervisor', W/'out/desktop-supervisor',
            W/'out/desktop-fixtures', W/'experiments/xrt/runtime',
            H.parent/'integrated_candidate', H.parent/'semantic_compat']

def stage():
    O.mkdir(exist_ok=True)
    core.require(not (O/'preservation-before.json').exists(),'baseline already exists')
    save(O/'preservation-before.json', dict(trees={str(p):preserved_tree(p) for p in preserved_roots()},
                                           lock_exclusion='Only supervisor.lock: open by running fixture service; not read, opened for writing, or changed.',
                                           protected=A.verify()))
    for name in ('build.json', 'object-lineage.json'):
        shutil.copy2(SEALED/name, O/name)
    # Inventory all earlier recovery evidence, including consumed candidates,
    # without rewriting or copying executable bytes. Hashes above cover the
    # current candidates/policies; immutable-file metadata detects older writes.
    prior = {}
    for p in (W/'out/recovery').rglob('*'):
        if p.is_file() and not p.is_relative_to(O):
            s=p.stat();prior[str(p)]=[s.st_size,s.st_mtime_ns]
    save(O/'historical-inventory.json', prior)
    print('Preservation baseline saved', flush=True)

def preserved_tree(root):
    return {p.relative_to(root).as_posix():core.sha(core.independent(p))
            for p in root.rglob('*') if p.is_file() and p.name!='supervisor.lock' and '__pycache__' not in p.parts}

def verify():
    m=load('init_monitoring_identity', H.parent/'integrated_candidate/identity.py')
    m.EXE,m.SHA,m.PDB=identity()
    save(O/'candidate-identity.json',m.verify())
    m=load('init_monitoring_mapping', H.parent/'integrated_candidate/mapping.py')
    m.H=H.parent/'integrated_candidate'
    m.main()
    # Resolve additional observation-only symbols independently from the PDB.
    import ctypes as C
    from ctypes import wintypes as T
    l=legacy();api=l.D.api;dll=C.WinDLL('dbghelp',use_last_error=True)
    h=api(l.D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(dll,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    assert api(dll,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(identity()[0].parent),False)
    plan=read(O/'stop-mapping.json')
    try:
        base=api(dll,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(identity()[0]),None,0x140000000,0,None,0)
        assert base
        for name in ('d8_semantic_checkpoint','d8_resources','d8_resource_used','d8_locks','did_lifecycle_frame','gui_diagnostic_ingress'):
            s=l.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            assert api(dll,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(l.D.Symbol)])(h,name.encode(),C.byref(s)),name
            plan['symbols'][name]=dict(rva=s.Address-base,size=s.Size)
    finally:
        assert api(dll,'SymCleanup',[T.HANDLE])(h)
    save(O/'composed-mapping.json',plan)
    print('PE/PDB, 279 objects, 60 bindings and observation symbols verified',flush=True)

def preservation():
    baseline=read(O/'preservation-before.json')
    content_changes=[]
    for root,tree in baseline['trees'].items():
        actual=preserved_tree(Path(root))
        content_changes += [dict(path=str(Path(root)/p),before=tree.get(p),after=actual.get(p))
                            for p in tree.keys()|actual.keys() if tree.get(p)!=actual.get(p)]
    metadata_changes=[]
    for p,state in read(O/'historical-inventory.json').items():
        path=Path(p)
        actual=[path.stat().st_size,path.stat().st_mtime_ns] if path.exists() else None
        if actual!=state:metadata_changes.append(dict(path=p,before=state,after=actual))
    audit=dict(content_changes=content_changes,metadata_changes=metadata_changes,exact_snapshot_unchanged=False)
    save(O/('preservation-audit-'+str(uuid.uuid4())+'.json'),audit)
    # Never backdate or restore a service-owned file. Explicitly retain this
    # imperfect metadata preservation and all earlier receipts/digests.
    status=str(W/'out/desktop-fixtures/status.json')
    core.require(all(r['path']==status for r in content_changes),'historical content/policy change')
    allowed={str(W/'out/recovery/resource-functional-assessment-20261030-01'/n)
             for n in ('assessment-tests.json','monitor-coverage.json','reader-crosscheck.json')}
    core.require({r['path'] for r in metadata_changes}<=allowed,'unexpected historical metadata change')
    for r in metadata_changes:
        p=Path(r['path']);original=baseline['trees'][str(p.parent)][p.name]
        core.require(core.sha(p)==original,'historical receipt content changed')
        r.update(content_sha256=original,content_unchanged=True,
                 cause='Retained verify.py __main__ rewrote identical JSON; runner corrected to import tests only. Timestamps not restored.')
    core.require(A.verify()==baseline['protected'],'protected asset identity')
    save(O/'preservation-after.json',dict(passed=True,scope='Protected contents/ledgers/candidate; audited timestamp/status exceptions, not an exact metadata snapshot.',
        exact_snapshot_unchanged=not content_changes and not metadata_changes,
        historical_content_unchanged=True,status_updates=content_changes,metadata_changes=metadata_changes,protected=baseline['protected'],
        historical_files=len(read(O/'historical-inventory.json')),genuine_launches=0,physical_launches=0))
    print('Historical contents, ledgers, runtime, installation and saves match; status/timestamp exceptions recorded',flush=True)

if __name__=='__main__':
    assert sys.argv[1] in ('stage','verify','preservation')
    globals()[sys.argv[1]]()
