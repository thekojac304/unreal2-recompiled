/* One additional phase in the same synthetic three-process physical batch. */
static void surface_matrix(uintptr_t dev,uintptr_t original_rt,uintptr_t original_ds){
 uintptr_t back,image,copy,target,depth;BYTE*data;INT pitch;unsigned x,y,hash=2166136261u;DWORD pixel;
 RECT rect={0,0,4,4};POINT point={4,4};D8Viewport view;
 gphase=1;
 RC(16,4,dev,U(0),U(0),U(0x7000));back=gobject;CHECK(back==original_rt);RC(302,1,back);
 RC(27,5,dev,U(8),U(8),U(21),U(0x7000));image=gobject;
 RC(27,5,dev,U(8),U(8),U(21),U(0x7000));copy=gobject;
 RC(25,7,dev,U(8),U(8),U(21),U(0),U(1),U(0x7000));target=gobject;
 RC(26,6,dev,U(8),U(8),U(75),U(0),U(0x7000));depth=gobject;
 RC(41,2,dev,U(0x8000));memcpy(&view,G2H(0x8000),24);
 RC(31,3,dev,target,depth);RC(36,7,dev,U(0),U(0),U(1),U(0xff123456),U(0x3f800000),U(0));
 RC(31,3,dev,original_rt,original_ds);memcpy(G2H(0x8000),&view,24);RC(40,2,dev,U(0x8000));
 RC(316,4,image,U(0x7000),U(0),U(0));data=gbits;pitch=gpitch;
 for(y=0;y<8;y++)for(x=0;x<8;x++){pixel=0xff309060;memcpy(data+y*pitch+4*x,&pixel,4);}RC(317,1,image);
 RC(28,6,dev,image,U(0),U(0),copy,U(0));
 memcpy(G2H(0x8000),&rect,16);memcpy(G2H(0x8100),&point,8);
 RC(28,6,dev,image,U(0x8000),U(1),copy,U(0x8100));
 RC(28,6,dev,copy,U(0),U(0),target,U(0));
 RC(316,4,target,U(0x7000),U(0),U(0x10));data=gbits;pitch=gpitch;
 for(y=0;y<8;y++)for(x=0;x<8;x++){memcpy(&pixel,data+y*pitch+4*x,4);CHECK(pixel==0xff309060);hash=(hash^pixel)*16777619u;}RC(317,1,target);
 printf("{\"kind\":\"transfer-pixels\",\"pixels\":64,\"hash\":%u}\n",hash);
 /* Native error transfer only: no desktop front-buffer capture. */
 CHECK((DWORD)rcall(30,2,dev,U(0))==0x8876086cu);
 RC(302,1,image);RC(302,1,copy);RC(302,1,target);RC(302,1,depth);
 gphase=0;
}
