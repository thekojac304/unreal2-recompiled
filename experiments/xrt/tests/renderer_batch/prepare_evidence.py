"""Build an additive evidence package. Original sources/delivery/results stay frozen.

Only explicit --contract-only and non-graphical smoke fixtures run in preparation.
"""
import json, shutil, sys
from pathlib import Path
sys.dont_write_bytecode=True
import desktop_batch as D
P=D.P
H=P.H
O=P.W/'out/recovery/renderer-evidence-20261029-03'

def replace(s,a,b):
    assert s.count(a)==1,('instrumentation anchor',a)
    return s.replace(a,b)

def instrument():
    src=O/'sources';src.mkdir(exist_ok=True)
    for name in ['evidence_fixture.h','evidence_native.cpp','evidence_smoke.c','evidence_dummy.c']:
        shutil.copy2(H/name,src/name)
    s=(H/'support.inc').read_text()
    s=replace(s,'void xrt_event(const char*k,const char*f,...){(void)k;(void)f;}',
        'void xrt_event(const char*k,const char*f,...){char b[16384];int n;va_list ap;va_start(ap,f);n=vsnprintf(b,sizeof b,f,ap);va_end(ap);if(n<0||n>=sizeof b)ev_die();ev_event(k,"%s",b);}')
    s=replace(s,'inside_adapter=1;dispatch(&cpu);inside_adapter=0;',
        'ev_event("adapter-enter","\\"site\\":%u,\\"slot\\":%u",batch_case->site,batch_case->slot);inside_adapter=1;dispatch(&cpu);inside_adapter=0;ev_event("adapter-leave","\\"site\\":%u,\\"slot\\":%u",batch_case->site,batch_case->slot);')
    (src/'support.inc').write_text(s)
    s=(H/'fixture.c').read_text()
    s=replace(s,'#include "support.inc"','#include "evidence_fixture.h"\n#include "support.inc"')
    s=replace(s,'bytes(out.post,512);puts("}");',
        'bytes(out.post,512);printf(",\\"regs\\":[");for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)out.regs[i]);printf("],\\"xmm\\":");bytes(out.xmm,160);puts("}");')
    s=replace(s,'graphics=emit_calls=1;', '''graphics=emit_calls=1;
    {D8Interface*q=NULL;D8Creation cp={0};D8Identifier id={0};D8Caps caps={0};ULONG add,balance,qr;HRESULT ph,ch,ih,caphr;
    add=fixture_device->vt->AddRef(fixture_device);balance=fixture_device->vt->Release(fixture_device);
    ph=fixture_device->vt->GetDirect3D(fixture_device,&q);qr=q?q->vt->Release(q):999;ch=fixture_device->vt->GetCreationParameters(fixture_device,&cp);
    printf("{\\"kind\\":\\"ownership\\",\\"add\\":%lu,\\"balance\\":%lu,\\"parent_hr\\":%lu,\\"same_parent\\":%s,\\"parent_release\\":%lu,\\"creation_hr\\":%lu,\\"same_window\\":%s,\\"flags\\":%lu}\\n",add,balance,(DWORD)ph,q==p?"true":"false",qr,(DWORD)ch,cp.focus==fixture_window?"true":"false",cp.flags);
    ih=p->vt->GetAdapterIdentifier(p,0,0,&id);caphr=p->vt->GetDeviceCaps(p,0,1,&caps);
    printf("{\\"kind\\":\\"adapter-identity\\",\\"hr\\":%lu,\\"vendor\\":%lu,\\"device\\":%lu,\\"subsystem\\":%lu,\\"revision\\":%lu,\\"caps_hr\\":%lu,\\"caps\\":[",(DWORD)ih,id.vendor,id.device,id.subsystem,id.revision,(DWORD)caphr);
    for(i=0;i<53;i++)printf("%s%lu",i?",":"",caps.words[i]);puts("]}");ev_backend_luid(dep);}
    ev_checkpoint("loaded");''')
    s=replace(s,'dr=fixture_device->vt->Release(fixture_device);pr=p->vt->Release(p);CHECK(dr==0&&pr==0);',
        'dr=fixture_device->vt->Release(fixture_device);pr=p->vt->Release(p);printf("{\\"kind\\":\\"release\\",\\"device_release\\":%lu,\\"parent_release\\":%lu}\\n",dr,pr);CHECK(dr==0&&pr==0);')
    s=replace(s,'DestroyWindow(fixture_window);UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(lib);FreeLibrary(dep);\n    printf',
        '''{BOOL destroy=DestroyWindow(fixture_window),unreg=UnregisterClassW(wc.lpszClassName,wc.hInstance),ul=FreeLibrary(lib),ud=FreeLibrary(dep);
    printf("{\\"kind\\":\\"lifecycle\\",\\"destroyed\\":%s,\\"unregistered\\":%s,\\"window_valid\\":%s,\\"free_d3d8\\":%s,\\"free_d3d9\\":%s,\\"d3d8_loaded\\":%s,\\"d3d9_loaded\\":%s}\\n",destroy?"true":"false",unreg?"true":"false",IsWindow(fixture_window)?"true":"false",ul?"true":"false",ud?"true":"false",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false");}
    ev_checkpoint("cleaned");
    printf''')
    s=replace(s,'if(argc!=2||strcmp(argv[1],"--contract-only"))return 2;', '''if(argc==2&&!strcmp(argv[1],"--abi-evidence")){
        emit_calls=1;ev_checkpoint("loaded");
        for(i=0;i<sizeof batch_cases/sizeof batch_cases[0];i++)if(batch_cases[i].group==BATCH_GROUP){
            batch_case=&batch_cases[i];for(j=0;j<4;j++)for(k=0;k<2;k++){host_result=S_OK;host_error=seeds[j];invoke(seeds[j]);}
        }
        CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));ev_checkpoint("cleaned");
        printf("{\\"kind\\":\\"abi-only-summary\\",\\"passed\\":true,\\"calls\\":%u,\\"graphics\\":false,\\"double_only\\":true}\\n",calls);return 0;
    }
    if(argc!=2||strcmp(argv[1],"--contract-only"))return 2;''')
    (src/'fixture.c').write_text(s)
    # The original state oracle is rebuilt with checkpoint additions only.
    s=(H.parent/'d3d8_state/native.c').read_text()
    s=replace(s,'#include "../../runtime/d3d8_device_abi.h"',f'#include "{(P.W/"experiments/xrt/runtime/d3d8_device_abi.h").as_posix()}"\n#include "evidence_fixture.h"')
    s=replace(s,' a.device=d;', ' ev_backend_luid(dep);ev_checkpoint("loaded");\n a.device=d;')
    s=replace(s,'callbacks,foreign);return 0;', 'callbacks,foreign);ev_checkpoint("cleaned");return 0;')
    (src/'preflight.c').write_text(s)

def inputs(paths):return {str(p):P.core.sha(p) for p in paths if p.is_file()}

def build():
    D.verify_bundle();O.mkdir(exist_ok=True)
    original=[P.O,P.W/'out/recovery/renderer-physical-batch-01',P.W/'out/recovery/renderer-physical-audit-20261029-01',
              P.W/'experiments/xrt/runtime',P.W/'experiments/xrt/gen',P.W/'tools/xrt/supervisor',P.core.HOME]
    if (O/'preservation.json').exists():preserve()
    else:P.core.atomic(O/'preservation.json',dict(trees={str(p):P.core.tree(p) for p in original},protected=P.A.verify(),
        old_delivery_sha256=P.core.sha(P.O/'delivery.json'),old_audit_source_sha256=P.core.sha(H/'audit_saved.py')))
    instrument();src=O/'sources';build=O/'build';build.mkdir(exist_ok=True);runs=[]
    rebuild_collector()
    for arch in ['x86','x64']:
        b=build/arch;b.mkdir(exist_ok=True)
        P.R.script(b,'smoke-build',arch,f'cl /nologo /LD /O1 /W3 /Fo"{b}/dummy.obj" /Fe"{b}/disposable.dll" "{src}/evidence_dummy.c" /link /IMPLIB:"{b}/dummy.lib" || exit /b 1\ncl /nologo /O1 /fp:strict /W3 /D_CRT_SECURE_NO_WARNINGS /Fo"{b}/smoke.obj" /Fe"{b}/smoke.exe" "{src}/evidence_smoke.c" user32.lib /link /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup || exit /b 1')
        P.core.atomic(b/'build-record.json',dict(arch=arch,fp='/fp:strict',inputs=inputs([src/'evidence_smoke.c',src/'evidence_fixture.h',src/'evidence_dummy.c']),outputs=inputs([b/'smoke.exe',b/'smoke.obj',b/'disposable.dll']),command=(b/'smoke-build.cmd').read_text(),graphics=False))
        d=build/('preflight-'+arch);d.mkdir(exist_ok=True)
        abi=P.PRIOR/'state-fixtures'/arch/'abi.obj'
        P.R.script(d,'build',arch,f'cl /nologo /O2 /fp:strict /W4 /D_CRT_SECURE_NO_WARNINGS /Fo"{d}/fixture.obj" /Fe"{d}/fixture.exe" "{src}/preflight.c" "{abi}" user32.lib /link /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup || exit /b 1')
        write_build(d,arch,False,0,[src/'preflight.c',src/'evidence_fixture.h',abi,P.W/'experiments/xrt/runtime/d3d8_device_abi.h'])
    for group in range(1,8):
        name=P.GROUPS[group];rt=P.O/'snapshots'/name/'runtime'
        for arch,translated in [('x86',False),('x64',False),('x86',True),('x64',True)]:
            d=build/f'{name}-{arch}-{"translated" if translated else "native"}';d.mkdir(exist_ok=True)
            abi=P.O/'fixtures'/arch/'abi.obj'
            P.R.script(d,'build',arch,f'cl /nologo /O1 /Gy /fp:strict /W4 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /DBATCH_TRANSLATED={int(translated)} /DBATCH_GROUP={group} /I"{rt}" /Fo"{d}/fixture.obj" /Fe"{d}/fixture.exe" "{src}/fixture.c" "{abi}" kernel32.lib user32.lib /link /OPT:REF /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup || exit /b 1')
            write_build(d,arch,translated,group,[src/'fixture.c',src/'support.inc',src/'evidence_fixture.h',abi,*rt.glob('*')])
            r=P.R.execute([d/'fixture.exe','--contract-only'],d,'contract',timeout=60)
            rows=[P.core.loads(line.encode()) for line in r.stdout.splitlines()]
            assert len(rows)==1 and rows[0]['passed'] and not rows[0]['graphics']
            runs.append(dict(rows[0],arch=arch,translated=translated))
    assert len(runs)==28
    for group in range(1,8):assert len({r['observations_hash'] for r in runs if r['group']==group})==1
    P.core.atomic(O/'contract-results.json',runs)
    toolchain()
    preserve()
    freeze()

def write_build(d,arch,translated,group,paths):
    P.core.atomic(d/'build-record.json',dict(arch=arch,translated=translated,group=group,fp='/fp:strict',
        inputs=inputs(paths),outputs=inputs([d/'fixture.exe',d/'fixture.obj']),command=(d/'build.cmd').read_text(),
        original_snapshot_sha256=P.core.sha(P.O/'snapshots'/P.GROUPS[group]/'snapshot.json') if group else None))

def preserve():
    p=P.core.read_large(O/'preservation.json')
    for path,tree in p['trees'].items():assert P.core.tree(Path(path))==tree,path
    assert P.A.verify()==p['protected'];D.verify_bundle()

def rebuild_collector():
    src=O/'sources';build=O/'build';shutil.copy2(H/'evidence_native.cpp',src/'evidence_native.cpp')
    P.R.script(build,'collector','x64',f'cl /nologo /LD /EHsc /O2 /W4 /Fo"{build}/collector.obj" /Fe"{build}/collector.dll" "{src}/evidence_native.cpp" dxgi.lib user32.lib advapi32.lib wtsapi32.lib psapi.lib version.lib /link /IMPLIB:"{build}/collector.lib" || exit /b 1')
    P.core.atomic(build/'collector-build-record.json',dict(inputs=inputs([src/'evidence_native.cpp']),outputs=inputs([build/'collector.dll',build/'collector.obj']),command=(build/'collector.cmd').read_text()))

def toolchain():
    for arch in ['x86','x64']:
        d=O/'build'/arch
        P.R.script(d,'toolchain',arch,'where cl\nwhere link')
        paths=[Path(s) for s in (d/'toolchain.stdout.txt').read_text().splitlines() if s.strip()]
        need=len(paths)>=2 and all(p.is_file() for p in paths);assert need,'toolchain paths missing'
        identity=inputs([*paths,Path(P.R.VC)])
        for record in (O/'build').glob('*/build-record.json'):
            data=P.core.read_large(record)
            if data['arch']==arch:data['toolchain']=identity;P.core.atomic(record,data)

def freeze():
    files={str(p):P.core.sha(p) for root in [O,H] for p in root.rglob('*') if p.is_file() and p.name!='evidence-delivery.json' and '__pycache__' not in p.parts}
    P.core.atomic(O/'evidence-delivery.json',dict(schema=2,files=files,graphics_executed=False,genuine_launches=0))

if __name__=='__main__':
    assert not sys.flags.optimize
    globals()[sys.argv[1]]()
