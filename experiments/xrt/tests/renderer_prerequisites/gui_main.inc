int main(int argc,char**argv){
    HWND h;unsigned i;DWORD seeds[]={18,0,0x13572468,0xffffffff};
    if(argc<3)return 2;h=make(argv[1],argv[2],0);if(!h)return 3;
    for(i=0;i<8;i++){
        RECT before,after,cr,desired={0,0,1540,945};DWORD error,result;HWND focus=GetFocus();
        GetWindowRect(h,&before);AdjustWindowRect(&desired,GetWindowLongW(h,GWL_STYLE),FALSE);
#ifdef GUI_TRANSLATED
        {CPU original=*cpu,expected;uint32_t s=cpu->r[ESP]-64;
        cpu->pc=0x110018e2;cpu->r[ESP]=s;wr32(s,0x12345678);wr32(s+4,xrt_gui_window_identity(cpu,h));
        wr32(s+8,before.left);wr32(s+12,before.top);wr32(s+16,desired.right-desired.left);wr32(s+20,desired.bottom-desired.top);wr32(s+24,1);
        if(argc>3){
            if(!strcmp(argv[3],"site"))cpu->pc++;
            if(!strcmp(argv[3],"size"))wr32(s+16,rd32(s+16)+1);
            if(!strcmp(argv[3],"repaint"))wr32(s+24,0);
            if(!strcmp(argv[3],"identity"))wr32(s+4,0x76543210);
        }
        expected=*cpu;expected.r[EAX]=1;expected.r[ESP]+=28;expected.rv=0x12345678;
        xrt_set_last_error(cpu,seeds[i%4]);hle_MoveWindow(cpu);result=cpu->r[EAX];error=xrt_get_last_error(cpu);
        if(memcmp(cpu,&expected,sizeof expected)){fprintf(stderr,"MoveWindow suspended CPU mismatch\n");return 9;}
        *cpu=original;}
#else
        SetLastError(seeds[i%4]);result=MoveWindow(h,before.left,before.top,desired.right-desired.left,desired.bottom-desired.top,TRUE);error=GetLastError();
#endif
        GetWindowRect(h,&after);GetClientRect(h,&cr);
        printf("{\"kind\":\"gui-move\",\"case\":%u,\"seed\":%lu,\"result\":%lu,\"error\":%lu,\"style\":%lu,\"client\":[%ld,%ld],\"outer\":[%ld,%ld,%ld,%ld],\"focus_unchanged\":%u}\n",i,seeds[i%4],result,error,(DWORD)GetWindowLongW(h,GWL_STYLE),cr.right,cr.bottom,after.left,after.top,after.right,after.bottom,GetFocus()==focus);
        if(!result||cr.right!=1540||cr.bottom!=945||GetFocus()!=focus)return 8;
    }
    if(!destroy(h))return 5;finish();return 0;
}
