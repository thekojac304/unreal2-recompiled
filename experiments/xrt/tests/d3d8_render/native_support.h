/* Fixture-only native observation. No guest surface/resource bridge. */
#include "../../runtime/d3d8_abi.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct RenderRect { LONG left,top,right,bottom; } RenderRect;
typedef HRESULT(WINAPI*ClearFn)(D8Device*,DWORD,const RenderRect*,DWORD,DWORD,float,DWORD);
typedef HRESULT(WINAPI*PresentFn)(D8Device*,const RECT*,const RECT*,HWND,const RGNDATA*);
typedef struct Locked { INT pitch;void*bits; } Locked;
static void** rvtable(void*p){return *(void***)p;}
static ULONG rrelease(void*p){typedef ULONG(WINAPI*Fn)(void*);return ((Fn)rvtable(p)[2])(p);}
static ULONG radd(void*p){typedef ULONG(WINAPI*Fn)(void*);return ((Fn)rvtable(p)[1])(p);}
static void snapshot(D8Device*d,const char*tag,int image) {
 typedef HRESULT(WINAPI*BB)(void*,UINT,UINT,void**);
 typedef HRESULT(WINAPI*Desc)(void*,DWORD*);
 typedef HRESULT(WINAPI*Lock)(void*,Locked*,const RECT*,DWORD);
 typedef HRESULT(WINAPI*Unlock)(void*);
 void*s=NULL;DWORD desc[8]={0},sample[5]={0},mismatch=0;Locked l={0};HRESULT hr,dh=E_FAIL,lh=E_FAIL,uh=E_FAIL;ULONG release=0;uint64_t hash=14695981039346656037ull;unsigned x,y;FILE*f=NULL;
 hr=((BB)rvtable(d)[16])(d,0,0,&s);
 if(SUCCEEDED(hr)&&s){dh=((Desc)rvtable(s)[8])(s,desc);lh=((Lock)rvtable(s)[9])(s,&l,NULL,0x10);
  if(SUCCEEDED(lh)){
   unsigned w=desc[6],h=desc[7];DWORD first=*(DWORD*)l.bits&0xffffff;
   if(image){char path[160];snprintf(path,sizeof path,"%s.ppm",tag);f=fopen(path,"wb");if(f)fprintf(f,"P6\n%u %u\n255\n",w,h);}
   for(y=0;y<h;y++)for(x=0;x<w;x++){
    DWORD v=*(DWORD*)((BYTE*)l.bits+y*l.pitch+x*4)&0xffffff;unsigned k;
    if(v!=first)mismatch++;
    for(k=0;k<3;k++){hash^=(BYTE)(v>>(k*8));hash*=1099511628211ull;}
    if(f){BYTE rgb[3]={(BYTE)(v>>16),(BYTE)(v>>8),(BYTE)v};fwrite(rgb,1,3,f);}
   }
   if(f)fclose(f);
   sample[0]=first;sample[1]=*(DWORD*)((BYTE*)l.bits+(h/2)*l.pitch+(w/2)*4)&0xffffff;
   sample[2]=*(DWORD*)((BYTE*)l.bits+(h-1)*l.pitch+(w-1)*4)&0xffffff;
   sample[3]=*(DWORD*)((BYTE*)l.bits+16*l.pitch+16*4)&0xffffff;
   sample[4]=*(DWORD*)((BYTE*)l.bits+200*l.pitch+200*4)&0xffffff;
   uh=((Unlock)rvtable(s)[10])(s);
  }release=rrelease(s);
 }
 printf("{\"kind\":\"backbuffer\",\"tag\":\"%s\",\"get_hr\":%lu,\"desc_hr\":%lu,\"lock_hr\":%lu,\"unlock_hr\":%lu,\"desc\":[%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu],\"pitch\":%d,\"samples\":[%lu,%lu,%lu,%lu,%lu],\"nonuniform_pixels\":%lu,\"rgb_fnv64\":\"%016llx\",\"surface_release\":%lu}\n",tag,(DWORD)hr,(DWORD)dh,(DWORD)lh,(DWORD)uh,desc[0],desc[1],desc[2],desc[3],desc[4],desc[5],desc[6],desc[7],l.pitch,sample[0],sample[1],sample[2],sample[3],sample[4],mismatch,(unsigned long long)hash,release);fflush(stdout);
}
static void capture_window(HWND w,const char*tag,int image){
 RECT r;HDC dc,mem;HBITMAP b,old;BITMAPINFO info;BYTE*data;DWORD pixels[3],x,y,mismatch=0;uint64_t hash=14695981039346656037ull;FILE*f=NULL;HMODULE dwm=LoadLibraryW(L"dwmapi.dll");
 {MSG msg;while(PeekMessageW(&msg,NULL,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
 if(dwm){HRESULT(WINAPI*flush)(void)=(void*)GetProcAddress(dwm,"DwmFlush");if(flush)flush();FreeLibrary(dwm);}Sleep(80);
 GetClientRect(w,&r);dc=GetDC(w);mem=CreateCompatibleDC(dc);memset(&info,0,sizeof info);info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=r.right;info.bmiHeader.biHeight=-r.bottom;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
 b=CreateDIBSection(dc,&info,DIB_RGB_COLORS,(void**)&data,NULL,0);old=SelectObject(mem,b);
 if(!b||!PrintWindow(w,mem,2))ExitProcess(83);
 pixels[0]=*(DWORD*)data&0xffffff;pixels[1]=*(DWORD*)(data+((r.bottom/2)*r.right+r.right/2)*4)&0xffffff;pixels[2]=*(DWORD*)(data+((r.bottom-1)*r.right+r.right-1)*4)&0xffffff;
 if(image){char path[160];snprintf(path,sizeof path,"%s-window.ppm",tag);f=fopen(path,"wb");if(f)fprintf(f,"P6\n%ld %ld\n255\n",r.right,r.bottom);}
 for(y=0;y<(DWORD)r.bottom;y++)for(x=0;x<(DWORD)r.right;x++){
  DWORD v=*(DWORD*)(data+(y*r.right+x)*4)&0xffffff;unsigned k;if(v!=pixels[0])mismatch++;
  for(k=0;k<3;k++){hash^=(BYTE)(v>>(k*8));hash*=1099511628211ull;}
  if(f){BYTE rgb[3]={(BYTE)(v>>16),(BYTE)(v>>8),(BYTE)v};fwrite(rgb,1,3,f);}
 }if(f)fclose(f);
 printf("{\"kind\":\"window_capture\",\"tag\":\"%s\",\"width\":%ld,\"height\":%ld,\"samples\":[%lu,%lu,%lu],\"nonuniform_pixels\":%lu,\"rgb_fnv64\":\"%016llx\",\"visible\":%s}\n",tag,r.right,r.bottom,pixels[0],pixels[1],pixels[2],mismatch,(unsigned long long)hash,IsWindowVisible(w)?"true":"false");
 SelectObject(mem,old);DeleteObject(b);DeleteDC(mem);ReleaseDC(w,dc);fflush(stdout);
}
static void state(D8Device*d,HWND w,const char*tag){
 typedef HRESULT(WINAPI*Coop)(void*);typedef HRESULT(WINAPI*Get)(void*,void*);typedef HRESULT(WINAPI*RS)(void*,DWORD,DWORD*);
 DWORD vp[6]={0},rs=0,cp[8]={0};HRESULT v=((Get)rvtable(d)[41])(d,vp),s=((RS)rvtable(d)[51])(d,7,&rs);LONG_PTR proc=GetWindowLongPtrW(w,GWLP_WNDPROC);ULONG add=radd(d),rel=rrelease(d);HRESULT c=((Get)rvtable(d)[9])(d,cp),coop=((Coop)rvtable(d)[3])(d);
 printf("{\"kind\":\"state\",\"tag\":\"%s\",\"coop\":%lu,\"viewport_hr\":%lu,\"viewport\":[%lu,%lu,%lu,%lu,%lu,%lu],\"renderstate_hr\":%lu,\"z_enable\":%lu,\"creation_hr\":%lu,\"add\":%lu,\"release\":%lu,\"window_valid\":%s,\"window_proc\":%llu}\n",tag,(DWORD)coop,(DWORD)v,vp[0],vp[1],vp[2],vp[3],vp[4],vp[5],(DWORD)s,rs,(DWORD)c,add,rel,IsWindow(w)?"true":"false",(unsigned long long)proc);fflush(stdout);
}
