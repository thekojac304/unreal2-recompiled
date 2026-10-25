static int failures;
static HCURSOR extra;
static uintptr_t extra_token;
static void expect(int ok){if(!ok)failures++;}
static int id(uintptr_t v) {
    unsigned i;if(!v)return 0;for(i=0;i<4;i++)if(v==get(cursors,i))return (int)i+1;
    if(v==extra_token && extra_token)return 5;
    expect(valid_cursor_token(v));return 6;
}
static int host_id(HCURSOR h) {
    unsigned i;if(!h)return 0;for(i=0;i<4;i++)if(h==LoadCursorW(NULL,MAKEINTRESOURCEW(32512+i)))return (int)i+1;
    if(h==extra)return 5;return 6;
}
static uintptr_t sample(uintptr_t h,DWORD s,const char* label) {
    DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};unsigned i;uintptr_t r;int state;
    put(cursor,(DWORD)h);put(seed,s);r=call(run_fn);for(i=0;i<5;i++)expect(get(abi,i)==want[i]);
    if(extra && !extra_token && r)extra_token=r;
    state=host_id(GetCursor());
    printf("%s input=%d previous=%d state=%d seed=%08lx error=%08lx abi=1\n",label,id(h),id(r),state,s,get(error,0));return r;
}
static DWORD WINAPI worker(void* unused) {
    HCURSOR original=GetCursor();(void)unused;thread_begin();SetCursor(NULL);
    sample(get(cursors,3),0x5555,"worker-cross");sample(0,0x5555,"worker-clear");
    SetCursor(original);thread_end();return 0;
}
int main(int argc,char**argv) {
    unsigned i,j;DWORD seeds[]={0,0x5555,0xdeadbeef};HCURSOR original;uintptr_t r;HANDLE t;
    if(argc<3)return 2;init(argv[1],argc>3?argv[3]:NULL);original=GetCursor();SetCursor(NULL);
    if(!strcmp(argv[2],"wrong-type")){sample(get(icon,0),0x5555,"icon");finish();SetCursor(original);return 0;}
    if(!strcmp(argv[2],"invalid")){sample(0x12345678,0x5555,"invalid");finish();SetCursor(original);return 0;}
    for(i=0;i<3;i++) {
        sample(0,seeds[i],"null-empty");
        for(j=0;j<4;j++) {
            sample(get(cursors,j),seeds[i],"set");r=sample(get(cursors,j),seeds[i],"same");expect(r==get(cursors,j));
        }
        sample(0,seeds[i],"clear");sample(0,seeds[i],"null-empty");
    }
    extra=CopyCursor(LoadCursorW(NULL,MAKEINTRESOURCEW(32644)));expect(extra!=NULL);SetCursor(extra);
    r=sample(0,0x5555,"borrowed-previous");expect(r==extra_token && r!=0);
    sample(r,0x5555,"reuse-borrowed");expect(GetCursor()==extra);
    expect(sample(0,0x5555,"clear-borrowed")==r);expect(DestroyCursor(extra)!=0);extra=NULL;
    release_guest();t=CreateThread(NULL,0,worker,NULL,0,NULL);expect(t!=NULL);
    expect(WaitForSingleObject(t,10000)==WAIT_OBJECT_0);CloseHandle(t);acquire_guest();
    expect(GetCursor()==NULL);SetCursor(original);finish();printf("failures=%d\n",failures);return failures?1:0;
}
