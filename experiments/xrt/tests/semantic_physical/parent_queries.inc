static const unsigned queries[][6]={{209,0,1,22,22,1},{209,0,1,22,22,32},{209,0,1,22,0xdead,1},{211,0,1,22,1,0},{211,0,1,22,32,2},{211,0,1,22,1,17}};
static const unsigned*query;
static DWORD WINAPI query_wrapper(uintptr_t p,uintptr_t unused){HRESULT hr;DWORD error;CPU before;unsigned i;(void)unused;
#if BATCH_TRANSLATED
 before=cpu;guest_error=GetLastError();if(query[0]==209)d8_CheckDeviceType(&cpu);else d8_CheckDeviceMultiSampleType(&cpu);hr=(HRESULT)cpu.r[EAX];error=guest_error;before.r[EAX]=(DWORD)hr;before.r[ESP]+=28;before.rv=rd32(0x2000);CHECK(!memcmp(&cpu,&before,sizeof cpu));CHECK(parent.pending==0&&parent.refs==1&&parent.children==1&&!active&&!d8_creating);
#else
 if(query[0]==209)hr=((D8Interface*)p)->vt->CheckDeviceType((D8Interface*)p,query[1],query[2],query[3],query[4],query[5]);else hr=((D8Interface*)p)->vt->CheckDeviceMultiSampleType((D8Interface*)p,query[1],query[2],query[3],query[4],query[5]);error=GetLastError();
#endif
 SetLastError(error);return (DWORD)hr;
}
static void parent_queries(void){unsigned i,j,k;static const DWORD seeds[]={0,18,0x13572468,0xffffffff};Args args;ABI abi;DWORD error;CPU before;
 for(i=0;i<6;i++)for(j=0;j<4;j++){query=queries[i];setup();wr32(0x2004,parent.guest);for(k=1;k<6;k++)wr32(0x2004+4*k,query[k]);before=cpu;args.fn=query_wrapper;args.a[0]=(uintptr_t)parent.host;args.a[1]=0;args.count=2;memset(&abi,0,sizeof abi);SetLastError(seeds[j]);batch_abi(&args,&abi);error=GetLastError();
 printf("{\"kind\":\"parent-query\",\"index\":%u,\"slot\":%u,\"seed\":%lu,\"error\":%lu,\"hr\":%lu,\"stack_delta\":%lu,\"pre\":",i,query[0],seeds[j],error,abi.hr,abi.delta);bytes(abi.pre,512);printf(",\"post\":");bytes(abi.post,512);printf(",\"regs\":[");for(k=0;k<8;k++)printf("%s%llu",k?",":"",(unsigned long long)abi.regs[k]);printf("],\"xmm\":");bytes(abi.xmm,160);printf(",\"cpu_before\":");bytes(&before,sizeof before);printf(",\"cpu_after\":");bytes(&cpu,sizeof cpu);puts("}");}
}
