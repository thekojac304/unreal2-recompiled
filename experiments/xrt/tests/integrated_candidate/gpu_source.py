"""Reproducibly extend the preceding GPU fixture source; no execution."""
from pathlib import Path
H=Path(__file__).resolve().parent
def source():
    s=(H.parent/'resource_frame/gpu_resources.inc').read_text()
    s=s.replace('static uintptr_t ga[9]','static unsigned gphase;\nstatic uintptr_t ga[9]')
    s=s.replace(' case 15:d8_device_Present', ''' case 16:d8_device_GetBackBuffer(&cpu);break;
 case 25:d8_device_CreateRenderTarget(&cpu);break;case 26:d8_device_CreateDepthStencilSurface(&cpu);break;case 27:d8_device_CreateImageSurface(&cpu);break;case 28:d8_device_CopyRects(&cpu);break;case 30:d8_device_GetFrontBuffer(&cpu);break;
 case 15:d8_device_Present''')
    s=s.replace('if(gslot==20||','if(gslot==16||gslot==25||gslot==26||gslot==27||gslot==20||')
    s=s.replace(' case 15:hr=dev->vt->Present', ''' case 16:hr=dev->vt->GetBackBuffer(dev,(UINT)ga[1],(DWORD)ga[2],(D8Surface**)&q);break;
 case 25:hr=dev->vt->CreateRenderTarget(dev,(UINT)ga[1],(UINT)ga[2],(DWORD)ga[3],(DWORD)ga[4],(BOOL)ga[5],(D8Surface**)&q);break;
 case 26:hr=dev->vt->CreateDepthStencilSurface(dev,(UINT)ga[1],(UINT)ga[2],(DWORD)ga[3],(DWORD)ga[4],(D8Surface**)&q);break;
 case 27:hr=dev->vt->CreateImageSurface(dev,(UINT)ga[1],(UINT)ga[2],(DWORD)ga[3],(D8Surface**)&q);break;
 case 28:hr=dev->vt->CopyRects(dev,(D8Surface*)ga[1],ga[2]?(RECT*)G2H((uint32_t)ga[2]):NULL,(UINT)ga[3],(D8Surface*)ga[4],ga[5]?(POINT*)G2H((uint32_t)ga[5]):NULL);break;
 case 30:hr=dev->vt->GetFrontBuffer(dev,(D8Surface*)ga[1]);break;
 case 15:hr=dev->vt->Present''')
    s=s.replace(r'\"kind\":\"resource-call\"',r'\"kind\":\"%s\"').replace('slot,n,abi.hr,error,gobject?', 'gphase?"transfer-call":"resource-call",slot,n,abi.hr,error,gobject?')
    s=s.replace('static void resource_matrix(void)',(H/'gpu_surface.inc').read_text()+'\nstatic void resource_matrix(void)')
    s=s.replace(' RC(83,4,dev,U(0),U(0),U(0));RC(83,4,dev,U(1)', ' surface_matrix(dev,rt,ds);\n RC(83,4,dev,U(0),U(0),U(0));RC(83,4,dev,U(1)')
    return s
if __name__=='__main__':print(source())
