int main(int argc,char**argv){
    HWND h;unsigned i;DWORD seeds[]={18,0,0x13572468,0xffffffff};
    if(argc<3)return 2;h=make(argv[1],argv[2],0);if(!h)return 3;
    for(i=0;i<12;i++){
        int width=640+40*(i%3),height=480+30*(i%4),x=(int)i*7-30,y=(int)i*3;
        BOOL repaint=i%3==0?0:i%3==1?1:32;RECT desired={0,0,width,height},after,cr;
        DWORD error,result;HWND focus=GetFocus();
        AdjustWindowRect(&desired,GetWindowLongW(h,GWL_STYLE),FALSE);
#ifdef GUI_TRANSLATED
        {CPU original=*cpu,expected;uint32_t s=cpu->r[ESP]-64;
        cpu->pc=0x76543210+i;cpu->r[ESP]=s;wr32(s,0x12345678);wr32(s+4,xrt_gui_window_identity(cpu,h));
        wr32(s+8,x);wr32(s+12,y);wr32(s+16,desired.right-desired.left);wr32(s+20,desired.bottom-desired.top);wr32(s+24,repaint);
        if(argc>3)wr32(s+4,0x76543210);
        expected=*cpu;expected.r[EAX]=1;expected.r[ESP]+=28;expected.rv=0x12345678;
        xrt_set_last_error(cpu,seeds[i%4]);hle_MoveWindow(cpu);result=cpu->r[EAX];error=xrt_get_last_error(cpu);
        if(memcmp(cpu,&expected,sizeof expected)){fprintf(stderr,"MoveWindow CPU mismatch\n");return 9;}
        *cpu=original;}
#else
        SetLastError(seeds[i%4]);result=MoveWindow(h,x,y,desired.right-desired.left,desired.bottom-desired.top,repaint);error=GetLastError();
#endif
        GetWindowRect(h,&after);GetClientRect(h,&cr);
        printf("{\"case\":%u,\"seed\":%lu,\"result\":%lu,\"error\":%lu,\"repaint\":%d,\"client\":[%ld,%ld],\"outer\":[%ld,%ld,%ld,%ld],\"focus_unchanged\":%u}\n",i,seeds[i%4],result,error,repaint,cr.right,cr.bottom,after.left,after.top,after.right,after.bottom,GetFocus()==focus);
        if(!result||cr.right!=width||cr.bottom!=height||GetFocus()!=focus)return 8;
        {static const unsigned dpis[]={0,48,96,120,144,192};unsigned dpi=dpis[i%6],selector=i%3,present;
#ifdef GUI_TRANSLATED
        CPU original=*cpu,expected;uint32_t s=cpu->r[ESP]-64;
        cpu->r[ESP]=s;wr32(s,0x12345678);wr32(s+4,xrt_gui_window_identity(cpu,h));wr32(s+8,WM_GETICON);wr32(s+12,selector);wr32(s+16,dpi);
        expected=*cpu;expected.r[ESP]+=20;expected.rv=0x12345678;xrt_set_last_error(cpu,seeds[i%4]);send_message(cpu,1);
        error=xrt_get_last_error(cpu);expected.r[EAX]=cpu->r[EAX];present=cpu->r[EAX]!=0;
        if(present && !guest_icon(cpu,cpu->r[EAX]))return 10;
        if(memcmp(cpu,&expected,sizeof expected))return 11;*cpu=original;
#else
        SetLastError(seeds[i%4]);present=SendMessageW(h,WM_GETICON,selector,dpi)!=0;error=GetLastError();
#endif
        printf("{\"kind\":\"icon\",\"selector\":%u,\"dpi\":%u,\"present\":%u,\"error\":%lu}\n",selector,dpi,present,error);
        }
    }
    if(!destroy(h))return 5;finish();return 0;
}
