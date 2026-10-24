/* No input injection, activation, or AttachThreadInput. Hidden stock windows only.
 * Each guest read is compared with real USER32 on that exact calling OS thread.
 * Native and translated stdout normalizes identities; HWND bits are never logged. */
static int failures;
static HANDLE ready,proceed;
static HWND foreign_window;
static void expect(int ok){if(!ok)failures++;}
static uintptr_t sample(const char* label) {
    DWORD seeds[]={0,0x5555,0xdeadbeef},e,wanted_error;unsigned i;uintptr_t first=0,r;
    HWND wanted;
    for(i=0;i<3;i++) {
        SetLastError(seeds[i]);wanted=GetFocus();wanted_error=GetLastError();
        r=query(seeds[i],&e);
        expect(host(r)==wanted);expect(e==wanted_error);expect((r==0)==(wanted==NULL));
        if(i)expect(r==first);else first=r;
        printf("%s seed=%08lx null=%d identity=%d stable=%d error=%08lx\n",label,seeds[i],r==0,host(r)==wanted,r==first,e);
    }
    return first;
}
static DWORD WINAPI worker(void* unused) {
    (void)unused;thread_begin();
    sample("worker-empty");
    foreign_window=CreateWindowExA(0,"STATIC","worker focus",WS_POPUP,0,0,16,16,NULL,NULL,NULL,NULL);
    expect(foreign_window!=NULL);SetFocus(foreign_window);expect(GetFocus()==foreign_window);
    sample("worker-owned-unrepresented");release_guest();SetEvent(ready);
    expect(WaitForSingleObject(proceed,10000)==WAIT_OBJECT_0);acquire_guest();
    sample("worker-after-foreign-attempt");
    SetFocus(NULL);DestroyWindow(foreign_window);thread_end();return 0;
}
int main(int argc,char**argv) {
    uintptr_t a,b,u;HWND raw;DWORD e;HANDLE t;int before;
    if(argc<2)return 2;
#ifdef XRT_INTERNAL_H
    xrt_report_path=argc>2?argv[2]:NULL;
#endif
    init(argv[1]);SetFocus(NULL);sample("empty");
    a=make();b=make();expect(a&&b&&a!=b);expect(valid(a)&&valid(b));
    SetFocus(host(a));expect(GetFocus()==host(a));expect(sample("owned-a")==a);
    SetFocus(host(b));expect(GetFocus()==host(b));expect(sample("owned-b")==b);
    SetFocus(host(a));expect(sample("owned-a-again")==a);
    SetFocus(NULL);sample("cleared");
    SetLastError(0x5555);raw=SetFocus((HWND)(uintptr_t)0x12345678);e=GetLastError();
    printf("invalid-set null=%d error=%08lx\n",raw==NULL,e);sample("after-invalid");
    SetFocus(host(a));raw=host(a);expect(destroy(a));expect(!valid(a));sample("after-destroy-focused");
    SetLastError(0x5555);raw=SetFocus(raw);e=GetLastError();
    printf("destroyed-set null=%d error=%08lx\n",raw==NULL,e);sample("after-destroyed-set");
    raw=CreateWindowExA(0,"STATIC","unrepresented focus",WS_POPUP,0,0,16,16,NULL,NULL,NULL,NULL);
    expect(raw!=NULL);SetFocus(raw);expect(GetFocus()==raw);u=sample("unrepresented");
    expect(u&&host(u)==raw&&valid(u));expect(destroy(u));expect(!valid(u));sample("unrepresented-destroyed");
    SetFocus(NULL);ready=CreateEventA(NULL,TRUE,FALSE,NULL);proceed=CreateEventA(NULL,TRUE,FALSE,NULL);
    release_guest();t=CreateThread(NULL,0,worker,NULL,0,NULL);expect(t!=NULL);
    expect(WaitForSingleObject(ready,10000)==WAIT_OBJECT_0);acquire_guest();
    sample("main-while-worker-focused");
    SetLastError(0x5555);raw=SetFocus(foreign_window);e=GetLastError();
    printf("cross-thread-set null=%d error=%08lx\n",raw==NULL,e);sample("main-after-foreign-attempt");
    SetFocus(host(b));expect(sample("main-own-while-worker-focused")==b);
    release_guest();SetEvent(proceed);expect(WaitForSingleObject(t,10000)==WAIT_OBJECT_0);acquire_guest();
    CloseHandle(t);CloseHandle(ready);CloseHandle(proceed);
    expect(destroy(b));before=failures;finish();printf("failures=%d\n",before);return before?1:0;
}
