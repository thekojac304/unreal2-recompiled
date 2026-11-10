"""Reproducibly extend sealed input without modifying it."""
import sys,re,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
METHODS=['GetRenderTarget','GetDepthStencilSurface','CreateTexture','CreateVertexBuffer','CreateIndexBuffer','SetRenderTarget','UpdateTexture','DrawPrimitive','DrawIndexedPrimitive','GetTexture','GetStreamSource','GetIndices','CreateVertexShader','GetVertexShader','DeleteVertexShader']
RESOURCE_METHODS=['Unsupported','QueryInterface','AddRef','Release','GetDevice','GetContainer','GetDesc','GetLevelDesc','GetSurfaceLevel','LockRect','UnlockRect','Lock','Unlock','SetPriority','GetPriority','PreLoad','GetType','SetLOD','GetLOD','GetLevelCount','AddDirtyRect']
def main():
    for p in (PRIOR/'runtime').iterdir():
        if p.is_file():shutil.copy2(p,RT/p.name)
    for n in ('resource_abi.h','resources.inc','resource_storage.inc','resource_draw.inc','vertex_declaration.inc'):shutil.copy2(H/n,RT/n)
    p=RT/'d3d8_device_abi.h';s=p.read_text().replace('typedef struct D8Creation','#include "resource_abi.h"\n\ntypedef struct D8Creation')
    s=s.replace('void* unsupported20_33[14];','''HRESULT(WINAPI*CreateTexture)(D8Device*,UINT,UINT,UINT,DWORD,DWORD,DWORD,D8Texture**);
    void* unsupported21_22[2];
    HRESULT(WINAPI*CreateVertexBuffer)(D8Device*,UINT,DWORD,DWORD,DWORD,D8Buffer**);
    HRESULT(WINAPI*CreateIndexBuffer)(D8Device*,UINT,DWORD,DWORD,DWORD,D8Buffer**);
    void* unsupported25_28[4];
    HRESULT(WINAPI*UpdateTexture)(D8Device*,D8Texture*,D8Texture*);
    void* unsupported30;
    HRESULT(WINAPI*SetRenderTarget)(D8Device*,D8Surface*,D8Surface*);
    HRESULT(WINAPI*GetRenderTarget)(D8Device*,D8Surface**);
    HRESULT(WINAPI*GetDepthStencilSurface)(D8Device*,D8Surface**);''')
    s=s.replace('void* unsupported64_71[8];','''void* unsupported64_69[6];
    HRESULT(WINAPI*DrawPrimitive)(D8Device*,DWORD,UINT,UINT);
    HRESULT(WINAPI*DrawIndexedPrimitive)(D8Device*,DWORD,UINT,UINT,UINT,UINT);''')
    s=s.replace('void* unsupported74_75[2];','void* unsupported74;\n    HRESULT(WINAPI*CreateVertexShader)(D8Device*,const DWORD*,const DWORD*,DWORD*,DWORD);')
    s=s.replace('void* unsupported78_82[5];','HRESULT(WINAPI*DeleteVertexShader)(D8Device*,DWORD);\n    void* unsupported79_82[4];')
    for name,slot in [('CreateTexture',20),('CreateVertexBuffer',23),('CreateIndexBuffer',24),('SetRenderTarget',31),('GetRenderTarget',32),('GetDepthStencilSurface',33),('DrawPrimitive',70),('DrawIndexedPrimitive',71)]:
        s=s.replace('#endif',f'typedef char resource_slot_{name}[offsetof(D8DeviceVtable,{name})=={slot}*sizeof(void*)?1:-1];\n#endif')
    p.write_text(s)
    p=RT/'hle_d3d8_device.inc';s=p.read_text().replace('guest,refs,focus,window,presents;','guest,refs,focus,window,presents,children;')
    s=s.replace('static void d8_device_dead(D8DeviceObject*o) {','static void d8_declaration_device_dead(void);\nstatic void d8_layout_requirements(CPU*,D8DeviceObject*,unsigned,unsigned[16]);\nstatic void d8_resource_device_dead(void);\nstatic void d8_resource_up_reset(int);\nstatic void d8_device_dead(D8DeviceObject*o) {\n    d8_declaration_device_dead();d8_resource_device_dead();')
    s=s.replace('static void d8_device_cleanup(void) {','static void d8_resource_cleanup(void);\nstatic void d8_device_cleanup(void) {')
    s=s.replace('while(d8_device.refs) {','d8_resource_cleanup();\n    while(d8_device.refs) {')
    s=s.replace('if(!--o->refs)d8_device_dead(o);','if(!--o->refs && !o->children)d8_device_dead(o);')
    # These methods can reenter guest callbacks and must keep the native frame live.
    start=s.index('static void d8_device_QueryInterface');end=s.index('static void d8_device_GetCreationParameters',start)
    block=s[start:end]
    block=block.replace('DWORD error;uint32_t out=ARG(2);','DWORD error;CPU*previous;uint32_t out=ARG(2);')
    block=block.replace('ULONG n;DWORD error;\n','ULONG n;DWORD error;CPU*previous;\n')
    block=block.replace('D8Interface*q=NULL;HRESULT hr;DWORD error;','D8Interface*q=NULL;HRESULT hr;DWORD error;CPU*previous;')
    block=block.replace('    D8DeviceObject*o=d8_device_object(c,ARG(0));','    if(d8_rendering||d8_native_failed)xrt_fatal(c,76,"D3D8 device COM: reentrant/failed native operation");\n    D8DeviceObject*o=d8_device_object(c,ARG(0));')
    block=block.replace('if(d8_rendering)xrt_fatal(c,76,"Direct3DDevice8: Release during native rendering unsupported");','if(d8_rendering||d8_locks)xrt_fatal(c,76,"Direct3DDevice8: Release during native rendering or map unsupported");')
    block=block.replace('previous=xrt_gui_callback_enter(c);','previous=xrt_gui_callback_enter(c);d8_rendering=1;')
    block=block.replace('memcpy(&iid,G2H(ARG(1)),16);SetLastError','memcpy(&iid,G2H(ARG(1)),16);previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError')
    block=block.replace('    SetLastError(xrt_get_last_error(c));n=o->host->vt->AddRef','    if(o->refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 device reference overflow");\n    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));n=o->host->vt->AddRef')
    block=block.replace('d8_device_memory(c,ARG(1),4,1);SetLastError','d8_device_memory(c,ARG(1),4,1);previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError')
    block=block.replace('error=GetLastError();','error=GetLastError();d8_rendering=0;xrt_gui_callback_leave(previous);')
    block=block.replace('    xrt_gui_callback_leave(previous);\n','')
    block=block.replace('if(out)wr32(out,SUCCEEDED(hr)?o->guest:0);','if(out){d8_device_memory(c,out,4,1);wr32(out,SUCCEEDED(hr)?o->guest:0);}')
    block=block.replace('    wr32(ARG(1),SUCCEEDED(hr)?o->parent->guest:0);','    d8_device_memory(c,ARG(1),4,1);wr32(ARG(1),SUCCEEDED(hr)?o->parent->guest:0);')
    s=s[:start]+block+s[end:]
    s=s.replace('if(d8_rendering)xrt_fatal(c,76,"Direct3DDevice8: reentrant rendering unsupported");','if(d8_rendering||d8_native_failed)xrt_fatal(c,76,"Direct3DDevice8: reentrant or failed native operation");')
    s=s.replace('    d8_resource_cleanup();','    d8_rendering=1;d8_resource_cleanup();')
    s=s.replace('    xrt_gui_callback_leave(previous);\n    xrt_event("d3d8_device_cleanup"','    d8_rendering=0;xrt_gui_callback_leave(previous);\n    xrt_event("d3d8_device_cleanup"')
    s=s.replace('#include "scene_draw.inc"','#include "scene_draw.inc"\n#include "resources.inc"\n#include "resource_storage.inc"\n#include "vertex_declaration.inc"\n#include "resource_draw.inc"')
    p.write_text(s)
    p=RT/'scene_draw.inc';s=p.read_text().replace('if(vertices)HeapFree(GetProcessHeap(),0,vertices);','d8_resource_up_reset(0);\n    if(vertices)HeapFree(GetProcessHeap(),0,vertices);')
    s=s.replace('if(indices)HeapFree(GetProcessHeap(),0,indices);','d8_resource_up_reset(1);\n    if(indices)HeapFree(GetProcessHeap(),0,indices);')
    s,count=re.subn(r'static void d8_draw_layout\(CPU\*c,D8DeviceObject\*o,unsigned primitives,unsigned stride\) \{.*?\n\}', '''static void d8_draw_layout(CPU*c,D8DeviceObject*o,unsigned primitives,unsigned stride) {
    unsigned bytes[16],i;d8_layout_requirements(c,o,primitives,bytes);
    for(i=1;i<16;i++)if(bytes[i])xrt_fatal(c,76,"Draw UP: multiple declaration streams unsupported");
    if(!bytes[0]||!stride||stride<bytes[0]||stride>o->caps.words[48])xrt_fatal(c,76,"Draw UP: stride incompatible with layout/caps");
}''',s,flags=re.S);assert count==1;p.write_text(s)
    p=RT/'d3d8_device_slots.inc';s=p.read_text()
    for n in METHODS:
        s,count=re.subn(r'static void d8_device_'+n+r'\(CPU\*c\) \{[^\n]*\}\n','',s);assert count==1,n
    p.write_text(s)
    p=RT/'semantic_renderer.inc';s=p.read_text()
    for name in ('SetTexture','SetStreamSource','SetIndices','SetVertexShader'):
        s,count=re.subn(r'static void d8_device_'+name+r'\(CPU\*c\) \{.*?\n\}', '',s,flags=re.S);assert count==1
    p.write_text(s)
    # Resource method dispatch uses the same HLE binding table as device methods.
    p=RT/'hle_d3d8.inc';s=p.read_text();s=s.replace('    XRT_D3D8_DEVICE_BINDINGS \\', '    XRT_D3D8_DEVICE_BINDINGS \\\n'+''.join('    {"xrt.com","D8R.'+n+'",d8_resource_'+n+'}, \\\n' for n in RESOURCE_METHODS).rstrip('\n'))
    p.write_text(s)
    # Do not unload native mappings underneath a locked resource at fatal exit.
    p=RT/'hle_d3d8_device.inc';s=p.read_text().replace('static int d8_native_failed,d8_creating,d8_rendering;','static int d8_native_failed,d8_creating,d8_rendering;\nstatic unsigned d8_locks;')
    p.write_text(s)
    p=RT/'resources.inc';p.write_text(p.read_text().replace('static unsigned d8_resource_used,d8_locks;','static unsigned d8_resource_used;'))
    # Existing containment predicate is in the creation implementation.
    p=RT/'hle_d3d8.inc';s=p.read_text();s=s.replace('d8_native_failed || d8_creating || d8_rendering','d8_native_failed || d8_creating || d8_rendering || d8_locks');p.write_text(s)
    save(O/'source-change.json',dict(runtime=core.tree(RT),templates={str(p):core.sha(p) for p in H.iterdir() if p.suffix in ('.h','.inc','.py')},genuine_launches=0))
if __name__=='__main__':main()
