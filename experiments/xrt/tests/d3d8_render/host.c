#include <xmmintrin.h>
#define main inherited_main
#include "../d3d8_boundary/host.c"
#undef main
int main(int argc,char**argv){
 XrtModule*m;XrtThread*t;CPU*c;char full[520];uint32_t r,log,n,k,abi;unsigned j;const char*names[]={"abi_clear","abi_present"};
 if(argc!=7)return 2;
 GetFullPathNameA(argv[1],sizeof full,full,NULL);xrt_report_path=argv[2];snprintf(xrt_sandbox_root,sizeof xrt_sandbox_root,"%s",full);*strrchr(xrt_sandbox_root,'\\')=0;
 xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);m=xrt_module_load(full,&xrt_mod_d3dprobe);xrt_module_bind_imports(m);xrt_cmdline_a=xrt_guest_strdup_a("render-probe");hle_msvcr70_init();t=xrt_thread_main(0x100000);xrt_baton_acquire();c=&t->cpu;
 wr32(xrt_module_export(m,"probe_case",0),(uint32_t)strtoul(argv[3],NULL,0));wr32(xrt_module_export(m,"probe_arg",0),(uint32_t)strtoul(argv[4],NULL,0));wr32(xrt_module_export(m,"probe_seed",0),(uint32_t)strtoul(argv[5],NULL,0));
 if(atoi(argv[3])==30){DWORD old;DWORD fields[4]={8,8,64,64};xrt_commit(0x25000000,8192);memcpy(G2H(0x25001000-12),fields,16);if(!VirtualProtect(G2H(0x25001000),4096,strtoul(argv[4],NULL,0),&old))return 2;xrt_event("test_rect_pages","\"protection\":%u",strtoul(argv[4],NULL,0));}
 if(atoi(argv[6]))SetEnvironmentVariableA("XRT_RENDER_CALLBACKS",argv[6]);
 _mm_setcsr(0x3f80);r=xrt_call_guest(c,xrt_module_export(m,"probe_main",0),0,NULL,0);
 printf("returned %u log",r);log=xrt_module_export(m,"probe_log",0);n=rd32(xrt_module_export(m,"probe_log_n",0));for(k=0;k<n;k++)printf(" %u",rd32(log+k*4));
 for(j=0;j<2;j++){printf("\n%s",names[j]);abi=xrt_module_export(m,names[j],0);for(k=0;k<16;k++)printf(" %u",rd32(abi+k*4));}printf("\nmxcsr %u\n",_mm_getcsr());fflush(stdout);xrt_cleanup_atoms();xrt_report_write(r,"exited");return(int)r;
}
