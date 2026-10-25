static int failures;
static void expect(int ok){if(!ok)failures++;}
static void sample(uintptr_t a,uintptr_t b,unsigned n,unsigned pattern,DWORD s,const char*label) {
    DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};
    DWORD data[2][8]={{0,0,1540,945,0x7fffffff,0x80000000,32767,0xffff8000},{0xfffffff5,23,0xffff8ad0,0x7fff,0xffffffff,0xffffffff,0x80000000,0x7fffffff}};
    DWORD r;unsigned i;unsigned char*p=buffer+0x1ff8;
    memset(p-4,0xa5,40);memcpy(p,data[pattern],32);
    put(from,(DWORD)a);put(to,(DWORD)b);put(points,(DWORD)(base+0x1ff8));put(count,n);put(seed,s);
    r=(DWORD)call(run_fn);for(i=0;i<5;i++)expect(get(abi,i)==want[i]);
    expect(*(DWORD*)(p-4)==0xa5a5a5a5);expect(!memcmp(p+n*8,((unsigned char*)data[pattern])+n*8,32-n*8));expect(*(DWORD*)(p+32)==0xa5a5a5a5);
    printf("%s n=%u pattern=%u seed=%08lx result=%08lx error=%08lx abi=1 guards=1 points=",label,n,pattern,s,r,get(error,0));
    for(i=0;i<8;i++)printf("%08lx,",((DWORD*)p)[i]);printf("\n");
}
int main(int argc,char**argv) {
    HWND h[5]={0};uintptr_t w[5]={0},dead;DWORD seeds[]={0,0x5555,0xdeadbeef};unsigned a,b,n,k,s;DWORD exception=0;
    if(argc<3)return 2;init(argv[1],argc>3?argv[3]:NULL);
    h[1]=CreateWindowExW(0,L"STATIC",L"map a",WS_OVERLAPPEDWINDOW,137,83,321,243,NULL,NULL,NULL,NULL);
    h[2]=CreateWindowExW(0,L"STATIC",L"map b",WS_POPUP,30001,-30011,111,92,NULL,NULL,NULL,NULL);
    h[3]=CreateWindowExW(WS_EX_LAYOUTRTL,L"STATIC",L"map rtl",WS_POPUP,-33,-77,233,133,NULL,NULL,NULL,NULL);
    h[4]=CreateWindowExW(0,L"STATIC",L"map child",WS_CHILD,17,23,121,80,h[1],NULL,NULL,NULL);
    for(a=1;a<5;a++){expect(h[a]!=NULL);w[a]=token(h[a]);}
    if(!strcmp(argv[2],"wrong-type")){sample(wrong(),0,2,0,0x5555,"wrong-type");finish();return 0;}
    if(!strcmp(argv[2],"count-zero")){sample(w[1],0,0,0,0x5555,"count-zero");finish();return 0;}
    if(!strcmp(argv[2],"bad-points")) {
        put(from,(DWORD)w[1]);put(to,0);put(points,1);put(count,2);put(seed,0x5555);
#ifdef XRT_INTERNAL_H
        call(run_fn);
#else
        __try{call(run_fn);}__except(EXCEPTION_EXECUTE_HANDLER){exception=GetExceptionCode();}
#endif
        printf("bad-points exception=%08lx result=%08lx error=%08lx\n",exception,get(result,0),get(error,0));finish();return 0;
    }
    for(a=0;a<5;a++)for(b=0;b<5;b++)for(n=1;n<=4;n++)for(k=0;k<2;k++)for(s=0;s<3;s++) {
        printf("mapping=%u-to-%u ",a,b);sample(w[a],w[b],n,k,seeds[s],"map");
    }
    for(s=0;s<3;s++)for(n=1;n<=3;n++) {
        sample(0x12345678,w[1],n,0,seeds[s],"invalid-from");sample(w[1],0x12345678,n,0,seeds[s],"invalid-to");
    }
    dead=w[2];expect(DestroyWindow(h[2])!=0);h[2]=NULL;
    for(s=0;s<3;s++)for(n=1;n<=3;n++)sample(dead,0,n,0,seeds[s],"destroyed-from");
    for(a=4;a>0;a--)if(h[a])expect(DestroyWindow(h[a])!=0);
    finish();printf("failures=%d\n",failures);return failures?1:0;
}
