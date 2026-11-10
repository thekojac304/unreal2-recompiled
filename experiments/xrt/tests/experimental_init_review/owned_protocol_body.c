/* Appended to the sealed owned host's process stubs. No game/module load. */
static DWORD WINAPI testworker(void*p){(void)p;Sleep(5);return 0;}
int main(int argc,char**argv){
 static XrtThread owned;CPU*c=&owned.cpu;HANDLE worker;unsigned object;
 if(argc!=2)return 2;
 if(!GetCurrentDirectoryA(sizeof xrt_sandbox_root,xrt_sandbox_root))return 3;
 xm_init(getenv("XRT_MONITOR_STREAM"));xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
 owned.host_tid=owned.guest_tid=GetCurrentThreadId();owned.state=1;
 c->thread=&owned;c->fcw=0x027f;c->fs_base=xrt_rt_alloc(4096,4096);
 c->r[ESP]=xrt_rt_alloc(65536,16)+65000;c->r[EBX]=0x11111111;c->r[EBP]=0x22222222;c->r[ESI]=0x33333333;c->r[EDI]=0x44444444;
 xrt_cur=&owned;xrt_baton_acquire();object=xrt_rt_alloc(256,4);c->r[ECX]=object;
 push32(c,0x1090ed5c);c->pc=0x1090ed59;
 xrt_world_enter(c,0x1038f460);owned_gate(c);
 worker=CreateThread(NULL,0,testworker,NULL,0,NULL);
 if(!worker||WaitForSingleObject(worker,5000)!=WAIT_OBJECT_0)return 4;CloseHandle(worker);
 if(!strcmp(argv[1],"tick"))xrt_event("engine_tick_call","\"owned_negative\":true");
 if(!strcmp(argv[1],"nonvolatile"))c->r[EBX]^=1;
 c->rv=pop32(c);c->pc=0x1038fba9;
 if(strcmp(argv[1],"missing-return"))xrt_world_return(c);
 owned_invoke(c,0x1090ed5c);ExitProcess(92);
}
