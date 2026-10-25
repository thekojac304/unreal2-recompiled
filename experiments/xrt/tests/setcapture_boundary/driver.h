/* Native GetCapture/ReleaseCapture observations stay in this test driver. */
static int failures;
static uintptr_t handles[8];
static HWND raw_handles[8];
static HANDLE ready,proceed;
static void expect(int ok){if(!ok)failures++;}
static int identity(HWND h){unsigned i;if(!h)return 0;for(i=1;i<8;i++)if(raw_handles[i]==h)return (int)i;failures++;return -1;}
static int token_identity(uintptr_t h){unsigned i;if(!h)return 0;for(i=1;i<8;i++)if(handles[i]==h)return (int)i;expect(host(h)!=NULL);return identity(host(h));}
static void logs(const char* label){
    unsigned i,n=get(log_n,0);expect(n%6==0);
    for(i=0;i<n;i+=6)printf("%s msg=%05lx h=%d other=%d wparam=%08lx result=%d error=%08lx\n",label,get(log_data,i),
        token_identity(get(log_data,i+1)),token_identity(get(log_data,i+2)),get(log_data,i+3),token_identity(get(log_data,i+4)),get(log_data,i+5));
    put(log_n,0);
}
static uintptr_t make(unsigned i,DWORD creation){uintptr_t h;put(mode,creation);h=call(make_fn);expect(h!=0);handles[i]=h;raw_handles[i]=host(h);expect(IsWindow(raw_handles[i]));return h;}
static uintptr_t sample(const char* label,uintptr_t h,DWORD s){
    uintptr_t r;DWORD e;unsigned i;DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};
    put(window,(DWORD)h);put(seed,s);r=call(run_fn);e=get(error,0);
    for(i=0;i<5;i++)expect(get(abi,i)==want[i]);
    printf("%s seed=%08lx previous=%d capture=%d error=%08lx abi=%d\n",label,s,token_identity(r),identity(GetCapture()),e,
        get(abi,0)==0 && get(abi,1)==want[1] && get(abi,2)==want[2] && get(abi,3)==want[3] && get(abi,4)==want[4]);
    logs(label);return r;
}
static void release(const char* label,DWORD seed_value){BOOL r;DWORD e;SetLastError(seed_value);r=release_capture();e=GetLastError();printf("%s result=%d capture=%d error=%08lx\n",label,r,identity(GetCapture()),e);logs(label);}
static void destroy(uintptr_t h){put(window,(DWORD)h);expect(call(destroy_fn)!=0);}
static DWORD WINAPI worker(void* unused){
    (void)unused;thread_begin();make(5,0);sample("worker-owned",handles[5],0x5555);release_guest();SetEvent(ready);
    expect(WaitForSingleObject(proceed,10000)==WAIT_OBJECT_0);acquire_guest();
    printf("worker-after-foreign capture=%d\n",identity(GetCapture()));
    sample("worker-clear",0,0x5555);release("worker-release",0x5555);destroy(handles[5]);logs("worker-destroy");thread_end();return 0;
}
int main(int argc,char**argv){
    DWORD seeds[]={0,0x5555,0xdeadbeef};unsigned i;HANDLE t;uintptr_t dead;HWND unrepresented;
    if(argc<3)return 2;
#ifdef XRT_INTERNAL_H
    xrt_report_path=argc>3?argv[3]:NULL;
#endif
    init(argv[1]);
    if(!strcmp(argv[2],"borrowed")){
        unrepresented=CreateWindowExA(0,"STATIC","native previous",WS_POPUP,0,0,16,16,NULL,NULL,NULL,NULL);
        expect(unrepresented!=NULL);raw_handles[6]=unrepresented;SetCapture(unrepresented);
        handles[6]=sample("unrepresented-previous",0,0x5555);expect(host(handles[6])==unrepresented);
        sample("reuse-previous-token",handles[6],0x5555);expect(GetCapture()==unrepresented);
        expect(sample("clear-unrepresented",0,0x5555)==handles[6]);release("release-unrepresented",0x5555);DestroyWindow(unrepresented);
        finish();printf("failures=%d\n",failures);return failures?1:0;
    }
    if(!strcmp(argv[2],"wrong-type")){sample("wrong-type",wrong(),0x5555);finish();return failures?1:0;}
    if(!strcmp(argv[2],"cross-thread")){
        ready=CreateEventA(NULL,TRUE,FALSE,NULL);proceed=CreateEventA(NULL,TRUE,FALSE,NULL);
        release_guest();t=CreateThread(NULL,0,worker,NULL,0,NULL);expect(t!=NULL);
        expect(WaitForSingleObject(ready,10000)==WAIT_OBJECT_0);acquire_guest();
        for(i=0;i<3;i++)sample("foreign-window",handles[5],seeds[i]);
        release_guest();SetEvent(proceed);expect(WaitForSingleObject(t,10000)==WAIT_OBJECT_0);acquire_guest();
        CloseHandle(t);CloseHandle(ready);CloseHandle(proceed);finish();printf("failures=%d\n",failures);return failures?1:0;
    }
    make(7,0);put(parent,(DWORD)handles[7]);make(1,0);make(2,0);make(3,0);put(log_n,0);
    for(i=0;i<3;i++){
        sample("null-empty",0,seeds[i]);release("release-empty",seeds[i]);
        sample("set-a",handles[1],seeds[i]);
        expect(sample("same-a",handles[1],seeds[i])==handles[1]);
        expect(sample("a-to-b",handles[2],seeds[i])==handles[1]);
        expect(sample("b-to-a",handles[1],seeds[i])==handles[2]);
        expect(sample("null-with-a",0,seeds[i])==handles[1]);sample("null-after-null",0,seeds[i]);
        release("release-after-null",seeds[i]);sample("set-before-release",handles[1],seeds[i]);release("release-a",seeds[i]);
        sample("invalid-empty",0x12345678,seeds[i]);sample("invalid-minus-one",0xffffffff,seeds[i]);
        sample("set-before-invalid",handles[1],seeds[i]);sample("invalid-with-a",0x12345678,seeds[i]);sample("clear-after-invalid",0,seeds[i]);release("release-after-invalid",seeds[i]);
    }
    sample("before-destroy",handles[3],0x5555);dead=handles[3];destroy(dead);logs("destroy-capture");
    for(i=0;i<3;i++)sample("destroyed",dead,seeds[i]);release("release-destroyed",0x5555);handles[3]=0;raw_handles[3]=NULL;
    sample("prepare-reentrant",handles[1],0x5555);put(trigger,WM_CAPTURECHANGED);put(target,(DWORD)handles[1]);
    sample("reentrant-transition",handles[2],0xdeadbeef);release("release-reentrant",0x5555);
    put(trigger,WM_CAPTURECHANGED);put(target,(DWORD)handles[1]);sample("prepare-reentrant-null",handles[2],0x5555);
    sample("reentrant-null",0,0xdeadbeef);release("release-reentrant-null",0x5555);
    make(4,1);logs("capture-nccreate");printf("capture-nccreate completed=1 capture=%d\n",identity(GetCapture()));destroy(handles[4]);logs("destroy-nccreate");
    make(4,2);logs("capture-create");printf("capture-create completed=1 capture=%d\n",identity(GetCapture()));
    sample("clear-final",0,0x5555);release("release-final",0x5555);destroy(handles[4]);destroy(handles[1]);destroy(handles[2]);destroy(handles[7]);logs("destroy-final");
    finish();printf("failures=%d\n",failures);return failures?1:0;
}
