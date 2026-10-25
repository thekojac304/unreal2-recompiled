static int failures;
static uintptr_t worker_window;
static DWORD worker_tid;
static HANDLE ready,proceed;
static void expect(int ok){if(!ok)failures++;}
static int tid_id(DWORD v){return !v?0:v==get(tid,0)?1:v==worker_tid?2:3;}
static void sample(uintptr_t h,uintptr_t out,DWORD s,const char*label) {
    DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};DWORD v,r;unsigned i;unsigned char* b=NULL;
    if(out>=base && out<base+0x3000){b=buffer+(out-base);memset(b-4,0xa5,12);}
    put(window,(DWORD)h);put(output,(DWORD)out);put(seed,s);r=(DWORD)call(run_fn);
    for(i=0;i<5;i++)expect(get(abi,i)==want[i]);
    expect(get(pid,0)==GetCurrentProcessId());expect(get(tid,0)==GetCurrentThreadId());
    v=b?*(DWORD*)b:0;
    if(b){expect(*(DWORD*)(b-4)==0xa5a5a5a5 && *(DWORD*)(b+4)==0xa5a5a5a5);if(!r)expect(v==0xa5a5a5a5);}
    printf("%s seed=%08lx tid=%d output=%d pid=%d unchanged=%d error=%08lx abi=1 guards=1\n",label,s,tid_id(r),out!=0,v==get(pid,0),b && v==0xa5a5a5a5,get(error,0));
}
static DWORD WINAPI worker(void*unused) {
    (void)unused;thread_begin();worker_tid=GetCurrentThreadId();worker_window=call(make_fn);expect(worker_window!=0);
    sample(worker_window,base+0x1000,0x5555,"worker-own");release_guest();SetEvent(ready);
    expect(WaitForSingleObject(proceed,10000)==WAIT_OBJECT_0);acquire_guest();put(window,(DWORD)worker_window);expect(call(destroy_fn)!=0);thread_end();return 0;
}
int main(int argc,char**argv) {
    uintptr_t h,dead;DWORD seeds[]={0,0x5555,0xdeadbeef};unsigned i,j;unsigned offsets[]={0x1000,0x1001,0x1ffc,0x1ffe};HANDLE t;DWORD exception=0;
    if(argc<3)return 2;init(argv[1],argc>3?argv[3]:NULL);h=call(make_fn);expect(h!=0);
    if(!strcmp(argv[2],"wrong-type")){sample(wrong(),base+0x1000,0x5555,"wrong-type");finish();return 0;}
    if(!strcmp(argv[2],"bad-output")) {
#ifdef XRT_INTERNAL_H
        sample(h,1,0x5555,"bad-output");
#else
        __try{sample(h,1,0x5555,"bad-output");}__except(EXCEPTION_EXECUTE_HANDLER){exception=GetExceptionCode();}
#endif
        printf("bad-output exception=%08lx\n",exception);finish();return 0;
    }
    for(i=0;i<3;i++) {
        sample(h,0,seeds[i],"own-null");for(j=0;j<4;j++)sample(h,base+offsets[j],seeds[i],"own-output");
        sample(0,base+0x1000,seeds[i],"null-window");sample(0x12345678,base+0x1000,seeds[i],"invalid-window");
        sample(0xffffffff,0,seeds[i],"minus-one");sample(0x12345678,1,seeds[i],"invalid-window-bad-output");
    }
    ready=CreateEventA(NULL,TRUE,FALSE,NULL);proceed=CreateEventA(NULL,TRUE,FALSE,NULL);
    release_guest();t=CreateThread(NULL,0,worker,NULL,0,NULL);expect(t!=NULL);expect(WaitForSingleObject(ready,10000)==WAIT_OBJECT_0);acquire_guest();
    for(i=0;i<3;i++)sample(worker_window,base+0x1000,seeds[i],"worker-from-main");
    release_guest();SetEvent(proceed);expect(WaitForSingleObject(t,10000)==WAIT_OBJECT_0);acquire_guest();CloseHandle(t);CloseHandle(ready);CloseHandle(proceed);
    dead=h;put(window,(DWORD)h);expect(call(destroy_fn)!=0);
    for(i=0;i<3;i++)sample(dead,base+0x1000,seeds[i],"destroyed");
    finish();printf("failures=%d\n",failures);return failures?1:0;
}
