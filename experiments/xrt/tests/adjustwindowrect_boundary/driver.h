/* Each host supplies only fixture memory and invocation. No border dimensions. */
static const DWORD styles[]={0x10cf0000u,0x54000000u,WS_POPUP,WS_OVERLAPPEDWINDOW,
    WS_BORDER,WS_DLGFRAME,WS_CAPTION,WS_THICKFRAME,WS_CAPTION|WS_SYSMENU,
    WS_POPUP|WS_BORDER,WS_CHILD|WS_BORDER,WS_OVERLAPPEDWINDOW|WS_HSCROLL|WS_VSCROLL};
static const LONG rectangles[][4]={{0,0,640,480},{17,31,817,631},{-320,-200,320,280},
    {-900,-700,-100,-100},{0,0,0,0},{99,101,22,13},{1,-2,2,-1},
    {0x7ffffff0,0x7ffffff1,0x7ffffffe,0x7fffffff},{(LONG)0x80000000u,(LONG)0x80000001u,-1,0}};
static const DWORD menus[]={0,1,2,0xffffffffu},seeds[]={0,0x5555,0xdeadbeef};
int main(int argc,char**argv) {
    unsigned i,j,k,l,placement,n=0;int failures=0;
    if(argc<3)return 2;init(argv[1],argv[2]);
    if(argc>3) {
        uintptr_t p=0;DWORD exception;
        memset(buffer,0x5a,0x3000);
        if(!strcmp(argv[3],"null"))p=0;
        else if(!strcmp(argv[3],"low"))p=1;
        else if(!strcmp(argv[3],"uncommitted"))p=base+0x3000;
        else if(!strcmp(argv[3],"readonly")){p=base+0x1000;protect(0x1000,PAGE_READONLY);}
        else if(!strcmp(argv[3],"noaccess")){p=base+0x2000;protect(0x2000,PAGE_NOACCESS);}
        else if(!strcmp(argv[3],"partial")){p=base+0x3000-8;}
        else if(!strcmp(argv[3],"guard")){p=base+0x1000;protect(0x1000,PAGE_READWRITE|PAGE_GUARD);}
        else if(!strcmp(argv[3],"wrap"))p=0xfffffff8u;
        else return 2;
        exception=invoke(p,0x10cf0000u,0,0x5555);
        printf("{\"invalid\":\"%s\",\"exception\":%lu,\"result\":%lu,\"error\":%lu}\n",argv[3],exception,result(),error());
        finish();return 0;
    }
    for(placement=0;placement<3;placement++)for(i=0;i<sizeof styles/sizeof styles[0];i++)
    for(j=0;j<sizeof rectangles/sizeof rectangles[0];j++)for(k=0;k<4;k++)for(l=0;l<3;l++) {
        unsigned offset=placement==0?4:placement==1?5:0x1000-8;LONG out[4];DWORD exception;
        memset(buffer,0xa5,0x3000);memcpy(buffer+offset,rectangles[j],16);
        exception=invoke(base+offset,styles[i],menus[k],seeds[l]);memcpy(out,buffer+offset,16);
        if(exception||abi(0)||abi(1)!=0x12345678||abi(2)!=0x23456789||abi(3)!=0x3456789a||abi(4)!=0x456789ab||buffer[offset-1]!=0xa5||buffer[offset+16]!=0xa5)failures++;
        printf("{\"case\":%u,\"placement\":%u,\"style\":%lu,\"menu\":%lu,\"seed\":%lu,\"result\":%lu,\"error\":%lu,\"exception\":%lu,\"in\":[%ld,%ld,%ld,%ld],\"out\":[%ld,%ld,%ld,%ld],\"abi\":[%lu,%lu,%lu,%lu,%lu],\"guards\":[%u,%u]}\n",
            n++,placement,styles[i],menus[k],seeds[l],result(),error(),exception,
            rectangles[j][0],rectangles[j][1],rectangles[j][2],rectangles[j][3],out[0],out[1],out[2],out[3],
            abi(0),abi(1),abi(2),abi(3),abi(4),buffer[offset-1],buffer[offset+16]);
    }
    printf("failures=%d cases=%u\n",failures,n);finish();return failures?1:0;
}
