/* Run the original 13k+ semantic contracts against the new integrated runtime,
 * then exercise the new adapters. All D3D services here are declared doubles. */
#define main retained_contract_main
#include "../semantic_compat/fixture.c"
#undef main
static unsigned draw_count,draw_stride,draw_type,draw_min,draw_num,draw_fmt,draw_bytes,index_bytes,draw_mode;
static unsigned scene_cases,scene_negatives,queries;
static DWORD current_fvf=0x44;
static D8Viewport viewport={0,0,640,480,0,0x3f800000};
static void scene_dispatch(CPU*c){switch(draw_mode){
 case 3:d8_device_TestCooperativeLevel(c);break;case 34:d8_device_BeginScene(c);break;case 35:d8_device_EndScene(c);break;
 case 40:d8_device_SetViewport(c);break;case 41:d8_device_GetViewport(c);break;
 case 72:d8_device_DrawPrimitiveUP(c);break;case 73:d8_device_DrawIndexedPrimitiveUP(c);break;default:abort();}}
static HRESULT WINAPI simple_scene(D8Device*p){host_enter(p);SetLastError(host_error);return host_result;}
static HRESULT WINAPI get_fvf(D8Device*p,DWORD*q){CHECK(p==&host&&active&&d8_rendering);queries++;*q=current_fvf;SetLastError(0xbad);return S_OK;}
static HRESULT WINAPI set_view(D8Device*p,const D8Viewport*q){host_enter(p);CHECK((BYTE*)q<xrt_g || (BYTE*)q>=xrt_g+guest_capacity);CHECK(!memcmp(q,&viewport,24));SetLastError(host_error);return host_result;}
static HRESULT WINAPI get_view(D8Device*p,D8Viewport*q){DWORD old;host_enter(p);CHECK((BYTE*)q<xrt_g || (BYTE*)q>=xrt_g+guest_capacity);*q=viewport;
    if(reenter==4)CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_READONLY,&old));
    SetLastError(host_error);return host_result;}
static void copied(const void*p,uint32_t guest,unsigned n){if(n){CHECK(p!=G2H(guest));if(memcmp(p,G2H(guest),n))fprintf(stderr,"copy mismatch mode=%u case=%u negative=%u type=%u count=%u bytes=%u guest=%x arg=%x\n",draw_mode,scene_cases,scene_negatives,draw_type,draw_count,n,guest,rd32(active->r[ESP]+16));CHECK(!memcmp(p,G2H(guest),n));}else CHECK(!p);}
static HRESULT WINAPI draw_up(D8Device*p,DWORD type,UINT count,const void*v,UINT stride){
    host_enter(p);CHECK(type==draw_type&&count==draw_count&&stride==draw_stride);copied(v,0x6001,draw_bytes);
    if(reenter==3)scene_dispatch(active);SetLastError(host_error);return host_result;
}
static HRESULT WINAPI draw_indexed(D8Device*p,DWORD type,UINT min,UINT num,UINT count,const void*ix,DWORD fmt,const void*v,UINT stride){
    host_enter(p);CHECK(type==draw_type&&min==draw_min&&num==draw_num&&count==draw_count&&fmt==draw_fmt&&stride==draw_stride);
    copied(ix,0x8001,index_bytes);copied(v,0x6001,draw_bytes);if(reenter==3)scene_dispatch(active);SetLastError(host_error);return host_result;
}
static unsigned scene_nargs(void){return draw_mode==72?5:draw_mode==73?9:draw_mode==40||draw_mode==41?2:1;}
static void scene_setup(CPU*c){
    unsigned i,n;slot=50;a=14;b=1;d=0;setup(c);d8_device.caps.words[45]=65535;d8_device.caps.words[46]=1000000;d8_device.caps.words[48]=255;
    draw_stride=24;draw_type=4;draw_count=2;draw_min=1;draw_num=5;draw_fmt=101;current_fvf=0x44;queries=0;
    n=6;draw_bytes=n*draw_stride;index_bytes=n*2;
    for(i=0;i<1024;i++)wr8(0x6001+i,(BYTE)i);
    for(i=0;i<n;i++)wr16(0x8001+2*i,(WORD)(1+i%5));
    if(draw_mode==40||draw_mode==41){wr32(0x2008,0x6ffd);memcpy(G2H(0x6ffd),&viewport,24);}
    if(draw_mode==72){wr32(0x2008,draw_type);wr32(0x200c,draw_count);wr32(0x2010,0x6001);wr32(0x2014,draw_stride);}
    if(draw_mode==73){wr32(0x2008,draw_type);wr32(0x200c,draw_min);wr32(0x2010,draw_num);wr32(0x2014,draw_count);wr32(0x2018,0x8001);wr32(0x201c,draw_fmt);wr32(0x2020,0x6001);wr32(0x2024,draw_stride);}
    suspended=*c;guest_error=0x13572468;
}
static void scene_positive(CPU*c){
    CPU expected=*c;BYTE frame[48];unsigned mx=_mm_getcsr();memcpy(frame,G2H(0x2000),48);
    expected.rv=rd32(0x2000);expected.r[ESP]+=4*(scene_nargs()+1);expected.r[EAX]=(unsigned)host_result;
    scene_dispatch(c);CHECK(!memcmp(c,&expected,sizeof *c)&&!memcmp(frame,G2H(0x2000),48));
    CHECK(native_calls==1&&guest_error==host_error&&enters==leaves&&!active&&!d8_rendering);
    CHECK(_mm_getcsr()==mx&&d8_device.refs==1&&parent.children==1);scene_cases++;
}
static void scene_negative(CPU*c,unsigned allowed){
    CPU saved=*c;allow_fatal=1;if(!setjmp(stop)){scene_dispatch(c);CHECK(0);}allow_fatal=0;
    CHECK(failed_code==76&&native_calls==allowed&&!memcmp(&saved,c,sizeof *c));scene_negatives++;active=NULL;d8_rendering=0;reenter=0;
}
int main(void){
    CPU c;unsigned i,j,t,fmt,old;char*argv[]={"contracts",NULL};const unsigned modes[]={3,34,35,40,41,72,73};
    CHECK(retained_contract_main(1,argv)==0);
    guest_capacity=0x20000;xrt_g=VirtualAlloc(NULL,guest_capacity,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);CHECK(xrt_g);
    vt.TestCooperativeLevel=simple_scene;vt.BeginScene=simple_scene;vt.EndScene=simple_scene;vt.SetViewport=set_view;vt.GetViewport=get_view;
    vt.GetVertexShader=get_fvf;vt.DrawPrimitiveUP=draw_up;vt.DrawIndexedPrimitiveUP=draw_indexed;
    for(i=0;i<7;i++)for(j=0;j<3;j++){
        draw_mode=modes[i];scene_setup(&c);host_result=j==0?S_OK:j==1?S_FALSE:E_FAIL;host_error=j?0xffffffff:87;
        if(draw_mode==41){memset(G2H(0x6ffd),0xcc,24);scene_positive(&c);CHECK(!memcmp(G2H(0x6ffd),&viewport,24));}
        else scene_positive(&c);
    }
    for(t=1;t<=6;t++)for(j=0;j<2;j++){
        static const unsigned counts[]={0,2,4,3,6,4,4};
        draw_mode=72;scene_setup(&c);draw_type=t;draw_count=j?0:2;draw_bytes=(j?0:counts[t])*draw_stride;
        wr32(0x2008,t);wr32(0x200c,draw_count);host_result=S_OK;scene_positive(&c);
    }
    for(t=4;t<=6;t++)for(fmt=101;fmt<=102;fmt++){
        draw_mode=73;scene_setup(&c);draw_type=t;draw_fmt=fmt;draw_bytes=6*draw_stride;index_bytes=(t==4?6:4)*(fmt==101?2:4);
        wr32(0x2008,t);wr32(0x201c,fmt);if(fmt==102)for(j=0;j<6;j++)wr32(0x8001+4*j,1+j%5);scene_positive(&c);
    }
    draw_mode=72;scene_setup(&c);CHECK(VirtualProtect(G2H(0x6000),4096,PAGE_READONLY,&old));scene_positive(&c);CHECK(VirtualProtect(G2H(0x6000),4096,old,&old));
    scene_setup(&c);current_fvf=1;scene_negative(&c,0);
    scene_setup(&c);wr32(0x2014,4);scene_negative(&c,0);
    scene_setup(&c);wr32(0x200c,UINT32_MAX);scene_negative(&c,0);
    scene_setup(&c);wr32(0x2008,7);scene_negative(&c,0);
    scene_setup(&c);wr32(0x2010,0xfffffff0);scene_negative(&c,0);
    scene_setup(&c);wr32(0x2010,0x1fff0);scene_negative(&c,0);
    scene_setup(&c);CHECK(VirtualProtect(G2H(0x6000),4096,PAGE_NOACCESS,&old));scene_negative(&c,0);CHECK(VirtualProtect(G2H(0x6000),4096,old,&old));
    scene_setup(&c);d8_device.refs=0;scene_negative(&c,0);
    scene_setup(&c);reenter=3;scene_negative(&c,1);
    draw_mode=73;scene_setup(&c);wr16(0x8001,0);scene_negative(&c,0);
    scene_setup(&c);wr16(0x8001,6);scene_negative(&c,0);
    scene_setup(&c);wr32(0x201c,22);scene_negative(&c,0);
    scene_setup(&c);wr32(0x200c,UINT32_MAX);scene_negative(&c,0);
    scene_setup(&c);wr32(0x2020,0);scene_negative(&c,0);
    draw_mode=41;scene_setup(&c);CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_READONLY,&old));scene_negative(&c,0);CHECK(VirtualProtect(G2H(0x7000),4096,old,&old));
    scene_setup(&c);reenter=4;scene_negative(&c,1);CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_READWRITE,&old));
    draw_mode=40;scene_setup(&c);wr32(0x6ffd+16,0x7fc00000);scene_negative(&c,0);
    CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));
    printf("{\"passed\":true,\"scene_cases\":%u,\"scene_negatives\":%u,\"checks\":%u,\"graphics\":false}\n",scene_cases,scene_negatives,checks);return 0;
}
