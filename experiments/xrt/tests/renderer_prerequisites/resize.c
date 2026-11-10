/* Real original/generated ResizeViewport body. Project-owned object graph only. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "xrt.h"
uint8_t *xrt_g;
volatile long xrt_preempt_req;
void xrt_preempt(CPU*c){(void)c;ExitProcess(92);}
void xrt_eh_register(CPU*c,XrtEhPad*p){(void)c;p->active=0;}
void xrt_eh_landed(CPU*c,XrtEhPad*p){(void)c;(void)p;ExitProcess(92);}
void xrt_eh_pop(CPU*c,XrtEhPad*p){(void)c;(void)p;ExitProcess(92);}
static HWND win;
static unsigned callbacks, moved, frame_callbacks;
static DWORD messages[64][9];
static BYTE *arena;
static uint32_t viewport=0x4000,client=0x5000,windowobj=0x6000,actor=0x7000;
static void die(void){fprintf(stderr,"resize fixture unexpected path/error %lu\n",GetLastError());ExitProcess(93);}
void xrt_badret(CPU*c,uint32_t s,uint32_t e){(void)c;(void)s;(void)e;die();}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){
    DWORD error=GetLastError();LRESULT result;unsigned at=callbacks;
    if(m==WM_WINDOWPOSCHANGING||m==WM_WINDOWPOSCHANGED||m==WM_SIZE||m==WM_MOVE){
        if(at>=64)die();messages[at][0]=m;messages[at][1]=(DWORD)w;messages[at][2]=error;messages[at][3]=h==win;
        if(m==WM_WINDOWPOSCHANGING||m==WM_WINDOWPOSCHANGED){WINDOWPOS*p=(WINDOWPOS*)l;
            messages[at][4]=p->x;messages[at][5]=p->y;messages[at][6]=p->cx;messages[at][7]=p->cy;messages[at][8]=p->flags;
        }else{messages[at][4]=(DWORD)l;messages[at][5]=messages[at][6]=messages[at][7]=messages[at][8]=0;}
        callbacks++;
    }
    SetLastError(error);result=DefWindowProcW(h,m,w,l);return result;
}
#if defined(_M_IX86)
static void* __fastcall outer(void*t,void*d){(void)t;(void)d;return G2H(client);}
static RECT* __fastcall rect(void*t,void*d,RECT*out,int full){(void)t;(void)d;if(full!=1)die();if(!GetWindowRect(win,out))die();return out;}
static void __fastcall move(void*t,void*d,RECT r,int repaint){(void)t;(void)d;moved++;if(!MoveWindow(win,r.left,r.top,r.right-r.left,r.bottom-r.top,repaint))die();}
static void __fastcall update(void*t,void*d){(void)t;(void)d;frame_callbacks++;}
static void __fastcall input(void*t,void*d,int active){(void)t;(void)d;if(active)die();frame_callbacks++;}
static void __fastcall saveconfig(void*t,void*d,unsigned flags,void*name){(void)t;(void)d;if(flags!=0x4000||name)die();frame_callbacks++;}
static DWORD __fastcall getflags(void*t,void*d){(void)t;(void)d;return 0x800000;}
static uint32_t p32(void*p){return (uint32_t)(uintptr_t)p;}
static void slot(unsigned at,void*p){*(void**)(arena+at)=p;}
#endif
void xrt_icall(CPU*c,uint32_t target,uint32_t site){
    uint32_t s=c->r[ESP];unsigned n=0;DWORD result=0;RECT r;(void)target;
    switch(site){
    case 0x14f48:result=client;break;
    case 0x14f6e:result=0x800000;break;
    case 0x14fd2:n=2;if(!GetWindowRect(win,&r))die();memcpy(G2H(rd32(s+4)),&r,16);result=rd32(s+4);break;
    case 0x1562a:case 0x15618:n=2;result=GetWindowLongW(win,(int)rd32(s+8));break;
    case 0x15637:n=3;memcpy(&r,G2H(rd32(s+4)),16);result=AdjustWindowRect(&r,rd32(s+8),rd32(s+12));memcpy(G2H(rd32(s+4)),&r,16);break;
    case 0x15691:n=5;memcpy(&r,G2H(s+4),16);moved++;result=MoveWindow(win,r.left,r.top,r.right-r.left,r.bottom-r.top,rd32(s+20));if(!result)die();break;
    case 0x156ad:n=1;if(rd32(s+4))die();frame_callbacks++;break;
    case 0x1551c:frame_callbacks++;break;
    case 0x15705:n=2;if(rd32(s+4)!=0x4000||rd32(s+8))die();frame_callbacks++;break;
    default:fprintf(stderr,"unhandled site=%x target=%x\n",site,target);die();
    }
    c->r[EAX]=result;RET(n*4);
}
static unsigned char xrt_hits_WinDrv[1024];
static void f_11102900(CPU*c){(void)c;die();}
#include "resize_generated.inc"

int main(void){
    WNDCLASSW wc={0};RECT before,after,cr;DWORD error;unsigned i,j;
    const DWORD seeds[]={18,0,0x13572468,0xffffffff};
    wc.lpfnWndProc=proc;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XrtOriginalResizeFixture";
    if(!RegisterClassW(&wc))die();
    xrt_g=VirtualAlloc(NULL,0x40000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!xrt_g)die();
#if defined(_M_IX86)
    arena=VirtualAlloc(NULL,0x20000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!arena)die();
    memcpy(arena+0x4f20,resize_bytes,sizeof resize_bytes);
    for(i=0;i<sizeof resize_reloc/sizeof resize_reloc[0];i++){
        const unsigned*r=resize_reloc[i];DWORD v=r[2]?(r[1]-0x4f20-r[3]):p32(arena+r[1]);
        memcpy(arena+0x4f20+r[0],&v,4);
    }
    slot(0xb008,outer);slot(0xb128,getflags);slot(0xb498,rect);slot(0xb490,move);slot(0xb130,saveconfig);
    slot(0xb33c,GetWindowLongW);slot(0xb340,GetWindowLongA);slot(0xb378,AdjustWindowRect);
    slot(0xb048,G2H(0x8000));slot(0xb078,G2H(0x8004));
    {DWORD old;if(!VirtualProtect(arena,0x20000,PAGE_EXECUTE_READWRITE,&old))die();FlushInstructionCache(GetCurrentProcess(),arena,0x20000);}
#endif
    for(j=0;j<8;j++){
        CPU c={0};DWORD result;unsigned delta;
        win=CreateWindowW(wc.lpszClassName,L"disposable resize",WS_OVERLAPPEDWINDOW,40,50,400,300,NULL,NULL,wc.hInstance,NULL);
        if(!win)die();GetWindowRect(win,&before);callbacks=moved=frame_callbacks=0;
        memset(G2H(0x4000),0,0x5000);
#if defined(_M_IX86)
        wr32(client+0x28,p32(G2H(0xa000)));
        wr32(viewport,p32(G2H(0x9000)));wr32(viewport+0x16c,p32(G2H(windowobj)));wr32(viewport+0x30,p32(G2H(actor)));
        wr32(windowobj+4,p32(win));wr32(viewport+0x5c,1);
        *(void**)G2H(0x9000+0x90)=update;*(void**)G2H(0x9000+0x80)=input;
        {void*fn=arena+0x4f20;void*vp=G2H(viewport);DWORD sp1,sp2;
        SetLastError(seeds[j%4]);
        __asm {
            mov sp1,esp
            push 945
            push 1540
            push 16
            mov ecx,vp
            call fn
            mov result,eax
            mov sp2,esp
        }
        delta=sp2-sp1;}
#else
        wr32(client+0x28,0xa000);
        wr32(viewport,0x9000);wr32(viewport+0x16c,windowobj);wr32(viewport+0x30,actor);wr32(viewport+0x5c,1);wr32(windowobj+4,0x123);
        wr32(0x1b048,0x8000);wr32(0x1b078,0x8004);
        wr32(0x2000,0xabcdef);wr32(0x2004,16);wr32(0x2008,1540);wr32(0x200c,945);
        c.r[ESP]=0x2000;c.r[ECX]=viewport;c.fs_base=0x3000;c.fcw=0x027f;
        SetLastError(seeds[j%4]);generated_resize(&c);result=c.r[EAX];delta=c.r[ESP]-0x2010;
#endif
        error=GetLastError();GetWindowRect(win,&after);GetClientRect(win,&cr);
        printf("{\"kind\":\"resize\",\"case\":%u,\"seed\":%lu,\"result\":%lu,\"error\":%lu,\"delta\":%u,\"style\":%lu,\"before\":[%ld,%ld,%ld,%ld],\"after\":[%ld,%ld,%ld,%ld],\"client\":[%ld,%ld],\"focus_self\":%u,\"callbacks\":%u,\"moves\":%u,\"virtual_callbacks\":%u,\"width\":%u,\"height\":%u}\n",
            j,seeds[j%4],result,error,delta,(DWORD)GetWindowLongW(win,GWL_STYLE),before.left,before.top,before.right,before.bottom,
            after.left,after.top,after.right,after.bottom,cr.right,cr.bottom,GetFocus()==win,callbacks,moved,frame_callbacks,rd32(viewport+0x74),rd32(viewport+0x78));
        if(result!=1||delta||cr.right!=1540||cr.bottom!=945||moved!=1||frame_callbacks!=3)die();
        printf("{\"kind\":\"resize-callbacks\",\"case\":%u,\"messages\":[",j);
        for(i=0;i<callbacks;i++){unsigned k;printf("%s[",i?",":"");for(k=0;k<9;k++)printf("%s%lu",k?",":"",messages[i][k]);putchar(']');}puts("]}");
        if(!DestroyWindow(win))die();
    }
    if(!UnregisterClassW(wc.lpszClassName,wc.hInstance))die();
    VirtualFree(xrt_g,0,MEM_RELEASE);
#if defined(_M_IX86)
    VirtualFree(arena,0,MEM_RELEASE);
#endif
    return 0;
}
