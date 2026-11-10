/* Typed translated guest COM interfaces, independent of the selected backend's
 * architecture, COM implementation and transport. All pointers below are guest
 * local; the backend only receives opaque IDs, GUIDs and marshalled values. */
typedef struct {uint32_t guest,id,type,refs;DWORD owner;unsigned gen;} DmiObject;   /* gen 0: inert proxy (dmi_synthesize) */
typedef struct {uint32_t guest,id;DWORD owner;} DmiTool;
static DmiObject dmi_objects[128];static DmiTool dmi_tools[8];
static uint32_t dmi_tables[8];
static DmiObject*dmi_find(CPU*c,uint32_t guest){unsigned i;
 for(i=0;i<128;i++)if(dmi_objects[i].guest==guest&&dmi_objects[i].refs){dm_owner(c,dmi_objects[i].owner);return &dmi_objects[i];}
 xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic IPC stale or unknown guest interface %08x",guest);
}
static DmiObject*dmi_id(CPU*c,uint32_t id){unsigned i;
 for(i=0;i<128;i++)if(dmi_objects[i].id==id&&dmi_objects[i].refs&&dmi_objects[i].gen==dm_generation){dm_owner(c,dmi_objects[i].owner);return &dmi_objects[i];}
 xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic backend returned an unknown object ID %u",id);
}
static void dmi_text(CPU*c,uint32_t guest,uint16_t*out){unsigned i;
 for(i=0;i<511;i++){com_memory(c,guest+i*2,2,"DirectMusic UTF16");out[i]=rd16(guest+i*2);if(!out[i])return;}
 xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic string exceeds protocol bound");
}
static void dmi_guid(CPU*c,uint32_t guest,uint8_t*out){com_memory(c,guest,16,"DirectMusic GUID");memcpy(out,G2H(guest),16);}
static void dmi_Unsupported(CPU*c){DmiObject*o=dmi_find(c,ARG(0));xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured method on type %u opaque ID %u (caller %08x)",o->type,o->id,rd32(c->r[ESP]));}
#define DMI_INERT 0x7f000000u   /* ids of inert proxies (dmi_synthesize); never sent to a helper */
static uint32_t dmi_wrap(CPU*c,DmbMessage*m){
 DmiObject*o=NULL;unsigned i,n,gen;const char*names[53];uint32_t type=m->v[2];
 if(FAILED((HRESULT)m->v[0])){if(m->v[1])xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic failure with object ID");return 0;}
 if(!m->v[1]||type<1||type>7)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic invalid object type/ID");
 gen=m->v[1]>=DMI_INERT?0:dm_generation;
 for(i=0;i<128;i++)if(dmi_objects[i].id==m->v[1]&&dmi_objects[i].refs&&dmi_objects[i].gen==gen&&dmi_objects[i].owner==xm_win_GetCurrentThreadId()){
  if(dmi_objects[i].type!=type)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic changed interface identity type");
  dmi_objects[i].refs++;return dmi_objects[i].guest;
 }
 for(i=0;i<128;i++)if(!dmi_objects[i].refs){o=&dmi_objects[i];break;}
 if(!o)xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic guest interface limit");
 if(!dmi_tables[type]){
  n=type==DMB_LOADER?15:type==DMB_PERFORMANCE?53:type==DMB_SCRIPT_OBJECT?13:type==DMB_SOUND?11:7;
  for(i=0;i<n;i++)names[i]="DMI.Unsupported";
  names[0]="DMI.QI";names[1]="DMI.AddRef";names[2]="DMI.Release";
  if(type==DMB_LOADER){names[3]="DMI.Script";names[5]="DMI.Search";names[13]="DMI.ReleaseObject";names[14]="DMI.Load";}
  if(type==DMB_PERFORMANCE){names[17]="DMI.FreePMsg";names[5]="DMI.Stop";names[34]="DMI.Volume";names[38]="DMI.Close";names[44]="DMI.InitAudio";names[51]="DMI.Path";}
  if(type==DMB_AUDIOPATH)names[3]="DMI.Graph";
  if(type==DMB_TOOLGRAPH){names[3]="DMI.Stamp";names[4]="DMI.Insert";}
  if(type==DMB_SCRIPT_OBJECT){names[3]="DMI.ScriptInit";names[4]="DMI.Routine";}
  dmi_tables[type]=com_vtable(names,n);
 }
 /* a released slot is reused with a NEW guest proxy address, so a stale pointer still fails dmi_find (long sessions:
  * every level load and quickload creates ~10 objects; the table used to fill after about a dozen) */
 o->guest=xrt_rt_alloc(4,4);
 o->id=m->v[1];o->refs=1;o->type=type;o->owner=xm_win_GetCurrentThreadId();o->gen=gen;wr32(o->guest,dmi_tables[type]);return o->guest;
}
/* Local answer for a request whose object belongs to a failed helper (or when none is live): success, and an inert
 * proxy of the measured type for every interface the call returns; QueryInterface reports E_NOINTERFACE, Release
 * reports the last reference. The guest keeps working with these proxies; nothing reaches a helper. */
static void dmi_synthesize(DmbMessage*m,const DmbMessage*q){
 static uint32_t inert=DMI_INERT;static unsigned logged;uint32_t type=0;
 *m=*q;m->kind=DMB_REPLY;m->status=0;memset(m->v,0,sizeof m->v);
 switch(q->op){
 case DMB_CREATE:type=q->v[0]==DMB_LOADER||q->v[0]==DMB_PERFORMANCE?q->v[0]:0;break;
 case DMB_INIT_AUDIO:type=DMB_SOUND;break;
 case DMB_PATH:type=DMB_AUDIOPATH;break;
 case DMB_GRAPH:type=DMB_TOOLGRAPH;break;
 case DMB_LOAD:type=DMB_CONTAINER;break;
 case DMB_SCRIPT:type=DMB_SCRIPT_OBJECT;break;
 case DMB_QI:m->v[0]=0x80004002u;break;          /* E_NOINTERFACE */
 case DMB_ADDREF:m->v[0]=1;break;
 default:break;                                   /* S_OK: Release (0 = last reference), Stop, Close, CallRoutine ... */
 }
 if(type){m->v[1]=++inert;m->v[2]=type;}
 if(logged++<24)xrt_log("DirectMusic: request op %u on object %u answered locally (music stopped)%s",q->op,q->object,type?" with an inert proxy":"");
}
static int dmi_callback_sync(void*context,const DmbMessage*q,DmbMessage*r){
 CPU*c=(CPU*)context,nested;DmiTool*t=NULL;uint32_t a[4],scratch,table,fn,result;unsigned i,nargs=1;
 xm_scope(c,XM_BEGIN,XM_CALLBACK,"DirectMusic.IPC.callback",q->op);
 xm_span(c,"DirectMusic.IPC.callback.request",q,sizeof *q);
 static const GUID tool_iid={0xd2ac28ba,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
 static const GUID tool8_iid={0x0e674303,0x3b05,0x11d3,{0x9b,0xd1,0xf9,0xe7,0xf0,0xa0,0x15,0x36}};
 static const GUID persist_iid={0x109,0,0,{0xc0,0,0,0,0,0,0,0x46}};
 for(i=0;i<8;i++)if(dmi_tools[i].id==q->object&&dmi_tools[i].owner==xm_win_GetCurrentThreadId()){t=&dmi_tools[i];break;}
 if(!t||q->op>6)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unsupported tool callback ID %u slot %u",q->object,q->op);
 dm_owner(c,t->owner);com_memory(c,t->guest,4,"DirectMusic tool");table=rd32(t->guest);com_memory(c,table,36,"DirectMusic tool vtable");
 scratch=xrt_rt_alloc(64,4);memset(G2H(scratch),0,64);a[0]=t->guest;fn=rd32(table+q->op*4);nested=*c;
 switch(q->op){
 case 0:
  if(memcmp(q->guid[0],&com_iunknown,16)&&memcmp(q->guid[0],&tool_iid,16)&&memcmp(q->guid[0],&tool8_iid,16)&&memcmp(q->guid[0],&persist_iid,16))
   xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured tool QI");
  memcpy(G2H(scratch),q->guid[0],16);a[1]=scratch;a[2]=scratch+16;nargs=3;break;
 case 3:a[1]=dmi_id(c,q->v[0])->guest;nargs=2;break;
 case 4:case 5:a[1]=scratch;nargs=2;break;
 case 6:if(q->v[0]!=2)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured media count");wr32(scratch,scratch+4);a[1]=scratch;a[2]=2;nargs=3;break;
 }
 result=xrt_call_guest(&nested,fn,nargs,a,1);memset(r->v,0,sizeof r->v);r->v[0]=result;
 if(q->op==0){uint32_t p=rd32(scratch+16);
  if((SUCCEEDED((HRESULT)result)&&p!=t->guest)||(FAILED((HRESULT)result)&&p))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic tool QI changed identity");
  r->v[1]=p?t->id:0;
 }
 if(q->op==4||q->op==5)r->v[1]=rd32(scratch);
 if(q->op==6){if(rd32(scratch)!=scratch+4)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic tool changed media buffer");r->v[1]=rd32(scratch+4);r->v[2]=rd32(scratch+8);}
 xrt_event("dmusic_tool_callback","\"id\": %u, \"slot\": %u, \"result\": %u, \"value1\": %u, \"value2\": %u",t->id,q->op,result,r->v[1],r->v[2]);xm_span(c,"DirectMusic.IPC.callback.response",r,sizeof *r);xm_scope(c,XM_END,XM_CALLBACK,"DirectMusic.IPC.callback",1);return 1;
}
/* Synchronous tool callbacks arrive while this thread waits on IPC without the baton. */
static int dmi_callback(void*context,const DmbMessage*q,DmbMessage*r){int ok;
 if(!xrt_exiting)xrt_baton_acquire();ok=dmi_callback_sync(context,q,r);if(!xrt_exiting)xrt_baton_release();return ok;
}
/* ---- Asynchronous tool callbacks (protocol v2) ----------------------------------
 * DirectMusic delivers ProcessPMsg (ATTIME, realtime thread), AddRef/Release and
 * Flush from its own threads. The helper forwards them on a separate pipe pair to
 * this runtime-owned guest thread, which runs the guest tool under the baton.
 * A delivered lyric PMSG is copied to the guest heap; the native message stays in
 * the helper under a handle until the guest frees it (IDirectMusicPerformance::FreePMsg). */
typedef struct {HANDLE in,out;unsigned gen;} DmiAsync;
static DmiAsync dmi_async,dmi_async_gens[DM_RESTARTS+1];static DWORD dmi_async_tid;static int dmi_async_started;static volatile LONG dmi_async_shutdown;
typedef struct {uint32_t guest,handle,size;unsigned gen;} DmiPmsg;
static DmiPmsg dmi_pmsgs[256];
static uint32_t dmi_active_handle,dmi_active_guest,dmi_active_sequence;
static unsigned dmi_async_events,dmi_async_logged,dmi_free_logged,dmi_pmsg_live,dmi_pmsg_unmapped;
static DmiObject*dmi_lookup(uint32_t id,uint32_t type){unsigned i; /* identity only: no owner rule */
 for(i=0;i<128;i++)if(dmi_objects[i].id==id&&dmi_objects[i].refs&&dmi_objects[i].gen==dm_generation&&(!type||dmi_objects[i].type==type))return &dmi_objects[i];return NULL;
}
static int dmi_async_read(HANDLE h,DmbMessage*m){DWORD n,total=0;
 while(total<sizeof *m){if(!ReadFile(h,(BYTE*)m+total,(DWORD)sizeof *m-total,&n,NULL)||!n)return 0;total+=n;}return 1;
}
static int dmi_async_write(HANDLE h,const DmbMessage*m){DWORD n;return WriteFile(h,m,sizeof *m,&n,NULL)&&n==sizeof *m;}
/* Native pointer identities in a PMSG header become guest identities; one the guest cannot
 * represent (an internal native tool/graph) is stored as 0 and counted, never dereferenced. */
static void dmi_pmsg_header(CPU*c,uint32_t g,const uint8_t*native,DmiTool*t,uint32_t graph_id,uint32_t tool_token){
 DmiObject*graph=graph_id?dmi_lookup(graph_id,DMB_TOOLGRAPH):NULL;uint32_t tool=0,graph_guest=0;unsigned i;
 if(graph_id&&!graph){ /* graph first met in a PMSG: guest proxy owned by this callback thread */
  DmbMessage w;memset(&w,0,sizeof w);w.v[0]=0;w.v[1]=graph_id;w.v[2]=DMB_TOOLGRAPH;graph_guest=dmi_wrap(c,&w);
  graph=dmi_lookup(graph_id,DMB_TOOLGRAPH);
  xrt_event("dmusic_pmsg","\"event\": \"graph-proxy\", \"graph\": %u, \"guest\": %u",graph_id,graph_guest);}
 for(i=0;i<8;i++)if(tool_token&&dmi_tools[i].guest&&dmi_tools[i].id==tool_token)tool=dmi_tools[i].guest;
 memcpy(G2H(g),native,DMB_PMSG_HEADER);
 if(graph_id&&!graph)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic PMSG graph ID %u has no guest proxy",graph_id);
 if(!tool&&tool_token)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic PMSG tool token %u has no guest tool",tool_token);
 if(!tool_token||!graph_id)dmi_pmsg_unmapped++;
 wr32(g+DMB_PMSG_TOOL,tool);wr32(g+DMB_PMSG_GRAPH,graph?graph->guest:0);wr32(g+DMB_PMSG_USER,0);(void)t;
}
static uint32_t dmi_pmsg_copy(CPU*c,const DmbMessage*q,DmiTool*t){uint32_t size=q->v[3],g;
 if(size<DMB_PMSG_HEADER+2||size>sizeof q->data)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic PMSG size %u outside lyric range",size);
 g=xrt_heap_alloc(size);if(!g)xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic PMSG guest allocation");
 memcpy(G2H(g),q->data,size);dmi_pmsg_header(c,g,q->data,t,q->v[1],q->v[4]);return g;
}
static void dmi_async_dispatch(CPU*c,const DmbMessage*q,DmbMessage*r){
 DmiTool*t=NULL;uint32_t a[5],table,fn,result,perf=0,g=0,type,scratch,esp=c->r[ESP];unsigned i,nargs=1;CPU nested;
 static const GUID tool_iid={0xd2ac28ba,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
 static const GUID tool8_iid={0x0e674303,0x3b05,0x11d3,{0x9b,0xd1,0xf9,0xe7,0xf0,0xa0,0x15,0x36}};
 for(i=0;i<8;i++)if(dmi_tools[i].guest&&dmi_tools[i].id==q->object){t=&dmi_tools[i];break;}
 if(!t)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic asynchronous callback for unknown tool %u",q->object);
 com_memory(c,t->guest,4,"DirectMusic tool");table=rd32(t->guest);com_memory(c,table,36,"DirectMusic tool vtable");fn=rd32(table+q->op*4);
 scratch=(esp-128u)&~15u;memset(G2H(scratch),0,64);a[0]=t->guest;nested=*c;nested.r[ESP]=scratch;
 switch(q->op){
 case 0:
  if(memcmp(q->guid[0],&com_iunknown,16)&&memcmp(q->guid[0],&tool_iid,16)&&memcmp(q->guid[0],&tool8_iid,16))
   xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured asynchronous tool QI");
  memcpy(G2H(scratch),q->guid[0],16);a[1]=scratch;a[2]=scratch+16;nargs=3;break;
 case 1:case 2:break;
 case 7:case 8:{DmiObject*pf=dmi_lookup(q->v[2],DMB_PERFORMANCE);
  if(!pf)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic PMSG performance %u has no guest proxy",q->v[2]);
  perf=pf->guest;g=dmi_pmsg_copy(c,q,t);a[1]=perf;a[2]=g;nargs=3;
  if(q->op==8){a[3]=q->v[5];a[4]=q->v[6];nargs=5;}
  else{for(i=0;i<256&&dmi_pmsgs[i].guest;i++){}if(i==256)xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic guest PMSG table full");
   dmi_pmsgs[i].guest=g;dmi_pmsgs[i].handle=q->v[0];dmi_pmsgs[i].size=q->v[3];dmi_pmsgs[i].gen=dm_generation;dmi_pmsg_live++;
   dmi_active_handle=q->v[0];dmi_active_guest=g;dmi_active_sequence=q->sequence;}
  break;}
 default:xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmodelled asynchronous tool slot %u",q->op);
 }
 result=xrt_call_guest(&nested,fn,nargs,a,1);
 type=g?rd32(g+DMB_PMSG_TYPE):0;
 memset(r->v,0,sizeof r->v);r->v[0]=result;
 if(q->op==0){uint32_t p=rd32(scratch+16);
  if((SUCCEEDED((HRESULT)result)&&p!=t->guest)||(FAILED((HRESULT)result)&&p))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic tool QI changed identity");
  r->v[1]=p?t->id:0;}
 if(q->op==7){dmi_active_handle=dmi_active_guest=dmi_active_sequence=0;
  /* Not retained (DMUS_S_FREE/REQUEUE/failure): DirectMusic keeps ownership natively. */
  if(result!=S_OK){for(i=0;i<256;i++)if(dmi_pmsgs[i].guest==g){memset(&dmi_pmsgs[i],0,sizeof dmi_pmsgs[i]);dmi_pmsg_live--;}xrt_heap_free(c,g);}}
 if(q->op==8)xrt_heap_free(c,g);
 if(q->op==7&&type==13)xrt_dev_music_cue((const unsigned short*)(q->data+DMB_PMSG_HEADER));
 if(q->op>=7&&dmi_async_logged<64){dmi_async_logged++;
  xrt_log("DirectMusic async slot %u tool %u pmsg %u type %u guest %08x text '%ls' result %08x live %u",q->op,t->id,q->v[0],type,g,(const wchar_t*)(q->data+DMB_PMSG_HEADER),result,dmi_pmsg_live);}
 if(dmi_async_events++<4096)
  xrt_event("dmusic_async_callback","\"tool\": %u, \"slot\": %u, \"pmsg\": %u, \"type\": %u, \"guest\": %u, \"result\": %u, \"live\": %u",
   t->id,q->op,q->op>=7?q->v[0]:0,type,g,result,dmi_pmsg_live);
}
static void dmi_async_body(CPU*c,void*arg){DmbMessage q,r;DmiAsync pipes=*(DmiAsync*)arg;
 dmi_async_tid=xm_win_GetCurrentThreadId();
 for(;;){
  if(!dmi_async_read(pipes.in,&q)){
   if(dmi_async_shutdown||xrt_exiting){xrt_log("DirectMusic asynchronous channel closed");return;}
   if(pipes.gen!=dm_generation||dm_lost){xrt_log("DirectMusic asynchronous channel of helper generation %u closed (music already stopped)",pipes.gen);return;}
   /* The helper's exit code tells how it ended: 0 its request loop stopped, 80 die() (message on stderr), an NTSTATUS
    * such as c0000005/c0000374/c0000409 a crash, including fail-fast exits that bypass its own crash reporter. */
   {DWORD code=STILL_ACTIVE;if(dm_helper_process&&xm_win_WaitForSingleObject(dm_helper_process,2000)==WAIT_OBJECT_0)GetExitCodeProcess(dm_helper_process,&code);
    /* Exit 0: the helper's request loop saw its pipe close, which is what the runtime's dmb_failed (request deadline,
     * rejected op, response mismatch ...) does on the request thread before that thread reports its own, precise error.
     * Beta batch: this thread used to win the race to xrt_fatal and hid that error behind "exit code 0" (runs
     * 20261102-203529/-203818). Stand down and leave the report to the request thread (its next exchange fails anyway). */
    if(code==0){xrt_log("DirectMusic asynchronous channel closed after the helper's request loop stopped (exit 0): the request thread reports the cause");return;}
    /* The helper died on its own (e.g. a crash in dmusic.dll while playing): music stops, the game goes on. The game
     * thread's next request finds the pipes broken and moves the objects to the stale generation. */
    {char why[160];snprintf(why,sizeof why,"helper process ended (exit code %08lx) - asynchronous channel closed",code);
     xrt_baton_acquire();dm_music_lost(c,why);xrt_baton_release();}
    return;}}
  if(xrt_exiting)return;
  xrt_baton_acquire();
  if(xrt_exiting){xrt_baton_release();return;}
  if(q.magic!=DMB_MAGIC||q.version!=DMB_VERSION||q.bytes!=sizeof q||q.kind!=DMB_ASYNC_CALLBACK)
   xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic invalid asynchronous frame");
  r=q;r.kind=DMB_ASYNC_REPLY;dmi_async_dispatch(c,&q,&r);
  xrt_baton_release();
  if(!dmi_async_write(pipes.out,&r)){xrt_log("DirectMusic asynchronous reply failed");return;}
 }
}
static void dmi_async_start(CPU*c){
 if(dmi_async_started||!dm_backend_connection.async_input)return;
 dmi_async.in=dm_backend_connection.async_input;dmi_async.out=dm_backend_connection.async_output;dmi_async.gen=dm_generation;
 dmi_async_gens[dm_restarts]=dmi_async;
 dmi_async_started=1;xrt_thread_service(c,"DirectMusic tool callbacks",dmi_async_body,&dmi_async_gens[dm_restarts]);
}
/* IDirectMusicGraph::StampPMsg, admitted only from the asynchronous callback thread for
 * the message currently being processed; executed natively on the waiting DirectMusic thread. */
static void dmi_Stamp(CPU*c){DmiObject*o=NULL;DmbMessage m,r;unsigned i;uint32_t g=ARG(1);
 for(i=0;i<128;i++)if(dmi_objects[i].guest==ARG(0)&&dmi_objects[i].refs)o=&dmi_objects[i];
 if(!o||o->type!=DMB_TOOLGRAPH)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic StampPMsg on unknown graph %08x",ARG(0));
 if(!dmi_active_handle||g!=dmi_active_guest||xm_win_GetCurrentThreadId()!=dmi_async_tid)
  xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic StampPMsg outside the active asynchronous tool callback");
 dmb_message(&m,DMB_STAMP_PMSG,o->id);m.kind=DMB_ASYNC_NESTED;m.sequence=dmi_active_sequence;m.v[0]=dmi_active_handle;
 xrt_baton_release();
 if(!dmi_async_write(dmi_async.out,&m))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic nested StampPMsg transport failed");
 /* Native StampPMsg re-targets pTool and so calls the tool's Release/AddRef on the same
  * DirectMusic thread: serve those callbacks recursively until the nested reply. */
 for(;;){
  if(!dmi_async_read(dmi_async.in,&r))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic nested StampPMsg transport failed");
  if(r.magic==DMB_MAGIC&&r.version==DMB_VERSION&&r.bytes==sizeof r&&r.kind==DMB_ASYNC_CALLBACK){DmbMessage reply=r;
   if(r.op==7||r.op==8)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic PMSG delivery nested inside StampPMsg");
   reply.kind=DMB_ASYNC_REPLY;xrt_baton_acquire();dmi_async_dispatch(c,&r,&reply);xrt_baton_release();
   if(!dmi_async_write(dmi_async.out,&reply))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic nested callback reply failed");continue;}
  break;
 }
 xrt_baton_acquire();
 if(r.magic!=DMB_MAGIC||r.kind!=DMB_ASYNC_NESTED_REPLY||r.sequence!=m.sequence||r.op!=DMB_STAMP_PMSG)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic invalid nested reply");
 dmi_pmsg_header(c,g,r.data,NULL,r.v[1],r.v[3]);
 xrt_event("dmusic_pmsg","\"event\": \"stamped\", \"pmsg\": %u, \"guest\": %u, \"result\": %u",m.v[0],g,r.v[0]);
 RET_STD(2,r.v[0]);
}
/* IDirectMusicPerformance::FreePMsg of a retained guest PMSG copy. */
static void dmi_FreePMsg(CPU*c){unsigned i;DmiPmsg*e=NULL;DmiObject*o=dmi_find(c,ARG(0));DmbMessage m;dmb_message(&m,DMB_FREE_PMSG,o->id);(void)o;
 for(i=0;i<256;i++)if(dmi_pmsgs[i].guest&&dmi_pmsgs[i].guest==ARG(1))e=&dmi_pmsgs[i];
 if(!e)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic FreePMsg of a PMSG not delivered to the guest (%08x)",ARG(1));
 m.v[0]=e->handle;dmi_invoke_dead=o->gen!=dm_generation||e->gen!=dm_generation;dm_backend_invoke(c,&m);
 xrt_event("dmusic_pmsg","\"event\": \"freed\", \"pmsg\": %u, \"guest\": %u, \"result\": %u, \"live\": %u",e->handle,e->guest,m.v[0],dmi_pmsg_live-1);
 if(dmi_free_logged++<64)xrt_log("DirectMusic FreePMsg pmsg %u guest %08x result %08x (game thread) live %u unmapped %u",e->handle,e->guest,m.v[0],dmi_pmsg_live-1,dmi_pmsg_unmapped);
 if(SUCCEEDED((HRESULT)m.v[0])){xrt_heap_free(c,e->guest);memset(e,0,sizeof *e);dmi_pmsg_live--;}
 RET_STD(2,m.v[0]);
}
static void dmipc_thread_cleanup(CPU*c){unsigned i,released=0;DmbMessage m;
 if(!dm_backend_alive())return;
 for(i=128;i;i--){DmiObject*o=&dmi_objects[i-1];if(o->owner!=xm_win_GetCurrentThreadId())continue;
  while(o->refs){dmb_message(&m,DMB_RELEASE,o->id);dmi_invoke_dead=o->gen!=dm_generation;dm_backend_invoke(c,&m);o->refs--;released++;}
 }
 dmi_async_shutdown=1;dm_backend_end(c);xrt_event("dmusic_backend_cleanup","\"references_released\": %u",released);
}
static int dmipc_factory(CPU*c,const GUID*cls,const GUID*iid){
 DmbMessage m;uint32_t type,p;
 if(!dm_backend_selected())return 0;
 if(dm_equal(cls,&dm_clsid_loader)&&dm_equal(iid,&dm_iid_loader8))type=DMB_LOADER;
 else if(dm_equal(cls,&dm_clsid_performance)&&dm_equal(iid,&dm_iid_performance8))type=DMB_PERFORMANCE;
 else xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured factory");
 dm_owner(c,c->thread->host_tid);
 if(dm_started&&!dm_backend_alive()){
  /* the helper failed earlier in this session: the game is re-initializing music, start a fresh one (bounded) */
  if(dm_restarts<DM_RESTARTS){
   dm_restarts++;xrt_log("DirectMusic: starting a new helper for the game's music re-initialization (restart %u of %u)",dm_restarts,DM_RESTARTS);
   xrt_event("dmusic_restart","\"restart\": %u, \"generation\": %u",dm_restarts,dm_generation);
   memset(dmi_tools,0,sizeof dmi_tools);dmi_active_handle=dmi_active_guest=dmi_active_sequence=0;
   dmi_async_started=0;dmi_async_shutdown=0;
   if(dm_backend_start(c,dmi_callback)){dm_lost=0;dmi_async_start(c);}
  }else{static int told;if(!told++)xrt_log("DirectMusic: restart limit (%u) reached; music stays off for this session",DM_RESTARTS);}
 }else{dm_backend_start(c,dmi_callback);dmi_async_start(c);}
 xrt_cleanup_register(dm_cleanup);
 dmb_message(&m,DMB_CREATE,0);m.v[0]=type;dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(4),p);
 xrt_event("com_factory","\"class\": \"%s\", \"backend\": \"ipc\", \"result\": %u, \"object\": %u",type==DMB_LOADER?"DirectMusicLoader8":"DirectMusicPerformance8",m.v[0],p);
 RET_STD(5,m.v[0]);return 1;
}
#define DMI_BEGIN(op) DmiObject*o=dmi_find(c,ARG(0));DmbMessage m;dmb_message(&m,op,o->id);dmi_invoke_dead=o->gen!=dm_generation
static void dmi_QI(CPU*c){uint32_t p;DMI_BEGIN(DMB_QI);dmi_guid(c,ARG(1),m.guid[0]);com_memory(c,ARG(2),4,"DirectMusic QI");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(2),p);RET_STD(3,m.v[0]);}
static void dmi_AddRef(CPU*c){DMI_BEGIN(DMB_ADDREF);dm_backend_invoke(c,&m);o->refs++;RET_STD(1,m.v[0]);}
static void dmi_Release(CPU*c){DMI_BEGIN(DMB_RELEASE);dm_backend_invoke(c,&m);o->refs--;RET_STD(1,m.v[0]);}
static void dmi_InitAudio(CPU*c){uint32_t p;DMI_BEGIN(DMB_INIT_AUDIO);
 if(ARG(1)||!ARG(2)||ARG(3)||ARG(7))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured InitAudio pointers");
 com_memory(c,ARG(2),4,"DirectMusic DirectSound output");m.v[0]=ARG(4);m.v[1]=ARG(5);m.v[2]=ARG(6);dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(2),p);RET_STD(8,m.v[0]);}
static void dmi_Search(CPU*c){WCHAR full[512];DMI_BEGIN(DMB_SEARCH);dmi_guid(c,ARG(1),m.guid[0]);dmi_text(c,ARG(2),m.text);m.v[0]=ARG(3);
 if(!xm_win_GetFullPathNameW((WCHAR*)m.text,512,full,NULL))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic invalid search directory");
 {size_t n=wcslen(full);while(n&&full[n-1]==L'\\')full[--n]=0;}
 /* player: the music folder is read from the installation (the helper's read-only root, dmusic_backend_pipe.inc) */
 {WCHAR content[512];if(xrt_overlay_content_dir((const uint16_t*)full,(uint16_t*)content,512))wcscpy(full,content);}
 wcscpy((WCHAR*)m.text,full);dm_backend_invoke(c,&m);RET_STD(4,m.v[0]);}
static void dmi_Path(CPU*c){uint32_t p;DMI_BEGIN(DMB_PATH);com_memory(c,ARG(1),4,"DirectMusic path output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(1),p);RET_STD(2,m.v[0]);}
static void dmi_Graph(CPU*c){uint32_t p;DMI_BEGIN(DMB_GRAPH);m.v[0]=ARG(1);m.v[1]=ARG(2);m.v[2]=ARG(3);m.v[3]=ARG(5);dmi_guid(c,ARG(4),m.guid[0]);dmi_guid(c,ARG(6),m.guid[1]);com_memory(c,ARG(7),4,"DirectMusic graph output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(7),p);RET_STD(8,m.v[0]);}
static void dmi_Insert(CPU*c){unsigned i;DmiTool*t=NULL;DMI_BEGIN(DMB_INSERT);
 if(ARG(2)||ARG(3)||ARG(4))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured tool insertion");
 if(dmi_invoke_dead){dm_backend_invoke(c,&m);RET_STD(5,m.v[0]);return;}
 for(i=0;i<8;i++)if(!dmi_tools[i].guest){t=&dmi_tools[i];t->id=i+1;break;}
 if(!t)xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic tool limit");com_memory(c,ARG(1),4,"DirectMusic tool");t->guest=ARG(1);t->owner=xm_win_GetCurrentThreadId();m.v[0]=t->id;dm_backend_invoke(c,&m);RET_STD(5,m.v[0]);}
static void dmi_Load(CPU*c){uint32_t p;DMI_BEGIN(DMB_LOAD);dmi_guid(c,ARG(1),m.guid[0]);dmi_guid(c,ARG(2),m.guid[1]);dmi_text(c,ARG(3),m.text);com_memory(c,ARG(4),4,"DirectMusic container output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(4),p);RET_STD(5,m.v[0]);}
static void dmi_Script(CPU*c){uint32_t p;DMI_BEGIN(DMB_SCRIPT);com_memory(c,ARG(1),848,"DirectMusic object descriptor");
 /* Validate the pointer-free measured descriptor before serializing anything.
  * Memory/stream fields and every unused byte must be zero. */
 *(uint32_t*)m.data=848;*(uint32_t*)(m.data+4)=0x206;
 {static const GUID cls={0x810b5013,0xe88d,0x11d2,{0x8b,0xc1,0,0x60,8,0x93,0xb1,0xb6}};memcpy(m.data+24,&cls,16);}
 memcpy(m.data+56,L"Script1",16);
 if(memcmp(m.data,G2H(ARG(1)),848))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured script descriptor (not serialized)");
 dmi_guid(c,ARG(2),m.guid[0]);com_memory(c,ARG(3),4,"DirectMusic script output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(3),p);RET_STD(4,m.v[0]);}
static void dmi_ScriptInit(CPU*c){DMI_BEGIN(DMB_SCRIPT_INIT);if(ARG(2))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic script error-info pointer is unmeasured");{DmiObject*x=dmi_find(c,ARG(1));m.v[0]=x->id;if(x->gen!=dm_generation)dmi_invoke_dead=1;}dm_backend_invoke(c,&m);RET_STD(3,m.v[0]);}
static void dmi_Volume(CPU*c){DMI_BEGIN(DMB_VOLUME);dmi_guid(c,ARG(1),m.guid[0]);if(ARG(3)!=4)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured global parameter size");com_memory(c,ARG(2),4,"DirectMusic volume");m.v[0]=rd32(ARG(2));m.v[1]=ARG(3);dm_backend_invoke(c,&m);RET_STD(4,m.v[0]);}
static void dmi_Routine(CPU*c){DMI_BEGIN(DMB_ROUTINE);if(ARG(2))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic script error-info pointer is unmeasured");dmi_text(c,ARG(1),m.text);{wchar_t name[64];wcsncpy(name,(const wchar_t*)m.text,63);name[63]=0;dm_backend_invoke(c,&m);xrt_log("DirectMusic CallRoutine '%ls' -> %08x",name,m.v[0]);}RET_STD(3,m.v[0]);}
static void dmi_ReleaseObject(CPU*c){DMI_BEGIN(DMB_RELEASE_OBJECT);{DmiObject*x=dmi_find(c,ARG(1));m.v[0]=x->id;if(x->gen!=dm_generation)dmi_invoke_dead=1;}dm_backend_invoke(c,&m);RET_STD(2,m.v[0]);}
static void dmi_Stop(CPU*c){DMI_BEGIN(DMB_STOP);if(ARG(1)||ARG(2)||ARG(3)||ARG(4))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured Stop arguments");dm_backend_invoke(c,&m);RET_STD(5,m.v[0]);}
static void dmi_Close(CPU*c){DMI_BEGIN(DMB_CLOSE);dm_backend_invoke(c,&m);RET_STD(1,m.v[0]);}
#undef DMI_BEGIN
#define XRT_DMIPC_BINDINGS \
 {"xrt.com","DMI.Unsupported",dmi_Unsupported},{"xrt.com","DMI.QI",dmi_QI}, \
 {"xrt.com","DMI.AddRef",dmi_AddRef},{"xrt.com","DMI.Release",dmi_Release}, \
 {"xrt.com","DMI.InitAudio",dmi_InitAudio},{"xrt.com","DMI.Search",dmi_Search}, \
 {"xrt.com","DMI.Path",dmi_Path},{"xrt.com","DMI.Graph",dmi_Graph},{"xrt.com","DMI.Insert",dmi_Insert},{"xrt.com","DMI.Stamp",dmi_Stamp},{"xrt.com","DMI.FreePMsg",dmi_FreePMsg}, \
 {"xrt.com","DMI.Load",dmi_Load},{"xrt.com","DMI.Script",dmi_Script},{"xrt.com","DMI.ScriptInit",dmi_ScriptInit}, \
 {"xrt.com","DMI.Volume",dmi_Volume},{"xrt.com","DMI.Routine",dmi_Routine}, \
 {"xrt.com","DMI.ReleaseObject",dmi_ReleaseObject},{"xrt.com","DMI.Stop",dmi_Stop},{"xrt.com","DMI.Close",dmi_Close},
