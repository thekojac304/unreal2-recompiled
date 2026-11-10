int main(int argc,char**argv){
 HWND h;unsigned i,j;DWORD seed,ret,error,style;MSG msg;
 if(argc<3)return 2;h=make(argv[1],argv[2],0);if(!h)return 3;
 put(log_n,0);
 for(i=0;i<12;i++){
  int index=i&1?GWL_EXSTYLE:GWL_STYLE,wide=i&2;
  DWORD value=i&1?(i&4?WS_EX_CLIENTEDGE:0):(i&4?0x90000000:WS_OVERLAPPEDWINDOW);
  seed=i%3==0?0:i%3==1?0x13572468:0xffffffff;put(mode,i%2);
#ifdef GUI_TRANSLATED
  {CPU saved=*cpu,expected;unsigned s=cpu->r[ESP]-64;
   cpu->r[ESP]=s;wr32(s,0x12345678);wr32(s+4,xrt_gui_window_identity(cpu,h));wr32(s+8,index);wr32(s+12,value);
   if(argc>3){if(!strcmp(argv[3],"field"))wr32(s+8,(unsigned)-4);if(!strcmp(argv[3],"identity"))wr32(s+4,0x12345);if(!strcmp(argv[3],"readonly"))put(mode,2);}
   expected=*cpu;expected.r[ESP]+=16;expected.rv=0x12345678;xrt_set_last_error(cpu,seed);gui_set_window_long(cpu,wide);
   ret=cpu->r[EAX];error=xrt_get_last_error(cpu);expected.r[EAX]=ret;if(memcmp(&expected,cpu,sizeof expected))return 9;*cpu=saved;}
#else
  SetLastError(seed);ret=wide?SetWindowLongW(h,index,value):SetWindowLongA(h,index,value);error=GetLastError();
#endif
  style=GetWindowLongW(h,index);
  printf("{\"kind\":\"style\",\"case\":%u,\"ret\":%lu,\"error\":%lu,\"style\":%lu}\n",i,ret,error,style);
 }
 for(i=0;i<4;i++){
  seed=i?0x13572468:0;
#ifdef GUI_TRANSLATED
  {CPU saved=*cpu,expected;unsigned s=cpu->r[ESP]-64;
   cpu->r[ESP]=s;wr32(s,0x12345678);wr32(s+4,xrt_gui_window_identity(cpu,h));wr32(s+8,0);
   if(argc>3&&!strcmp(argv[3],"menu"))wr32(s+8,0x12345);
   expected=*cpu;expected.r[ESP]+=12;expected.rv=0x12345678;xrt_set_last_error(cpu,seed);hle_SetMenu(cpu);ret=cpu->r[EAX];error=xrt_get_last_error(cpu);expected.r[EAX]=ret;if(memcmp(&expected,cpu,sizeof expected))return 10;*cpu=saved;}
#else
  SetLastError(seed);ret=SetMenu(h,NULL);error=GetLastError();
#endif
  printf("{\"kind\":\"menu\",\"case\":%u,\"ret\":%lu,\"error\":%lu,\"no_menu\":%u}\n",i,ret,error,GetMenu(h)==NULL);
 }
 for(i=0;i<8;i++){
#ifdef GUI_TRANSLATED
  {CPU saved=*cpu,expected;unsigned s=cpu->r[ESP]-64;
   cpu->r[ESP]=s;wr32(s,0x12345678);wr32(s+4,xrt_gui_window_identity(cpu,h));wr32(s+8,WM_COMMAND);wr32(s+12,0x8004+i);wr32(s+16,0);
   if(argc>3){if(!strcmp(argv[3],"payload"))wr32(s+8,WM_SETTEXT);if(!strcmp(argv[3],"thread"))wr32(s+4,0);if(!strcmp(argv[3],"control"))wr32(s+16,0x12345);}
   expected=*cpu;expected.r[ESP]+=20;expected.rv=0x12345678;xrt_set_last_error(cpu,0x13572468);gui_post_message(cpu,i&1);ret=cpu->r[EAX];error=xrt_get_last_error(cpu);expected.r[EAX]=ret;if(memcmp(&expected,cpu,sizeof expected))return 11;*cpu=saved;}
#else
  SetLastError(0x13572468);ret=i&1?PostMessageW(h,WM_COMMAND,0x8004+i,0):PostMessageA(h,WM_COMMAND,0x8004+i,0);error=GetLastError();
#endif
  if(!ret||!PeekMessageW(&msg,h,WM_COMMAND,WM_COMMAND,PM_REMOVE)||msg.wParam!=0x8004+i||msg.lParam)return 12;
  /* Seed dispatch separately: queue inspection is not part of PostMessage. */
  SetLastError(0x24681357);DispatchMessageW(&msg);
  printf("{\"kind\":\"post\",\"case\":%u,\"ret\":%lu,\"error\":%lu}\n",i,ret,error);
 }
 for(i=0;i<get(log_n,0);i+=8){printf("{\"kind\":\"callback\",\"row\":[");for(j=0;j<8;j++)printf("%s%lu",j?",":"",get(log_data,i+j));puts("]}");}
 if(!destroy(h))return 5;finish();return 0;
}

