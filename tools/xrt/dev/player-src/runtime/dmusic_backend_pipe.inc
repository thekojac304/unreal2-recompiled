/* Selected backend adapter. The guest interface file below consumes only
 * DmbMessage, opaque IDs and these operations. Pipe/process details stay here. */
#include "dmusic_pipe.h"
static __declspec(thread) DmbConnection dm_backend_connection;
static HANDLE dm_helper_process;   /* the same process handle, visible to the asynchronous-channel thread (diagnostics) */
static int dm_backend_selected(void){const char*s=getenv("XRT_DMUSIC_BACKEND");return s&&!strcmp(s,"ipc");}
/* Helper failure policy (enhanced batch, 2026-11-02). The x86 helper is a separate process that can die (a crash
 * inside Windows' dmusic.dll was observed) or stop answering (request deadline, rejected request). Music is not needed
 * to play, so such a failure no longer ends the game:
 *  - the precise cause is logged once (xrt.log "DirectMusic: music stopped - ...", event dmusic_lost, stderr) and the
 *    helper is terminated (its Job is closed);
 *  - every guest DirectMusic object of the failed helper becomes stale (dm_generation advances): calls on it are
 *    answered here without IPC (dmi_synthesize: S_OK, or inert proxies for interfaces it returns), so the game's music
 *    code carries on silently; sound effects and speech use OpenAL/XAudio2 and are not affected;
 *  - when the game next creates a DirectMusic loader or performance (every level load and quickload re-initializes
 *    music) a fresh helper is started, at most DM_RESTARTS times per session (no restart loops); objects of the new
 *    helper never mix with stale ones (each guest object carries its generation, ids are matched within it).
 * Protocol violations inside a live exchange (identity changes, unmodelled callbacks ...) are still fatal: they are
 * runtime defects, not helper failures. */
#define DM_RESTARTS 3
static unsigned dm_generation=1,dm_restarts,dm_started;static volatile LONG dm_lost;static int dmi_invoke_dead;
static void dmi_synthesize(DmbMessage*m,const DmbMessage*q);
static void dm_music_lost(CPU*c,const char*why){
 if(InterlockedExchange(&dm_lost,1))return;
 xrt_log("DirectMusic: music stopped - %s. The game continues without music; the helper is restarted at the next music "
         "initialization (level load or quickload; %u of %u restarts used).",why,dm_restarts,DM_RESTARTS);
 xrt_event("dmusic_lost","\"reason\": \"%s\", \"generation\": %u, \"restarts\": %u",why,dm_generation,dm_restarts);
 fprintf(stderr,"DirectMusic: music stopped - %s (game continues)\n",why);fflush(stderr);(void)c;
}
static int dm_backend_invoke(CPU*c,DmbMessage*m){
 DmbMessage q=*m;int dead=dmi_invoke_dead;
 dmi_invoke_dead=0;
 if(dead||!dm_backend_connection.process){
  /* a stale object, or no live helper on this thread: answered locally */
  dmi_synthesize(m,&q);return 0;}
 dm_backend_connection.context=c;
 {int ok;xm_native(c,XM_BEGIN,"DirectMusic.IPC.exchange",0,0);
 xm_span(c,"DirectMusic.IPC.request",m,sizeof *m);
 if(!xrt_exiting)xrt_baton_release();
 ok=dmb_exchange(&dm_backend_connection,m);
 if(!xrt_exiting)xrt_baton_acquire();
 xm_span(c,"DirectMusic.IPC.response",m,sizeof *m);
 xm_native(c,XM_END,"DirectMusic.IPC.exchange",0,ok);
 if(!ok){
  char why[220];DWORD code=STILL_ACTIVE;
  /* dmb_failed has closed the pipes and the Job (the helper is terminated); keep its exit code for the report */
  if(dm_helper_process&&xm_win_WaitForSingleObject(dm_helper_process,0)==WAIT_OBJECT_0)GetExitCodeProcess(dm_helper_process,&code);
  snprintf(why,sizeof why,"%s during request op %u on object %u (helper exit code %08lx)",dm_backend_connection.error,q.op,q.object,code);
  dm_music_lost(c,why);dm_generation++;dm_helper_process=NULL;
  dmi_synthesize(m,&q);return 0;}}
 xrt_event("dmusic_backend","\"version\": %u, \"sequence\": %u, \"op\": %u, \"id\": %u, \"result\": %u, \"out_id\": %u, \"type\": %u",DMB_VERSION,m->sequence,m->op,m->object,m->v[0],m->v[1],m->v[2]);
 return 1;
}
/* Returns 1 with a live helper. The first start keeps the strict setup checks (fatal: a broken installation must be
 * visible); a restart after a failure only logs when it fails, and the game goes on without music. */
static int dm_backend_start(CPU*c,DmbCallback cb){
 WCHAR exe[600],root[600];const char*path=getenv("XRT_DMUSIC_HELPER");APTTYPE apt;APTTYPEQUALIFIER qualifier;
 if(dm_backend_connection.process)return 1;
 if(!path||!xm_win_MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,exe,600)||!xm_win_MultiByteToWideChar(CP_ACP,0,xrt_sandbox_root,-1,root,600))
  xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic IPC requires an explicit project helper path and isolated sandbox");
 /* Standalone player: the music files stay in the installation; the helper gets it as its read-only root (--content;
  * its disk guard still refuses writes and links). */
 {WCHAR music[620],content[620];swprintf(music,620,L"%s\\Music",root);dmb_content=0;
  if(xrt_overlay_content_dir((const uint16_t*)music,(uint16_t*)content,620)){content[wcslen(content)-6]=0;wcscpy(root,content);dmb_content=1;}}
 if(FAILED(xm_win_CoGetApartmentType(&apt,&qualifier))||(apt!=APTTYPE_STA&&apt!=APTTYPE_MAINSTA))
  xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic IPC requires the measured owning STA apartment");
 {int ok;xm_native(c,XM_BEGIN,"DirectMusic.IPC.connect",0,0);
 xm_span(c,"DirectMusic.IPC.helper",exe,(unsigned)(wcslen(exe)+1)*2);
 xm_span(c,"DirectMusic.IPC.root",root,(unsigned)(wcslen(root)+1)*2);
 ok=dmb_connect(&dm_backend_connection,exe,root,0,cb,c);
 xm_native(c,XM_END,"DirectMusic.IPC.connect",0,ok);
 if(!ok&&!dm_started)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s",dm_backend_connection.error);
 if(!ok){char why[220];snprintf(why,sizeof why,"helper restart failed: %s",dm_backend_connection.error);dm_lost=0;dm_music_lost(c,why);return 0;}}
 dm_started=1;
 dm_helper_process=dm_backend_connection.process;
 xrt_event("dmusic_backend_start","\"version\": %u, \"frame_bytes\": %u, \"child_pid\": %lu, \"timeout_ms\": %u",DMB_VERSION,DMB_LIMIT,xm_win_GetProcessId(dm_backend_connection.process),dm_backend_connection.timeout);
 return 1;
}
static int dm_backend_alive(void){return dm_backend_connection.process!=NULL;}
/* Developer test hook (dev_support.c input step "dmkill"): terminate the live helper process as a crash would, to
 * exercise the failure policy above deterministically. Exit code 0xDEAD0001 marks it in the reports. */
void xrt_dev_dmusic_kill(void){HANDLE h=dm_helper_process;
 if(!h){xrt_log("DEV dmkill: no live DirectMusic helper");return;}
 xrt_log("DEV dmkill: terminating the DirectMusic helper (pid %lu)",GetProcessId(h));TerminateProcess(h,0xDEAD0001);
}
static void dm_backend_end(CPU*c){
 DmbMessage m;if(!dm_backend_alive())return;
 dmb_message(&m,DMB_SHUTDOWN,0);dm_backend_invoke(c,&m);
 xm_win_WaitForSingleObject(dm_backend_connection.process,2000);dmb_disconnect(&dm_backend_connection);
}
