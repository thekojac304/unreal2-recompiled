/* Native x86/x64 COM protocol doubles, invoking the real integrated adapters.
 * These do not claim native GPU behavior or a rendered game scene. */
#include "retained_scene.inc"
static unsigned map_size,map_live,resource_cases,resource_negatives,device_refs;
static int resource_reenter,protect_output;
static HRESULT lock_result=S_OK;
static int lock_null_failure;
static DWORD resource_out=0x7000;
uint32_t xrt_virtual_alloc(CPU*c,uint32_t n){DWORD old;(void)c;CHECK(!map_live&&n<=0x8000);CHECK(VirtualProtect(G2H(0x20000),0x8000,PAGE_READWRITE,&old));map_size=n;map_live=1;return 0x20000;}
int xrt_virtual_free(CPU*c,uint32_t p){DWORD old;(void)c;CHECK(map_live&&p==0x20000);CHECK(VirtualProtect(G2H(p),0x8000,PAGE_NOACCESS,&old));map_live=0;return 1;}
typedef struct Fake {void*vt;unsigned refs,kind,format,size,width,height;BYTE data[4096];} Fake;
static D8SurfaceVtable svt;static D8TextureVtable tvt;static D8BufferVtable bvt;
static Fake render,depth,mip,tex,vbuf,ibuf;
static Fake*boundv,*boundi,*boundt;static unsigned boundstride,boundbase;
static Fake*boundv1;static unsigned boundstride1;
static unsigned shader_serial,decl_words;static DWORD declaration[256];
static void rent(void){DWORD old;CHECK(active&&d8_rendering);native_calls++;CHECK(!memcmp(active,&suspended,sizeof suspended));
 if(resource_reenter)d8_resource_AddRef(active);
 if(protect_output)CHECK(VirtualProtect(G2H(resource_out),4096,PAGE_READONLY,&old));
}
static ULONG WINAPI radd(D8Unknown*p){Fake*f=(Fake*)p;rent();if(f==&mip)f=&tex;if(!f->refs)device_refs++;f->refs++;SetLastError(host_error);return f->refs;}
static ULONG WINAPI rrelease(D8Unknown*p){Fake*f=(Fake*)p;rent();if(f==&mip)f=&tex;CHECK(f->refs);if(!--f->refs)device_refs--;SetLastError(host_error);return f->refs;}
static ULONG WINAPI devadd(D8Device*p){CHECK(p==&host);SetLastError(host_error);return ++device_refs;}
static ULONG WINAPI devrelease(D8Device*p){CHECK(p==&host&&device_refs);SetLastError(host_error);return --device_refs;}
static HRESULT WINAPI rqi(D8Unknown*p,REFIID iid,void**q){rent();CHECK(iid);if(SUCCEEDED(host_result)&&q){radd(p);*q=p;}else if(q)*q=NULL;SetLastError(host_error);return host_result;}
static HRESULT WINAPI rdevice(D8Unknown*p,D8Device**q){rent();CHECK(p);if(SUCCEEDED(host_result)&&q){*q=&host;device_refs++;}else if(q)*q=NULL;SetLastError(host_error);return host_result;}
static HRESULT return_resource(Fake*f,void**q){rent();if(SUCCEEDED(host_result)&&q){radd((D8Unknown*)f);*q=f;}else if(q)*q=NULL;SetLastError(host_error);return host_result;}
static HRESULT WINAPI getrt(D8Device*p,D8Surface**q){CHECK(p==&host);return return_resource(&render,(void**)q);}
static HRESULT WINAPI getds(D8Device*p,D8Surface**q){CHECK(p==&host);return return_resource(&depth,(void**)q);}
static HRESULT WINAPI createt(D8Device*p,UINT w,UINT h,UINT levels,DWORD usage,DWORD fmt,DWORD pool,D8Texture**q){CHECK(p==&host&&w==8&&h==4&&levels==0&&usage==0&&pool==1);tex.format=fmt;return return_resource(&tex,(void**)q);}
static HRESULT WINAPI createv(D8Device*p,UINT size,DWORD usage,DWORD fvf,DWORD pool,D8Buffer**q){CHECK(p==&host&&size==240&&usage==0&&fvf==0x44&&pool==1);vbuf.size=size;return return_resource(&vbuf,(void**)q);}
static HRESULT WINAPI createi(D8Device*p,UINT size,DWORD usage,DWORD fmt,DWORD pool,D8Buffer**q){CHECK(p==&host&&size==12&&usage==0&&pool==1);ibuf.size=size;ibuf.format=fmt;return return_resource(&ibuf,(void**)q);}
static HRESULT WINAPI descs(D8Surface*p,D8SurfaceDesc*q){Fake*f=(Fake*)p;rent();q->format=f->format;q->type=1;q->usage=0;q->pool=1;q->size=f->width*f->height*4;q->multisample=0;q->width=f->width;q->height=f->height;SetLastError(host_error);return host_result;}
static HRESULT WINAPI desct(D8Texture*p,UINT level,D8SurfaceDesc*q){CHECK(level<4);descs((D8Surface*)p,q);q->width=q->width>>level?q->width>>level:1;q->height=q->height>>level?q->height>>level:1;return host_result;}
static HRESULT WINAPI descb(D8Buffer*p,D8BufferDesc*q){Fake*f=(Fake*)p;rent();q->format=f->format;q->type=f->kind;q->usage=0;q->pool=1;q->size=f->size;if(f->kind==6)q->fvf=0x44;SetLastError(host_error);return host_result;}
static HRESULT WINAPI getmip(D8Texture*p,UINT level,D8Surface**q){CHECK(p==(D8Texture*)&tex&&level==1);return return_resource(&mip,(void**)q);}
static HRESULT WINAPI container(D8Surface*p,REFIID iid,void**q){CHECK(p==(D8Surface*)&mip&&!memcmp(iid,&d8_texture_iid,16));return return_resource(&tex,q);}
static HRESULT WINAPI locks(D8Surface*p,D8Locked*q,const RECT*rect,DWORD flags){Fake*f=(Fake*)p;rent();CHECK(flags==0||flags==0x10);if(rect)CHECK(rect->left==0&&rect->top==0);if(SUCCEEDED(lock_result)){q->pitch=40;q->bits=f->data;}else if(lock_null_failure)q->bits=NULL;SetLastError(host_error);return lock_result;}
static HRESULT WINAPI lockt(D8Texture*p,UINT level,D8Locked*q,const RECT*rect,DWORD flags){CHECK(level<4);return locks((D8Surface*)p,q,rect,flags);}
static HRESULT WINAPI lockb(D8Buffer*p,UINT offset,UINT size,BYTE**q,DWORD flags){Fake*f=(Fake*)p;rent();CHECK(offset+size<=f->size);if(SUCCEEDED(lock_result))*q=f->data+offset;else if(lock_null_failure)*q=NULL;SetLastError(host_error);return lock_result;}
static HRESULT WINAPI unlocks(D8Surface*p){rent();CHECK(p);SetLastError(host_error);return host_result;}
static HRESULT WINAPI unlockt(D8Texture*p,UINT level){CHECK(level<4);return unlocks((D8Surface*)p);}
static HRESULT WINAPI unlockb(D8Buffer*p){return unlocks((D8Surface*)p);}
static HRESULT WINAPI settexture(D8Device*p,DWORD stage,void*q){rent();CHECK(p==&host&&stage==0);if(SUCCEEDED(host_result))boundt=q;SetLastError(host_error);return host_result;}
static HRESULT WINAPI setstream(D8Device*p,DWORD stream,void*q,DWORD stride){rent();CHECK(p==&host&&stream<2);if(SUCCEEDED(host_result)){if(stream){boundv1=q;if(q)boundstride1=stride;}else{boundv=q;if(q)boundstride=stride;}}SetLastError(host_error);return host_result;}
static HRESULT WINAPI setindex(D8Device*p,void*q,DWORD base){rent();CHECK(p==&host);if(SUCCEEDED(host_result)){boundi=q;boundbase=base;}SetLastError(host_error);return host_result;}
static HRESULT WINAPI getstream(D8Device*p,DWORD stream,void**q,DWORD*stride){Fake*f=stream?boundv1:boundv;rent();CHECK(p==&host&&stream<2);*q=f;*stride=stream?boundstride1:boundstride;if(f)radd((D8Unknown*)f);SetLastError(host_error);return S_OK;}
static HRESULT WINAPI getindex(D8Device*p,void**q,DWORD*base){rent();CHECK(p==&host);*q=boundi;*base=boundbase;if(boundi)radd((D8Unknown*)boundi);SetLastError(host_error);return S_OK;}
static HRESULT WINAPI gettexture(D8Device*p,DWORD stage,void**q){rent();CHECK(p==&host&&stage==0);*q=boundt;if(boundt)radd((D8Unknown*)boundt);SetLastError(host_error);return S_OK;}
static HRESULT WINAPI drawbuffer(D8Device*p,DWORD type,UINT start,UINT count){rent();CHECK(p==&host&&type==4&&start==0&&count==1);SetLastError(host_error);return host_result;}
static HRESULT WINAPI drawib(D8Device*p,DWORD type,UINT min,UINT num,UINT start,UINT count){rent();CHECK(p==&host&&type==4&&min==1&&num==3&&start==0&&count==1);SetLastError(host_error);return host_result;}
static HRESULT WINAPI targets(D8Device*p,D8Surface*r,D8Surface*d){rent();CHECK(p==&host&&r==(D8Surface*)&render&&d==(D8Surface*)&depth);SetLastError(host_error);return host_result;}
static HRESULT WINAPI update(D8Device*p,D8Texture*s,D8Texture*t){rent();CHECK(p==&host&&s==(D8Texture*)&tex&&t==s);SetLastError(host_error);return host_result;}
static DWORD WINAPI levelcount(D8Texture*p){rent();CHECK(p==(D8Texture*)&tex);SetLastError(host_error);return 4;}
static void WINAPI preload(D8Texture*p){rent();CHECK(p==(D8Texture*)&tex);SetLastError(host_error);}
static HRESULT WINAPI createdecl(D8Device*p,const DWORD*decl,const DWORD*code,DWORD*q,DWORD usage){rent();CHECK(p==&host&&!code&&(usage==0||usage==16));CHECK((const void*)decl!=G2H(0x9000)&&!memcmp(decl,declaration,decl_words*4));if(SUCCEEDED(host_result))*q=0x80000001u+2*shader_serial++;SetLastError(host_error);return host_result;}
static HRESULT WINAPI setdecl(D8Device*p,DWORD value){rent();CHECK(p==&host);if(SUCCEEDED(host_result))current_fvf=value;SetLastError(host_error);return host_result;}
static HRESULT WINAPI deldecl(D8Device*p,DWORD value){rent();CHECK(p==&host&&(value&0x80000000u));if(SUCCEEDED(host_result)&&current_fvf==value)current_fvf=0;SetLastError(host_error);return host_result;}
static HRESULT WINAPI getdecl(D8Device*p,DWORD*value){CHECK(p==&host&&active&&d8_rendering);queries++;*value=current_fvf;SetLastError(host_error);return S_OK;}
static void decl_input(const DWORD*words,unsigned n){memcpy(declaration,words,n*4);decl_words=n;memcpy(G2H(0x9000),declaration,n*4);}
static void frame(CPU*c,unsigned n,...){unsigned i;va_list ap;memset(c,0,sizeof *c);for(i=0;i<8;i++){c->r[i]=0x12345670+i;c->st[i]=i+.25;}c->fcw=0x27f;c->fsw=0x4020;c->top=3;c->df=1;c->r[ESP]=0x2000;c->pc=0x696fbcc;
 memset(G2H(0x2000),0xcc,64);wr32(0x2000,0x12345678);va_start(ap,n);for(i=0;i<n;i++)wr32(0x2004+4*i,va_arg(ap,unsigned));va_end(ap);suspended=*c;guest_error=0x13572468;native_calls=0;}
static void run(CPU*c,void(*fn)(CPU*),unsigned n){CPU expected=*c;BYTE stack[64];DWORD mx=_mm_getcsr();memcpy(stack,G2H(0x2000),64);fn(c);expected.r[EAX]=c->r[EAX];expected.r[ESP]+=4*(n+1);expected.rv=0x12345678;
 CHECK(!memcmp(&expected,c,sizeof *c)&&!memcmp(stack,G2H(0x2000),64)&&guest_error==host_error&&!d8_rendering&&!active&&_mm_getcsr()==mx);resource_cases++;}
static void negative(CPU*c,void(*fn)(CPU*)){CPU before=*c;allow_fatal=1;if(!setjmp(stop)){fn(c);CHECK(0);}allow_fatal=0;CHECK(failed_code==76&&!memcmp(&before,c,sizeof *c));resource_negatives++;d8_rendering=0;active=NULL;resource_reenter=protect_output=0;}
static void init_fake(Fake*f,void*table,unsigned kind,unsigned fmt,unsigned w,unsigned h){memset(f,0,sizeof *f);f->vt=table;f->kind=kind;f->format=fmt;f->width=w;f->height=h;memset(f->data,0x5a,sizeof f->data);}
int main(void){CPU c;unsigned rt,ds,t,s,v,b,q,i,old,token,shader_handle;D8Resource*r;
 CHECK(scene_contract_main()==0);guest_capacity=0x30000;xrt_g=VirtualAlloc(NULL,guest_capacity,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(xrt_g);resource_bump=0x12000;
 slot=50;a=14;b=1;d=0;setup(&c);d8_device.caps.words[22]=4096;d8_device.caps.words[23]=4096;d8_device.caps.words[45]=65535;d8_device.caps.words[46]=1000000;d8_device.caps.words[47]=16;d8_device.caps.words[48]=255;device_refs=1;host_result=S_OK;host_error=0xdeadbeef;
 svt.QueryInterface=(void*)rqi;svt.AddRef=(void*)radd;svt.Release=(void*)rrelease;svt.GetDevice=(void*)rdevice;svt.GetDesc=descs;svt.GetContainer=container;svt.LockRect=locks;svt.UnlockRect=unlocks;
 tvt.QueryInterface=(void*)rqi;tvt.AddRef=(void*)radd;tvt.Release=(void*)rrelease;tvt.GetDevice=(void*)rdevice;tvt.GetLevelDesc=desct;tvt.GetSurfaceLevel=getmip;tvt.LockRect=lockt;tvt.UnlockRect=unlockt;tvt.GetLevelCount=levelcount;tvt.PreLoad=preload;
 bvt.QueryInterface=(void*)rqi;bvt.AddRef=(void*)radd;bvt.Release=(void*)rrelease;bvt.GetDevice=(void*)rdevice;bvt.GetDesc=descb;bvt.Lock=lockb;bvt.Unlock=unlockb;
 init_fake(&render,&svt,1,22,8,4);init_fake(&depth,&svt,1,75,8,4);init_fake(&tex,&tvt,3,21,8,4);init_fake(&mip,&svt,1,21,4,2);init_fake(&vbuf,&bvt,6,100,0,0);init_fake(&ibuf,&bvt,7,101,0,0);
 vt.GetRenderTarget=getrt;vt.GetDepthStencilSurface=getds;vt.CreateTexture=createt;vt.CreateVertexBuffer=createv;vt.CreateIndexBuffer=createi;vt.SetTexture=settexture;vt.SetStreamSource=setstream;vt.SetIndices=setindex;vt.GetStreamSource=getstream;vt.GetIndices=getindex;vt.GetTexture=gettexture;vt.DrawPrimitive=drawbuffer;vt.DrawIndexedPrimitive=drawib;vt.SetRenderTarget=targets;vt.UpdateTexture=update;vt.AddRef=devadd;vt.Release=devrelease;
 frame(&c,2,0x4000,0x7000);run(&c,d8_device_GetRenderTarget,2);rt=rd32(0x7000);CHECK(rt&&render.refs==1&&d8_device.children==1);
 frame(&c,2,0x4000,0x7000);run(&c,d8_device_GetRenderTarget,2);CHECK(rd32(0x7000)==rt&&render.refs==2);
 frame(&c,1,rt);run(&c,d8_resource_Release,1);CHECK(c.r[EAX]==1);
 frame(&c,1,rt);run(&c,d8_resource_AddRef,1);CHECK(c.r[EAX]==2);
 memcpy(G2H(0x8000),&d8_surface_iid,16);frame(&c,3,rt,0x8000,0x7000);run(&c,d8_resource_QueryInterface,3);CHECK(rd32(0x7000)==rt&&render.refs==3);
 frame(&c,2,0x4000,0x7000);run(&c,d8_device_GetDepthStencilSurface,2);ds=rd32(0x7000);CHECK(ds!=rt);
 frame(&c,3,0x4000,rt,ds);run(&c,d8_device_SetRenderTarget,3);
 frame(&c,2,rt,0x7000);run(&c,d8_resource_GetDesc,2);CHECK(rd32(0x7018)==8&&rd32(0x701c)==4);
 /* Device-first release, then resource GetDevice resurrection. */
 frame(&c,1,0x4000);run(&c,d8_device_Release,1);CHECK(!d8_device.refs&&d8_device.host&&device_refs==2&&parent.children==1);
 frame(&c,2,rt,0x7000);run(&c,d8_resource_GetDevice,2);CHECK(rd32(0x7000)==0x4000&&d8_device.refs==1);
 /* Native failures and output-page revalidation. */
 host_result=E_FAIL;wr32(0x7000,0xaabbccdd);frame(&c,2,0x4000,0x7000);run(&c,d8_device_GetDepthStencilSurface,2);CHECK(c.r[EAX]==(unsigned)E_FAIL&&!rd32(0x7000));host_result=S_OK;
 frame(&c,2,0x4000,0x7000);CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_READONLY,&old));negative(&c,d8_device_GetRenderTarget);CHECK(!native_calls);CHECK(VirtualProtect(G2H(0x7000),4096,old,&old));
 frame(&c,2,0x4000,0x7000);protect_output=1;negative(&c,d8_device_GetRenderTarget);CHECK(render.refs==4);CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_READWRITE,&old));
 frame(&c,1,rt);resource_reenter=1;negative(&c,d8_resource_AddRef);CHECK(render.refs==4);
 frame(&c,2,0x4000,0xffffffff);negative(&c,d8_device_GetRenderTarget);CHECK(!native_calls);
 frame(&c,2,0x4000,0x7000);c.r[ESP]=0x2fffdu;negative(&c,d8_device_GetRenderTarget);CHECK(!native_calls);
 /* Texture mip identity, container, padded map upload, readonly map. */
 frame(&c,8,0x4000,8,4,0,0,21,1,0x7000);run(&c,d8_device_CreateTexture,8);t=rd32(0x7000);
 frame(&c,1,t);run(&c,d8_resource_GetLevelCount,1);CHECK(c.r[EAX]==4);
 frame(&c,1,t);q=c.r[EAX];run(&c,d8_resource_PreLoad,1);CHECK(c.r[EAX]==q);
 frame(&c,3,t,1,0x7000);run(&c,d8_resource_GetLevelDesc,3);CHECK(rd32(0x7018)==4&&rd32(0x701c)==2);
 frame(&c,3,t,1,0x7000);run(&c,d8_resource_GetSurfaceLevel,3);s=rd32(0x7000);
 memcpy(G2H(0x8000),&d8_texture_iid,16);frame(&c,3,s,0x8000,0x7000);run(&c,d8_resource_GetContainer,3);CHECK(rd32(0x7000)==t);
 CHECK(tex.refs==3);frame(&c,1,t);run(&c,d8_resource_Release,1);CHECK(c.r[EAX]==2);frame(&c,1,t);run(&c,d8_resource_Release,1);CHECK(c.r[EAX]==1);
 frame(&c,3,s,0x8000,0x7000);run(&c,d8_resource_GetContainer,3);CHECK(rd32(0x7000)!=t);t=rd32(0x7000);
 for(i=0;i<2;i++){lock_result=E_FAIL;lock_null_failure=i;wr32(0x7000,123);wr32(0x7004,0xaabbccdd);frame(&c,5,t,0,0x7000,0,0);run(&c,d8_resource_LockRect,5);CHECK(c.r[EAX]==(unsigned)E_FAIL&&rd32(0x7000)==123&&rd32(0x7004)==(i?0:0xaabbccdd)&&!d8_locks);}lock_result=S_OK;lock_null_failure=0;
 frame(&c,5,t,0,0x7000,0,0);run(&c,d8_resource_LockRect,5);q=rd32(0x7004);CHECK(q==0x20000&&rd32(0x7000)==40&&map_size==160);memset(G2H(q),0x33,160);
 frame(&c,5,t,0,0x7000,0,0);negative(&c,d8_resource_LockRect);CHECK(!native_calls);
 frame(&c,2,t,1);negative(&c,d8_resource_UnlockRect);CHECK(!native_calls);
 frame(&c,1,t);negative(&c,d8_resource_Release);CHECK(!native_calls);
 frame(&c,2,t,0);run(&c,d8_resource_UnlockRect,2);CHECK(!map_live&&!d8_locks);for(i=0;i<160;i++)CHECK(tex.data[i]==(i%40<32?0x33:0x5a));
 frame(&c,5,t,0,0x7000,0,0x10);run(&c,d8_resource_LockRect,5);memset(G2H(0x20000),0x44,160);frame(&c,2,t,0);run(&c,d8_resource_UnlockRect,2);CHECK(tex.data[0]==0x33);
 frame(&c,4,s,0x7000,0,0);run(&c,d8_resource_LockRect,4);frame(&c,1,s);run(&c,d8_resource_UnlockRect,1);
 tex.format=0x31545844;frame(&c,5,t,0,0x7000,0,0);run(&c,d8_resource_LockRect,5);CHECK(map_size==40);memset(G2H(0x20000),0x66,40);frame(&c,2,t,0);run(&c,d8_resource_UnlockRect,2);CHECK(tex.data[15]==0x66&&tex.data[16]==0x33);tex.format=21;
 frame(&c,3,0x4000,0,t);run(&c,d8_device_SetTexture,3);frame(&c,3,0x4000,0,0x7000);run(&c,d8_device_GetTexture,3);CHECK(rd32(0x7000)==t);
 frame(&c,3,0x4000,t,t);run(&c,d8_device_UpdateTexture,3);
 /* Typed buffer uploads and actual buffer draw calls, 16/32-bit indices. */
 frame(&c,6,0x4000,240,0,0x44,1,0x7000);run(&c,d8_device_CreateVertexBuffer,6);v=rd32(0x7000);
 for(i=0;i<2;i++){lock_result=E_FAIL;lock_null_failure=i;wr32(0x7000,0xaabbccdd);frame(&c,5,v,0,0,0x7000,0);run(&c,d8_resource_Lock,5);CHECK(c.r[EAX]==(unsigned)E_FAIL&&rd32(0x7000)==(i?0:0xaabbccdd)&&!d8_locks);}lock_result=S_OK;lock_null_failure=0;
 frame(&c,5,v,0,0,0x7000,0);run(&c,d8_resource_Lock,5);CHECK(map_size==240);memset(G2H(rd32(0x7000)),0x11,240);
 frame(&c,1,v);run(&c,d8_resource_Unlock,1);CHECK(vbuf.data[239]==0x11);
 frame(&c,4,0x4000,0,v,24);run(&c,d8_device_SetStreamSource,4);
 frame(&c,4,0x4000,4,0,1);run(&c,d8_device_DrawPrimitive,4);
 /* Actual engine's declaration-only shader family, including two streams. */
 vt.CreateVertexShader=createdecl;vt.SetVertexShader=setdecl;vt.DeleteVertexShader=deldecl;vt.GetVertexShader=getdecl;
 {DWORD decl[]={0x20000000,0x40030000,0x40040005,0xffffffff};decl_input(decl,4);}
 host_result=E_FAIL;wr32(0x7000,0xaabbccdd);frame(&c,5,0x4000,0x9000,0,0x7000,0);run(&c,d8_device_CreateVertexShader,5);CHECK(c.r[EAX]==(unsigned)E_FAIL&&rd32(0x7000)==0xaabbccdd);host_result=S_OK;
 frame(&c,5,0x4000,0x9000,0,0x7000,16);run(&c,d8_device_CreateVertexShader,5);shader_handle=rd32(0x7000);CHECK(shader_handle!=0x80000001);
 frame(&c,2,0x4000,shader_handle);run(&c,d8_device_SetVertexShader,2);frame(&c,2,0x4000,0x7000);run(&c,d8_device_GetVertexShader,2);CHECK(rd32(0x7000)==shader_handle);
 frame(&c,4,0x4000,4,0,1);run(&c,d8_device_DrawPrimitive,4);
 frame(&c,2,0x4000,shader_handle);run(&c,d8_device_DeleteVertexShader,2);frame(&c,2,0x4000,shader_handle);negative(&c,d8_device_SetVertexShader);CHECK(!native_calls);
 {DWORD decl[]={0x20000000,0x50010000,0x40020000,0x20000001,0x40040005,0xffffffff};decl_input(decl,6);}
 frame(&c,5,0x4000,0x9000,0,0x7000,0);run(&c,d8_device_CreateVertexShader,5);shader_handle=rd32(0x7000);frame(&c,2,0x4000,shader_handle);run(&c,d8_device_SetVertexShader,2);
 frame(&c,4,0x4000,4,0,1);negative(&c,d8_device_DrawPrimitive);CHECK(!native_calls);
 frame(&c,4,0x4000,1,v,24);run(&c,d8_device_SetStreamSource,4);frame(&c,4,0x4000,4,0,1);run(&c,d8_device_DrawPrimitive,4);
 frame(&c,4,0x4000,1,0,0);run(&c,d8_device_SetStreamSource,4);frame(&c,2,0x4000,shader_handle);run(&c,d8_device_DeleteVertexShader,2);
 frame(&c,2,0x4000,0x44);run(&c,d8_device_SetVertexShader,2);
 {const DWORD bad[]={0x20000010,0x40000011,0x80000000,0x60000000,0x40080000,0x50000001};for(i=0;i<6;i++){DWORD decl[]={0,0xffffffff};decl[0]=bad[i];decl_input(decl,2);frame(&c,5,0x4000,0x9000,0,0x7000,0);negative(&c,d8_device_CreateVertexShader);CHECK(!native_calls);}}
 {DWORD decl[]={0x20000000,0x40020000,0x40020000,0xffffffff};decl_input(decl,4);frame(&c,5,0x4000,0x9000,0,0x7000,0);negative(&c,d8_device_CreateVertexShader);CHECK(!native_calls);}
 memset(G2H(0x9000),0,1024);frame(&c,5,0x4000,0x9000,0,0x7000,0);negative(&c,d8_device_CreateVertexShader);CHECK(!native_calls);
 frame(&c,5,0x4000,0x9000,0x8000,0x7000,0);negative(&c,d8_device_CreateVertexShader);CHECK(!native_calls);
 frame(&c,5,0x4000,0x2fffc,0,0x7000,0);wr32(0x2fffc,0);negative(&c,d8_device_CreateVertexShader);CHECK(!native_calls);
 frame(&c,6,0x4000,12,0,101,1,0x7000);run(&c,d8_device_CreateIndexBuffer,6);b=rd32(0x7000);
 for(i=101;i<=102;i++){
  ibuf.format=i; r=d8_resource(&c,b,D8_INDEX);if(r->shadow){d8_shadow_bytes-=2ull*r->length;HeapFree(GetProcessHeap(),0,r->shadow);HeapFree(GetProcessHeap(),0,r->valid);r->shadow=r->valid=NULL;}
  frame(&c,5,b,0,0,0x7000,0);run(&c,d8_resource_Lock,5);q=rd32(0x7000);if(i==101){wr16(q,1);wr16(q+2,2);wr16(q+4,3);}else{wr32(q,1);wr32(q+4,2);wr32(q+8,3);}
  frame(&c,1,b);run(&c,d8_resource_Unlock,1);frame(&c,3,0x4000,b,1);run(&c,d8_device_SetIndices,3);
  frame(&c,6,0x4000,4,1,3,0,1);run(&c,d8_device_DrawIndexedPrimitive,6);
 }
 frame(&c,6,0x4000,4,2,2,0,1);negative(&c,d8_device_DrawIndexedPrimitive);
 frame(&c,6,0x4000,4,1,3,3,1);negative(&c,d8_device_DrawIndexedPrimitive);
 frame(&c,4,0x4000,0,t,24);negative(&c,d8_device_SetStreamSource);CHECK(!native_calls);
 frame(&c,5,v,239,2,0x7000,0);negative(&c,d8_resource_Lock);
 frame(&c,5,v,0,0,0x7000,0);run(&c,d8_resource_Lock,5);CHECK(VirtualProtect(G2H(0x20000),4096,PAGE_NOACCESS,&old));frame(&c,1,v);negative(&c,d8_resource_Unlock);CHECK(!native_calls);CHECK(VirtualProtect(G2H(0x20000),4096,PAGE_READWRITE,&old));frame(&c,1,v);run(&c,d8_resource_Unlock,1);
 /* Bound reference is native-owned: external zero rejects stale use, getter revives identity. */
 frame(&c,1,v);run(&c,d8_resource_Release,1);frame(&c,1,v);negative(&c,d8_resource_AddRef);
 frame(&c,4,0x4000,0,0x7000,0x7004);run(&c,d8_device_GetStreamSource,4);CHECK(rd32(0x7000)==v&&rd32(0x7004)==24);
 frame(&c,3,0x4000,0x7000,0x7004);run(&c,d8_device_GetIndices,3);CHECK(rd32(0x7000)==b&&rd32(0x7004)==1);
 frame(&c,4,0x4000,0,0x7000,0x7002);negative(&c,d8_device_GetStreamSource);CHECK(!native_calls);
 frame(&c,4,0x4000,0,0,0);run(&c,d8_device_SetStreamSource,4);frame(&c,3,0x4000,0,0);run(&c,d8_device_SetIndices,3);frame(&c,3,0x4000,0,0);run(&c,d8_device_SetTexture,3);
 /* Native Unlock failure transfers the failure and retains uncertain state. */
 frame(&c,5,v,0,0,0x7000,0);run(&c,d8_resource_Lock,5);host_result=E_FAIL;frame(&c,1,v);run(&c,d8_resource_Unlock,1);CHECK(c.r[EAX]==(unsigned)E_FAIL&&d8_native_failed&&d8_locks&&map_live);
 frame(&c,2,0x4000,0x7000);negative(&c,d8_device_GetRenderTarget);CHECK(!native_calls);
 /* Only the declared double harness resets its injected failure for cleanup. */
 host_result=S_OK;d8_native_failed=0;d8_locks=0;r=d8_resource(&c,v,D8_VERTEX);CHECK(xrt_virtual_free(&c,r->staging));r->staging=0;r->locked=NULL;
 /* Retire and reacquire same native address: fresh guest identity. */
 frame(&c,1,ds);run(&c,d8_resource_Release,1);frame(&c,2,0x4000,0x7000);run(&c,d8_device_GetDepthStencilSurface,2);token=rd32(0x7000);CHECK(token!=ds);frame(&c,1,ds);negative(&c,d8_resource_AddRef);
 /* Cleanup releases each external ref, without inventing native release counts. */
 for(i=0;i<d8_resource_used;i++)while(d8_resources[i].refs){frame(&c,1,d8_resources[i].guest);run(&c,d8_resource_Release,1);}
 CHECK(!d8_device.children&&device_refs==1&&!d8_shadow_bytes);frame(&c,1,0x4000);run(&c,d8_device_Release,1);CHECK(!device_refs&&!d8_device.host&&!parent.children);
 CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));printf("{\"passed\":true,\"resource_cases\":%u,\"resource_negatives\":%u,\"checks\":%u,\"graphics\":false}\n",resource_cases,resource_negatives,checks);return 0;
}
