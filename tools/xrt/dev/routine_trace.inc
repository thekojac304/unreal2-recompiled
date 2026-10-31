/* Development only. All detail rolls by default, regardless of API name.
 * Called under the existing lock and assembly CPU/FPU/LastError boundary.
 * Rules classify outcomes; they do NOT decide which operations may roll. */
#define XD_SLOTS 512
#define XD_RECENT 512
#define XD_BATCH 16384
#define XD_FAILED 0x100u
#define XD_UNKNOWN 0x200u
#define XD_SUSPECT 0x400u
#define XD_OVERFLOW 0x800u
#define XD_FILE_META 0x1000u
#define XD_META_MISSING 0x2000u
static const struct { const char *name; unsigned failure; } xd_rules[] = {
#define CRT(n,f) {"msvcr70.dll!" n,f}
 CRT("wcslen",0), CRT("wcscpy",1), CRT("wcscat",1), CRT("wcsncpy",1),
 CRT("wcscmp",0), CRT("wcsncmp",0), CRT("_wcsicmp",0), CRT("_wcsnicmp",0),
 CRT("wcschr",0), CRT("wcsrchr",0), CRT("wcsstr",0), CRT("_wcsupr",1),
 CRT("_wtoi",0), CRT("strncpy",1), CRT("strchr",0), CRT("strrchr",0),
 CRT("_stricmp",0), CRT("atoi",0), CRT("toupper",0), CRT("tolower",0),
 CRT("memmove",1), CRT("malloc",1), CRT("realloc",1), CRT("free",0),
 CRT("_msize",2), CRT("_isnan",0), CRT("rand",0), CRT("srand",0),
 CRT("_vsnwprintf",2), CRT("sprintf",2), CRT("time",2), {"winmm.dll!timeGetTime",0}, {"kernel32.dll!GetTickCount",0},
 {"kernel32.dll!ReadFile",1}, {"kernel32.dll!WriteFile",1},
 {"kernel32.dll!CloseHandle",1}, {"kernel32.dll!CreateFileA",2},
 {"kernel32.dll!CreateFileW",2}, {"kernel32.dll!SetFilePointer",3},
 {"kernel32.dll!GetFileSize",3},
#undef CRT
};

typedef struct XdSummary {
 char name[128];
 uint64_t begins, ends, failures, aborts, minimum, maximum, changes, error_changes;
 uint64_t unclassified, suspects, bytes, short_io, metadata_missing;
 XmRecord first_begin, first_end, last_begin, last_end, first_failure;
} XdSummary;
/* Fixed snapshot, CRC checked. Abrupt overwrite can tear it; never an audit log. */
static struct XdSnapshot {
 uint32_t magic, version, size, slots;
 uint64_t generation, observed, routine_events, critical_records;
 uint64_t overwritten, table_overflow, selected_records, unclassified, suspects;
 uint64_t last_flush_observed;
 uint32_t terminal, recent_next;
 XdSummary imports[XD_SLOTS];
 XmRecord recent[XD_RECENT];
 uint32_t crc;
} xd;
static HANDLE xd_sink=INVALID_HANDLE_VALUE;
static unsigned xd_dirty, xd_since_flush, xd_force_flush, xd_durable;
static char xd_selected[2048], xd_addresses[2048];
#ifdef XRT_DEV_TRACE_TEST
void xd_test_break_sink(void){CloseHandle(xd_sink);xd_sink=INVALID_HANDLE_VALUE;}
#endif
static __declspec(thread) struct {
 struct { unsigned index, emitted, selected; XmRecord begin; } frames[XM_DEPTH];
} xd_tls;

static int xd_selected_name(const char *name) {
 const char *p=xd_selected;size_t n=strlen(name);
 while(*p){const char *end=strchr(p,';');size_t len=end?(size_t)(end-p):strlen(p);
  if(len==n&&!memcmp(p,name,n))return 1;if(!end)break;p=end+1;}
 return 0;
}
static int xd_selected_pc(const XmRecord*r) {
 const char *p=xd_addresses;uint32_t pc=0,caller=0;
 if(r->cpu_size)memcpy(&pc,r->cpu+offsetof(CPU,pc),4);
 if(r->stack_size)memcpy(&caller,r->stack,4);
 while(*p){char *end;unsigned long a=strtoul(p,&end,0);
  if(end==p || (*end && *end!=';') || !a)xm_failure(24);
  if(a==pc || a==caller)return 1;if(!*end)break;p=end+1;}
 return 0;
}
/* Names are mostly stable literals: a pointer-keyed hint, always confirmed by one strcmp, avoids scanning every
 * slot on each event. A reused buffer with new contents misses the hint and takes the scan. */
static struct {const char*name;unsigned index;} xd_hint[1024];
static unsigned xd_index(const char*name) {
 unsigned i,h=(unsigned)(((uintptr_t)name>>3)^((uintptr_t)name>>13))&1023;
 if(xd_hint[h].name==name&&!strcmp(name,xd.imports[xd_hint[h].index].name))return xd_hint[h].index;
 for(i=0;i<xd.slots;i++)if(!strcmp(name,xd.imports[i].name)){xd_hint[h].name=name;xd_hint[h].index=i;return i;}
 if(xd.slots<XD_SLOTS-1){i=xd.slots++;strcpy(xd.imports[i].name,name);xd_hint[h].name=name;xd_hint[h].index=i;return i;}
 xd.table_overflow++;return XD_SLOTS-1;
}
static void xd_flush(void) {
 DWORD written;LARGE_INTEGER zero;
 if(!xm_profile||!xd_dirty)return;
 zero.QuadPart=0;xd.generation++;xd.critical_records=xm_recorded;
 xd.last_flush_observed=xd.observed;
 xd.crc=crc32(&xd,offsetof(struct XdSnapshot,crc));
 if(!SetFilePointerEx(xd_sink,zero,NULL,FILE_BEGIN)||
    !WriteFile(xd_sink,&xd,sizeof xd,&written,NULL)||written!=sizeof xd||
    (xd_durable&&!FlushFileBuffers(xd_sink)))xm_failure(25);
 xd_dirty=xd_since_flush=0;
}
static void xd_init(const char*path) {
 char output[2048];const char *selected=getenv("XRT_DEV_TRACE_FULL");
 const char *addresses=getenv("XRT_DEV_TRACE_ADDRESS");
 if(!xm_profile)return;
 if(strlen(path)+9>=sizeof output || (selected&&strlen(selected)>=sizeof xd_selected) ||
    (addresses&&strlen(addresses)>=sizeof xd_addresses))xm_failure(24);
 strcpy(output,path);strcat(output,".routine");
 if(selected)strcpy(xd_selected,selected);if(addresses)strcpy(xd_addresses,addresses);
 xd_sink=CreateFileA(output,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
 if(xd_sink==INVALID_HANDLE_VALUE)xm_failure(25);
 xd.magic=0x31524458;xd.version=2;xd.size=sizeof xd;
 strcpy(xd.imports[XD_SLOTS-1].name,"<operation table overflow>");xd_dirty=1;
}
/* Explicit detail and durable exceptions use the existing stream without a
 * development record ceiling. Selected tracing can grow on disk by request. */
static void xd_append(XmRecord*r) {
 r->sequence=++serial;r->previous_crc=chain;r->crc=crc32(r,offsetof(XmRecord,crc));
 xm_pending=*r;MemoryBarrier();
 if(xm_buffer_count>=4096)xm_failure(22);
 xm_buffer[xm_buffer_count]=*r;MemoryBarrier();xm_buffer_count++;
 chain=r->crc;xm_recorded=r->sequence;MemoryBarrier();
 if(xm_buffer_count>=256)drain();
}
/* -1 means unclassified, never an assertion of success. Preserve the first
 * such return, count all, and separately preserve/count suspicious returns.
 * LastError is evidence, not a generic failure predicate for known APIs. */
static int xd_failure(const XmRecord*r) {
 unsigned i;uint32_t v=(uint32_t)r->result;
 for(i=0;i<sizeof xd_rules/sizeof xd_rules[0];i++)if(!strcmp(r->name,xd_rules[i].name)){
  unsigned rule=xd_rules[i].failure;
  return rule==1?!v:rule==2?v==0xffffffffu:rule==3?v==0xffffffffu&&r->guest_error!=0:0;
 }
 return -1;
}
static int xd_milestone(const char*name) {
 return !strcmp(name,"UGameEngine.Init");
}
static int xd_route(XmRecord*r,int bad) {
 unsigned d=tls.depth?tls.depth-1:0,i,index=0,selected=0,keep=0,urgent=0;
 /* Caught C++ exceptions (EH continuation 1 / rethrow 2) are routine control flow: retained, batched, not forced. */
 int eh_unwind=r->event==XM_ABORT&&(r->result==1||r->result==2);
 int failed=0,suspect=0;XdSummary*s=NULL;
 xd_force_flush=0;r->sequence=++xd.observed;xd_dirty=1;xd_since_flush++;
 if(r->event==XM_BEGIN&&!bad){
  index=xd_index(r->name);s=&xd.imports[index];
  selected=xd_selected_name(r->name)||xd_selected_pc(r)||(d&&xd_tls.frames[d-1].selected);
  xd_tls.frames[d].index=index;xd_tls.frames[d].emitted=0;xd_tls.frames[d].selected=selected;
  xd_tls.frames[d].begin=*r;
  if(!s->begins)s->first_begin=*r;s->begins++;s->last_begin=*r;
  keep=selected||xd_milestone(r->name);urgent=xd_milestone(r->name);
 }else if((r->event==XM_END||r->event==XM_ABORT)&&tls.depth&&!bad){
  index=xd_tls.frames[d].index;s=&xd.imports[index];selected=xd_tls.frames[d].selected;
  failed=r->event==XM_ABORT?1:xd_failure(r);
  if(failed<0){
   suspect=!(uint32_t)r->result||((uint32_t)r->result&0x80000000u)||
     r->guest_error!=xd_tls.frames[d].begin.guest_error||r->error!=xd_tls.frames[d].begin.error;
   r->flags|=XD_UNKNOWN;xd.unclassified++;keep=!s->unclassified++;
   if(suspect){r->flags|=XD_SUSPECT;xd.suspects++;keep|=!s->suspects++;}
  }
  if(failed>0){r->flags|=XD_FAILED;keep|=!s->failures++;if(s->failures==1)s->first_failure=*r;}
  if(r->event==XM_ABORT)s->aborts++;
  else {
   /* Read only the scalar bytes-transferred output named by the BEGIN args.
    * Never copy the file buffer. END ESP may already have popped arguments. */
   if(!strcmp(r->name,"kernel32.dll!ReadFile")||!strcmp(r->name,"kernel32.dll!WriteFile")){
    uint32_t args[4]={0},got=0;XmRecord*b=&xd_tls.frames[d].begin;
    if(b->stack_size>=20){memcpy(args,b->stack+4,sizeof args);
     r->flags|=XD_FILE_META;r->count=3;
     r->values[0]=(XmValue){XM_OPAQUE,4,args[0]};r->values[1]=(XmValue){XM_U32,4,args[2]};
     if(args[3]&&copy_guest(&got,args[3],4)){
      r->values[2]=(XmValue){XM_U32,4,got};if(r->result){s->bytes+=got;s->short_io+=got<args[2];}
     }else {r->flags|=XD_META_MISSING;s->metadata_missing++;}
    }else {r->flags|=XD_META_MISSING;s->metadata_missing++;}
   }
   if(!s->ends){s->first_end=*r;s->minimum=s->maximum=r->result;}
   else {s->changes+=s->last_end.result!=r->result;s->error_changes+=s->last_end.guest_error!=r->guest_error||s->last_end.error!=r->error;}
   s->ends++;if(r->result<s->minimum)s->minimum=r->result;if(r->result>s->maximum)s->maximum=r->result;s->last_end=*r;
  }
  urgent=keep||(r->event==XM_ABORT&&!eh_unwind)||xd_milestone(r->name);
  keep|=selected||xd_tls.frames[d].emitted||xd_milestone(r->name);
 }else {
  selected=xd_selected_name(r->name)||xd_selected_pc(r)||(tls.depth&&xd_tls.frames[d].selected);
  keep=selected;
 }
 if(s&&index==XD_SLOTS-1){r->flags|=XD_OVERFLOW;if(s->begins==1)keep=urgent=1;}
 if(bad||r->event==XM_OPEN||r->event==XM_CLOSE||r->event==XM_CHECKPOINT||
    r->event==XM_FATAL||r->event==XM_GAP||(r->event==XM_ABORT&&!eh_unwind))keep=urgent=1;
 if(eh_unwind)keep=1;
 if(r->event==XM_CLOSE)xd.terminal=1;
 if(r->event==XM_CHECKPOINT&&!strcmp(r->name,"dev.Init.return"))xd.terminal=2;
 if(r->event==XM_FATAL)xd.terminal=3;
 if(r->event==XM_GAP)xd.terminal=4;
 /* Every observed event goes through the ring, including selected/fatal detail. */
 xd.recent[xd.recent_next]=*r;xd.recent_next=(xd.recent_next+1)%XD_RECENT;
 if(xd.observed>XD_RECENT)xd.overwritten++;
 if(selected)xd.selected_records++;
 if(keep){
  /* Sparse durable stream still carries the active ancestry. Retained BEGINs
   * are emitted once; only selected scopes inherit full descendant tracing. */
  for(i=0;i<tls.depth;i++)if(!xd_tls.frames[i].emitted){
   if(r->event==XM_BEGIN&&i==d){xd_tls.frames[i].emitted=1;break;}
   xd_append(&xd_tls.frames[i].begin);xd_tls.frames[i].emitted=1;
  }
 }else xd.routine_events++;
 xd_force_flush=urgent||xd_since_flush>=XD_BATCH;
 /* Periodic snapshots are written (they survive process termination) but only urgent ones force the disk. */
 xd_durable=urgent;
 /* The caller only appends when keep is true, so flush suppressed batches here. */
 if(!keep&&xd_force_flush){drain();xd_flush();}
 return !keep;
}
