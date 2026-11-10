"""Apply versioned source templates only to this phase's isolated runtime."""
import sys,re,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    # Deterministic regeneration from read-only sealed input; never edit it.
    for name in ('hle_dinput.inc','hle_d3d8_device.inc','d3d8_device_abi.h','d3d8_device_slots.inc'):
        shutil.copy2(PRIOR/'runtime'/name,RT/name)
    for name in ('dinput_lifecycle.inc','scene_draw.inc'):shutil.copy2(H/name,RT/name)
    p=RT/'hle_dinput.inc';s=p.read_text()
    s=s.replace('uint32_t guest,refs;','uint32_t guest,refs,window,cooperative_flags;')
    start=s.index('static void did_Acquire(CPU*c)');end=s.index('static void did_SetDataFormat',start)
    s=s[:start]+'#include "dinput_lifecycle.inc"\n'+s[end:]
    # The active flag is needed by Release and shutdown, before the include.
    s=s.replace('static uint32_t did_vtable;','static uint32_t did_vtable;\nstatic int did_lifecycle_active;')
    s=s.replace('static DiDevice*did_object(CPU*c,uint32_t p) {','static DiDevice*did_object(CPU*c,uint32_t p) {\n    if(did_lifecycle_active)xrt_fatal(c,76,"DirectInput: device access during lifecycle callback");')
    s=s.replace('di_devices[i].guest==p && di_devices[i].refs','di_devices[i].guest==p && di_devices[i].refs && di_devices[i].input')
    s=s.replace('static void di_cleanup(void) {','static void di_cleanup(void) {\n    if(did_lifecycle_active)return; /* fatal callback: process teardown owns live native frames */')
    s=s.replace('if(!--di_devices[i].refs)di_devices[i].input=NULL;',
        'if(!--di_devices[i].refs){di_devices[i].input=NULL;if(di_devices[i].window)xrt_gui_window_unpin(di_devices[i].window);di_devices[i].window=0;}')
    old='DiDevice*o=did_object(c,ARG(0));ULONG n=o->input->lpVtbl->Release(o->input);\n    if(!--o->refs)o->input=NULL;\n    did_result("Release",o,(HRESULT)n);RET_STD(1,n);'
    new='''DiDevice*o;ULONG n;DWORD error;CPU*previous;
    if(did_lifecycle_active)xrt_fatal(c,76,"DirectInput: Release during lifecycle callback");
    did_memory_access(c,c->r[ESP],8,0);o=did_object(c,ARG(0));
    previous=xrt_gui_callback_enter(c);did_lifecycle_active=1;SetLastError(xrt_get_last_error(c));
    n=o->input->lpVtbl->Release(o->input);error=GetLastError();did_lifecycle_active=0;xrt_gui_callback_leave(previous);
    if(!--o->refs){o->input=NULL;if(o->window)xrt_gui_window_unpin(o->window);o->window=0;}
    did_result("Release",o,(HRESULT)n);xrt_set_last_error(c,error);RET_STD(1,n);'''
    assert old in s;s=s.replace(old,new)
    s=s.replace('static void did_Release(CPU*c)', 'static void did_memory_access(CPU*,uint32_t,uint32_t,int);\nstatic void did_Release(CPU*c)')
    s=s.replace('names[6]="DID.SetProperty";', 'names[8]="DID.Unacquire";names[13]="DID.SetCooperativeLevel";\n    names[6]="DID.SetProperty";')
    s=s.replace('    {"xrt.com","DID.Acquire",did_Acquire}, \\', '    {"xrt.com","DID.Unacquire",did_Unacquire}, \\\n    {"xrt.com","DID.SetCooperativeLevel",did_SetCooperativeLevel}, \\\n    {"xrt.com","DID.Acquire",did_Acquire}, \\')
    p.write_text(s)
    p=RT/'d3d8_device_abi.h';s=p.read_text()
    s=s.replace('typedef struct D8Gamma', 'typedef struct D8Viewport { DWORD x,y,width,height,minz,maxz; } D8Viewport;\ntypedef struct D8Gamma')
    s=s.replace('void* unsupported20_35[16];','void* unsupported20_33[14];\n    HRESULT (WINAPI *BeginScene)(D8Device*);\n    HRESULT (WINAPI *EndScene)(D8Device*);')
    s=s.replace('void* unsupported39_41[3];','void* unsupported39;\n    HRESULT (WINAPI *SetViewport)(D8Device*,const D8Viewport*);\n    HRESULT (WINAPI *GetViewport)(D8Device*,D8Viewport*);')
    s=s.replace('void* unsupported64_75[12];','''void* unsupported64_71[8];
    HRESULT (WINAPI *DrawPrimitiveUP)(D8Device*,DWORD,UINT,const void*,UINT);
    HRESULT (WINAPI *DrawIndexedPrimitiveUP)(D8Device*,DWORD,UINT,UINT,UINT,const void*,DWORD,const void*,UINT);
    void* unsupported74_75[2];''')
    checks='\n'.join(f'typedef char bringup_slot_{name}[offsetof(D8DeviceVtable,{name})=={slot}*sizeof(void*)?1:-1];' for slot,name in [(34,'BeginScene'),(35,'EndScene'),(40,'SetViewport'),(41,'GetViewport'),(72,'DrawPrimitiveUP'),(73,'DrawIndexedPrimitiveUP')])
    s=s.replace('#endif',checks+'\ntypedef char bringup_viewport_size[sizeof(D8Viewport)==24?1:-1];\n#endif');p.write_text(s)
    p=RT/'hle_d3d8_device.inc';s=p.read_text().replace('#include "d3d8_device_slots.inc"','#include "scene_draw.inc"\n#include "d3d8_device_slots.inc"');p.write_text(s)
    p=RT/'d3d8_device_slots.inc';s=p.read_text()
    for name in ('TestCooperativeLevel','BeginScene','EndScene','SetViewport','GetViewport','DrawPrimitiveUP','DrawIndexedPrimitiveUP'):
        s,n=re.subn(r'static void d8_device_'+name+r'\(CPU\*c\) \{[^\n]*\}\n','',s);assert n==1,name
    p.write_text(s)
    save(O/'source-change.json',dict(runtime=core.tree(RT),templates={str(H/n):core.sha(H/n) for n in ('dinput_lifecycle.inc','scene_draw.inc','integrate.py')},genuine_launches=0))
    print('Integrated DirectInput lifecycle and seven scene/draw methods',flush=True)
if __name__=='__main__':main()
