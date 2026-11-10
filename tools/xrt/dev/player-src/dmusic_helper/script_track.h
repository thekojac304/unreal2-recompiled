/* Developer-only fallback for DirectMusic script tracks (opt-in,
 * XRT_DMUSIC_SCRIPT_TRACK=helper). experiments/xrt/DMUSIC_SCRIPT_TRACK_DESIGN.md.
 *
 * On this host native script tracks never invoke their routines. This makes the
 * call the native track should make: the routine named in the container's own
 * script-track data, on the script that data references, when the event's
 * occurrence reaches the native performance's queue time. Native script-track
 * playback is switched off for the bound segments, so exactly one executor exists.
 * Malformed or unmodelled data fails closed through ST_FAIL.
 *
 * The includer defines ST_FAIL(message) (no return), ST_LOG(...) and
 * st_game_script(guid) -> the game's initialized script with that object GUID, or NULL. */
#ifndef XRT_SCRIPT_TRACK_H
#define XRT_SCRIPT_TRACK_H
#include <windows.h>
#include <stdint.h>
#include <string.h>
static IUnknown*st_game_script(const GUID*script);
static const GUID st_cls_segment={0xd2ac2882,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID st_iid_segment8={0xc6784488,0x41a3,0x418f,{0xaa,0x15,0xb3,0x50,0x93,0xba,0x42,0xd4}};
static const GUID st_cls_script_track={0x4108fa85,0x3586,0x11d3,{0x8b,0xd7,0,0x60,8,0x93,0xb1,0xb6}};
static const GUID st_cls_script={0x810b5013,0xe88d,0x11d2,{0x8b,0xc1,0,0x60,8,0x93,0xb1,0xb6}};
static const GUID st_iid_script8={0x2252373a,0x5814,0x489b,{0x82,9,0x31,0xfe,0xde,0xba,0xf1,0x37}};
enum {ST_SEGMENTS=16,ST_EVENTS=64,ST_QUEUE=2,ST_PLAY_ENABLED=0x10};
typedef struct {DWORD flags;LONG logical,physical;GUID script;WCHAR routine[64];unsigned segment;} StEvent;
typedef struct {
 GUID guid;WCHAR name[64];DWORD repeats;LONG length,play_start,loop_start,loop_end; /* parsed segh */
 unsigned first,count;                                                           /* events */
 IUnknown*segment,*identity;                                                      /* bound native */
} StSegment;
static StSegment st_seg[ST_SEGMENTS];static unsigned st_nseg;
static StEvent st_ev[ST_EVENTS];static unsigned st_nev;static int st_bound;
/* Tracked primary segment state and per-event next occurrence index. */
static IUnknown*st_state;static int st_row=-1;static LONG st_start,st_point;static DWORD st_repeats;
static LONG st_l0,st_l1,st_len;static unsigned st_next[ST_EVENTS];static unsigned st_dispatches;
static IUnknown*st_script,*st_loader;

static void*st_method(IUnknown*p,unsigned slot){return (*(void***)p)[slot];}
#define ST_ID(a,b,c,d) ((DWORD)(a)|((DWORD)(b)<<8)|((DWORD)(c)<<16)|((DWORD)(d)<<24))
/* Next RIFF chunk in [p,p+n). Truncation is malformed data. */
static int st_chunk(const BYTE*p,DWORD n,DWORD*off,DWORD*id,const BYTE**body,DWORD*size){
 if(*off>=n)return 0;
 if(n-*off<8)ST_FAIL("script track: truncated chunk header");
 *id=*(const DWORD*)(p+*off);*size=*(const DWORD*)(p+*off+4);
 if(*size>n-*off-8)ST_FAIL("script track: chunk exceeds its parent");
 *body=p+*off+8;*off+=8+*size+(*size&1);return 1;
}
static void st_text(WCHAR*out,const BYTE*b,DWORD size,const char*what){DWORD i,chars=size/2;
 if(!chars||chars>63)ST_FAIL(what);
 for(i=0;i<chars&&((const WCHAR*)b)[i];i++)out[i]=((const WCHAR*)b)[i];
 if(i==chars)ST_FAIL(what);out[i]=0;
}
static void st_event(const BYTE*p,DWORD n,unsigned segment){
 DWORD off=0,id,size,o2,id2,s2;const BYTE*b,*b2;StEvent e;int header=0,ref=0,refguid=0,name=0;
 memset(&e,0,sizeof e);e.segment=segment;
 while(st_chunk(p,n,&off,&id,&b,&size)){
  if(id==ST_ID('s','c','r','h')){if(size!=12)ST_FAIL("script track: scrh size");
   e.flags=*(const DWORD*)b;e.logical=*(const LONG*)(b+4);e.physical=*(const LONG*)(b+8);header=1;}
  else if(id==ST_ID('L','I','S','T')&&size>=4&&*(const DWORD*)b==ST_ID('D','M','R','F')){o2=0;ref=1;
   while(st_chunk(b+4,size-4,&o2,&id2,&b2,&s2)){
    if(id2==ST_ID('r','e','f','h')){if(s2!=20||memcmp(b2,&st_cls_script,16))ST_FAIL("script track: reference is not a DirectMusic script");
     if(!(*(const DWORD*)(b2+16)&1))ST_FAIL("script track: script reference without object GUID");}
    else if(id2==ST_ID('g','u','i','d')){if(s2!=16)ST_FAIL("script track: reference GUID size");memcpy(&e.script,b2,16);refguid=1;}
    else if(id2!=ST_ID('n','a','m','e')&&id2!=ST_ID('f','i','l','e')&&id2!=ST_ID('v','e','r','s')&&id2!=ST_ID('c','a','t','g')&&id2!=ST_ID('d','a','t','e'))
     ST_FAIL("script track: unmodelled reference chunk");
   }}
  else if(id==ST_ID('s','c','r','n')){st_text(e.routine,b,size,"script track: routine name");name=1;}
  else ST_FAIL("script track: unmodelled event chunk");
 }
 if(!header||!ref||!refguid||!name)ST_FAIL("script track: incomplete event");
 if(e.flags!=ST_QUEUE)ST_FAIL("script track: unmodelled event timing (only QUEUE is modelled)");
 if(e.logical<0||e.physical<0)ST_FAIL("script track: negative event time");
 if(st_nev==ST_EVENTS)ST_FAIL("script track: event capacity");
 st_ev[st_nev++]=e;st_seg[segment].count++;
}
/* LIST scrt -> LIST scrl -> LIST scre* */
static void st_script_track(const BYTE*p,DWORD n,unsigned segment){
 DWORD off=0,id,size,o2,id2,s2;const BYTE*b,*b2;int lists=0;
 while(st_chunk(p,n,&off,&id,&b,&size)){
  if(id!=ST_ID('L','I','S','T')||size<4||*(const DWORD*)b!=ST_ID('s','c','r','l'))ST_FAIL("script track: expected scrl list");
  lists++;o2=0;
  while(st_chunk(b+4,size-4,&o2,&id2,&b2,&s2)){
   if(id2!=ST_ID('L','I','S','T')||s2<4||*(const DWORD*)b2!=ST_ID('s','c','r','e'))ST_FAIL("script track: expected scre event");
   st_event(b2+4,s2-4,segment);
  }
 }
 if(lists!=1)ST_FAIL("script track: expected one event list");
}
static void st_track(const BYTE*p,DWORD n,unsigned segment){
 DWORD off=0,id,size;const BYTE*b;GUID cls;int have=0,script=0;
 while(st_chunk(p,n,&off,&id,&b,&size)){
  if(id==ST_ID('t','r','k','h')){if(size!=32)ST_FAIL("script track: trkh size");memcpy(&cls,b,16);have=1;
   script=!memcmp(&cls,&st_cls_script_track,16);
   if(script!=(*(const DWORD*)(b+28)==ST_ID('s','c','r','t')))ST_FAIL("script track: class and data type disagree");}
  else if(have&&script&&id==ST_ID('L','I','S','T')&&size>=4&&*(const DWORD*)b==ST_ID('s','c','r','t'))st_script_track(b+4,size-4,segment);
 }
}
static void st_segment(const BYTE*p,DWORD n){
 DWORD off=0,id,size,o2,id2,s2;const BYTE*b,*b2;StSegment*s;int header=0,guid=0;
 if(st_nseg==ST_SEGMENTS)ST_FAIL("script track: segment capacity");
 s=&st_seg[st_nseg];memset(s,0,sizeof *s);s->first=st_nev;
 while(st_chunk(p,n,&off,&id,&b,&size)){
  if(id==ST_ID('s','e','g','h')){if(size<24)ST_FAIL("script track: segh size");
   s->repeats=*(const DWORD*)b;s->length=*(const LONG*)(b+4);s->play_start=*(const LONG*)(b+8);
   s->loop_start=*(const LONG*)(b+12);s->loop_end=*(const LONG*)(b+16);header=1;}
  else if(id==ST_ID('g','u','i','d')){if(size!=16)ST_FAIL("script track: segment GUID size");memcpy(&s->guid,b,16);guid=1;}
  else if(id==ST_ID('L','I','S','T')&&size>=4&&*(const DWORD*)b==ST_ID('U','N','F','O')){o2=0;
   while(st_chunk(b+4,size-4,&o2,&id2,&b2,&s2))if(id2==ST_ID('U','N','A','M'))st_text(s->name,b2,s2,"script track: segment name");}
  else if(id==ST_ID('L','I','S','T')&&size>=4&&*(const DWORD*)b==ST_ID('t','r','k','l')){o2=0;
   while(st_chunk(b+4,size-4,&o2,&id2,&b2,&s2))
    if(id2==ST_ID('R','I','F','F')&&s2>=4&&*(const DWORD*)b2==ST_ID('D','M','T','K'))st_track(b2+4,s2-4,st_nseg);}
 }
 if(!header||!guid)ST_FAIL("script track: segment without header or GUID");
 st_nseg++;
}
static void st_walk(const BYTE*p,DWORD n,unsigned depth){
 DWORD off=0,id,size;const BYTE*b;
 if(depth>16)ST_FAIL("script track: container nesting");
 while(st_chunk(p,n,&off,&id,&b,&size))
  if((id==ST_ID('R','I','F','F')||id==ST_ID('L','I','S','T'))&&size>=4){
   if(id==ST_ID('R','I','F','F')&&*(const DWORD*)b==ST_ID('D','M','S','G'))st_segment(b+4,size-4);
   else st_walk(b+4,size-4,depth+1);
  }
}
/* Parses the same container file the native loader opened. */
static void st_load(const WCHAR*path){
 HANDLE f=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);DWORD n,got;BYTE*d;unsigned i;
 if(f==INVALID_HANDLE_VALUE)ST_FAIL("script track: cannot open the loaded container");
 n=GetFileSize(f,NULL);if(n<12||n>64u*1024*1024)ST_FAIL("script track: container size");
 d=(BYTE*)HeapAlloc(GetProcessHeap(),0,n);if(!d)ST_FAIL("script track: memory");
 if(!ReadFile(f,d,n,&got,NULL)||got!=n)ST_FAIL("script track: container read");CloseHandle(f);
 if(*(DWORD*)d!=ST_ID('R','I','F','F')||*(DWORD*)(d+8)!=ST_ID('D','M','C','N'))ST_FAIL("script track: not a DirectMusic container");
 st_nseg=st_nev=0;st_walk(d,n,0);HeapFree(GetProcessHeap(),0,d);
 ST_LOG("script-track fallback: %u segments, %u events parsed\n",st_nseg,st_nev);
 for(i=0;i<st_nev;i++)ST_LOG("  event %u: segment %ls flags %lu logical %ld physical %ld routine %ls\n",
  i,st_seg[st_ev[i].segment].name,st_ev[i].flags,st_ev[i].logical,st_ev[i].physical,st_ev[i].routine);
}
typedef HRESULT(WINAPI*StGetObject)(IUnknown*,void*,REFIID,void**);
static IUnknown*st_identity(IUnknown*p){IUnknown*u=NULL;if(FAILED(IUnknown_QueryInterface(p,&IID_IUnknown,(void**)&u))||!u)ST_FAIL("script track: identity query");IUnknown_Release(u);return u;}
static IUnknown*st_get(IUnknown*loader,const GUID*object,const GUID*cls,const GUID*iid){
 BYTE desc[848]={0};IUnknown*p=NULL;
 *(DWORD*)desc=848;*(DWORD*)(desc+4)=3;memcpy(desc+8,object,16);memcpy(desc+24,cls,16); /* OBJECT|CLASS */
 return SUCCEEDED(((StGetObject)st_method(loader,3))(loader,desc,iid,(void**)&p))?p:NULL;
}
/* Binds parsed segments to the loader's cached native segments and switches
 * their native script tracks off (single executor). Native timing values win. */
static void st_bind(IUnknown*loader){unsigned i;
 st_loader=loader;
 for(i=0;i<st_nseg;i++){StSegment*s=&st_seg[i];LONG len=0,l0=0,l1=0;DWORD rep=0;HRESULT h=S_OK;
  s->segment=st_get(loader,&s->guid,&st_cls_segment,&st_iid_segment8);
  if(!s->segment)ST_FAIL("script track: container segment not in the loader");
  s->identity=st_identity(s->segment);
  ((HRESULT(WINAPI*)(IUnknown*,LONG*))st_method(s->segment,3))(s->segment,&len);
  ((HRESULT(WINAPI*)(IUnknown*,DWORD*))st_method(s->segment,5))(s->segment,&rep);
  ((HRESULT(WINAPI*)(IUnknown*,LONG*,LONG*))st_method(s->segment,24))(s->segment,&l0,&l1);
  if(len!=s->length||rep!=s->repeats||l0!=s->loop_start||l1!=s->loop_end)
   ST_LOG("script-track fallback: %ls native length %ld repeats %lu loop %ld-%ld differ from data; native used\n",s->name,len,rep,l0,l1);
  s->length=len;s->repeats=rep;s->loop_start=l0;s->loop_end=l1;
  if(s->count)h=((HRESULT(WINAPI*)(IUnknown*,REFGUID,DWORD,DWORD,DWORD,DWORD))st_method(s->segment,26))
   (s->segment,&st_cls_script_track,0xffffffff,0,0,ST_PLAY_ENABLED);
  ST_LOG("script-track fallback: bound %ls (%u events), native script track disabled %08lx\n",s->name,s->count,(unsigned long)h);
  if(FAILED(h))ST_FAIL("script track: cannot disable native script track");
 }
 st_bound=1;
}
/* Music time of occurrence k of event time t for the tracked state, or 0 with
 * *none set. Pass 0 plays [start point, loop end), each repeat [l0, l1), then
 * the tail [l1, length) for finite repeats (DirectMusic segment looping). */
static LONG st_occurrence(LONG t,unsigned k,int*none){
 int first=st_point<=t&&t<st_l1,loop=st_l0<=t&&t<st_l1,infinite=st_repeats==0xffffffff;unsigned j;
 *none=0;
 if(!st_repeats){if(!k&&st_point<=t&&t<st_len)return st_start+(t-st_point);*none=1;return 0;}
 if(k<(unsigned)first)return st_start+(t-st_point);
 j=k-first;
 if(loop&&(infinite||j<st_repeats))return st_start+(st_l1-st_point)+(LONG)j*(st_l1-st_l0)+(t-st_l0);
 if(!loop&&!infinite&&t>=st_l1&&t<st_len&&j==0)return st_start+(st_l1-st_point)+(LONG)st_repeats*(st_l1-st_l0)+(t-st_l1);
 *none=1;return 0;
}
/* Object GUID of a DirectMusic object (IDirectMusicObject::GetDescriptor). */
static const GUID st_iid_object={0xd2ac28b5,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static int st_object_guid(IUnknown*p,GUID*out){IUnknown*o=NULL;BYTE desc[848]={0};HRESULT h;
 if(FAILED(IUnknown_QueryInterface(p,&st_iid_object,(void**)&o))||!o)return 0;
 *(DWORD*)desc=848;h=((HRESULT(WINAPI*)(IUnknown*,void*))st_method(o,3))(o,desc);IUnknown_Release(o);
 if(FAILED(h)||!(*(DWORD*)(desc+4)&1))return 0;memcpy(out,desc+8,16);return 1;
}
static void st_dispatch(const StEvent*e,unsigned k,LONG at,LONG queue){HRESULT h;
 if(!st_script){
  /* The event's reference (object GUID) must name the script the game initialized.
   * The game releases loader cache entries, so the loader cannot be asked. */
  st_script=st_game_script(&e->script);
  if(!st_script)ST_FAIL("script track: event references a script the game has not obtained");
 }
 h=((HRESULT(WINAPI*)(IUnknown*,WCHAR*,void*))st_method(st_script,4))(st_script,(WCHAR*)e->routine,NULL);
 st_dispatches++;
 ST_LOG("script-track dispatch %u: %ls pass %u event mt %ld (segment time %ld) at queue mt %ld late %ld -> %ls %08lx\n",
  st_dispatches,st_seg[e->segment].name,k,at,e->physical,queue,queue-at,e->routine,(unsigned long)h);
}
/* Dispatches the tracked state's occurrences up to limit (inclusive). */
static void st_run(LONG limit,LONG queue){unsigned i;int none;LONG at;
 if(st_row<0)return;
 for(i=st_seg[st_row].first;i<st_seg[st_row].first+st_seg[st_row].count;i++)
  for(;;){at=st_occurrence(st_ev[i].physical,st_next[i],&none);if(none||at>limit)break;st_dispatch(&st_ev[i],st_next[i]++,at,queue);}
}
typedef HRESULT(WINAPI*StQueueTime)(IUnknown*,LONGLONG*);
typedef HRESULT(WINAPI*StToMusic)(IUnknown*,LONGLONG,LONG*);
typedef HRESULT(WINAPI*StStateAt)(IUnknown*,IUnknown**,LONG);
/* Called on the script's STA between requests. */
static void st_tick(IUnknown*perf){LONGLONG rt;LONG qt;IUnknown*state=NULL,*segment=NULL,*id;unsigned i;
 if(!st_bound)return;
 if(FAILED(((StQueueTime)st_method(perf,36))(perf,&rt))||FAILED(((StToMusic)st_method(perf,13))(perf,rt,&qt)))return;
 if(FAILED(((StStateAt)st_method(perf,6))(perf,&state,qt)))state=NULL;
 if(state&&state==st_state){IUnknown_Release(state);st_run(qt,qt);return;}
 if(!state&&!st_state)return;
 /* Transition. Finish the old state's occurrences before the new state starts. */
 if(state){LONG start=0;((HRESULT(WINAPI*)(IUnknown*,LONG*))st_method(state,5))(state,&start);st_run(start-1<qt?start-1:qt,qt);}
 else st_run(qt,qt);
 if(st_state)IUnknown_Release(st_state);
 st_state=state;st_row=-1;
 if(!state){ST_LOG("script-track fallback: no primary segment at queue mt %ld\n",qt);return;}
 ((HRESULT(WINAPI*)(IUnknown*,IUnknown**))st_method(state,4))(state,&segment);
 ((HRESULT(WINAPI*)(IUnknown*,LONG*))st_method(state,5))(state,&st_start);
 ((HRESULT(WINAPI*)(IUnknown*,LONG*))st_method(state,7))(state,&st_point);
 ((HRESULT(WINAPI*)(IUnknown*,DWORD*))st_method(state,3))(state,&st_repeats);
 id=segment?st_identity(segment):NULL;
 for(i=0;i<st_nseg;i++)if(st_seg[i].identity==id)st_row=(int)i;
 if(segment)IUnknown_Release(segment);
 if(st_row<0){ST_LOG("script-track fallback: queue mt %ld enters a segment outside the container (no events)\n",qt);return;}
 {StSegment*s=&st_seg[st_row];st_len=s->length;st_l0=s->loop_start;st_l1=s->loop_end;
  if(!st_l1){st_l0=0;st_l1=st_len;} /* no loop points: the whole segment loops */
  if(st_l1<=st_l0||st_l1>st_len)ST_FAIL("script track: unmodelled loop points");
  for(i=s->first;i<s->first+s->count;i++)st_next[i]=0;
  ST_LOG("script-track fallback: segment %ls starts mt %ld (start point %ld, repeats %ld, loop %ld-%ld) seen at queue mt %ld\n",
   s->name,st_start,st_point,(long)st_repeats,st_l0,st_l1,qt);}
 st_run(qt,qt);
}
#endif
