/* Selected backend adapter. The guest interface file below consumes only
 * DmbMessage, opaque IDs and these operations. Pipe/process details stay here. */
#include "dmusic_pipe.h"
static __declspec(thread) DmbConnection dm_backend_connection;
static int dm_backend_selected(void){const char*s=getenv("XRT_DMUSIC_BACKEND");return s&&!strcmp(s,"ipc");}
static void dm_backend_invoke(CPU*c,DmbMessage*m){
 dm_backend_connection.context=c;
 if(!dmb_exchange(&dm_backend_connection,m))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s",dm_backend_connection.error);
 xrt_event("dmusic_backend","\"version\": %u, \"sequence\": %u, \"op\": %u, \"id\": %u, \"result\": %u, \"out_id\": %u, \"type\": %u",DMB_VERSION,m->sequence,m->op,m->object,m->v[0],m->v[1],m->v[2]);
}
static void dm_backend_start(CPU*c,DmbCallback cb){
 WCHAR exe[600],root[600];const char*path=getenv("XRT_DMUSIC_HELPER");APTTYPE apt;APTTYPEQUALIFIER qualifier;
 if(dm_backend_connection.process)return;
 if(!path||!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,exe,600)||!MultiByteToWideChar(CP_ACP,0,xrt_sandbox_root,-1,root,600))
  xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic IPC requires an explicit project helper path and isolated sandbox");
 if(FAILED(CoGetApartmentType(&apt,&qualifier))||(apt!=APTTYPE_STA&&apt!=APTTYPE_MAINSTA))
  xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic IPC requires the measured owning STA apartment");
 if(!dmb_connect(&dm_backend_connection,exe,root,0,cb,c))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s",dm_backend_connection.error);
 xrt_event("dmusic_backend_start","\"version\": %u, \"frame_bytes\": %u, \"child_pid\": %lu, \"timeout_ms\": %u",DMB_VERSION,DMB_LIMIT,GetProcessId(dm_backend_connection.process),dm_backend_connection.timeout);
}
static int dm_backend_alive(void){return dm_backend_connection.process!=NULL;}
static void dm_backend_end(CPU*c){
 DmbMessage m;if(!dm_backend_alive())return;
 dmb_message(&m,DMB_SHUTDOWN,0);dm_backend_invoke(c,&m);
 WaitForSingleObject(dm_backend_connection.process,2000);dmb_disconnect(&dm_backend_connection);
}
