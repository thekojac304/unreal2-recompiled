static D8Present presentation;
static void pp_words(DWORD*w){w[0]=presentation.width;w[1]=presentation.height;w[2]=presentation.format;w[3]=presentation.count;w[4]=presentation.multisample;w[5]=presentation.swap;w[6]=xrt_gui_window_identity(&cpu,presentation.window);w[7]=presentation.windowed;w[8]=presentation.depth;w[9]=presentation.depthformat;w[10]=presentation.flags;w[11]=presentation.refresh;w[12]=presentation.interval;}
static DWORD WINAPI create_wrapper(uintptr_t p,uintptr_t ignored){HRESULT hr;DWORD e;(void)ignored;
#if BATCH_TRANSLATED
 guest_error=GetLastError();d8_CreateDevice(&cpu);device=d8_device.host;hr=(HRESULT)cpu.r[EAX];e=guest_error;
 presentation.width=rd32(0x7000);presentation.height=rd32(0x7004);presentation.format=rd32(0x7008);presentation.count=rd32(0x700c);presentation.multisample=rd32(0x7010);presentation.swap=rd32(0x7014);presentation.window=xrt_gui_device_window(&cpu,rd32(0x7018));presentation.windowed=rd32(0x701c);presentation.depth=rd32(0x7020);presentation.depthformat=rd32(0x7024);presentation.flags=rd32(0x7028);presentation.refresh=rd32(0x702c);presentation.interval=rd32(0x7030);
#else
 hr=((D8Interface*)p)->vt->CreateDevice((D8Interface*)p,0,1,xrt_gui_device_window(&cpu,cfg[6]),cfg[11],&presentation,&device);e=GetLastError();
#endif
 SetLastError(e);return (DWORD)hr;
}
int main(int argc,char**argv){WNDCLASSW wc={0};HMODULE lib,dep;char path[2048];D8Factory factory;D8Interface*p;unsigned i;ULONG dr,pr;DWORD error,words[13],before[13];Args args;ABI abi;CPU start_cpu;BYTE frame[32];
 setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);if(argc!=3||strcmp(argv[1],"--physical"))return 2;
 xrt_g=VirtualAlloc(NULL,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(xrt_g);wc.hInstance=GetModuleHandleW(NULL);wc.lpfnWndProc=proc;wc.lpszClassName=L"SemanticCreationOwned";CHECK(RegisterClassW(&wc));owned_window=CreateWindowExW(0,wc.lpszClassName,L"Disposable semantic creation",WS_POPUP,20,20,800,600,NULL,NULL,wc.hInstance,NULL);owned_second=CreateWindowExW(0,wc.lpszClassName,L"Disposable semantic presentation",WS_POPUP,30,30,800,600,NULL,NULL,wc.hInstance,NULL);CHECK(owned_window&&owned_second);
 snprintf(path,sizeof path,"%s/d3d9.dll",argv[2]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);snprintf(path,sizeof path,"%s/d3d8.dll",argv[2]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);CHECK(dep&&lib);factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");CHECK(factory);p=factory(120);CHECK(p);
 sample=&samples[0];setup();parent.guest=0x3000;parent.host=p;parent.refs=1;parent.children=parent.pending=0;
 presentation.width=cfg[0];presentation.height=cfg[1];presentation.format=cfg[2];presentation.count=cfg[3];presentation.multisample=cfg[4];presentation.swap=cfg[5];presentation.window=xrt_gui_device_window(&cpu,cfg[7]);presentation.windowed=cfg[8];presentation.depth=cfg[9];presentation.depthformat=cfg[10];pp_words(before);
 memcpy(G2H(0x7000),before,52);wr32(0x8000,0xdeadbeef);wr32(0x2004,parent.guest);wr32(0x2008,0);wr32(0x200c,1);wr32(0x2010,cfg[6]);wr32(0x2014,cfg[11]);wr32(0x2018,0x7000);wr32(0x201c,0x8000);start_cpu=cpu;memcpy(frame,G2H(0x2000),32);
 args.fn=create_wrapper;args.a[0]=(uintptr_t)p;args.a[1]=0;args.count=2;memset(&abi,0,sizeof abi);creation_logging=1;SetLastError(0x13572468);batch_abi(&args,&abi);error=GetLastError();creation_logging=0;pp_words(words);
 printf("{\"kind\":\"creation-call\",\"hr\":%lu,\"error\":%lu,\"seed\":324478056,\"nonnull\":%s,\"outer_wrapper_abi\":true,\"stack_delta\":%lu,\"pre\":",abi.hr,error,device?"true":"false",abi.delta);bytes(abi.pre,512);printf(",\"post\":");bytes(abi.post,512);printf(",\"regs\":[");for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)abi.regs[i]);printf("],\"xmm\":");bytes(abi.xmm,160);printf(",\"cpu_before\":");bytes(&start_cpu,sizeof start_cpu);printf(",\"cpu_after\":");bytes(&cpu,sizeof cpu);printf(",\"pp_before\":");bytes(before,52);printf(",\"pp_after\":");bytes(words,52);printf(",\"guest_output\":%u,\"pending\":%u,\"refs\":%u,\"children\":%u,\"pins\":[%u,%u],\"active_callbacks\":%u}\n",rd32(0x8000),parent.pending,parent.refs,parent.children,pins[0],pins[1],callback_active);
 CHECK(abi.hr==0&&device&&!active&&!d8_creating);CHECK(!memcmp(frame,G2H(0x2000),32));
#if BATCH_TRANSLATED
 expected=start_cpu;expected.r[EAX]=abi.hr;expected.r[ESP]+=32;expected.rv=rd32(0x2000);CHECK(!memcmp(&expected,&cpu,sizeof cpu));CHECK(rd32(0x8000)==d8_device.guest&&d8_device.refs==1&&parent.children==1&&!parent.pending&&parent.refs==1);
#endif
 ev_backend_luid(dep);ev_checkpoint("loaded");record_events=1;
 {D8Interface*q=NULL;D8Creation cp={0};ULONG add=device->vt->AddRef(device),balance=device->vt->Release(device),qr;HRESULT ph=device->vt->GetDirect3D(device,&q),ch;CHECK(q);qr=q->vt->Release(q);ch=device->vt->GetCreationParameters(device,&cp);printf("{\"kind\":\"creation-ownership\",\"add\":%lu,\"balance\":%lu,\"parent_hr\":%lu,\"same_parent\":%s,\"parent_release\":%lu,\"creation_hr\":%lu,\"focus\":%u,\"flags\":%lu}\n",add,balance,(DWORD)ph,q==p?"true":"false",qr,(DWORD)ch,xrt_gui_window_identity(&cpu,cp.focus),cp.flags);}
#if BATCH_TRANSLATED
 setup();wr32(0x2004,d8_device.guest);guest_error=0x13572468;d8_device_Release(&cpu);dr=cpu.r[EAX];CHECK(d8_device.refs==0&&parent.children==0&&pins[0]==0&&pins[1]==0);
#else
 dr=device->vt->Release(device);
#endif
 record_events=0;pr=p->vt->Release(p);CHECK(dr==0&&pr==0);CHECK(DestroyWindow(owned_second));CHECK(DestroyWindow(owned_window));CHECK(UnregisterClassW(wc.lpszClassName,wc.hInstance));CHECK(FreeLibrary(lib)&&FreeLibrary(dep));CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));
 printf("{\"kind\":\"creation-cleanup\",\"device_release\":%lu,\"parent_release\":%lu,\"window_valid\":%s,\"d3d8_loaded\":%s,\"d3d9_loaded\":%s,\"pins\":[%u,%u],\"callbacks\":%u,\"active_callbacks\":%u}\n",dr,pr,IsWindow(owned_window)||IsWindow(owned_second)?"true":"false",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false",pins[0],pins[1],callbacks,callback_active);ev_checkpoint("cleaned");return 0;
}
