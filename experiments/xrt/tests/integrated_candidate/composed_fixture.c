/* Owned observer protocol double. No original code or graphics backend. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
extern void owned_entry(void*);
extern void owned_invoke(void*,unsigned);
extern void owned_stop(void);
extern void owned_fatal(void);
extern void owned_create(void);
static unsigned char cpu[416],guest[4096];
static void*guest_pointer=guest;
static int corrupt;
static DWORD WINAPI worker(void*unused){
 FILE*f; (void)unused;
 owned_entry(cpu);
 *(uint32_t*)(cpu+16)=0x104;*(uint32_t*)(cpu+64)=0x1090ed5c;*(uint32_t*)(cpu+68)=0x1038fba9;
 if(corrupt==1)*(uint32_t*)(cpu+12)^=1;
 if(fopen_s(&f,"runtime-events.json","w"))return 3;
 fprintf(f,"{\"events_dropped\":0,\"events\":[{\"seq\":1,\"thread\":0,\"kind\":\"engine_init_call\",\"this\":4660,\"esp\":256,\"return\":277933404},{\"seq\":2,\"thread\":0,\"kind\":\"engine_init_return\",\"this\":%u,\"esp_before\":256,\"esp_after\":260,\"return\":277933404,\"actual_return\":277933404}]}",corrupt==2?4664:4660);fclose(f);
 owned_invoke(cpu,0x1090ed5c);
 if(!fopen_s(&f,"FORBIDDEN.txt","w")){fputs("endpoint executed",f);fclose(f);}return 7;
}
int main(int argc,char**argv){FILE*f;HANDLE t;corrupt=argc>1?atoi(argv[1]):0;
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 memset(cpu,0x55,sizeof cpu);*(uint32_t*)(cpu+4)=0x1234;*(uint32_t*)(cpu+16)=0x100;*(uint32_t*)(cpu+68)=0x1090ed59;
 *(uint32_t*)(guest+0x100)=0x1090ed5c;
 if(fopen_s(&f,"ready.json","w"))return 2;
 fprintf(f,"{\"pid\":%lu,\"entry\":%llu,\"stop\":%llu,\"fatal\":%llu,\"create\":%llu,\"guest_pointer\":%llu}",GetCurrentProcessId(),
 (unsigned long long)(uintptr_t)owned_entry,(unsigned long long)(uintptr_t)owned_stop,(unsigned long long)(uintptr_t)owned_fatal,
 (unsigned long long)(uintptr_t)owned_create,(unsigned long long)(uintptr_t)&guest_pointer);fclose(f);
 DebugBreak();t=CreateThread(NULL,0,worker,NULL,0,NULL);if(!t)return 4;WaitForSingleObject(t,3000);return 5;
}
