/* Hidden owned windows; all state checks use actual IMM32 on this OS thread.
 * Reference calls restore the pre-call state before executing the x86 probe. */
static int failures;
static HANDLE ready,proceed;
static uintptr_t foreign_window,foreign_context;
static const char* mode;
static void expect(int ok){if(!ok)failures++;}
static HIMC current(HWND w) {HIMC h=ImmGetContext(w);if(h)expect(ImmReleaseContext(w,h));return h;}
static uintptr_t sample(const char* label,uintptr_t w,uintptr_t ctx,DWORD s) {
    HWND hw=host_window(w);HIMC hc=host_context(ctx),before=current(hw),wanted,after;
    DWORD we,e,out[5];uintptr_t r;
    SetLastError(s);wanted=ImmAssociateContext(hw,hc);we=GetLastError();after=current(hw);
    ImmAssociateContext(hw,before);
    r=query(w,ctx,s,&e,out);
    expect(host_context(r)==wanted);expect(e==we);expect(current(hw)==after);
    expect(out[0]==0&&out[1]==0x12345678&&out[2]==0x23456789&&out[3]==0x3456789a&&out[4]==0x456789ab);
    printf("%s seed=%08lx previous_null=%d identity=%d state=%d error=%08lx abi=%d\n",label,s,r==0,host_context(r)==wanted,current(hw)==after,e,out[0]==0&&out[1]==0x12345678&&out[2]==0x23456789&&out[3]==0x3456789a&&out[4]==0x456789ab);
    return r;
}
static void owned(const char* label) {
    DWORD seeds[]={0,0x5555,0xdeadbeef};unsigned i;uintptr_t a=make(),b=make(),saved,again,other;HIMC original,custom;
    expect(a&&b);original=current(host_window(a));expect(original!=NULL);expect(current(host_window(b))==original);
    for(i=0;i<3;i++) {
        saved=sample(label,a,0,seeds[i]);expect(saved!=0&&host_context(saved)==original);
        expect(sample("detach-again",a,0,seeds[i])==0);
        expect(sample("restore",a,saved,seeds[i])==0);
        again=sample("same-context",a,saved,seeds[i]);expect(again==saved);
        other=sample("shared-default",b,0,seeds[i]);expect(other==saved);
        sample("restore-shared",b,saved,seeds[i]);
        custom=ImmCreateContext();expect(custom!=NULL&&custom!=original);ImmAssociateContext(host_window(a),custom);
        again=sample("custom-detach",a,0,seeds[i]);expect(again&&again!=saved&&host_context(again)==custom);
        sample("custom-restore",a,again,seeds[i]);sample("restore-default",a,saved,seeds[i]);
        expect(ImmDestroyContext(custom));
    }
    /* Default context belongs to the thread and survives destruction of a window. */
    expect(destroy(a));other=sample("context-survives-window",b,saved,0x5555);expect(other==saved);
    expect(destroy(b));
}
static DWORD WINAPI worker(void* unused) {
    (void)unused;thread_begin();
    if(!strcmp(mode,"positive"))owned("worker-detach");
    else {foreign_window=make();foreign_context=sample("worker-context",foreign_window,0,0x5555);sample("worker-restore",foreign_window,foreign_context,0x5555);}
    release_guest();SetEvent(ready);expect(WaitForSingleObject(proceed,10000)==WAIT_OBJECT_0);acquire_guest();
    if(strcmp(mode,"positive")) {
        printf("worker-after null=%d\n",current(host_window(foreign_window))==NULL);
        expect(destroy(foreign_window));
    }
    thread_end();return 0;
}
int main(int argc,char**argv) {
    uintptr_t a;DWORD e,out[5],seeds[]={0,0x5555,0xdeadbeef};unsigned i;HANDLE t;int before;
    if(argc<3)return 2;mode=argv[2];
#ifdef XRT_INTERNAL_H
    xrt_report_path=argc>3?argv[3]:NULL;
#endif
    init(argv[1]);
    if(!strcmp(mode,"positive"))owned("main-detach");
    else if(!strcmp(mode,"invalid")) {
        a=make();expect(destroy(a));
        for(i=0;i<3;i++) {
            uintptr_t r=query(0,0,seeds[i],&e,out);printf("null previous_null=%d error=%08lx\n",r==0,e);
            r=query(0x12345678,0,seeds[i],&e,out);printf("invalid previous_null=%d error=%08lx\n",r==0,e);
            r=query(0xffffffffu,0,seeds[i],&e,out);printf("invalid-minus-one previous_null=%d error=%08lx\n",r==0,e);
            r=query(a,0,seeds[i],&e,out);printf("destroyed previous_null=%d error=%08lx\n",r==0,e);
        }
        finish();return failures?1:0;
    } else if(!strcmp(mode,"unknown-context")||!strcmp(mode,"wrong-type")) {
        uintptr_t r;a=make();r=query(a,!strcmp(mode,"wrong-type")?a:0x12345678,0x5555,&e,out);printf("unsupported-context previous_null=%d error=%08lx\n",r==0,e);finish();return 0;
    }
    ready=CreateEventA(NULL,TRUE,FALSE,NULL);proceed=CreateEventA(NULL,TRUE,FALSE,NULL);
    release_guest();t=CreateThread(NULL,0,worker,NULL,0,NULL);expect(t!=NULL);
    expect(WaitForSingleObject(ready,10000)==WAIT_OBJECT_0);acquire_guest();
    /* One-shot reference: a foreign-thread mutation cannot be restored here. */
    if(!strncmp(mode,"cross-",6)) {
        uintptr_t r;int own=!strcmp(mode,"cross-context");a=own?make():foreign_window;
        r=query(a,!strcmp(mode,"cross-window")?0:foreign_context,0x5555,&e,out);
        printf("%s previous_null=%d previous_is_worker=%d error=%08lx abi=%d\n",mode,r==0,host_context(r)==host_context(foreign_context),e,out[0]==0&&out[1]==0x12345678&&out[2]==0x23456789&&out[3]==0x3456789a&&out[4]==0x456789ab);
        if(own)expect(destroy(a));
    }
    release_guest();SetEvent(proceed);expect(WaitForSingleObject(t,10000)==WAIT_OBJECT_0);acquire_guest();
    if(!strcmp(mode,"dead-thread-context")){a=make();query(a,foreign_context,0x5555,&e,out);expect(destroy(a));}
    CloseHandle(t);CloseHandle(ready);CloseHandle(proceed);before=failures;finish();printf("failures=%d\n",before);return before?1:0;
}
