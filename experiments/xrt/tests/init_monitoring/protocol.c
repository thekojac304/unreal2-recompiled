/* Owned non-game observer protocol. No original module or graphics DLL loaded.
 * Real machine entry/return ABI, synthetic COM and callback bodies. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <xmmintrin.h>
extern void owned_entry(void*);
extern void owned_stop(void);
extern void owned_invoke(void*,unsigned);
static unsigned char cpu[416],initial[416],registry[280];
static unsigned char*guest;
static void*vtable[101];
static void*device=vtable;
static int mode,depth;
static DWORD WINAPI waiter(void*unused){(void)unused;Sleep(INFINITE);return 0;}
#define WORD(o) (*(uint32_t*)(cpu+(o)))
__declspec(noinline) static void fatal(void*c,unsigned code,const char*text){(void)c;(void)code;(void)text;ExitProcess(90);}
__declspec(noinline) static void checkpoint(void*c,unsigned phase,unsigned slot,const void*data,unsigned size,unsigned result,unsigned error){
 volatile unsigned sink=phase+slot+size+result+error;(void)c;(void)data;(void)sink;
}
__declspec(noinline) static void callback(void*c){
 unsigned char saved[416];memcpy(saved,c,416);((unsigned char*)c)[0]^=1;
 if(mode==9 && depth==0){
   FILE*f;
   /* Adversarial owned protocol: a new operation starts inside the callback.
    * The retained scheduler has replaced the checkpoint with callback-return.
    * This records the gap without executing a real resource/native API. */
   checkpoint(c,0,20,NULL,0,0,0);
   if(!fopen_s(&f,"UNOBSERVED-CHECKPOINT.txt","w")){fputs("owned phase-zero checkpoint was not trapped",f);fclose(f);}
 }
 if(depth++==0)callback(c);depth--;memcpy(c,saved,416);
 if(mode==3)((unsigned char*)c)[12]^=1;
 if(mode==4)fatal(c,76,"owned fatal inside callback");
}
static HRESULT WINAPI native(void*object,unsigned state,unsigned value){
 if(object!=&device||state!=14||value!=32)ExitProcess(91);
 callback(cpu);if(mode==8)_mm_setcsr(_mm_getcsr()|32);
 SetLastError(87);return mode==1?E_FAIL:S_OK;
}
static void events(int returned){
 FILE*f;if(fopen_s(&f,"runtime-events.json","w"))ExitProcess(92);
 fprintf(f,"{\"events_dropped\":0,\"events\":[{\"seq\":1,\"thread\":0,\"kind\":\"engine_init_call\",\"this\":4660,\"esp\":256,\"return\":277933404}");
 if(returned)fprintf(f,",{\"seq\":2,\"thread\":0,\"kind\":\"engine_init_return\",\"this\":4660,\"esp_before\":256,\"esp_after\":260,\"return\":277933404,\"actual_return\":277933404}");
 fputs("]}",f);fclose(f);
}
static DWORD WINAPI worker(void*unused){
 HRESULT hr;DWORD error;int i;(void)unused;
 events(0);owned_entry(cpu);
 if(mode==5)Sleep(INFINITE);
 for(i=0;i<2;i++){
   WORD(16)=0x2000;WORD(64)=0;WORD(68)=0x12345678;
   *(uint32_t*)(guest+0x2000)=0x98765432;*(uint32_t*)(guest+0x2004)=0x4000;
   *(uint32_t*)(guest+0x2008)=14;*(uint32_t*)(guest+0x200c)=32;
   checkpoint(cpu,0,mode==2?20:50,NULL,0,0,0x13572468);
   checkpoint(cpu,1,50,NULL,0,0,0x13572468);
   hr=native(&device,14,32);error=GetLastError();
   checkpoint(cpu,2,50,NULL,0,(unsigned)hr,error);
   WORD(0)=(unsigned)hr;WORD(16)+=16;WORD(64)=0x98765432;
   *(uint32_t*)(guest+0x1034)=error;
   checkpoint(cpu,3,50,NULL,0,(unsigned)hr,error);
 }
 memcpy(cpu,initial,416);WORD(16)=0x104;WORD(64)=0x1090ed5c;WORD(68)=0x1038fba9;
 if(mode==7)WORD(12)^=1;
 events(1);owned_invoke(cpu,0x1090ed5c);
 {FILE*f;if(!fopen_s(&f,"FORBIDDEN.txt","w")){fputs("endpoint executed",f);fclose(f);}}
 return 93;
}
int main(int argc,char**argv){
 FILE*f;HANDLE w,t;mode=argc>1?atoi(argv[1]):0;
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 guest=VirtualAlloc(NULL,(SIZE_T)0x100000000ull,MEM_RESERVE,PAGE_NOACCESS);
 if(!guest||VirtualAlloc(guest,0x10000,MEM_COMMIT,PAGE_READWRITE)!=guest)return 2;
 WORD(4)=0x1234;WORD(16)=0x100;WORD(68)=0x1090ed59;
 /* CPU fs_base offset is asserted by Python from the retained parser. */
 WORD(60)=0x1000;*(uint16_t*)(cpu+140)=0x27f;
 *(uint32_t*)(guest+0x100)=0x1090ed5c;
 memcpy(initial,cpu,416);vtable[50]=native;
 *(uint32_t*)(registry)=0x4000;*(uint32_t*)(registry+4)=1;
 *(void**)(registry+24)=&device;
 if(fopen_s(&f,"ready.json","w"))return 3;
 fprintf(f,"{\"pid\":%lu,\"entry\":%llu,\"stop\":%llu,\"checkpoint\":%llu,\"fatal\":%llu,\"callback\":%llu,\"guest_pointer\":%llu,\"cpu\":%llu,\"registry\":%llu}",GetCurrentProcessId(),
 (unsigned long long)(uintptr_t)owned_entry,(unsigned long long)(uintptr_t)owned_stop,
 (unsigned long long)(uintptr_t)checkpoint,(unsigned long long)(uintptr_t)fatal,
 (unsigned long long)(uintptr_t)callback,(unsigned long long)(uintptr_t)&guest,
 (unsigned long long)(uintptr_t)cpu,(unsigned long long)(uintptr_t)registry);fclose(f);
 w=CreateThread(NULL,0,waiter,NULL,0,NULL);if(!w)return 4;
 DebugBreak();t=CreateThread(NULL,0,worker,NULL,0,NULL);if(!t)return 5;
 WaitForSingleObject(t,INFINITE);return 6;
}
