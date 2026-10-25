int main(int argc,char**argv){
    RECT saved,observed;DWORD seeds[]={0,0x5555,0xdeadbeef};unsigned i,j,k;DWORD result;int failures=0;
    DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};
    if(argc<3)return 2;
#ifdef XRT_INTERNAL_H
    xrt_report_path=argc>3?argv[3]:NULL;
#endif
    if(!GetClipCursor(&saved))return 3;
    init(argv[1]);
    if(!strcmp(argv[2],"nonnull")){
        for(i=0;i<4;i++)put(rect,i,((DWORD*)&saved)[i]);
        put(pointer,0,address(rect));put(seed,0,0x5555);result=run();
        printf("nonnull result=%lu error=%08lx\n",result,get(error,0));
    }else{
        for(j=0;j<2;j++)for(i=0;i<3;i++){
            if(!ClipCursor(j?&saved:NULL))failures++;
            put(pointer,0,0);put(seed,0,seeds[i]);result=run();
            if(!GetClipCursor(&observed))failures++;
            for(k=0;k<5;k++)if(get(abi,k)!=want[k])failures++;
            printf("null original-clip=%u seed=%08lx result=%lu error=%08lx desktop=%ld,%ld,%ld,%ld abi=%d\n",j,seeds[i],result,get(error,0),observed.left,observed.top,observed.right,observed.bottom,
                get(abi,0)==0&&get(abi,1)==want[1]&&get(abi,2)==want[2]&&get(abi,3)==want[3]&&get(abi,4)==want[4]);
        }
    }
    if(!ClipCursor(&saved)||!GetClipCursor(&observed)||memcmp(&saved,&observed,sizeof saved))failures++;
    printf("clip-restored=%d failures=%d\n",memcmp(&saved,&observed,sizeof saved)==0,failures);finish();return failures?1:0;
}
