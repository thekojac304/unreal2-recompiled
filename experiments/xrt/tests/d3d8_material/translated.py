"""Staged typed bridge and disposable fixtures; production runtime unchanged."""
import json,os,re,shutil,struct,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
H,W,O,RT,R=P.H,P.W,P.O,P.RT,P.R
B=O/'fixtures-v4'

def stage():
    assert P.read(O/'native-audit.json')['passed']
    p=RT/'d3d8_device_abi.h';s=p.read_text().replace('typedef struct D8DeviceVtable {','typedef struct D8Material { float diffuse[4],ambient[4],specular[4],emissive[4],power; } D8Material;\n\ntypedef struct D8DeviceVtable {')
    s=s.replace('void* unsupported37_49[13];','void* unsupported37_41[5];\n    HRESULT (WINAPI *SetMaterial)(D8Device*,const D8Material*);\n    void* unsupported43_49[7];')
    s=s.replace('#endif','typedef char d8_material_size[sizeof(D8Material)==68?1:-1];\ntypedef char d8_material_power[offsetof(D8Material,power)==64?1:-1];\ntypedef char d8_material_slot[offsetof(D8DeviceVtable,SetMaterial)==42*sizeof(void*)?1:-1];\n#endif');p.write_text(s)
    p=RT/'d3d8_device_slots.inc';s=p.read_text();s,n=re.subn(r'^static void d8_device_SetMaterial[^\n]*\n','',s,flags=re.M);assert n==1;p.write_text(s)
    bridge='''/* One original SetRes material tuple, independently measured on pinned DXVK.
 * Copy the complete readable input before native entry; never pass guest memory. */
static void d8_device_SetMaterial(CPU*c) {
    static const uint32_t measured[17]={0x3f000000,0x3f000000,0x3f000000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0,0,0,0,0,0,0,0,0};
    D8DeviceObject*o=d8_device_object(c,ARG(0));
    uint32_t material=ARG(1),esp=c->r[ESP],ret=rd32(esp);
    D8Material n;HRESULT hr;DWORD error,before,after;CPU*previous;
    d8_device_memory(c,material,sizeof n,0);memcpy(&n,G2H(material),sizeof n);
    if(memcmp(&n,measured,sizeof n))
        xrt_fatal(c,76,"IDirect3DDevice8::SetMaterial: unsupported material tuple (native call refused)");
    d8_render_ready(c,o);
    xrt_event("d3d8_material_call","\\"method\\":\\"SetMaterial\\",\\"slot\\":42,\\"this\\":%u,\\"material\\":%u,\\"bytes\\":68,\\"esp\\":%u,\\"return\\":%u",o->guest,material,esp,ret);
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));before=_mm_getcsr();
    hr=o->host->vt->SetMaterial(o->host,&n);error=GetLastError();after=_mm_getcsr();
    d8_rendering=0;xrt_gui_callback_leave(previous);
    xrt_set_last_error(c,error);RET_STD(2,hr);
    xrt_event("d3d8_material_return","\\"method\\":\\"SetMaterial\\",\\"this\\":%u,\\"result\\":%lu,\\"last_error\\":%lu,\\"esp_before\\":%u,\\"esp_after\\":%u,\\"return\\":%u,\\"actual_return\\":%u,\\"mxcsr_before\\":%lu,\\"mxcsr_after\\":%lu",o->guest,(DWORD)hr,error,esp,c->r[ESP],ret,c->rv,before,after);
}
'''
    p=RT/'hle_d3d8_device.inc';s=p.read_text();assert s.count('#include "d3d8_device_slots.inc"')==1;p.write_text(s.replace('#include "d3d8_device_slots.inc"',bridge+'#include "d3d8_device_slots.inc"'))
    # Keep a concise, reviewable patch separate from the active source tree.
    import difflib
    patch=''
    for name in ['d3d8_device_abi.h','d3d8_device_slots.inc','hle_d3d8_device.inc']:
        patch+=''.join(difflib.unified_diff((W/'experiments/xrt/runtime'/name).read_text().splitlines(True),(RT/name).read_text().splitlines(True),fromfile='runtime/'+name,tofile='staged/runtime/'+name))
    (O/'runtime.patch').write_text(patch)
    P.save('staged-runtime.json',dict(files=P.core.tree(RT),genuine_launches=0,active_runtime_changed=False))

def probe_source():
    s=(H.parent/'d3d8_state/probe.c').read_text()
    s=s.replace('#include "../../runtime/d3d8_device_abi.h"','#include "'+str(RT/'d3d8_device_abi.h').replace('\\','/')+'"')
    s=s.replace('typedef HRESULT(WINAPI*SetFn)(D8Device*,DWORD,DWORD);','typedef HRESULT(WINAPI*SetFn)(D8Device*,const D8Material*);\nstatic DWORD words[17]={0x3f000000,0x3f000000,0x3f000000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0,0,0,0,0,0,0,0,0};\nstatic const D8Material*mat=(const D8Material*)words;')
    s=s.replace('((SetFn)(*(void***)d)[50])(d,STATE_TARGET,VALUE_TARGET)','((SetFn)(*(void***)d)[42])(d,mat)')
    s=s.replace('HRESULT __cdecl bridge_abi(D8Device*,DWORD,DWORD);','HRESULT __cdecl bridge_abi(D8Device*,const D8Material*);')
    s=s.replace('set=(SetFn)(*(void***)d)[50]','set=(SetFn)(*(void***)d)[42]').replace('set=(SetFn)(*(void***)d)[51]','set=(SetFn)(*(void***)d)[43]')
    s=s.replace('static D8Device*d;', '__declspec(dllexport)DWORD probe_pages;\nstatic D8Device*d;')
    s=s.replace('for(i=0;i<4;i++){','''if(probe_case==1)memset(words,0,sizeof words);
 if(probe_case==2)mat=NULL;
 if(probe_case==3)mat=(const D8Material*)1;
 if(probe_case==4||probe_case==5||probe_case==6){DWORD old;BYTE*pages=probe_pages?(BYTE*)probe_pages:VirtualAlloc(NULL,8192,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!pages)return 8;if(!probe_pages){memcpy(pages+4096-64,words,68);if(!VirtualProtect(pages+4096,4096,probe_case==4?PAGE_NOACCESS:probe_case==5?PAGE_READONLY:PAGE_READWRITE|PAGE_GUARD,&old))return 9;}mat=(const D8Material*)(pages+4096-64);}
 if(probe_case==7)mat=(const D8Material*)0x25000000;
 if(probe_case==8)words[16]=1;
 if(probe_case==9)words[16]=0x7fc00000;
 if(probe_case==10)words[8]=0x80000000;
 for(i=0;i<4;i++){''')
    s=s.replace('hr=set(thisdev,state,value)','hr=set(thisdev,mat)').replace('hr=bridge_abi(thisdev,state,value)','hr=bridge_abi(thisdev,mat)')
    (B/'probe.c').write_text(s)

def observed_source(d):
    s=(RT/'hle_d3d8_device.inc').read_text().replace('#include <xmmintrin.h>','#include <xmmintrin.h>\n#include <stdio.h>')
    call='hr=o->host->vt->SetMaterial(o->host,&n);error=GetLastError();after=_mm_getcsr();'
    hook='''{
 CPU saved=*c;BYTE frame[12],input[68];DWORD saved_error=GetLastError(),saved_mx=_mm_getcsr();unsigned i;static unsigned ordinal;HRESULT sh;D8Material got,zero={0};typedef HRESULT(WINAPI*GetFn)(D8Device*,D8Material*);GetFn get=(GetFn)(*(void***)o->host)[43];char mode[8]={0};
 memcpy(frame,G2H(esp),12);memcpy(input,G2H(material),68);GetEnvironmentVariableA("XRT_STATE_CALLBACKS",mode,sizeof mode);
 if(!ordinal)o->host->vt->SetMaterial(o->host,&zero);
 if(mode[0]=='1')SendMessageW((HWND)xrt_gui_device_window(c,o->window),WM_GETICON,0,0);
 if(memcmp(&saved,c,sizeof saved)||memcmp(frame,G2H(esp),12))xrt_fatal(c,77,"test pre-native CPU/frame changed");
 xrt_event("test_native_enter","\\"method\\":\\"SetMaterial\\",\\"ordinal\\":%u",ordinal);
 _mm_setcsr(saved_mx);SetLastError(saved_error);
 NATIVE_CALL
 xrt_event("test_native_leave","\\"method\\":\\"SetMaterial\\",\\"ordinal\\":%u,\\"result\\":%lu,\\"last_error\\":%lu",ordinal,(DWORD)hr,error);
 if(mode[0]=='1')SendMessageW((HWND)xrt_gui_device_window(c,o->window),WM_GETICON,0,0);
 if(memcmp(&saved,c,sizeof saved)||memcmp(frame,G2H(esp),12)||memcmp(input,G2H(material),68))xrt_fatal(c,77,"test post-native CPU/frame/input changed");
 sh=get(o->host,&got);printf("{\\"kind\\":\\"material\\",\\"ordinal\\":%u,\\"hr\\":%lu,\\"words\\":[",++ordinal,(DWORD)sh);for(i=0;i<17;i++){DWORD v;memcpy(&v,(BYTE*)&got+i*4,4);printf("%s%lu",i?",":"",v);}puts("]}");
 xrt_event("test_suspended_material_cpu","\\"all_cpu_bytes\\":true,\\"frame_bytes\\":12,\\"input_bytes\\":68,\\"ordinal\\":%u",ordinal);
 _mm_setcsr(after);SetLastError(error);
 }'''.replace('NATIVE_CALL',call)
    assert s.count(call)==1;s=s.replace(call,hook)
    (d/'hle_d3d8_device.inc').write_text(s)
    s=(RT/'hle_d3d8.inc').read_text().replace('#include "hle_d3d8_device.inc"','#include "'+str(d/'hle_d3d8_device.inc').replace('\\','/')+'"');(d/'hle_d3d8.inc').write_text(s)
    s=(RT/'hle_misc.c').read_text().replace('#include "hle_d3d8.inc"','#include "'+str(d/'hle_d3d8.inc').replace('\\','/')+'"');p=d/'hle_misc.c';p.write_text(s);return p

def build():
    B.mkdir()
    for arch in ['x86','x64']:shutil.copytree(O/'fixtures'/arch,B/arch)
    probe_source()
    for arch in ['x86','x64']:
        d=B/arch;asm=''
        if arch=='x86':
            s=(H.parent/'d3d8_render/abi32.asm').read_text().replace('    fld QWORD PTR onehalf','    fld QWORD PTR onehalf\n    ftst');start=s.index('    cmp DWORD PTR [ecx+24],0');end=s.index('done:',start)
            (d/'guestabi.asm').write_text(s[:start]+'    push DWORD PTR [ecx+24]\n    push eax\n    mov edx,[eax]\n    call DWORD PTR [edx+168]\n'+s[end:]);asm=f'ml /nologo /c /Fo"{d}/guestabi.obj" "{d}/guestabi.asm" || exit /b 1\n'
        R.script(B,'client-build-'+arch,arch,f'lib /nologo /def:"{H.parent}/d3d8_boundary/d3d8.def" /machine:{"X86"if arch=="x86"else"X64"} /out:"{d}/d3d8.lib" || exit /b 1\n'+asm+f'cl /nologo /c /O2 '+('/arch:IA32 'if arch=='x86'else'')+f'/GS- /W4 /Fo"{d}/probe.obj" "{B}/probe.c" || exit /b 1\nlink /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:{"0x12000000"if arch=="x86"else"0x180000000"} /DYNAMICBASE:NO /OUT:"{d}/d3dprobe.dll" "{d}/probe.obj" '+(f'"{d}/guestabi.obj" /alternatename:__imp__Direct3DCreate8@4=__imp__Direct3DCreate8 'if arch=='x86'else'')+f'"{d}/d3d8.lib" kernel32.lib user32.lib || exit /b 1\ncl /nologo /O2 /W4 /Fo"{d}/native_client.obj" /Fe"{d}/native_client.exe" "{H.parent}/d3d8_render/native_client.c" || exit /b 1')
    R.execute([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',B/'x86/d3dprobe.dll','--out',B/'gen'],B,'lift-material')
    sources=['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    host=(H.parent/'d3d8_render/host.c').read_text().replace('#include "../d3d8_boundary/host.c"','#include "'+str(H.parent/'d3d8_boundary/host.c').replace('\\','/')+'"')
    host=host.replace(' _mm_setcsr(0x3f80);', ''' if(atoi(argv[3])>=4&&atoi(argv[3])<=6){DWORD old,words[17]={0x3f000000,0x3f000000,0x3f000000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0,0,0,0,0,0,0,0,0};xrt_commit(0x25000000,8192);memcpy(G2H(0x25001000-64),words,68);wr32(xrt_module_export(m,"probe_pages",0),0x25000000);if(!VirtualProtect(G2H(0x25001000),4096,atoi(argv[3])==4?PAGE_NOACCESS:atoi(argv[3])==5?PAGE_READONLY:PAGE_READWRITE|PAGE_GUARD,&old))return 2;}
 _mm_setcsr(0x3f80);''')
    (B/'host.c').write_text(host)
    for variant in ['production','observed']:
        d=B/variant;d.mkdir();misc=RT/'hle_misc.c'if variant=='production'else observed_source(d)
        inputs=[B/'host.c',*(RT/p if p!='hle_misc.c'else misc for p in sources),H.parent/'common/xrt_test_stubs.c']
        R.script(B,'translated-build-'+variant,'x64',f'cl /nologo /O1 /Zi /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"{RT}" /Fo"{d}\\\\" /Fd"{d}/compile.pdb" /Fe"{d}/translated.exe" '+' '.join('"'+str(p)+'"'for p in inputs)+f' "{B}/gen/*.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib /link /DEBUG /PDB:"{d}/translated.pdb" /STACK:0x10000000 || exit /b 1')

def run():
    driver=P.load('material_reused_state_driver',H.parent/'d3d8_state/run.py');runs=[]
    def add(arch,case,seed=18,variant='production',inject=0,expected=0):
        r=driver.one(B,arch,case,0,seed,variant,inject,expected);runs.append(r);R.save(B/'translated-results.json',runs)
    for arch in ['x86','x64','translated']:
        for seed in [18,0,0x13572468,0xffffffff]:add(arch,0,seed)
        add(arch,5)
    add('translated',0,variant='observed');add('translated',0,variant='observed',inject=1)
    add('translated',253)
    for c in list(range(1,5))+list(range(6,11))+[250,251,252,254,256]:add('translated',c,expected=76)
    for c in [70,71,72]:add('translated',c,variant='observed',inject=1,expected=76)

def audit():
    runs=P.read(B/'translated-results.json')
    def log(r):return list(map(int,re.search(r'returned 0 log([^\n]*)',r['stdout'])[1].split()))
    def abi(r):return list(map(int,re.search(r'abi_clear([^\n]*)',r['stdout'])[1].split()))
    for case,seed in [(0,18),(0,0),(0,0x13572468),(0,0xffffffff),(5,18)]:
        group=[r for r in runs if r['state']==case and r['seed']==seed and r['variant']=='production'];assert len(group)==3
        assert len({tuple(log(r))for r in group})==1
        x86=next(r for r in group if r['arch']=='x86');tr=next(r for r in group if r['arch']=='translated');assert abi(x86)[1:]==abi(tr)[1:]
        a=abi(tr);assert a[2:8]==[0,0,0x12345678,0x23456789,0x3456789a,0x456789ab] and a[1]==a[8]
    for r in runs:
        if r['arch']!='translated':continue
        ev=r['events'];calls=[e for e in ev if e['kind']=='d3d8_material_call'];rets=[e for e in ev if e['kind']=='d3d8_material_return'];case=r['state']
        if r['exit']==0:
            assert len(calls)==len(rets)==4
            for c,t in zip(calls,rets):assert c['slot']==42 and c['this']==t['this'] and t['result']==0 and t['last_error']==r['seed'] and t['esp_after']==c['esp']+12 and t['actual_return']==c['return'] and t['mxcsr_before']==t['mxcsr_after']
            if r['variant']=='observed':
                assert len([e for e in ev if e['kind']=='test_suspended_material_cpu'])==4
                assert all(x['words']==P.read(O/'guest-disassembly.json')['material_words'] and x['hr']==0 for x in r['observations']if x['kind']=='material')
                en=[e['seq']for e in ev if e['kind']=='test_native_enter'];le=[e['seq']for e in ev if e['kind']=='test_native_leave'];assert len(en)==len(le)==4
                assert not[e for e in ev if 'callback'in e['kind']and any(a<e['seq']<b for a,b in zip(en,le))]
                if r['inject']:assert log(r)[-13]==16
        else:
            assert r['exit']==76 and not rets and not[e for e in ev if e['kind']=='test_native_enter']
            fatal=next(e['message']for e in ev if e['kind']=='fatal')
            if case in [70,71,72]:
                assert {70:'Release during native rendering',71:'reentrant rendering',72:'live D3D8 device retains'}[case]in fatal
                assert any(e['kind']=='d3d8_failure_containment'for e in ev)and not any(e['kind']=='d3d8_unload'for e in ev)
            else:assert not calls
        if case not in [70,71,72]:
            assert next(e for e in ev if e['kind']=='d3d8_device_cleanup')['final_native_count']==0
            u=next(e for e in ev if e['kind']=='d3d8_unload');assert not u['d3d8_loaded']and not u['d3d9_loaded']
    assert (RT/'d3d8_device_slots.inc').read_text().count('unsupported slot ')==88
    P.save('translated-audit.json',dict(passed=True,processes=len(runs),positive_native_translated_logs_abi_equal=True,
        read_only_cross_page_input=True,invalid_unreadable_guarded_cross_page_null_and_tuple_inputs_refused=True,
        unknown_stale_null_wrong_type_device_refused=True,getmaterial_still_unsupported=True,
        callback_suspended_cpu_frame_input_preserved=True,native_readback_exact=True,forced_nested_callbacks=16,
        release_reentrant_destroy_guards_preserved=True,parent_first_lifetime=True,cleanup=True,genuine_launches=0))
    print('TRANSLATED MATERIAL DIFFERENTIAL PASS',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
