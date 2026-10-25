int main(int argc,char**argv){
    unsigned w,s,i,j,k,n;DWORD result,seeds[]={0,0x5555,0xdeadbeef},want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};int failures=0;
    if(argc<3)return 2;
#ifdef XRT_INTERNAL_H
    xrt_report_path=argc>3?argv[3]:NULL;
#endif
    init(argv[1]);
    for(w=0;w<2;w++)for(s=0;s<2;s++){
        put(wide,0,w);put(style,0,s?WS_OVERLAPPEDWINDOW:WS_POPUP);put(window,0,call(make_fn));if(!get(window,0))return 3;
        if(!strcmp(argv[2],"wrong-wp"))put(wp,0,0);
        if(!strcmp(argv[2],"wrong-lp"))put(lp,0,1);
        for(i=0;i<3;i++)for(j=0;j<2;j++){
            put(log_n,0,0);put(trigger,0,j);put(seed,0,seeds[i]);SetLastError(seeds[i]);result=deliver(get(window,0),get(wp,0),get(lp,0));n=get(log_n,0);
            for(k=0;k<5;k++)if(get(abi,k)!=want[k])failures++;
            printf("wide=%u style=%u seed=%08lx repeat=%u result=%08lx error=%08lx abi=%d\n",w,s,seeds[i],j,result,get(error,0),get(abi,0)==0&&get(abi,1)==want[1]&&get(abi,2)==want[2]&&get(abi,3)==want[3]&&get(abi,4)==want[4]);
            for(k=0;k<n;k+=4)printf("callback kind=%05lx a=%08lx b=%08lx error=%08lx\n",get(log_data,k),get(log_data,k+1),get(log_data,k+2),get(log_data,k+3));
        }
        if(!call(destroy_fn))failures++;
    }
    printf("failures=%d\n",failures);finish();return failures?1:0;
}
