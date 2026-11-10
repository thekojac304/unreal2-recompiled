"""Stage and build one isolated runtime; never runs its game entry point."""
import difflib
import shutil
import uuid
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def stage():
    O.mkdir()
    roots=[PRIOR,W/'experiments/xrt/runtime',W/'experiments/xrt/gen',W/'tools/xrt/supervisor',core.HOME,
           W/'out/recovery/renderer-acceptance-20261029-01',W/'out/recovery/renderer-gamma-integration-20261029-01']
    save(O/'preservation.json',dict(trees={str(p):core.tree(p) for p in roots},protected=A.verify(),genuine_launches=0))
    refresh()

def refresh():
    shutil.copytree(PRIOR/'runtime',RT,dirs_exist_ok=True)
    for name in ('semantic_policy.h','semantic_evidence.inc','semantic_renderer.inc','semantic_clear.inc','semantic_create.inc','semantic_parent.inc'):
        shutil.copy2(H/name,RT/name)
    p=RT/'hle_d3d8_device.inc';t=p.read_text()
    t=t.replace('D8Object* parent;','D8Object* parent;\n    D8Caps caps;int caps_valid;\n    unsigned width,height,depth,depthformat,behavior;')
    anchor='/* A writable Windows page'
    t=t.replace(anchor,'#include "semantic_evidence.inc"\n\n'+anchor)
    start=t.index('/* Exact genuine scalar tuples only.')
    end=t.index('#include "d3d8_device_slots.inc"',start)
    t=t[:start]+'#include "semantic_renderer.inc"\n'+t[end:]
    # Callers already resolve both same-process, same-thread pinned windows.
    t=t.replace('!o->focus || !o->window || o->focus!=o->window','!o->window')
    # Guard every device argument frame BEFORE ARG/return-address dereferences.
    import re
    methods={'QueryInterface':(0,3),'AddRef':(1,1),'Release':(2,1),'GetDirect3D':(6,2),'GetCreationParameters':(9,2),'Clear':(36,7),'Present':(15,5)}
    for method,(slot,n) in methods.items():
        t=t.replace('static void d8_device_'+method+'(CPU*c) {','static void d8_device_'+method+'(CPU*c) {\n    d8_api_entry(c,'+str(slot)+','+str(n)+');')
    t=t.replace('static void d8_CreateDevice(CPU*c) {','static void d8_CreateDevice(CPU*c) {\n    d8_api_entry(c,100,7);')
    t=t.replace('    d8_api_entry(c,100,7);','    d8_api_entry(c,100,7);\n    if(d8_creating || d8_rendering)xrt_fatal(c,76,"SAFETY: reentrant CreateDevice");')
    t=t.replace('hr=parent->vt->CreateDevice(parent,adapter,type,focus_host,flags,&n,&host);error=GetLastError();mxcsr_after=_mm_getcsr();',
        'd8_semantic_checkpoint(c,1,100,&n,sizeof n,0,xrt_get_last_error(c));\n        SetLastError(xrt_get_last_error(c));\n        hr=parent->vt->CreateDevice(parent,adapter,type,focus_host,flags,&n,&host);error=GetLastError();mxcsr_after=_mm_getcsr();\n        d8_semantic_checkpoint(c,2,100,&n,sizeof n,(unsigned)hr,error);')
    t=t.replace('wr32(out,o->refs?o->guest:0);xrt_set_last_error(c,error);RET_STD(7,hr);',
        'wr32(out,o->refs?o->guest:0);xrt_set_last_error(c,error);RET_STD(7,hr);\n    d8_semantic_checkpoint(c,3,100,&n,sizeof n,(unsigned)hr,error);')
    t=t.replace('hr=o->host->vt->Present(o->host,NULL,NULL,NULL,NULL);error=GetLastError();after=_mm_getcsr();',
        'd8_semantic_checkpoint(c,1,15,NULL,0,0,xrt_get_last_error(c));SetLastError(xrt_get_last_error(c));\n    hr=o->host->vt->Present(o->host,NULL,NULL,NULL,NULL);error=GetLastError();after=_mm_getcsr();\n    d8_semantic_checkpoint(c,2,15,NULL,0,(unsigned)hr,error);')
    t=t.replace('xrt_set_last_error(c,error);RET_STD(5,hr);',
        'xrt_set_last_error(c,error);RET_STD(5,hr);\n    d8_semantic_checkpoint(c,3,15,NULL,0,(unsigned)hr,error);')
    # Keep the measured windowed HAL/presentation backend and process-once scope.
    # Width and height are ordinary scalar dimensions, not a 1540x945 contract.
    t=t.replace('rd32(pp)!=1540 || rd32(pp+4)!=945','!rd32(pp) || !rd32(pp+4) || rd32(pp)>16384 || rd32(pp+4)>16384')
    # The dimension ceiling is replaced below by queried hardware caps.
    t=t.replace(' || rd32(pp)>16384 || rd32(pp+4)>16384','')
    before='    window=rd32(pp+24);memset(&n,0,sizeof n);'
    validation='''    { D8Caps caps; HRESULT caphr;DWORD saved=GetLastError();
      caphr=p->host->vt->GetDeviceCaps(p->host,adapter,type,&caps);SetLastError(saved);
      d8_evidence_blob(0,"creation_caps",&caps,sizeof caps);
      if(FAILED(caphr) || rd32(pp)>caps.words[22] || rd32(pp+4)>caps.words[23])
          xrt_fatal(c,76,"CreateDevice dimensions exceed live capabilities or query failed"); }
'''
    assert before in t;t=t.replace(before,validation+before)
    begin=t.index('    if(adapter!=0 || type!=1 || flags!=0x42')
    finish=t.index('    window=rd32(pp+24);memset(&n,0,sizeof n);',begin)
    t=t[:begin]+'    if(!focus && !rd32(pp+24))xrt_fatal(c,76,"SAFETY: CreateDevice requires an owned presentation/focus window");\n    d8_creation_domain(c,p,adapter,type,flags,pp);\n'+t[finish:]
    start=t.index('static void d8_device_Clear(CPU*c) {')
    end=t.index('static void d8_device_Present(CPU*c)',start)
    t=t[:start]+t[end:]
    t=t.replace('#include "semantic_renderer.inc"','#include "semantic_renderer.inc"\n#include "semantic_clear.inc"')
    t=t.replace('#include "semantic_clear.inc"','#include "semantic_clear.inc"\n#include "semantic_create.inc"')
    t=t.replace('D8Caps caps; HRESULT caphr;DWORD saved=GetLastError();','D8Caps caps={0}; HRESULT caphr;DWORD saved=GetLastError();')
    t=t.replace('o->parent=p;o->focus=focus;o->window=window;', 'o->parent=p;o->focus=focus;o->window=window;\n        o->width=n.width;o->height=n.height;o->depth=n.depth;o->depthformat=n.depthformat;o->behavior=flags;')
    t=t.replace('n.window=xrt_gui_device_window(c,window);','n.window=window?xrt_gui_device_window(c,window):NULL;')
    t=t.replace('o->window=window;', 'o->window=window?window:focus;')
    t=t.replace('xrt_gui_window_pin(c,focus);xrt_gui_window_pin(c,window);','xrt_gui_window_pin(c,focus);xrt_gui_window_pin(c,o->window);')
    p.write_text(t)
    # Parent query outputs must check page protection, not just commitment.
    p=RT/'hle_d3d8.inc';t=p.read_text()
    t=t.replace('#include "d3d8_abi.h"','#include "d3d8_abi.h"\nstatic void d8_device_memory(CPU*,uint32_t,uint32_t,int);\nstatic LONG d8_api_entry(CPU*,unsigned,unsigned);')
    t=t.replace('com_memory(c,ARG(1),16,"Direct3D8")','d8_device_memory(c,ARG(1),16,0)')
    t=re.sub(r'com_memory\(c,([^,]+),([^,]+),"Direct3D8[^"\n]*"\)',r'd8_device_memory(c,\1,\2,1)',t)
    methods={'QueryInterface':(200,3),'AddRef':(201,1),'Release':(202,1),'GetAdapterCount':(204,1),
        'GetAdapterIdentifier':(205,4),'GetAdapterModeCount':(206,2),'EnumAdapterModes':(207,4),
        'GetAdapterDisplayMode':(208,3),'CheckDeviceType':(209,6),'CheckDeviceFormat':(210,7),
        'CheckDeviceMultiSampleType':(211,6),'CheckDepthStencilMatch':(212,6),'GetDeviceCaps':(213,4),'GetAdapterMonitor':(214,2)}
    for method,(slot,n) in methods.items():
        t=t.replace('static void d8_'+method+'(CPU*c) {','static void d8_'+method+'(CPU*c) {\n    d8_api_entry(c,'+str(slot)+','+str(n)+');')
    begin=t.index('#define D8_UNSUPPORTED(name)')
    end=t.index('#include "hle_d3d8_device.inc"',begin)
    t=t[:begin]+'''#define D8_UNSUPPORTED(name,n) static void d8_##name(CPU*c) { \\
    d8_api_entry(c,299,n); \\
    D8Object*o=d8_object(c,ARG(0)); \\
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirect3D8::" #name " requires implementation (interface %08x, site %08x)",o->guest,c->pc); }
D8_UNSUPPORTED(RegisterSoftwareDevice,2)
D8_UNSUPPORTED(CheckDeviceType,6)
D8_UNSUPPORTED(CheckDeviceMultiSampleType,6)
D8_UNSUPPORTED(GetAdapterMonitor,2)
''' +t[end:]
    t=t.replace('    if(ARG(0)!=120)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"Direct3DCreate8: unmeasured SDK version %u",ARG(0));','    d8_api_entry(c,300,1); /* Known UINT API; backend supplies its actual pointer/NULL result. */')
    # All implemented parent queries transfer actual last-error, including
    # failures; formatting/memory validation must not become the API's seed.
    for method in ('QueryInterface','AddRef','GetAdapterCount','GetAdapterModeCount','GetAdapterIdentifier','GetDeviceCaps','CheckDeviceFormat'):
        begin=t.index('static void d8_'+method+'(CPU*c) {');end=t.index('\n}',begin)+2;body=t[begin:end]
        if method in ('AddRef','GetAdapterCount'):
            typ='ULONG' if method=='AddRef' else 'UINT'
            body=re.sub(r'\b'+typ+r' n=(o->host->vt->\w+\([^;]*\));',
                typ+r' n;DWORD error;SetLastError(xrt_get_last_error(c));n=\1;error=GetLastError();',body)
        elif method=='GetAdapterModeCount':
            body=body.replace('    n=o->host->vt->GetAdapterModeCount(o->host,adapter);',
                '    DWORD error;SetLastError(xrt_get_last_error(c));n=o->host->vt->GetAdapterModeCount(o->host,adapter);error=GetLastError();')
        else:
            body=body.replace('HRESULT hr=','HRESULT hr;DWORD error;hr=')
            body=body.replace('HRESULT hr;','HRESULT hr;DWORD error;')
            body=body.replace('DWORD error;DWORD error;','DWORD error;')
            body=re.sub(r'(hr=o->host->vt->\w+\([^;]*\);)',r'SetLastError(xrt_get_last_error(c));\1error=GetLastError();',body)
        body=body.replace('RET_STD(', 'xrt_set_last_error(c,error);RET_STD(')
        t=t[:begin]+body+t[end:]
    t=t.replace('D8Factory fn;D8Interface*host;D8Object*o=NULL;','D8Factory fn;D8Interface*host;D8Object*o=NULL;DWORD error;')
    t=t.replace('host=fn(ARG(0));if(host)o=d8_wrap(c,host);','SetLastError(xrt_get_last_error(c));host=fn(ARG(0));error=GetLastError();if(host)o=d8_wrap(c,host);xrt_set_last_error(c,error);')
    t=t.replace('d8_objects[i].guest==p && d8_objects[i].refs','d8_objects[i].guest==p && d8_objects[i].refs && d8_objects[i].host')
    t=t.replace('D8_UNSUPPORTED(CheckDeviceType,6)\n','').replace('D8_UNSUPPORTED(CheckDeviceMultiSampleType,6)\n','')
    t=t.replace('#include "hle_d3d8_device.inc"','#include "hle_d3d8_device.inc"\n#include "semantic_parent.inc"')
    p.write_text(t)
    # Even unimplemented slots collect raw evidence before reading this.
    p=RT/'d3d8_device_slots.inc';t=p.read_text()
    t=re.sub(r'(static void d8_device_\w+\(CPU\*c\) \{ )(d8_device_object\(c,ARG\(0\)\);xrt_fatal\(c,76,"IDirect3DDevice8 unsupported slot (\d+))',
             lambda m:m[1]+'d8_api_entry(c,'+m[3]+',1);'+m[2],t)
    p.write_text(t)
    # Retire unused profile data from this candidate; historical files are untouched.
    (RT/'integrated_renderer.inc').unlink();(RT/'batch_cases.inc').unlink()
    p=RT/'hle_gui.c';t=p.read_text();start=t.index('/* Original WWindow::MoveWindow')
    end=t.index('static void hle_SetWindowPos',start)
    t=t[:start]+'''/* MoveWindow accepts signed geometry and BOOL repaint. Ownership/thread
 * checks and typed callback marshalling remain in xrt_gui_device_window. */
static void hle_MoveWindow(CPU*c) {
    HWND h;BOOL ok;CPU*previous;DWORD error;
    { DWORD saved_error=GetLastError(),saved_mxcsr=_mm_getcsr();
      __declspec(align(16)) CONTEXT context;LONG id=InterlockedIncrement(&gui_diagnostic_serial);
      RtlCaptureContext(&context);gui_diagnostic_bytes(id,"move_host_context",&context,sizeof context);
      gui_diagnostic_bytes(id,"move_guest_cpu",c,sizeof *c);_mm_setcsr(saved_mxcsr);SetLastError(saved_error); }
    if((uint64_t)c->r[ESP]+28>0x100000000ull || !xrt_is_committed(c->r[ESP],28) ||
       !gui_diagnostic_readable(G2H(c->r[ESP]),28))
        xrt_fatal(c,76,"SAFETY: MoveWindow unreadable argument frame");
    xrt_event("gui_move_window_call","\\"hwnd\\":%u,\\"x\\":%u,\\"y\\":%u,\\"width\\":%u,\\"height\\":%u,\\"repaint\\":%u,\\"site\\":%u",
        ARG(0),ARG(1),ARG(2),ARG(3),ARG(4),ARG(5),c->pc);
    h=xrt_gui_device_window(c,ARG(0));previous=xrt_gui_callback_enter(c);begin(c);
    ok=MoveWindow(h,(int)ARG(1),(int)ARG(2),(int)ARG(3),(int)ARG(4),(BOOL)ARG(5));
    error=GetLastError();xrt_gui_callback_leave(previous);xrt_set_last_error(c,error);RET_STD(6,ok);
    xrt_event("gui_move_window_return","\\"result\\":%u,\\"last_error\\":%lu,\\"esp\\":%u,\\"return\\":%u",(unsigned)ok,error,c->r[ESP],c->rv);
}
''' +t[end:]
    # Diagnostics for callbacks are unconditional in this experimental runtime.
    t=t.replace('if(wp>ICON_SMALL2 || (lp && lp!=96))',
        'if(wp>ICON_SMALL2 || ((uint64_t)(uintptr_t)lp>0xffffffffull && lp!=(LPARAM)(int32_t)(uint32_t)lp))')
    t=t.replace('if(wp>ICON_SMALL2 || (ARG(3) && ARG(3)!=96))','if(wp>ICON_SMALL2)')
    t=t.replace('WM_GETICON: unmeasured selector/DPI','WM_GETICON: invalid selector or unrepresentable DPI')
    p.write_text(t)
    p=RT/'hle_gui_diag.inc';t=p.read_text();t=t.replace('if(GetEnvironmentVariableA("XRT_GUI_DIAGNOSTICS",enabled,sizeof enabled)==1 && enabled[0]==\'1\') {','if(1) {');p.write_text(t)
    t=t.replace('char enabled[2];','');p.write_text(t)
    t=t.replace('id=InterlockedIncrement(&gui_diagnostic_serial);QueryPerformanceCounter(&qpc);',
        'id=InterlockedIncrement(&gui_diagnostic_serial);QueryPerformanceCounter(&qpc);\n        { __declspec(align(16)) CONTEXT context;RtlCaptureContext(&context);\n          gui_diagnostic_bytes(id,"host_context",&context,sizeof context); }')
    p.write_text(t)
    changes=[]
    for p in sorted(RT.iterdir()):
        old=PRIOR/'runtime'/p.name
        if not old.exists() or core.sha(p)!=core.sha(old):
            changes.append(p.name)
    save(O/'source-change.json',dict(changed=changes,removed=['integrated_renderer.inc','batch_cases.inc'],runtime=core.tree(RT),genuine_launches=0,supervisor_policy_changed=False))
    print('Staged semantic runtime:',changes,flush=True)

def build():
    b=read(PRIOR/'build.json');previous=Path(b['root']);origin=read(PRIOR/'object-lineage.json')
    core.require(core.tree(previous)==b['outputs'] and core.tree(W/'experiments/xrt/gen')==b['generated'],'prior/generated identity')
    target=W/'experiments/xrt/build/semantic-compat-20261029-01'/str(uuid.uuid4());target.mkdir(parents=True)
    helper=load('semantic_build_tools',H.parent/'getobject_boundary/phase.py');helper.O=O/('client-build-'+str(uuid.uuid4()));helper.O.mkdir();env=helper.env()
    lineage={};copied={};changed={'obj/rt/hle_gui.obj','obj/rt/hle_misc.obj'}
    for rel,row in origin.items():
        core.require(core.sha(previous/rel)==row['object_sha256'] and core.sha(row['source'])==row['source_sha256'],'inherited object/source')
        for name,digest in row.get('verified_local_headers',{}).items():core.require(core.sha(name)==digest,'inherited header')
        if rel in changed:continue
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest);copied[rel]=core.sha(dest)
        lineage[rel]=dict(row,reused=True,reused_in_this_candidate=True,inherited_from=str(PRIOR/'object-lineage.json'))
    for rel in sorted(changed):
        name=Path(rel).stem;cmd=origin[rel]['command'];old_source=Path(origin[rel]['source']);old_output=Path(next(s[3:] for s in cmd if s.startswith('/Fo')))
        cmd=[s.replace(str(old_source.parent),str(RT)).replace(str(old_output.parent),str(target/'obj/rt')) for s in cmd]
        cmd.insert(1,'/showIncludes')
        helper.run(cmd,name,cwd=W/'experiments/xrt',environment=env,timeout=120)
        lineage[rel]=dict(source=str(RT/(name+'.c')),source_sha256=core.sha(RT/(name+'.c')),object_sha256=core.sha(target/rel),command=cmd,
            reused=False,reused_in_this_candidate=False,verified_local_headers={str(RT/n):v for n,v in core.tree(RT).items() if n.endswith(('.h','.inc'))})
    includes=(helper.O/'hle_misc.stdout.txt').read_text()
    core.require(all(n in includes for n in ('semantic_policy.h','semantic_renderer.inc','semantic_evidence.inc','semantic_clear.inc')),'actual compiler include closure missing semantic renderer')
    link=[s.replace(str(previous),str(target)) for s in b['commands'][-1]['command']]
    (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
    helper.run(link,'link',cwd=W/'experiments/xrt',environment=env,timeout=120)
    save(O/'object-lineage.json',lineage)
    save(O/'build.json',dict(passed=True,root=str(target),outputs=core.tree(target),runtime_root=str(RT),runtime=core.tree(RT),generated=b['generated'],
        binary_sha256=core.sha(target/'xrt_ucc.exe'),pdb_sha256=core.sha(target/'xrt_ucc.pdb'),compiled_objects=2,reused_objects=277,reused_object_hashes=copied,
        commands=[read(helper.O/(n+'.json')) for n in ('hle_gui','hle_misc','link')],inherited_build=str(PRIOR/'build.json'),inherited_build_sha256=core.sha(PRIOR/'build.json'),
        toolchain=b['toolchain'],gamma_profile=b['gamma_profile'],genuine_launches=0,execution_authorized=False))
    print('Built',target,flush=True)

if __name__=='__main__':
    assert sys.argv[1:] in (['stage'],['refresh'],['build']);globals()[sys.argv[1]]()
