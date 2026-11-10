"""Deterministic recorder-only changes to the immutable finished runtime."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    s=(FINISHED/'runtime/monitor.c').read_text()
    s=s.replace('#include <stddef.h>', '#include <stddef.h>\n#include <stdlib.h>')
    s=s.replace('static uint32_t chain;', '''static uint32_t chain;
/* Tail contains ALL accepted records after the last successful flush. It is
 * never reused until WriteFile and FlushFileBuffers have both succeeded. */
volatile uint64_t xm_recorded, xm_written, xm_flushes;
volatile unsigned xm_buffer_count, xm_profile;
XmRecord xm_buffer[4096];
#ifdef XM_QUALIFICATION
static unsigned hold_drain, fail_flush, partial_write;
void xm_qualification_hold_drain(void){hold_drain=1;}
void xm_qualification_fail_flush(void){fail_flush=1;}
void xm_qualification_partial_write(void){partial_write=1;}
#endif
/* Called under the recorder lock, inside the state-preserving assembly probe.
 * Counters are conservative on interruption. Flush success is the Windows
 * persistence contract; storage firmware/power-loss behavior is not measured. */
static void drain(void) {
 DWORD written;unsigned bytes=xm_buffer_count*(unsigned)sizeof(XmRecord);
 if(!bytes)return;
#ifdef XM_QUALIFICATION
 if(hold_drain)return;
 if(partial_write){WriteFile(sink,xm_buffer,bytes/2,&written,NULL);xm_failure(9);}
#endif
 if(!WriteFile(sink,xm_buffer,bytes,&written,NULL)||written!=bytes)xm_failure(9);
 xm_written=xm_recorded;MemoryBarrier();
#ifdef XM_QUALIFICATION
 if(fail_flush)xm_failure(23);
#endif
 if(!FlushFileBuffers(sink))xm_failure(9);
 xm_committed=xm_recorded;xm_flushes++;MemoryBarrier();xm_buffer_count=0;
}
''')
    s=s.replace('DWORD saved=GetLastError(),written;XmRecord r;', 'DWORD saved=GetLastError();XmRecord r;')
    s=s.replace('r.version=2;', 'r.version=3;')
    a='''    if(!WriteFile(sink,&r,sizeof r,&written,NULL)||written!=sizeof r||!FlushFileBuffers(sink))xm_failure(9);
    chain=r.crc;xm_committed=r.sequence;'''
    b='''    if(xm_buffer_count>=4096)xm_failure(22);
    xm_buffer[xm_buffer_count]=r;MemoryBarrier();xm_buffer_count++;
    chain=r.crc;xm_recorded=r.sequence;MemoryBarrier();
    if(!xm_profile || xm_buffer_count>=256 || bad || q->event==XM_OPEN ||
       q->event==XM_CLOSE || q->event==XM_FATAL || q->event==XM_GAP ||
       q->event==XM_CHECKPOINT ||
       (q->event==XM_END && q->name && !strcmp(q->name,"UGameEngine.Init")))drain();'''
    assert a in s;s=s.replace(a,b)
    a='''    unsigned off;XmValue v[2]={{XM_U32,4,size},{XM_U32,4,0}};'''
    b='''    unsigned off;XmValue v[2]={{XM_U32,4,size},{XM_U32,4,0}};
    /* Only these two explicitly approved bulk evidence categories are omitted.
     * Adapter range, ownership, pitch, transfer and COM checks stay upstream.
     * No pointer is dereferenced here or forwarded to native code. */
    if(xm_profile && (!strcmp(name,"resource.map.download") || !strcmp(name,"resource.map.upload"))){
        XmRequest q={0};q.event=XM_OMITTED;q.name=name;q.result=size;
        q.count=1;q.values[0]=v[0];xm_probe(c,&q);return;
    }'''
    assert a in s;s=s.replace(a,b)
    a='''    sink=CreateFileA(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_WRITE_THROUGH,NULL);'''
    b='''    {const char*p=getenv("XRT_MONITOR_PROFILE");
     if(!p || !strcmp(p,"forensic"))xm_profile=0;
     else if(!strcmp(p,"development"))xm_profile=1;
     else xm_failure(24);}
    sink=CreateFileA(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL|(xm_profile?0:FILE_FLAG_WRITE_THROUGH),NULL);'''
    assert a in s;s=s.replace(a,b)
    s=s.replace('SetLastError(saved);xm_scope(NULL,XM_OPEN,0,"xrt.monitor.v2",0);', '''SetLastError(saved);
    {XmRequest q={0};q.event=XM_OPEN;q.name=xm_profile?"xrt.monitor.v3.development":"xrt.monitor.v3.forensic";
     q.count=4;q.values[0]=(XmValue){XM_U32,4,xm_profile};
     q.values[1]=(XmValue){XM_U32,4,4096};q.values[2]=(XmValue){XM_U32,4,xm_profile?256:1};
     q.values[3]=(XmValue){XM_U32,4,xm_profile?3:0};xm_probe(NULL,&q);}''')
    s=s.replace('"xrt.monitor.v2",0);', '"xrt.monitor.v3",0);')
    s+='''
void xm_checkpoint(CPU*c,const char*name) {
    xm_scope(c,XM_CHECKPOINT,0,name,0);
}
'''
    (H/'monitor.c').write_text(s);(RT/'monitor.c').write_text(s)
    s=(FINISHED/'runtime/monitor.h').read_text().replace('XM_ABORT=9','XM_ABORT=9, XM_CHECKPOINT=10, XM_OMITTED=11')
    s=s.replace('void xm_close(void);','''void xm_close(void);
void xm_checkpoint(CPU*,const char*name);
extern volatile uint64_t xm_recorded, xm_written, xm_flushes;
extern volatile unsigned xm_buffer_count, xm_profile;
extern XmRecord xm_buffer[4096];''')
    (H/'monitor.h').write_text(s);(RT/'monitor.h').write_text(s)
    print('Bounded recorder and explicit profiles generated')

if __name__=='__main__':main()
