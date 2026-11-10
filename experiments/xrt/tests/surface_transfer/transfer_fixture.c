/* Declared backend doubles plus the entire preceding resource/scene suite. */
#include "retained_resource.inc"
static Fake offscreen,customrt,customds;
static unsigned fail_output,copy_mode,copy_count;
static RECT expected_rects[256];static POINT expected_points[256];
static HRESULT surface_return(Fake*f,D8Surface**q){
 if(FAILED(host_result)){rent();if(q&&fail_output==1)*q=NULL;else if(q&&fail_output==2)*q=(D8Surface*)f;SetLastError(host_error);return host_result;}
 return return_resource(f,(void**)q);
}
static HRESULT WINAPI back(D8Device*p,UINT index,DWORD type,D8Surface**q){CHECK(p==&host&&index==0&&type==0);return surface_return(&render,q);}
static HRESULT WINAPI image_surface(D8Device*p,UINT w,UINT h,DWORD format,D8Surface**q){CHECK(p==&host&&w==8&&h==4&&format==21);return surface_return(&offscreen,q);}
static HRESULT WINAPI render_surface(D8Device*p,UINT w,UINT h,DWORD format,DWORD ms,BOOL lock,D8Surface**q){CHECK(p==&host&&w==8&&h==4&&format==21&&ms==0&&lock==1);return surface_return(&customrt,q);}
static HRESULT WINAPI depth_surface(D8Device*p,UINT w,UINT h,DWORD format,DWORD ms,D8Surface**q){CHECK(p==&host&&w==8&&h==4&&format==75&&ms==0);return surface_return(&customds,q);}
static HRESULT WINAPI copy_rects(D8Device*p,D8Surface*src,const RECT*rects,UINT n,D8Surface*dst,const POINT*points){
 rent();CHECK(p==&host&&src==(D8Surface*)&offscreen&&dst==(D8Surface*)&customrt&&n==copy_count);
 CHECK((rects!=NULL)==!!(copy_mode&1)&&(points!=NULL)==!!(copy_mode&2));
 if(rects){CHECK((const void*)rects!=G2H(0x8000));memset(G2H(0x8000),0xdd,n*sizeof(RECT));CHECK(!memcmp(rects,expected_rects,n*sizeof(RECT)));}
 if(points){CHECK((const void*)points!=G2H(0xa000));memset(G2H(0xa000),0xee,n*sizeof(POINT));CHECK(!memcmp(points,expected_points,n*sizeof(POINT)));}
 if(SUCCEEDED(host_result))memcpy(customrt.data,offscreen.data,sizeof customrt.data);
 SetLastError(host_error);return host_result;
}
static HRESULT WINAPI front(D8Device*p,D8Surface*dst){rent();CHECK(p==&host&&dst==(D8Surface*)&offscreen);SetLastError(host_error);return host_result;}
static void transfer_cases(CPU*c){
 unsigned start=resource_cases,neg=resource_negatives,im,rt,ds,bb,old,i,j;
 init_fake(&offscreen,&svt,1,21,8,4);init_fake(&customrt,&svt,1,21,8,4);init_fake(&customds,&svt,1,75,8,4);
 vt.GetBackBuffer=back;vt.CreateImageSurface=image_surface;vt.CreateRenderTarget=render_surface;vt.CreateDepthStencilSurface=depth_surface;vt.CopyRects=copy_rects;vt.GetFrontBuffer=front;
 frame(c,4,0x4000,0,0,0x7000);run(c,d8_device_GetBackBuffer,4);bb=rd32(0x7000);CHECK(d8_resource(c,bb,1)->host==(D8Unknown*)&render);
 frame(c,5,0x4000,8,4,21,0x7000);run(c,d8_device_CreateImageSurface,5);im=rd32(0x7000);
 frame(c,7,0x4000,8,4,21,0,1,0x7000);run(c,d8_device_CreateRenderTarget,7);rt=rd32(0x7000);
 frame(c,6,0x4000,8,4,75,0,0x7000);run(c,d8_device_CreateDepthStencilSurface,6);ds=rd32(0x7000);CHECK(im!=rt&&rt!=ds);
 /* Writable upload, copied rectangle arrays, surface readback and release. */
 frame(c,4,im,0x7000,0,0);run(c,d8_resource_LockRect,4);memset(G2H(rd32(0x7004)),0x79,160);frame(c,1,im);run(c,d8_resource_UnlockRect,1);
 for(i=0;i<256;i++){expected_rects[i].left=0;expected_rects[i].top=0;expected_rects[i].right=8;expected_rects[i].bottom=4;expected_points[i].x=0;expected_points[i].y=0;}
 for(copy_count=0;copy_count<=256;copy_count=copy_count?copy_count*256:1){
  for(copy_mode=0;copy_mode<4;copy_mode++){
   memcpy(G2H(0x8000),expected_rects,sizeof expected_rects);memcpy(G2H(0xa000),expected_points,sizeof expected_points);
   frame(c,6,0x4000,im,copy_mode&1?0x8000:0,copy_count,rt,copy_mode&2?0xa000:0);run(c,d8_device_CopyRects,6);
  }
 }
 frame(c,4,rt,0x7000,0,0x10);run(c,d8_resource_LockRect,4);CHECK(*(BYTE*)G2H(rd32(0x7004))==0x79);frame(c,1,rt);run(c,d8_resource_UnlockRect,1);
 frame(c,2,0x4000,im);run(c,d8_device_GetFrontBuffer,2);
 /* Each object's failed getter/creation output may be untouched or NULL. */
 host_result=E_FAIL;
 for(fail_output=0;fail_output<2;fail_output++)for(j=0;j<4;j++){
  wr32(0x7000,0xaabbccdd);
  if(j==0){frame(c,4,0x4000,0,0,0x7000);run(c,d8_device_GetBackBuffer,4);}
  if(j==1){frame(c,5,0x4000,8,4,21,0x7000);run(c,d8_device_CreateImageSurface,5);}
  if(j==2){frame(c,7,0x4000,8,4,21,0,1,0x7000);run(c,d8_device_CreateRenderTarget,7);}
  if(j==3){frame(c,6,0x4000,8,4,75,0,0x7000);run(c,d8_device_CreateDepthStencilSurface,6);}
  CHECK(c->r[EAX]==(unsigned)E_FAIL&&rd32(0x7000)==(fail_output?0:0xaabbccdd));
 }
 frame(c,5,0x4000,8,4,21,0);run(c,d8_device_CreateImageSurface,5);CHECK(c->r[EAX]==(unsigned)E_FAIL);
 copy_count=1;copy_mode=0;frame(c,6,0x4000,im,0,1,rt,0);run(c,d8_device_CopyRects,6);CHECK(c->r[EAX]==(unsigned)E_FAIL);
 frame(c,2,0x4000,im);run(c,d8_device_GetFrontBuffer,2);CHECK(c->r[EAX]==(unsigned)E_FAIL);
 fail_output=2;frame(c,5,0x4000,8,4,21,0x7000);negative(c,d8_device_CreateImageSurface);CHECK(d8_native_failed);d8_native_failed=0;fail_output=0;host_result=S_OK;
 /* Invalid guest ranges/types/counts stop before the native copy. */
 frame(c,6,0x4000,im,0x8000,257,rt,0);negative(c,d8_device_CopyRects);CHECK(!native_calls);
 frame(c,6,0x4000,im,0xfffffff8,1,rt,0);negative(c,d8_device_CopyRects);CHECK(!native_calls);
 frame(c,6,0x4000,im,0x8000,1,rt,0x2fffc);negative(c,d8_device_CopyRects);CHECK(!native_calls);
 frame(c,6,0x4000,0xdead,0,1,rt,0);negative(c,d8_device_CopyRects);CHECK(!native_calls);
 frame(c,5,0x4000,16385,4,21,0x7000);negative(c,d8_device_CreateImageSurface);CHECK(!native_calls);
 frame(c,5,0x4000,8,4,21,0x2ffff);negative(c,d8_device_CreateImageSurface);CHECK(!native_calls);
 frame(c,4,im,0x7000,0,0);run(c,d8_resource_LockRect,4);
 frame(c,6,0x4000,im,0,1,rt,0);negative(c,d8_device_CopyRects);CHECK(!native_calls);
 frame(c,2,0x4000,im);negative(c,d8_device_GetFrontBuffer);CHECK(!native_calls);
 frame(c,1,im);run(c,d8_resource_UnlockRect,1);
 frame(c,5,0x4000,8,4,21,0x7000);protect_output=1;negative(c,d8_device_CreateImageSurface);CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_READWRITE,&old));CHECK(offscreen.refs==2);
 frame(c,2,0x4000,im);resource_reenter=1;negative(c,d8_device_GetFrontBuffer);
 /* Device-first release and resurrection through a created surface. */
 frame(c,1,0x4000);run(c,d8_device_Release,1);CHECK(!d8_device.refs&&d8_device.host);
 frame(c,2,im,0x7000);run(c,d8_resource_GetDevice,2);CHECK(d8_device.refs==1);
 printf("{\"passed\":true,\"transfer_cases\":%u,\"transfer_negatives\":%u,\"native_gpu\":false}\n",resource_cases-start,resource_negatives-neg);
}
int main(void){return resources_main();}
