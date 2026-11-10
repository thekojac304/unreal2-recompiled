/* Non-game guard qualification: synthetic marker files, no COM game objects. */
#define COBJMACROS
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "../../../experiments/xrt/runtime/dmusic_pipe.h"

int wmain(int argc,WCHAR**argv) {
 DmbConnection c;DmbMessage m;unsigned i;DWORD exitcode;
 if(argc!=3)return 2;
 if(!dmb_connect(&c,argv[1],argv[2],1,NULL,NULL)) {fprintf(stderr,"%s\n",c.error);return 3;}
 /* allow in-tree read; deny write, outside read and traversal. */
 for(i=0;i<4;i++) {
  dmb_message(&m,DMB_TEST_OPEN,0);
  if(i<2)swprintf((WCHAR*)m.text,512,L"%s\\marker.txt",argv[2]);
  else swprintf((WCHAR*)m.text,512,L"%s\\..\\outside.txt",argv[2]);
  if(i==3)wcscpy((WCHAR*)m.text,L"..\\..\\outside.txt");
  m.v[0]=i==1?GENERIC_WRITE:GENERIC_READ;
  if(!dmb_exchange(&c,&m))return 4;
  if(m.v[0]!=(i==0))return 40+i; /* prohibited successful opens are explicit isolation violations */
 }
 dmb_message(&m,DMB_SHUTDOWN,0);if(!dmb_exchange(&c,&m))return 5;
 if(WaitForSingleObject(c.process,2000)!=WAIT_OBJECT_0)return 6;
 if(!GetExitCodeProcess(c.process,&exitcode)||exitcode)return 7;
 dmb_disconnect(&c);puts("guard verified: read allowed; write/outside/traversal denied");return 0;
}
