/* Typed translated guest COM interfaces, independent of the selected backend's
 * architecture, COM implementation and transport. All pointers below are guest
 * local; the backend only receives opaque IDs, GUIDs and marshalled values. */
typedef struct {uint32_t guest,id,type,refs;DWORD owner;} DmiObject;
typedef struct {uint32_t guest,id;DWORD owner;} DmiTool;
static DmiObject dmi_objects[128];static DmiTool dmi_tools[8];
static uint32_t dmi_tables[8];
static DmiObject*dmi_find(CPU*c,uint32_t guest){unsigned i;
 for(i=0;i<128;i++)if(dmi_objects[i].guest==guest&&dmi_objects[i].refs){dm_owner(c,dmi_objects[i].owner);return &dmi_objects[i];}
 xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic IPC stale or unknown guest interface %08x",guest);
}
static DmiObject*dmi_id(CPU*c,uint32_t id){unsigned i;
 for(i=0;i<128;i++)if(dmi_objects[i].id==id&&dmi_objects[i].refs){dm_owner(c,dmi_objects[i].owner);return &dmi_objects[i];}
 xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic backend returned an unknown object ID %u",id);
}
static void dmi_text(CPU*c,uint32_t guest,uint16_t*out){unsigned i;
 for(i=0;i<511;i++){com_memory(c,guest+i*2,2,"DirectMusic UTF16");out[i]=rd16(guest+i*2);if(!out[i])return;}
 xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic string exceeds protocol bound");
}
static void dmi_guid(CPU*c,uint32_t guest,uint8_t*out){com_memory(c,guest,16,"DirectMusic GUID");memcpy(out,G2H(guest),16);}
static void dmi_Unsupported(CPU*c){DmiObject*o=dmi_find(c,ARG(0));xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured method on type %u opaque ID %u (caller %08x)",o->type,o->id,rd32(c->r[ESP]));}
static uint32_t dmi_wrap(CPU*c,DmbMessage*m){
 DmiObject*o=NULL;unsigned i,n;const char*names[53];uint32_t type=m->v[2];
 if(FAILED((HRESULT)m->v[0])){if(m->v[1])xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic failure with object ID");return 0;}
 if(!m->v[1]||type<1||type>7)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic invalid object type/ID");
 for(i=0;i<128;i++)if(dmi_objects[i].id==m->v[1]&&dmi_objects[i].refs&&dmi_objects[i].owner==GetCurrentThreadId()){
  if(dmi_objects[i].type!=type)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic changed interface identity type");
  dmi_objects[i].refs++;return dmi_objects[i].guest;
 }
 for(i=0;i<128;i++)if(!dmi_objects[i].guest){o=&dmi_objects[i];break;}
 if(!o)xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic guest interface limit");
 if(!dmi_tables[type]){
  n=type==DMB_LOADER?15:type==DMB_PERFORMANCE?53:type==DMB_SCRIPT_OBJECT?13:type==DMB_SOUND?11:7;
  for(i=0;i<n;i++)names[i]="DMI.Unsupported";
  names[0]="DMI.QI";names[1]="DMI.AddRef";names[2]="DMI.Release";
  if(type==DMB_LOADER){names[3]="DMI.Script";names[5]="DMI.Search";names[13]="DMI.ReleaseObject";names[14]="DMI.Load";}
  if(type==DMB_PERFORMANCE){names[5]="DMI.Stop";names[34]="DMI.Volume";names[38]="DMI.Close";names[44]="DMI.InitAudio";names[51]="DMI.Path";}
  if(type==DMB_AUDIOPATH)names[3]="DMI.Graph";
  if(type==DMB_TOOLGRAPH)names[4]="DMI.Insert";
  if(type==DMB_SCRIPT_OBJECT){names[3]="DMI.ScriptInit";names[4]="DMI.Routine";}
  dmi_tables[type]=com_vtable(names,n);
 }
 o->guest=xrt_rt_alloc(4,4);o->id=m->v[1];o->refs=1;o->type=type;o->owner=GetCurrentThreadId();wr32(o->guest,dmi_tables[type]);return o->guest;
}
static int dmi_callback(void*context,const DmbMessage*q,DmbMessage*r){
 CPU*c=(CPU*)context,nested;DmiTool*t=NULL;uint32_t a[4],scratch,table,fn,result;unsigned i,nargs=1;
 static const GUID tool_iid={0xd2ac28ba,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
 static const GUID tool8_iid={0x0e674303,0x3b05,0x11d3,{0x9b,0xd1,0xf9,0xe7,0xf0,0xa0,0x15,0x36}};
 static const GUID persist_iid={0x109,0,0,{0xc0,0,0,0,0,0,0,0x46}};
 for(i=0;i<8;i++)if(dmi_tools[i].id==q->object&&dmi_tools[i].owner==GetCurrentThreadId()){t=&dmi_tools[i];break;}
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
 xrt_event("dmusic_tool_callback","\"id\": %u, \"slot\": %u, \"result\": %u, \"value1\": %u, \"value2\": %u",t->id,q->op,result,r->v[1],r->v[2]);return 1;
}
static void dmipc_thread_cleanup(CPU*c){unsigned i,released=0;DmbMessage m;
 if(!dm_backend_alive())return;
 for(i=128;i;i--){DmiObject*o=&dmi_objects[i-1];if(o->owner!=GetCurrentThreadId())continue;
  while(o->refs){dmb_message(&m,DMB_RELEASE,o->id);dm_backend_invoke(c,&m);o->refs--;released++;}
 }
 dm_backend_end(c);xrt_event("dmusic_backend_cleanup","\"references_released\": %u",released);
}
static int dmipc_factory(CPU*c,const GUID*cls,const GUID*iid){
 DmbMessage m;uint32_t type,p;
 if(!dm_backend_selected())return 0;
 if(dm_equal(cls,&dm_clsid_loader)&&dm_equal(iid,&dm_iid_loader8))type=DMB_LOADER;
 else if(dm_equal(cls,&dm_clsid_performance)&&dm_equal(iid,&dm_iid_performance8))type=DMB_PERFORMANCE;
 else xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured factory");
 dm_owner(c,c->thread->host_tid);dm_backend_start(c,dmi_callback);xrt_cleanup_register(dm_cleanup);
 dmb_message(&m,DMB_CREATE,0);m.v[0]=type;dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(4),p);
 xrt_event("com_factory","\"class\": \"%s\", \"backend\": \"ipc\", \"result\": %u, \"object\": %u",type==DMB_LOADER?"DirectMusicLoader8":"DirectMusicPerformance8",m.v[0],p);
 RET_STD(5,m.v[0]);return 1;
}
#define DMI_BEGIN(op) DmiObject*o=dmi_find(c,ARG(0));DmbMessage m;dmb_message(&m,op,o->id)
static void dmi_QI(CPU*c){uint32_t p;DMI_BEGIN(DMB_QI);dmi_guid(c,ARG(1),m.guid[0]);com_memory(c,ARG(2),4,"DirectMusic QI");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(2),p);RET_STD(3,m.v[0]);}
static void dmi_AddRef(CPU*c){DMI_BEGIN(DMB_ADDREF);dm_backend_invoke(c,&m);o->refs++;RET_STD(1,m.v[0]);}
static void dmi_Release(CPU*c){DMI_BEGIN(DMB_RELEASE);dm_backend_invoke(c,&m);o->refs--;RET_STD(1,m.v[0]);}
static void dmi_InitAudio(CPU*c){uint32_t p;DMI_BEGIN(DMB_INIT_AUDIO);
 if(ARG(1)||!ARG(2)||ARG(3)||ARG(7))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured InitAudio pointers");
 com_memory(c,ARG(2),4,"DirectMusic DirectSound output");m.v[0]=ARG(4);m.v[1]=ARG(5);m.v[2]=ARG(6);dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(2),p);RET_STD(8,m.v[0]);}
static void dmi_Search(CPU*c){WCHAR full[512];DMI_BEGIN(DMB_SEARCH);dmi_guid(c,ARG(1),m.guid[0]);dmi_text(c,ARG(2),m.text);m.v[0]=ARG(3);
 if(!GetFullPathNameW((WCHAR*)m.text,512,full,NULL))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic invalid search directory");
 {size_t n=wcslen(full);while(n&&full[n-1]==L'\\')full[--n]=0;}
 wcscpy((WCHAR*)m.text,full);dm_backend_invoke(c,&m);RET_STD(4,m.v[0]);}
static void dmi_Path(CPU*c){uint32_t p;DMI_BEGIN(DMB_PATH);com_memory(c,ARG(1),4,"DirectMusic path output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(1),p);RET_STD(2,m.v[0]);}
static void dmi_Graph(CPU*c){uint32_t p;DMI_BEGIN(DMB_GRAPH);m.v[0]=ARG(1);m.v[1]=ARG(2);m.v[2]=ARG(3);m.v[3]=ARG(5);dmi_guid(c,ARG(4),m.guid[0]);dmi_guid(c,ARG(6),m.guid[1]);com_memory(c,ARG(7),4,"DirectMusic graph output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(7),p);RET_STD(8,m.v[0]);}
static void dmi_Insert(CPU*c){unsigned i;DmiTool*t=NULL;DMI_BEGIN(DMB_INSERT);
 if(ARG(2)||ARG(3)||ARG(4))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured tool insertion");
 for(i=0;i<8;i++)if(!dmi_tools[i].guest){t=&dmi_tools[i];t->id=i+1;break;}
 if(!t)xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic tool limit");com_memory(c,ARG(1),4,"DirectMusic tool");t->guest=ARG(1);t->owner=GetCurrentThreadId();m.v[0]=t->id;dm_backend_invoke(c,&m);RET_STD(5,m.v[0]);}
static void dmi_Load(CPU*c){uint32_t p;DMI_BEGIN(DMB_LOAD);dmi_guid(c,ARG(1),m.guid[0]);dmi_guid(c,ARG(2),m.guid[1]);dmi_text(c,ARG(3),m.text);com_memory(c,ARG(4),4,"DirectMusic container output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(4),p);RET_STD(5,m.v[0]);}
static void dmi_Script(CPU*c){uint32_t p;DMI_BEGIN(DMB_SCRIPT);com_memory(c,ARG(1),848,"DirectMusic object descriptor");
 /* Validate the pointer-free measured descriptor before serializing anything.
  * Memory/stream fields and every unused byte must be zero. */
 *(uint32_t*)m.data=848;*(uint32_t*)(m.data+4)=0x206;
 {static const GUID cls={0x810b5013,0xe88d,0x11d2,{0x8b,0xc1,0,0x60,8,0x93,0xb1,0xb6}};memcpy(m.data+24,&cls,16);}
 memcpy(m.data+56,L"Script1",16);
 if(memcmp(m.data,G2H(ARG(1)),848))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured script descriptor (not serialized)");
 dmi_guid(c,ARG(2),m.guid[0]);com_memory(c,ARG(3),4,"DirectMusic script output");dm_backend_invoke(c,&m);p=dmi_wrap(c,&m);wr32(ARG(3),p);RET_STD(4,m.v[0]);}
static void dmi_ScriptInit(CPU*c){DMI_BEGIN(DMB_SCRIPT_INIT);if(ARG(2))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic script error-info pointer is unmeasured");m.v[0]=dmi_find(c,ARG(1))->id;dm_backend_invoke(c,&m);RET_STD(3,m.v[0]);}
static void dmi_Volume(CPU*c){DMI_BEGIN(DMB_VOLUME);dmi_guid(c,ARG(1),m.guid[0]);if(ARG(3)!=4)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured global parameter size");com_memory(c,ARG(2),4,"DirectMusic volume");m.v[0]=rd32(ARG(2));m.v[1]=ARG(3);dm_backend_invoke(c,&m);RET_STD(4,m.v[0]);}
static void dmi_Routine(CPU*c){DMI_BEGIN(DMB_ROUTINE);if(ARG(2))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic script error-info pointer is unmeasured");dmi_text(c,ARG(1),m.text);dm_backend_invoke(c,&m);RET_STD(3,m.v[0]);}
static void dmi_ReleaseObject(CPU*c){DMI_BEGIN(DMB_RELEASE_OBJECT);m.v[0]=dmi_find(c,ARG(1))->id;dm_backend_invoke(c,&m);RET_STD(2,m.v[0]);}
static void dmi_Stop(CPU*c){DMI_BEGIN(DMB_STOP);if(ARG(1)||ARG(2)||ARG(3)||ARG(4))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic unmeasured Stop arguments");dm_backend_invoke(c,&m);RET_STD(5,m.v[0]);}
static void dmi_Close(CPU*c){DMI_BEGIN(DMB_CLOSE);dm_backend_invoke(c,&m);RET_STD(1,m.v[0]);}
#undef DMI_BEGIN
#define XRT_DMIPC_BINDINGS \
 {"xrt.com","DMI.Unsupported",dmi_Unsupported},{"xrt.com","DMI.QI",dmi_QI}, \
 {"xrt.com","DMI.AddRef",dmi_AddRef},{"xrt.com","DMI.Release",dmi_Release}, \
 {"xrt.com","DMI.InitAudio",dmi_InitAudio},{"xrt.com","DMI.Search",dmi_Search}, \
 {"xrt.com","DMI.Path",dmi_Path},{"xrt.com","DMI.Graph",dmi_Graph},{"xrt.com","DMI.Insert",dmi_Insert}, \
 {"xrt.com","DMI.Load",dmi_Load},{"xrt.com","DMI.Script",dmi_Script},{"xrt.com","DMI.ScriptInit",dmi_ScriptInit}, \
 {"xrt.com","DMI.Volume",dmi_Volume},{"xrt.com","DMI.Routine",dmi_Routine}, \
 {"xrt.com","DMI.ReleaseObject",dmi_ReleaseObject},{"xrt.com","DMI.Stop",dmi_Stop},{"xrt.com","DMI.Close",dmi_Close},
