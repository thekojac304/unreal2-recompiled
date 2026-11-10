"""Reproduce initialization monitoring additions in the isolated runtime."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def edit(name, old, new, count=1):
    p=RT/name;s=p.read_text();assert s.count(old)==count,(name,old,s.count(old));p.write_text(s.replace(old,new))


def main():
    from integrate import integrate
    integrate()
    import shutil
    shutil.copy2(H/'monitor_crc.inc',RT/'monitor_crc.inc')
    # Replace misleading outer begin/end pseudo-native scopes with real calls.
    edit('hle_gui.c', '    xm_scope(c,XM_BEGIN,XM_NATIVE,"USER32.begin-end.untyped",0);\n', '')
    edit('hle_gui.c', '    xm_scope(c,XM_END,XM_NATIVE,"USER32.begin-end.untyped",0);\n', '')
    # DmLoader8 is deliberately declared locally: only its measured IUnknown
    # prefix is callable. A method is identified by interface AND slot.
    dm=[];lines=[]
    for result,name,args,slot in [('HRESULT','QueryInterface',['DmLoader8*','REFIID','void**'],0),
                                  ('ULONG','AddRef',['DmLoader8*'],1),('ULONG','Release',['DmLoader8*'],2)]:
        label='DmLoader8.'+name
        lines += [f'typedef char xm_dm_slot_{name}[offsetof(DmLoader8Vtbl,{name})=={slot}*sizeof(void*)?1:-1];',
                  f'static {result} xm_dm_{name}(CPU*c,'+','.join(t+' a'+str(i) for i,t in enumerate(args))+'){',
                  f' XmRequest q={{0}};{result} ret;q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="{label}";',
                  f' q.slot={slot};q.interface_id=5;q.host=(uint64_t)(uintptr_t)a0;q.count={len(args)};']
        for i,t in enumerate(args):
            lines += [f' q.values[{i}].type=XM_OPAQUE;q.values[{i}].bytes=sizeof(a{i});q.values[{i}].value=(uint64_t)(uintptr_t)a{i};']
        lines += [' xm_probe(c,&q);']
        if slot==0:lines+=[' if(a1)xm_blob(c,"DmLoader8.QueryInterface.iid",a1,16);']
        lines += [f' ret=a0->lpVtbl->{name}('+','.join('a'+str(i) for i in range(len(args)))+');']
        if slot==0:lines+=[' if(a2)xm_blob(c,"DmLoader8.QueryInterface.output",a2,sizeof *a2);']
        lines += [' q.event=XM_END;q.result=(uint32_t)ret;xm_probe(c,&q);return ret;}']
        dm.append(dict(interface='DmLoader8',interface_id=5,method=name,slot=slot,args=args,result=result))
    (RT/'monitor_dmusic.inc').write_text('\n'.join(lines)+'\n')
    edit('hle_dmusic.inc','struct DmLoader8 {const DmLoader8Vtbl*lpVtbl;};',
         'struct DmLoader8 {const DmLoader8Vtbl*lpVtbl;};\n#include "monitor_dmusic.inc"')
    replacements=[('o->host->lpVtbl->Release(o->host)','xm_dm_Release(c,o->host)',2),
                  ('o->host->lpVtbl->AddRef(o->host)','xm_dm_AddRef(c,o->host)',1),
                  ('o->host->lpVtbl->QueryInterface(o->host,&iid,&q)','xm_dm_QueryInterface(c,o->host,&iid,&q)',1),
                  ('((IUnknown*)q)->lpVtbl->Release((IUnknown*)q)','XM_Release(c,(IUnknown*)q)',1),
                  ('host->lpVtbl->Release(host)','xm_dm_Release(c,host)',1),
                  ('((IUnknown*)host)->lpVtbl->Release((IUnknown*)host)','XM_Release(c,(IUnknown*)host)',1)]
    for old,new,n in replacements:edit('hle_dmusic.inc',old,new,n)
    edit('hle_dmusic.inc','o->owner=GetCurrentThreadId();o->host=host;wr32(o->guest,dm_vtable);',
         'o->owner=GetCurrentThreadId();o->host=host;wr32(o->guest,dm_vtable);\n    xm_resource(c,5,o->guest,(unsigned)(o-dm_objects)+1,(uint64_t)(uintptr_t)host,o->refs,0,"created");')
    edit('hle_dmusic.inc','dm_owner(c,dm_objects[i].owner);return &dm_objects[i];',
         'dm_owner(c,dm_objects[i].owner);xm_resource(c,5,p,i+1,(uint64_t)(uintptr_t)dm_objects[i].host,dm_objects[i].refs,0,"receiver");return &dm_objects[i];')
    edit('hle_dmusic.inc','o->refs--;if(!o->refs)o->host=NULL;',
         'o->refs--;xm_resource(c,5,o->guest,(unsigned)(o-dm_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,0,"released");if(!o->refs)o->host=NULL;')
    edit('hle_dmusic.inc','o->refs--;released++;',
         'o->refs--;xm_resource(c,5,o->guest,(unsigned)(o-dm_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,0,"cleanup-release");released++;')
    # Transport copies the fixed, pointer-free bounded frame; the existing
    # deadline, validation, child Job, native backend and errors stay intact.
    edit('dmusic_backend_pipe.inc',' if(!dmb_exchange(&dm_backend_connection,m))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s",dm_backend_connection.error);',
         ''' {int ok;xm_native(c,XM_BEGIN,"DirectMusic.IPC.exchange",0,0);
 xm_span(c,"DirectMusic.IPC.request",m,sizeof *m);
 ok=dmb_exchange(&dm_backend_connection,m);
 xm_span(c,"DirectMusic.IPC.response",m,sizeof *m);
 xm_native(c,XM_END,"DirectMusic.IPC.exchange",0,ok);
 if(!ok)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s",dm_backend_connection.error);}''')
    edit('dmusic_backend_pipe.inc',' if(!dmb_connect(&dm_backend_connection,exe,root,0,cb,c))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s",dm_backend_connection.error);',
         ''' {int ok;xm_native(c,XM_BEGIN,"DirectMusic.IPC.connect",0,0);
 xm_span(c,"DirectMusic.IPC.helper",exe,(unsigned)(wcslen(exe)+1)*2);
 xm_span(c,"DirectMusic.IPC.root",root,(unsigned)(wcslen(root)+1)*2);
 ok=dmb_connect(&dm_backend_connection,exe,root,0,cb,c);
 xm_native(c,XM_END,"DirectMusic.IPC.connect",0,ok);
 if(!ok)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"%s",dm_backend_connection.error);}''')
    edit('hle_dmusic_guest.inc',' CPU*c=(CPU*)context,nested;',
         ' CPU*c=(CPU*)context,nested;') # exact declaration anchor checked below
    edit('hle_dmusic_guest.inc',' static const GUID tool_iid=',
         ' xm_scope(c,XM_BEGIN,XM_CALLBACK,"DirectMusic.IPC.callback",q->op);\n xm_span(c,"DirectMusic.IPC.callback.request",q,sizeof *q);\n static const GUID tool_iid=')
    edit('hle_dmusic_guest.inc','r->v[1],r->v[2]);return 1;',
         'r->v[1],r->v[2]);xm_span(c,"DirectMusic.IPC.callback.response",r,sizeof *r);xm_scope(c,XM_END,XM_CALLBACK,"DirectMusic.IPC.callback",1);return 1;')
    # SDK-exact native arguments/results. Memory-validation and state-accessor
    # support calls are intentionally catalogued separately from guest natives.
    from windows_wrappers import generate
    sdk=Path(read(O/'sdk-prototypes.json')['preprocessed']) if (O/'sdk-prototypes.json').exists() else O/'sdk-prototypes/preprocess.stdout.txt'
    win=generate(RT,sdk.read_text())
    save(O/'windows-methods.json',win);save(O/'dmusic-methods.json',dm)
    # The previous inventory sampled receivers but left stale reference counts
    # after final releases. Publish actual registry state at those transitions.
    edit('hle_d3d8.inc','static void d8_result(CPU*c,const char*method,D8Object*o,uint32_t adapter,uint32_t arg,HRESULT hr) {',
         '''static void d8_result(CPU*c,const char*method,D8Object*o,uint32_t adapter,uint32_t arg,HRESULT hr) {
    if(o)xm_resource(c,1,o->guest,(unsigned)(o-d8_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,o->children+o->pending,method);''')
    edit('hle_d3d8.inc','if(!--d8_objects[i].refs)d8_objects[i].host=NULL;',
         'if(!--d8_objects[i].refs)d8_objects[i].host=NULL;xm_resource(NULL,1,d8_objects[i].guest,i+1,(uint64_t)(uintptr_t)d8_objects[i].host,d8_objects[i].refs,d8_objects[i].children,"cleanup-release");')
    edit('hle_d3d8_device.inc','    o->host=NULL;',
         '    o->host=NULL;xm_resource(NULL,2,o->guest,1,0,o->refs,o->children,"destroyed");')
    edit('hle_d3d8_device.inc','    if(!--o->parent->children && !o->parent->refs)o->parent->host=NULL;',
         '    if(!--o->parent->children && !o->parent->refs)o->parent->host=NULL;xm_resource(NULL,1,o->parent->guest,0,(uint64_t)(uintptr_t)o->parent->host,o->parent->refs,o->parent->children,"child-destroyed");')
    edit('hle_d3d8_device.inc','    if(!--o->refs && !o->children)d8_device_dead(o);',
         '    if(!--o->refs && !o->children)d8_device_dead(o);xm_resource(c,2,o->guest,1,(uint64_t)(uintptr_t)o->host,o->refs,o->children,"released");')
    edit('hle_dinput.inc','        devices++;',
         '        devices++;xm_resource(NULL,4,di_devices[i].guest,i+1,(uint64_t)(uintptr_t)di_devices[i].input,di_devices[i].refs-1,0,"cleanup-release");')
    edit('hle_dinput.inc','        count++;',
         '        count++;xm_resource(NULL,3,di_objects[i].guest,i+1,(uint64_t)(uintptr_t)di_objects[i].input,di_objects[i].refs-1,0,"cleanup-release");')
    edit('resources.inc','{XmValue v[8]=', '{XmValue v[11]=')
    edit('resources.inc','(uint64_t)(uintptr_t)r->locked}};',
         '(uint64_t)(uintptr_t)r->locked},{XM_U32,4,r->offset},{XM_U32,4,r->length},{XM_U32,4,r->format}};')
    edit('resources.inc','xm_values(c,"resource.map",8,v);','xm_values(c,"resource.map",11,v);')
    # Byte transport is explicit and bounded. A map above the monitor span
    # capacity stops before unobserved native upload; no sampling or digest-only
    # substitute is advertised as full payload coverage.
    edit('resource_storage.inc','d8_device_memory(c,out,4,1);wr32(out,r->staging);xm_d8_resource(c,r,"mapped");',
         'd8_device_memory(c,out,4,1);wr32(out,r->staging);xm_d8_resource(c,r,"mapped");xm_span(c,"resource.map.download",G2H(r->staging),r->bytes);')
    edit('resource_storage.inc','  d8_device_memory(c,out,8,1);wr32(out,(unsigned)lock.pitch);wr32(out+4,stage);',
         '  xm_span(c,"resource.map.download",G2H(stage),r->bytes);d8_device_memory(c,out,8,1);wr32(out,(unsigned)lock.pitch);wr32(out+4,stage);')
    edit('resource_storage.inc','  copy=d8_draw_copy(c,r->staging,r->bytes);',
         '  copy=d8_draw_copy(c,r->staging,r->bytes);xm_span(c,"resource.map.upload",copy,r->bytes);')
    # Resource binding location is a registry identity (kind/index), not a slot
    # guessed from a native vtable. The pointer is only compared, never read.
    edit('resources.inc',' D8Resource*old=*binding;if(r)r->bindings++;',
         ''' unsigned xm_kind=0,xm_index=0,xm_i;XmValue xm_v[4];
 for(xm_i=0;xm_i<16;xm_i++)if(binding==&d8_bound_streams[xm_i]){xm_kind=1;xm_index=xm_i;}
 for(xm_i=0;xm_i<8;xm_i++)if(binding==&d8_bound_textures[xm_i]){xm_kind=2;xm_index=xm_i;}
 if(binding==&d8_bound_indices)xm_kind=3;
 xm_v[0]=(XmValue){XM_U32,4,xm_kind};xm_v[1]=(XmValue){XM_U32,4,xm_index};
 xm_v[2]=(XmValue){XM_GUEST_ADDRESS,4,*binding?(*binding)->guest:0};
 xm_v[3]=(XmValue){XM_GUEST_ADDRESS,4,r?r->guest:0};xm_values(NULL,"resource.binding-location",4,xm_v);
 if(!xm_kind&&xm_enabled())xm_failure(22);
 D8Resource*old=*binding;if(r)r->bindings++;''')
    # Checkpoints live in the monitor, not XrtEhPad: inherited translated
    # objects retain the exact original pad ABI and strict /fp:strict lineage.
    edit('xrt_eh.c','    pad->host_calls = t->host_calls;',
         '    pad->host_calls = t->host_calls;\n    xm_mark(pad);')
    edit('xrt_eh.c','    pad->active = 0;','    pad->active = 0;\n    xm_forget(pad);')
    edit('xrt_eh.c','    k->pad.active = 0;','    k->pad.active = 0;\n    xm_forget(&k->pad);')
    edit('xrt_eh.c','    longjmp(p->jb, p->kind ? LJ_RESUME : 1);',
         '    xm_restore(c,p,1);\n    longjmp(p->jb, p->kind ? LJ_RESUME : 1);')
    edit('xrt_eh.c','                longjmp(k->pad.jb, LJ_RETHROW);',
         '                xm_restore(c,&k->pad,2);\n                longjmp(k->pad.jb, LJ_RETHROW);')
    edit('xrt_thread.c','    longjmp(t->exit_jmp, 1);',
         '    xm_unwind(c,0,3);\n    longjmp(t->exit_jmp, 1);')
    # Preserve runtime guards that forbid EH crossing an active host callback.
    # Unsafe native-callback thread exits are stopped, with fatal evidence.
    edit('xrt_thread.c','    t->exit_code = code;',
         '    if(t->host_calls>1)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ExitThread through nested native callback is unqualified");\n    t->exit_code = code;')
    p=RT/'xrt_loader.c';s=p.read_text()
    a=s.index('uint32_t xrt_call_funclet(');b=s.index('\nvoid xrt_imports_report',a)
    t=s[a:b]
    t=t.replace('    uint32_t esp0 = c->r[ESP];','    xm_scope(c,XM_BEGIN,XM_CALLBACK,"EH.funclet",va);\n    uint32_t esp0 = c->r[ESP];')
    t=t.replace('    dispatch(c, va, expected_return, "catch continuation");','    xm_scope(c,XM_BEGIN,XM_CALLBACK,"EH.continuation",va);\n    dispatch(c, va, expected_return, "catch continuation");')
    # Each function has one normal return. Aborted paths use the checkpoint.
    left,right=t.split('uint32_t xrt_call_continuation(',1)
    left=left.replace('    return c->r[EAX];','    xm_scope(c,XM_END,XM_CALLBACK,"EH.funclet",c->r[EAX]);\n    return c->r[EAX];')
    right=right.replace('    return c->r[EAX];','    xm_scope(c,XM_END,XM_CALLBACK,"EH.continuation",c->r[EAX]);\n    return c->r[EAX];')
    p.write_text(s[:a]+left+'uint32_t xrt_call_continuation('+right+s[b:])
    sites=read(O/'native-sites.json')
    for row in sites['calls']:
        if row['file']=='hle_dmusic.inc':row.update(instrumented=True,typed_arguments=True);row.pop('gap',None)
    sites.update(instrumented=sum(r['instrumented'] for r in sites['calls']),complete=False,source=core.tree(RT));save(O/'native-sites.json',sites)
    print('Initialization additions:',len(win['methods']),'Windows signatures,',len(win['sites']),'Windows sites; all',sites['instrumented'],'COM sites',flush=True)

if __name__=='__main__':main()
