static int failures;
static void expect(int ok){if(!ok)failures++;}
static int icon_id(uintptr_t v) {
    unsigned i;if(!v)return 0;
    for(i=0;i<3;i++)if(v==get(icons,i))return (int)i+1;
    expect(valid_icon_token(v));return 4;
}
static int host_id(HICON v) {
    unsigned i;if(!v)return 0;
    for(i=0;i<3;i++)if(v==icon_host(get(icons,i)))return (int)i+1;
    return 4;
}
static void logs(void) {
    unsigned i,n=get(log_n,0);expect(n<=4096 && n%6==0);
    if(n>4096)return;
    for(i=0;i<n;i+=6)printf("callback stage=%lu depth=%lu selector=%lu dpi=%lu result=%d error=%08lx\n",
        get(log_data,i),get(log_data,i+1),get(log_data,i+2),get(log_data,i+3),icon_id(get(log_data,i+4)),get(log_data,i+5));
    put(log_n,0);
}
static void sample(void) {
    DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};unsigned i;uintptr_t r;
    put(log_n,0);r=call(run_fn);
    for(i=0;i<5;i++)expect(get(abi,i)==want[i]);
    printf("sample mode=%lu nested=%lu selector=%lu seed=%08lx result=%d error=%08lx abi=1\n",
        get(mode,0),get(nested,0),get(selector,0),get(seed,0),icon_id(r),get(error,0));logs();
}
int main(int argc,char**argv) {
    unsigned c,s,m,n,j,i_dummy;uintptr_t h,old;DWORD seeds[]={0,0x5555,0xdeadbeef};ICONINFO info;
    if(argc<4)return 2;c=(unsigned)atoi(argv[3]);init(argv[1],c,argc>4?argv[4]:NULL);
    h=call(make_fn);expect(h!=0);put(window,(DWORD)h);put(log_n,0);
    printf("class=%u big=%d small=%d\n",c,host_id((HICON)GetClassLongPtrW(window_host(h),GCLP_HICON)),host_id((HICON)GetClassLongPtrW(window_host(h),GCLP_HICONSM)));
    if(!strcmp(argv[2],"wrong-type")){put(mode,4);sample();finish();return failures?1:0;}
    if(!strcmp(argv[2],"selector")){put(selector,3);sample();finish();return failures?1:0;}
    if(!strcmp(argv[2],"dpi")){put(dpi,96);sample();finish();return failures?1:0;}
    for(j=0;j<4;j++) {
        DefWindowProcW(window_host(h),WM_SETICON,ICON_BIG,j&1?(LPARAM)icon_host(get(icons,0)):0);
        DefWindowProcW(window_host(h),WM_SETICON,ICON_SMALL,j&2?(LPARAM)icon_host(get(icons,1)):0);
        printf("explicit-icons=%u\n",j);
        for(m=0;m<4;m++)for(n=0;n<2;n++)for(s=0;s<3;s++)for(c=0;c<3;c++) {
            put(mode,m);put(nested,n);put(selector,s);put(seed,seeds[c]);sample();
        }
    }
    put(mode,0);put(nested,0);put(log_n,0);SetLastError(0x5555);old=call(focus_fn);
    printf("focus returned-null=%d focus-self=%d\n",old==0,GetFocus()==window_host(h));logs();
    expect(call(destroy_fn)!=0);
    for(i_dummy=0;i_dummy<2;i_dummy++) {
        expect(GetIconInfo(icon_host(get(icons,i_dummy)),&info)!=0);
        if(info.hbmMask)DeleteObject(info.hbmMask);if(info.hbmColor)DeleteObject(info.hbmColor);
    }
    h=call(make_fn);put(window,(DWORD)h);put(selector,2);put(seed,0x5555);sample();
    expect(call(destroy_fn)!=0);finish();printf("failures=%d\n",failures);return failures?1:0;
}
