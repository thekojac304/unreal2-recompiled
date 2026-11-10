/* Physical fixture only: actual pinned native D3D8, no game code. */
static uintptr_t ga[9],gobject;static unsigned gslot,gn,gcalls;static void*gbits;static INT gpitch;
static D8SurfaceDesc gdesc;static DWORD gscalar;
static DWORD WINAPI resource_wrapper(uintptr_t ignored,uintptr_t unused) {
 HRESULT hr=E_FAIL;DWORD error;void*q=NULL;D8Locked locked={0};D8Device*dev=device;D8Texture*t=(D8Texture*)ga[0];D8Buffer*b=(D8Buffer*)ga[0];D8Surface*s=(D8Surface*)ga[0];D8Unknown*u=(D8Unknown*)ga[0];
 (void)ignored;(void)unused;gobject=0;gbits=NULL;gpitch=0;gscalar=0;
#if BATCH_TRANSLATED
 guest_error=GetLastError();
 switch(gslot){
 case 15:d8_device_Present(&cpu);break;case 20:d8_device_CreateTexture(&cpu);break;case 23:d8_device_CreateVertexBuffer(&cpu);break;case 24:d8_device_CreateIndexBuffer(&cpu);break;
 case 31:d8_device_SetRenderTarget(&cpu);break;case 32:d8_device_GetRenderTarget(&cpu);break;case 33:d8_device_GetDepthStencilSurface(&cpu);break;
 case 34:d8_device_BeginScene(&cpu);break;case 35:d8_device_EndScene(&cpu);break;case 36:d8_device_Clear(&cpu);break;
 case 40:d8_device_SetViewport(&cpu);break;case 41:d8_device_GetViewport(&cpu);break;
 case 61:d8_device_SetTexture(&cpu);break;case 70:d8_device_DrawPrimitive(&cpu);break;case 71:d8_device_DrawIndexedPrimitive(&cpu);break;
 case 75:d8_device_CreateVertexShader(&cpu);break;case 76:d8_device_SetVertexShader(&cpu);break;case 77:d8_device_GetVertexShader(&cpu);break;case 78:d8_device_DeleteVertexShader(&cpu);break;
 case 83:d8_device_SetStreamSource(&cpu);break;case 85:d8_device_SetIndices(&cpu);break;
 case 300:d8_resource_QueryInterface(&cpu);break;case 301:d8_resource_AddRef(&cpu);break;case 302:d8_resource_Release(&cpu);break;case 303:d8_resource_GetDevice(&cpu);break;
 case 308:d8_resource_GetDesc(&cpu);break;case 311:d8_resource_Lock(&cpu);break;case 312:d8_resource_Unlock(&cpu);break;case 313:d8_resource_GetLevelCount(&cpu);break;
 case 314:d8_resource_GetLevelDesc(&cpu);break;case 315:d8_resource_GetSurfaceLevel(&cpu);break;case 316:d8_resource_LockRect(&cpu);break;case 317:d8_resource_UnlockRect(&cpu);break;
 default:abort();}
 hr=(HRESULT)cpu.r[EAX];error=guest_error;
 if(gslot==20||gslot==23||gslot==24||gslot==32||gslot==33||gslot==300||gslot==303||gslot==315)gobject=rd32(0x7000);
 if(gslot==311&&SUCCEEDED(hr))gbits=G2H(rd32(0x7000));
 if(gslot==316&&SUCCEEDED(hr)){gpitch=(INT)rd32(0x7000);gbits=G2H(rd32(0x7004));}
 if(gslot==308||gslot==314)memcpy(&gdesc,G2H(0x7000),sizeof gdesc);
 if(gslot==313)gscalar=cpu.r[EAX];
 if(gslot==75||gslot==77)gscalar=rd32(0x7000);
#else
 switch(gslot){
 case 15:hr=dev->vt->Present(dev,NULL,NULL,NULL,NULL);break;
 case 20:hr=dev->vt->CreateTexture(dev,(UINT)ga[1],(UINT)ga[2],(UINT)ga[3],(DWORD)ga[4],(DWORD)ga[5],(DWORD)ga[6],(D8Texture**)&q);break;
 case 23:hr=dev->vt->CreateVertexBuffer(dev,(UINT)ga[1],(DWORD)ga[2],(DWORD)ga[3],(DWORD)ga[4],(D8Buffer**)&q);break;
 case 24:hr=dev->vt->CreateIndexBuffer(dev,(UINT)ga[1],(DWORD)ga[2],(DWORD)ga[3],(DWORD)ga[4],(D8Buffer**)&q);break;
 case 31:hr=dev->vt->SetRenderTarget(dev,(D8Surface*)ga[1],(D8Surface*)ga[2]);break;
 case 32:hr=dev->vt->GetRenderTarget(dev,(D8Surface**)&q);break;case 33:hr=dev->vt->GetDepthStencilSurface(dev,(D8Surface**)&q);break;
 case 34:hr=dev->vt->BeginScene(dev);break;case 35:hr=dev->vt->EndScene(dev);break;
 case 36:hr=dev->vt->Clear(dev,0,NULL,1,0xff123456,1,0);break;
 case 40:hr=dev->vt->SetViewport(dev,(D8Viewport*)G2H(0x8000));break;case 41:hr=dev->vt->GetViewport(dev,(D8Viewport*)G2H(0x8000));break;
 case 61:hr=dev->vt->SetTexture(dev,(DWORD)ga[1],(void*)ga[2]);break;
 case 70:hr=dev->vt->DrawPrimitive(dev,(DWORD)ga[1],(UINT)ga[2],(UINT)ga[3]);break;
 case 71:hr=dev->vt->DrawIndexedPrimitive(dev,(DWORD)ga[1],(UINT)ga[2],(UINT)ga[3],(UINT)ga[4],(UINT)ga[5]);break;
 case 75:hr=dev->vt->CreateVertexShader(dev,(DWORD*)G2H(0x9000),NULL,&gscalar,(DWORD)ga[4]);break;
 case 76:hr=dev->vt->SetVertexShader(dev,(DWORD)ga[1]);break;
 case 77:hr=dev->vt->GetVertexShader(dev,&gscalar);break;
 case 78:hr=dev->vt->DeleteVertexShader(dev,(DWORD)ga[1]);break;
 case 83:hr=dev->vt->SetStreamSource(dev,(DWORD)ga[1],(void*)ga[2],(DWORD)ga[3]);break;case 85:hr=dev->vt->SetIndices(dev,(void*)ga[1],(DWORD)ga[2]);break;
 case 300:hr=u->vt->QueryInterface(u,(GUID*)G2H(0x8000),&q);break;case 301:hr=(HRESULT)u->vt->AddRef(u);break;case 302:hr=(HRESULT)u->vt->Release(u);break;
 case 303:hr=u->vt->GetDevice(u,(D8Device**)&q);break;
 case 308:hr=s->vt->GetDesc(s,&gdesc);break;
 case 311:hr=b->vt->Lock(b,(UINT)ga[1],(UINT)ga[2],(BYTE**)&gbits,(DWORD)ga[4]);break;case 312:hr=b->vt->Unlock(b);break;
 case 313:gscalar=t->vt->GetLevelCount(t);hr=(HRESULT)gscalar;break;
 case 314:hr=t->vt->GetLevelDesc(t,(UINT)ga[1],&gdesc);break;case 315:hr=t->vt->GetSurfaceLevel(t,(UINT)ga[1],(D8Surface**)&q);break;
 case 316:hr=gn==5?t->vt->LockRect(t,(UINT)ga[1],&locked,NULL,(DWORD)ga[4]):s->vt->LockRect(s,&locked,NULL,(DWORD)ga[3]);gpitch=locked.pitch;gbits=locked.bits;break;
 case 317:hr=gn==2?t->vt->UnlockRect(t,(UINT)ga[1]):s->vt->UnlockRect(s);break;
 default:abort();}
 error=GetLastError();gobject=(uintptr_t)q;
#endif
 SetLastError(error);return (DWORD)hr;
}
static HRESULT rcall(unsigned slot,unsigned n,...){
 unsigned i,prior_presents=d8_device.presents;va_list ap;Args args={0};ABI abi={0};CPU before;DWORD error;
 sample=&samples[0];setup();gslot=slot;gn=n;
 va_start(ap,n);for(i=0;i<n;i++)ga[i]=va_arg(ap,uintptr_t);va_end(ap);
 for(i=0;i<n;i++)wr32(0x2004+4*i,(uint32_t)ga[i]);before=cpu;args.fn=resource_wrapper;args.count=2;
 SetLastError(0x13572468);batch_abi(&args,&abi);error=GetLastError();gcalls++;
 printf("{\"kind\":\"resource-call\",\"slot\":%u,\"nargs\":%u,\"hr\":%lu,\"last_error\":%lu,\"nonnull\":%s,\"stack_delta\":%lu,\"pre\":",slot,n,abi.hr,error,gobject?"true":"false",abi.delta);bytes(abi.pre,512);printf(",\"post\":");bytes(abi.post,512);printf(",\"regs\":[");for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)abi.regs[i]);printf("],\"xmm\":");bytes(abi.xmm,160);printf(",\"cpu_before\":");bytes(&before,sizeof before);printf(",\"cpu_after\":");bytes(&cpu,sizeof cpu);puts("}");
#if BATCH_TRANSLATED
 expected=before;expected.r[EAX]=abi.hr;expected.r[ESP]+=4*(n+1);expected.rv=rd32(0x2000);
 if(slot==15&&!prior_presents&&abi.hr==0)expected.fsw|=0x20;
 CHECK(!memcmp(&expected,&cpu,sizeof cpu)&&!active&&!d8_rendering);
#endif
 return (HRESULT)abi.hr;
}
#define U(x) ((uintptr_t)(x))
#define RC(slot,n,...) CHECK(SUCCEEDED(rcall(slot,n,__VA_ARGS__)))
typedef struct ResourceVertex {float x,y,z,rhw;DWORD diffuse;float u,v;} ResourceVertex;
static const ResourceVertex resource_triangle[]={{0,0,0,1,0,0,0},{20,20,.5f,1,0xffffffff,0,0},{220,20,.5f,1,0xffffffff,1,0},{20,220,.5f,1,0xffffffff,0,1}};
static void resource_pixels(uintptr_t rt,unsigned mode){unsigned x,y,hash=2166136261u,changed=0;DWORD px;BYTE*data;INT pitch;
 RC(316,4,rt,U(0x7000),U(0),U(0x10));data=gbits;pitch=gpitch;CHECK(data&&pitch>=3200);
 for(y=0;y<600;y++)for(x=0;x<800;x++){memcpy(&px,data+y*pitch+x*4,4);px&=0xffffff;hash=(hash^px)*16777619u;if(px!=0x123456)changed++;}
 RC(317,1,rt);CHECK(changed>100&&changed<800*600);printf("{\"kind\":\"resource-pixels\",\"mode\":%u,\"changed\":%u,\"hash\":%u}\n",mode,changed,hash);
}
static void resource_matrix(void){uintptr_t dev,rt,rt2,ds,texture,surf,vb,ib,positions=0,attributes=0,declaration_handle=0;unsigned level,x,y,mode,size;BYTE*data;INT pitch;D8Viewport view={0,0,800,600,0,0x3f800000};
#if BATCH_TRANSLATED
 dev=0x4000;
#else
 dev=(uintptr_t)device;
#endif
 RC(32,2,dev,U(0x7000));rt=gobject;RC(32,2,dev,U(0x7000));rt2=gobject;CHECK(rt==rt2);RC(302,1,rt2);
 RC(33,2,dev,U(0x7000));ds=gobject;RC(308,2,rt,U(0x7000));CHECK(gdesc.width==800&&gdesc.height==600);
 RC(301,1,rt);RC(302,1,rt);memcpy(G2H(0x8000),&d8_surface_iid,16);RC(300,3,rt,U(0x8000),U(0x7000));CHECK(gobject==rt);RC(302,1,rt);
 RC(303,2,rt,U(0x7000));CHECK(gobject==dev);
 /* Balance the returned real device ref through the relevant adapter. */
#if BATCH_TRANSLATED
 setup();wr32(0x2004,(uint32_t)dev);guest_error=0x13572468;d8_device_Release(&cpu);
#else
 device->vt->Release(device);
#endif
 RC(31,3,dev,rt,ds);memcpy(G2H(0x8000),&view,24);RC(40,2,dev,U(0x8000));RC(41,2,dev,U(0x8000));CHECK(!memcmp(G2H(0x8000),&view,24));
 RC(20,8,dev,U(8),U(8),U(0),U(0),U(21),U(1),U(0x7000));texture=gobject;RC(313,1,texture);CHECK(gscalar==4);
 for(level=0;level<4;level++){
  RC(314,3,texture,U(level),U(0x7000));size=8>>level;CHECK(gdesc.width==size&&gdesc.height==size);
  RC(316,5,texture,U(level),U(0x7000),U(0),U(0));data=gbits;pitch=gpitch;CHECK(data&&pitch>=(INT)size*4);
  for(y=0;y<size;y++)for(x=0;x<size;x++){DWORD value=0xff40c080;memcpy(data+y*pitch+x*4,&value,4);}RC(317,2,texture,U(level));
 }
 RC(315,3,texture,U(1),U(0x7000));surf=gobject;RC(316,4,surf,U(0x7000),U(0),U(0x10));{DWORD px;memcpy(&px,gbits,4);CHECK(px==0xff40c080);}RC(317,1,surf);RC(302,1,surf);
 RC(61,3,dev,U(0),texture);
 CHECK(SUCCEEDED(device->vt->SetVertexShader(device,0x144)));CHECK(SUCCEEDED(device->vt->SetRenderState(device,137,0)));CHECK(SUCCEEDED(device->vt->SetRenderState(device,22,1)));CHECK(SUCCEEDED(device->vt->SetRenderState(device,7,0)));
 CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,1,2)));CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,2,2)));CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,4,2)));CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,5,2)));
 RC(23,6,dev,U(sizeof resource_triangle),U(0),U(0x144),U(1),U(0x7000));vb=gobject;RC(311,5,vb,U(0),U(0),U(0x7000),U(0));memcpy(gbits,resource_triangle,sizeof resource_triangle);RC(312,1,vb);RC(83,4,dev,U(0),vb,U(sizeof(ResourceVertex)));
 for(mode=0;mode<3;mode++){
  if(mode==1){
   static const float pos[4][3]={{0,0,0},{-.95f,.9333333f,.5f},{-.45f,.9333333f,.5f},{-.95f,.2666667f,.5f}};
   static const struct{DWORD color;float u,v;}attr[]={{0,0,0},{0xffffffff,0,0},{0xffffffff,1,0},{0xffffffff,0,1}};
   static const DWORD declaration[]={0x20000000,0x40020000,0x20000001,0x40040005,0x40010007,0xffffffff};
   D8Matrix identity={0};identity.bits[0]=identity.bits[5]=identity.bits[10]=identity.bits[15]=0x3f800000;
   CHECK(SUCCEEDED(device->vt->SetTransform(device,256,&identity)));CHECK(SUCCEEDED(device->vt->SetTransform(device,2,&identity)));CHECK(SUCCEEDED(device->vt->SetTransform(device,3,&identity)));
   memcpy(G2H(0x9000),declaration,sizeof declaration);RC(75,5,dev,U(0x9000),U(0),U(0x7000),U(0));declaration_handle=gscalar;
   RC(76,2,dev,declaration_handle);RC(77,2,dev,U(0x7000));CHECK(gscalar==declaration_handle);
   RC(23,6,dev,U(sizeof pos),U(0),U(0),U(1),U(0x7000));positions=gobject;RC(311,5,positions,U(0),U(0),U(0x7000),U(0));memcpy(gbits,pos,sizeof pos);RC(312,1,positions);
   RC(23,6,dev,U(sizeof attr),U(0),U(0),U(1),U(0x7000));attributes=gobject;RC(311,5,attributes,U(0),U(0),U(0x7000),U(0));memcpy(gbits,attr,sizeof attr);RC(312,1,attributes);
   RC(83,4,dev,U(0),positions,U(12));RC(83,4,dev,U(1),attributes,U(12));
  }
  ib=0;if(mode){RC(24,6,dev,U(mode==1?6:12),U(0),U(mode==1?101:102),U(1),U(0x7000));ib=gobject;RC(311,5,ib,U(0),U(0),U(0x7000),U(0));for(x=0;x<3;x++){if(mode==1){WORD v=(WORD)(x+1);memcpy((BYTE*)gbits+2*x,&v,2);}else{DWORD v=x+1;memcpy((BYTE*)gbits+4*x,&v,4);}}RC(312,1,ib);RC(85,3,dev,ib,U(0));}
  RC(36,7,dev,U(0),U(0),U(1),U(0xff123456),U(0x3f800000),U(0));RC(34,1,dev);
  if(mode){RC(71,6,dev,U(4),U(1),U(3),U(0),U(1));}else{RC(70,4,dev,U(4),U(1),U(1));}RC(35,1,dev);resource_pixels(rt,mode);RC(15,5,dev,U(0),U(0),U(0),U(0));
  if(ib){RC(85,3,dev,U(0),U(0));RC(302,1,ib);}
 }
 RC(83,4,dev,U(0),U(0),U(0));RC(83,4,dev,U(1),U(0),U(0));RC(78,2,dev,declaration_handle);RC(76,2,dev,U(0x144));RC(302,1,positions);RC(302,1,attributes);RC(61,3,dev,U(0),U(0));RC(302,1,vb);RC(302,1,texture);RC(302,1,ds);RC(302,1,rt);
#if BATCH_TRANSLATED
 CHECK(!d8_locks&&!d8_device.children&&d8_device.refs==1);
#endif
 printf("{\"kind\":\"resource-summary\",\"calls\":%u,\"synthetic_only\":true,\"game_scene\":false}\n",gcalls);
}
