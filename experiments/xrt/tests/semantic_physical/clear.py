from recheck import HERE

ROWS=[[36,0,1,0,0,0],[36,2,3,0x3f000000,0,0],[36,2,7,0x3f800000,7,0],
      [36,0,3,0x80000000,0,0],[36,0,8,0,0,1],[36,0,3,0x3fc00000,0,1]]


def sources():
    text=(HERE/'support.inc').read_text()
    text=text.replace('/* SAMPLE_ROWS */','static const Sample samples[]={'+','.join('{'+','.join(str(v)+'u' for v in r)+'}' for r in ROWS)+'};')
    text=text.replace('return sample->slot==63', 'return sample->slot==36?7:sample->slot==63')
    text=text.replace('switch(sample->slot){case 42:', 'switch(sample->slot){case 36:d8_device_Clear(c);break;case 42:')
    text=text.replace('if(input_size)memcpy(G2H(0x5ffd)', '''if(sample->slot==36){D8Rect*r=(D8Rect*)input_data;input_size=sample->a*16;r[0].left=0;r[0].top=0;r[0].right=800;r[0].bottom=600;r[1].left=20;r[1].top=20;r[1].right=100;r[1].bottom=100;wr32(0x200c,sample->a?0x5ffd:0);wr32(0x2010,sample->b);wr32(0x2014,0xff123456);wr32(0x2018,sample->c);wr32(0x201c,sample->input_kind);}
 if(input_size)memcpy(G2H(0x5ffd)''')
    fixture=(HERE/'fixture.c').read_text()
    marker='static void readback(void)'
    start=fixture.index(marker);end=fixture.index('static void invoke(',start)
    fixture=fixture[:start]+'''typedef struct PixelLock{INT pitch;void*bits;}PixelLock;
static void readback(void){typedef HRESULT(WINAPI*BB)(D8Device*,UINT,UINT,void**);typedef HRESULT(WINAPI*Lock)(void*,PixelLock*,const RECT*,DWORD);typedef HRESULT(WINAPI*Unlock)(void*);typedef ULONG(WINAPI*Release)(void*);void*s=NULL;PixelLock locked={0};DWORD pixel=0xa5a5a5a5;ULONG rel=999;HRESULT h=((BB)table(device)[16])(device,0,0,&s),l=E_FAIL,u=E_FAIL;if(SUCCEEDED(h)&&s){l=((Lock)table(s)[9])(s,&locked,NULL,0x10);if(SUCCEEDED(l)){pixel=*(DWORD*)locked.bits&0xffffff;u=((Unlock)table(s)[10])(s);}rel=((Release)table(s)[2])(s);}printf("{\\"kind\\":\\"semantic-readback\\",\\"hr\\":%lu,\\"value\\":%lu,\\"extra\\":%lu,\\"nonnull\\":false,\\"bytes\\":\\"\\",\\"get_hr\\":%lu,\\"lock_hr\\":%lu,\\"unlock_hr\\":%lu}\\n",(DWORD)(FAILED(h)?h:FAILED(l)?l:u),pixel,rel,(DWORD)h,(DWORD)l,(DWORD)u);}
static DWORD WINAPI clear_native(uintptr_t p,uintptr_t ignored){float z;(void)ignored;memcpy(&z,&sample->c,4);return (DWORD)((D8Device*)p)->vt->Clear((D8Device*)p,sample->a,sample->a?(D8Rect*)input_data:NULL,sample->b,0xff123456,z,sample->input_kind);}
'''+fixture[end:]
    fixture=fixture.replace('memset(&out,0,sizeof out);SetLastError(seed);', 'args.fn=BATCH_TRANSLATED?(void*)wrap2:(void*)clear_native;args.count=2;\n memset(&out,0,sizeof out);SetLastError(seed);')
    fixture=fixture.replace('1,1,75,0,0,0};HRESULT hr;', '1,1,75,1,0,0};HRESULT hr;')
    return fixture,text
