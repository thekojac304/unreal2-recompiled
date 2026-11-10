/* Native x86 test with actual CALL/RET 20. No game or runtime links. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
uint32_t fixture_frame[6],fixture_this,entry_esp,before_esp,after_esp,expected_return,request_flags;
unsigned char viewport[0x100],renderer[0x4700];
extern int frame_invoke(int);
int main(int argc,char**argv) {
    int mode=argc>1?atoi(argv[1]):0,rv;FILE*out;
    *(uint32_t*)(viewport+0x74)=1540;*(uint32_t*)(viewport+0x78)=945;
    if(mode==2)*(uint32_t*)(renderer+0x70)=1;
    if(mode==3)request_flags=1;
    rv=frame_invoke(mode);
    if(rv!=1 || fixture_frame[0]!=expected_return || fixture_frame[1]!=(uint32_t)(uintptr_t)viewport ||
       fixture_frame[2]!=1540 || fixture_frame[3]!=945 || fixture_frame[4]!=(mode>=2?1u:0u) || fixture_frame[5]!=32 ||
       fixture_this!=(uint32_t)(uintptr_t)renderer || before_esp!=after_esp || after_esp-entry_esp!=24)return 4;
    if(fopen_s(&out,"ready.json","w"))return 2;
    fprintf(out,"{\"pid\":%lu,\"frame_address\":%u,\"frame\":[%u,%u,%u,%u,%u,%u],\"this\":%u,\"stack_delta\":%u,\"ret20\":true}",
      GetCurrentProcessId(),(uint32_t)(uintptr_t)fixture_frame,fixture_frame[0],fixture_frame[1],fixture_frame[2],fixture_frame[3],fixture_frame[4],fixture_frame[5],fixture_this,after_esp-entry_esp);
    fclose(out);DebugBreak();
    if(!fopen_s(&out,"FORBIDDEN.txt","w")){fputs("post-observation resumed",out);fclose(out);}
    return 3;
}
