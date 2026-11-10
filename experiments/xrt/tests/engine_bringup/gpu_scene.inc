/* Disposable physical GPU qualification only; never a game module. */
static unsigned scene_slot,scene_n,scene_index_format;
static D8Viewport scene_view={0,0,800,600,0,0x3f800000};
typedef struct SceneVertex {float x,y,z,rhw;DWORD diffuse;} SceneVertex;
static const SceneVertex triangle[]={{0,0,0,1,0},{20,20,.5f,1,0xffff0000},{220,20,.5f,1,0xff00ff00},{20,220,.5f,1,0xff0000ff}};
static DWORD WINAPI scene_wrapper(uintptr_t p,uintptr_t unused){
    HRESULT hr;DWORD error;(void)p;(void)unused;
#if BATCH_TRANSLATED
    guest_error=GetLastError();
    switch(scene_slot){
    case 3:d8_device_TestCooperativeLevel(&cpu);break;case 34:d8_device_BeginScene(&cpu);break;case 35:d8_device_EndScene(&cpu);break;
    case 40:d8_device_SetViewport(&cpu);break;case 41:d8_device_GetViewport(&cpu);break;
    case 72:d8_device_DrawPrimitiveUP(&cpu);break;case 73:d8_device_DrawIndexedPrimitiveUP(&cpu);break;default:abort();}
    hr=(HRESULT)cpu.r[EAX];error=guest_error;
#else
    switch(scene_slot){
    case 3:hr=device->vt->TestCooperativeLevel(device);break;case 34:hr=device->vt->BeginScene(device);break;case 35:hr=device->vt->EndScene(device);break;
    case 40:hr=device->vt->SetViewport(device,&scene_view);break;case 41:hr=device->vt->GetViewport(device,&scene_view);break;
    case 72:hr=device->vt->DrawPrimitiveUP(device,4,1,triangle+1,sizeof(SceneVertex));break;
    case 73:{WORD ix16[]={1,2,3};DWORD ix32[]={1,2,3};hr=device->vt->DrawIndexedPrimitiveUP(device,4,1,3,1,scene_index_format==101?(void*)ix16:(void*)ix32,scene_index_format,triangle,sizeof(SceneVertex));break;}
    default:abort();}
    error=GetLastError();
#endif
    SetLastError(error);return (DWORD)hr;
}
static HRESULT scene_call(unsigned slot){
    Args args={0};ABI abi={0};CPU before;BYTE frame[40];DWORD error;unsigned i;
    sample=&samples[0];setup();scene_slot=slot;scene_n=slot==73?9:slot==72?5:slot==40||slot==41?2:1;
    memset(G2H(0x2008),0,36);
    if(slot==40||slot==41){wr32(0x2008,0x6001);memcpy(G2H(0x6001),&scene_view,sizeof scene_view);}
    if(slot==72){wr32(0x2008,4);wr32(0x200c,1);wr32(0x2010,0x6001);wr32(0x2014,sizeof(SceneVertex));memcpy(G2H(0x6001),triangle+1,3*sizeof(SceneVertex));}
    if(slot==73){wr32(0x2008,4);wr32(0x200c,1);wr32(0x2010,3);wr32(0x2014,1);wr32(0x2018,0x8001);wr32(0x201c,scene_index_format);wr32(0x2020,0x6001);wr32(0x2024,sizeof(SceneVertex));memcpy(G2H(0x6001),triangle,sizeof triangle);
      for(i=0;i<3;i++)if(scene_index_format==101)wr16(0x8001+2*i,(WORD)(i+1));else wr32(0x8001+4*i,i+1);}
    before=cpu;memcpy(frame,G2H(0x2000),40);args.fn=scene_wrapper;args.count=2;args.a[0]=(uintptr_t)device;
    SetLastError(0x13572468);batch_abi(&args,&abi);error=GetLastError();
    printf("{\"kind\":\"bringup-scene-call\",\"slot\":%u,\"hr\":%lu,\"last_error\":%lu,\"stack_delta\":%lu,\"pre\":",slot,abi.hr,error,abi.delta);bytes(abi.pre,512);printf(",\"post\":");bytes(abi.post,512);
    printf(",\"regs\":[");for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)abi.regs[i]);printf("],\"xmm\":");bytes(abi.xmm,160);
    printf(",\"cpu_before\":");bytes(&before,sizeof before);printf(",\"cpu_after\":");bytes(&cpu,sizeof cpu);puts("}");
#if BATCH_TRANSLATED
    expected=before;expected.r[EAX]=abi.hr;expected.r[ESP]+=4*(scene_n+1);expected.rv=rd32(0x2000);
    CHECK(!memcmp(&expected,&cpu,sizeof cpu)&&!memcmp(frame,G2H(0x2000),40));CHECK(!active&&!d8_rendering&&d8_device.refs==1&&parent.children==1);
    if(slot==41)memcpy(&scene_view,G2H(0x6001),sizeof scene_view);
#endif
    if(slot==41){printf("{\"kind\":\"bringup-viewport\",\"bytes\":");bytes(&scene_view,sizeof scene_view);puts("}");}
    return (HRESULT)abi.hr;
}
static void scene_pixels(unsigned mode){
    typedef struct PixelLock{INT pitch;void*bits;}PixelLock;
    typedef HRESULT(WINAPI*BB)(D8Device*,UINT,UINT,void**);
    typedef HRESULT(WINAPI*Lock)(void*,PixelLock*,const RECT*,DWORD);
    typedef HRESULT(WINAPI*Unlock)(void*);typedef ULONG(WINAPI*Release)(void*);
    void*surface=NULL;PixelLock locked={0};unsigned x,y,changed=0,hash=2166136261u;HRESULT h,l,u;ULONG refs;
    h=((BB)table(device)[16])(device,0,0,&surface);CHECK(SUCCEEDED(h)&&surface);
    l=((Lock)table(surface)[9])(surface,&locked,NULL,0x10);CHECK(SUCCEEDED(l)&&locked.bits&&locked.pitch>=3200);
    for(y=0;y<600;y++)for(x=0;x<800;x++){DWORD pixel;memcpy(&pixel,(BYTE*)locked.bits+y*locked.pitch+4*x,4);pixel&=0xffffff;if(pixel!=0x123456)changed++;hash=(hash^pixel)*16777619u;}
    u=((Unlock)table(surface)[10])(surface);refs=((Release)table(surface)[2])(surface);
    printf("{\"kind\":\"bringup-pixels\",\"mode\":%u,\"get_hr\":%lu,\"lock_hr\":%lu,\"unlock_hr\":%lu,\"changed_pixels\":%u,\"rgb_hash\":%u,\"release_count\":%lu}\n",mode,(DWORD)h,(DWORD)l,(DWORD)u,changed,hash,refs);
    CHECK(SUCCEEDED(u)&&changed>100&&changed<800*600);
}
static void scene_matrix(void){
    unsigned mode;HRESULT hr;void*bound=NULL;UINT stride=0;
    CHECK(SUCCEEDED(device->vt->SetVertexShader(device,0x44)));
    CHECK(SUCCEEDED(device->vt->SetRenderState(device,137,0)));
    CHECK(SUCCEEDED(device->vt->SetRenderState(device,22,1)));
    CHECK(SUCCEEDED(device->vt->SetRenderState(device,7,0)));
    CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,1,2)));
    CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,2,0)));
    CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,4,2)));
    CHECK(SUCCEEDED(device->vt->SetTextureStageState(device,0,5,0)));
    CHECK(SUCCEEDED(scene_call(3)));CHECK(SUCCEEDED(scene_call(40)));CHECK(SUCCEEDED(scene_call(41)));
    for(mode=0;mode<3;mode++){
        CHECK(SUCCEEDED(device->vt->Clear(device,0,NULL,1,0xff123456,1,0)));
        CHECK(SUCCEEDED(scene_call(34)));scene_index_format=mode==2?102:101;
        CHECK(SUCCEEDED(scene_call(mode?73:72)));CHECK(SUCCEEDED(scene_call(35)));
        CHECK(SUCCEEDED(device->vt->GetStreamSource(device,0,&bound,&stride))&&!bound);
        if(mode){CHECK(SUCCEEDED(device->vt->GetIndices(device,&bound,&stride))&&!bound);}
        scene_pixels(mode);hr=device->vt->Present(device,NULL,NULL,NULL,NULL);
        printf("{\"kind\":\"bringup-present\",\"mode\":%u,\"hr\":%lu}\n",mode,(DWORD)hr);CHECK(SUCCEEDED(hr));
    }
    /* Preserve backend failures; don't assume the success result for bad sequencing. */
    scene_call(35);CHECK(SUCCEEDED(scene_call(34)));scene_call(34);CHECK(SUCCEEDED(scene_call(35)));
}
