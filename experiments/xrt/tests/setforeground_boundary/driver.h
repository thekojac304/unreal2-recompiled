/* Real visible owned top-level HWND, matching the encountered game style. */
static int failures;
static uintptr_t handles[8];static HWND raw_handles[8];
static void expect(int ok){if(!ok)failures++;}
static int identity(HWND h){unsigned i;if(!h)return 0;for(i=1;i<8;i++)if(raw_handles[i]==h)return (int)i;return 9;}
static int token_identity(uintptr_t h){return identity(host(h));}
static void logs(const char* label){unsigned i,n=get(log_n,0);expect(n%6==0);for(i=0;i<n;i+=6)printf("%s msg=%05lx h=%d other=%d focus=%d result=%lu error=%08lx\n",label,get(log_data,i),token_identity(get(log_data,i+1)),token_identity(get(log_data,i+2)),token_identity(get(log_data,i+3)),get(log_data,i+4),get(log_data,i+5));put(log_n,0);}
static uintptr_t make(unsigned i){uintptr_t h;h=call(make_fn);expect(h!=0);handles[i]=h;raw_handles[i]=host(h);expect(IsWindow(raw_handles[i]));return h;}
static void sample(const char* label,uintptr_t h,DWORD s){uintptr_t r;unsigned i;DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};put(window,(DWORD)h);put(seed,s);r=call(run_fn);for(i=0;i<5;i++)expect(get(abi,i)==want[i]);printf("%s seed=%08lx result=%lu focus=%d foreground=%d error=%08lx abi=%d\n",label,s,(DWORD)r,identity(GetFocus()),identity(GetForegroundWindow()),get(error,0),get(abi,0)==0&&get(abi,1)==want[1]&&get(abi,2)==want[2]&&get(abi,3)==want[3]&&get(abi,4)==want[4]);logs(label);}
static void destroy(uintptr_t h){put(window,(DWORD)h);expect(call(destroy_fn)!=0);}
int main(int argc,char**argv){DWORD seeds[]={0,0x5555,0xdeadbeef};unsigned i;
    if(argc<3)return 2;
#ifdef XRT_INTERNAL_H
    xrt_report_path=argc>3?argv[3]:NULL;
#endif
    init(argv[1]);if(!strcmp(argv[2],"wrong-type")){sample("wrong-type",wrong(),0x5555);finish();return 0;}
    make(1);make(2);logs("creation");
    for(i=0;i<3;i++){sample("game-a",handles[1],seeds[i]);sample("same-a",handles[1],seeds[i]);sample("to-b",handles[2],seeds[i]);sample("null",0,seeds[i]);}
    destroy(handles[1]);destroy(handles[2]);logs("destroy");finish();printf("failures=%d\n",failures);return failures?1:0;
}
