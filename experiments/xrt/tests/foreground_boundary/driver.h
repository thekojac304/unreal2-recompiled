int main(int argc,char**argv){
    DWORD seeds[]={0,0x5555,0xdeadbeef},want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab},result,previous=0,pid,tid;
    HWND before,after,prior=NULL;unsigned i,j,k;int failures=0,owner_ok,stable;
    if(argc<3)return 2;
#ifdef XRT_INTERNAL_H
    xrt_report_path=argc>3?argv[3]:NULL;
#endif
    init(argv[1]);
    for(j=0;j<3;j++)for(i=0;i<3;i++){
        before=GetForegroundWindow();put(seed,0,seeds[i]);result=run();after=GetForegroundWindow();pid=0;tid=after?GetWindowThreadProcessId(after,&pid):0;
        owner_ok=get(rect,0)==pid&&get(rect,1)==tid;
        stable=prior!=after||previous==result;
        if(before!=after||host(result)!=after||!owner_ok||!stable)failures++;
        for(k=0;k<5;k++)if(get(abi,k)!=want[k])failures++;
        printf("seed=%08lx present=%d matches-native=%d reused=%d owner=%d error=%08lx abi=%d\n",seeds[i],result!=0,host(result)==after,stable,owner_ok,get(error,0),get(abi,0)==0&&get(abi,1)==want[1]&&get(abi,2)==want[2]&&get(abi,3)==want[3]&&get(abi,4)==want[4]);
        prior=after;previous=result;
    }
    printf("failures=%d\n",failures);finish();return failures?1:0;
}
