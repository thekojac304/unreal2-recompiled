"""Extend a preserved isolated runtime; no launch or supervisor mutation."""
import sys,re,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
METHODS={'GetBackBuffer':16,'CreateRenderTarget':25,'CreateDepthStencilSurface':26,'CreateImageSurface':27,'CopyRects':28,'GetFrontBuffer':30}
def main():
    for p in (PRIOR/'runtime').iterdir():
        if p.is_file():shutil.copy2(p,RT/p.name)
    shutil.copy2(H/'surface_transfer.inc',RT/'surface_transfer.inc')
    p=RT/'d3d8_device_abi.h';s=p.read_text()
    s=s.replace('void* unsupported16_17[2];','HRESULT(WINAPI*GetBackBuffer)(D8Device*,UINT,DWORD,D8Surface**);\n    void* unsupported17;')
    s=s.replace('void* unsupported25_28[4];','''HRESULT(WINAPI*CreateRenderTarget)(D8Device*,UINT,UINT,DWORD,DWORD,BOOL,D8Surface**);
    HRESULT(WINAPI*CreateDepthStencilSurface)(D8Device*,UINT,UINT,DWORD,DWORD,D8Surface**);
    HRESULT(WINAPI*CreateImageSurface)(D8Device*,UINT,UINT,DWORD,D8Surface**);
    HRESULT(WINAPI*CopyRects)(D8Device*,D8Surface*,const RECT*,UINT,D8Surface*,const POINT*);''')
    s=s.replace('void* unsupported30;','HRESULT(WINAPI*GetFrontBuffer)(D8Device*,D8Surface*);')
    for n,slot in METHODS.items():s=s.replace('#endif',f'typedef char transfer_slot_{n}[offsetof(D8DeviceVtable,{n})=={slot}*sizeof(void*)?1:-1];\n#endif')
    p.write_text(s)
    p=RT/'d3d8_device_slots.inc';s=p.read_text()
    for n in METHODS:
        s,count=re.subn(r'static void d8_device_'+n+r'\(CPU\*c\) \{[^\n]*\}\n','',s);assert count==1,n
    p.write_text(s)
    p=RT/'hle_d3d8_device.inc';s=p.read_text().replace('#include "resource_draw.inc"','#include "resource_draw.inc"\n#include "surface_transfer.inc"');p.write_text(s)
    shutil.copy2(H/'window_transitions.inc',RT/'window_transitions.inc')
    p=RT/'hle_gui.c';s=p.read_text()
    anchor='static INT_PTR invoke_gui_proc('
    s=s.replace(anchor,'#include "window_transitions.inc"\n'+anchor)
    anchor='    case WM_WINDOWPOSCHANGING:\n'
    assert s.count(anchor)==1
    s=s.replace(anchor,'''    case WM_STYLECHANGING: case WM_STYLECHANGED:
        if(!lp || ((int32_t)wp!=GWL_STYLE && (int32_t)wp!=GWL_EXSTYLE))
            xrt_fatal(&nested,76,"style callback: unsupported field or NULL structure");
        gui_transition_memory(&nested,scratch,8,1);memcpy(G2H(scratch),(void*)lp,8);args[3]=scratch;
        break;
'''+anchor)
    s=s.replace('    if (msg == WM_GETMINMAXINFO)\n','    if(msg==WM_STYLECHANGING || msg==WM_STYLECHANGED)gui_style_sync(&nested,msg,scratch,lp);\n    if (msg == WM_GETMINMAXINFO)\n')
    anchor='{"user32.dll", "GetWindowLongW", hle_GetWindowLongW},'
    s=s.replace(anchor,anchor+'\n'+''.join('                              {"user32.dll", "'+n+'", hle_'+n+'},\n' for n in ('SetWindowLongA','SetWindowLongW','SetMenu','PostMessageA','PostMessageW')))
    p.write_text(s)
    p=RT/'hle_gui_classes.inc';s=p.read_text()
    s=s.replace('        case WM_GETMINMAXINFO: memcpy((void*)f->host_lp,G2H(lp),40);break;', '        case WM_STYLECHANGING: case WM_STYLECHANGED: gui_style_sync(c,msg,lp,f->host_lp);break;\n        case WM_GETMINMAXINFO: memcpy((void*)f->host_lp,G2H(lp),40);break;')
    s=s.replace('    case WM_GETMINMAXINFO: memcpy(G2H(lp),(void*)host_lp,40);break;', '    case WM_STYLECHANGING: case WM_STYLECHANGED: gui_transition_memory(callback_cpu,lp,8,1);memcpy(G2H(lp),(void*)host_lp,8);break;\n    case WM_GETMINMAXINFO: memcpy(G2H(lp),(void*)host_lp,40);break;')
    p.write_text(s)
    save(O/'source-change.json',dict(runtime=core.tree(RT),templates={str(p):core.sha(p) for p in H.iterdir() if p.suffix in ('.h','.inc','.py','.c')},genuine_launches=0))
if __name__=='__main__':main()
