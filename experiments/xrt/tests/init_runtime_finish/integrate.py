"""Deterministic isolated instrumentation, with explicit unhandled site inventory."""
import re, shutil, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def masked(s):
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda m: ''.join('\n' if c=='\n' else ' ' for c in m[0]),s,flags=re.S)
def matching(s,start):
    depth=0
    for i in range(start,len(s)):
        if s[i]=='(':depth+=1
        elif s[i]==')':
            depth-=1
            if not depth:return i
    raise ValueError('unbalanced')
def stage():
    O.mkdir()
    roots=[BASELINE,PRIOR,W/'out/recovery/integrated-candidate-20261030-01',W/'out/recovery/init-monitoring-20261030-01',
           W/'experiments/xrt/runtime',W/'tools/xrt/supervisor',W/'experiments/xrt/gen']
    state=[W/'out/desktop-supervisor'/n for n in ('ledger.jsonl','status.json','HALTED.json','STOP','qualification.json')]
    save(O/'preservation.json',dict(trees={str(p):core.tree(p) for p in roots},
        state={str(p):core.sha(p) if p.exists() else None for p in state},protected=A.verify()))
    shutil.copytree(PRIOR/'runtime',RT)
    print('Staged isolated runtime; protected evidence pinned',flush=True)

def integrate():
    # Reproducible from the immutable prior source, never mutate prior artifacts.
    for p in (PRIOR/'runtime').iterdir():
        if p.is_file():shutil.copy2(p,RT/p.name)
    for n in ('monitor.c','monitor.h','monitor.asm'):shutil.copy2(H/n,RT/n)
    p=RT/'xrt_internal.h';s=p.read_text();s=s.replace('#include "xrt.h"','#include "xrt.h"\n#include "monitor.h"');p.write_text(s)
    p=RT/'xrt_loader.c';s=p.read_text()
    anchor='            if (stubs[i].export_owner[0]'
    s=s.replace(anchor,'            xm_scope(c,XM_BEGIN,XM_ADAPTER,stubs[i].name,0);\n'+anchor)
    s=s.replace('            stubs[i].fn(c);','            stubs[i].fn(c);\n            xm_scope(c,XM_END,XM_ADAPTER,stubs[i].name,c->r[EAX]);')
    anchor='    uint32_t esp0 = c->r[ESP];'
    start=s.index('uint32_t xrt_call_guest(');end=s.index('/* Calls made by',start)
    t=s[start:end].replace(anchor,'    xm_scope(c,XM_BEGIN,XM_CALLBACK,"xrt_call_guest",va);\n'+anchor)
    t=t.replace('    return c->r[EAX];','    xm_scope(c,XM_END,XM_CALLBACK,"xrt_call_guest",c->r[EAX]);\n    return c->r[EAX];')
    s=s[:start]+t+s[end:];p.write_text(s)
    p=RT/'xrt_diag.c';s=p.read_text().replace('    va_list ap;\n    char msg[1024];','    xm_scope(c,XM_FATAL,0,fmt,(unsigned)code);\n    va_list ap;\n    char msg[1024];');p.write_text(s)
    p=RT/'xrt_events.c';s=p.read_text()
    s=s.replace('case 0x8f460:kind="engine_init";break;', 'case 0x8f460:xm_scope(c,XM_BEGIN,XM_ADAPTER,"UGameEngine.Init",target);kind="engine_init";break;')
    s=s.replace('        p->kind=NULL;', '        if(!strcmp(p->kind,"engine_init"))xm_scope(c,XM_END,XM_ADAPTER,"UGameEngine.Init",c->r[EAX]);\n        p->kind=NULL;')
    p.write_text(s)
    p=RT/'xrt_main.c';s=p.read_text();assert s.count('    xrt_events_init();')==1
    s=s.replace('    xrt_events_init();','    xm_init(getenv("XRT_MONITOR_STREAM"));\n    xrt_events_init();');p.write_text(s)
    # Guest callback scope is independent of renderer context, and starts before
    # GUI marshalling/assertions. All normal exits in this function are wrapped.
    p=RT/'hle_gui.c';s=p.read_text();a=s.index('static INT_PTR invoke_gui_proc(');b=s.index('\nstatic ',a+20)
    t=s[a:b];brace=t.index('{');t=t[:brace+1]+'\n    xm_scope(callback_cpu,XM_BEGIN,XM_CALLBACK,"USER32.invoke_gui_proc",msg);'+t[brace+1:]
    t,n=re.subn(r'\breturn ([^;]+);',r'{ INT_PTR xm_ret=(\1);xm_scope(callback_cpu,XM_END,XM_CALLBACK,"USER32.invoke_gui_proc",(uint64_t)xm_ret);return xm_ret;}',t)
    assert n>=1;s=s[:a]+t+s[b:];p.write_text(s)
    # Existing GUI begin/end pairs encompass native calls but lack a typed result.
    s=s.replace('    SetLastError(xrt_get_last_error(c));\n}', '    xm_scope(c,XM_BEGIN,XM_NATIVE,"USER32.begin-end.untyped",0);\n    SetLastError(xrt_get_last_error(c));\n}',1)
    s=s.replace('    xrt_set_last_error(c, GetLastError());\n}', '    xm_scope(c,XM_END,XM_NATIVE,"USER32.begin-end.untyped",0);\n    xrt_set_last_error(c, GetLastError());\n}',1);p.write_text(s)

    # Typed wrappers preserve call argument evaluation and native return type.
    # _Generic does not evaluate its controlling receiver expression. Complex
    # ternaries and casts remain at their original evaluation point.
    from wrappers import generate
    manifest=generate(RT);save(O/'typed-methods.json',manifest)
    calls=[]
    for p in sorted(RT.iterdir()):
        if p.suffix not in ('.c','.inc') or p.name.startswith('monitor'):continue
        s=p.read_text();m=masked(s);edits=[]
        pattern=r'->(?:vt|lpVtbl)->(\w+)\s*\('
        for hit in re.finditer(pattern,m):
            last=hit.start()-1
            if m[last]==')':
                depth=1;start=last
                while depth:
                    start-=1
                    if m[start]==')':depth+=1
                    elif m[start]=='(':depth-=1
            else:
                start=last
                while start>=0 and re.match(r'[\w.>\-\[\]]',m[start]):start-=1
                start+=1
            op=m.index('(',hit.end()-1);end=matching(m,op)
            line=s.count('\n',0,start)+1;method=hit[1];expr=s[start:end+1]
            first=s[op+1:end].split(',')[0].strip()
            row=dict(file=p.name,line=line,method=method,expression=expr,instrumented=False)
            if p.name not in ('hle_dmusic.inc','hle_dmusic_guest.inc'):
                # Determine CPU availability from enclosing function header.
                funcs=list(re.finditer(r'^[\w* ]+\s+(\w+)\s*\(([^;{}]*)\)\s*\{',m[:start],re.M))
                funcs=[f for f in funcs if f[1] not in ('if','while','for','switch')]
                cp='c' if funcs and re.search(r'CPU\s*\*\s*c\b',funcs[-1][2]) else 'NULL'
                edits.append((start,end+1,f'XM_{method}({cp},{s[op+1:end]})'))
                row.update(instrumented=True,host_receiver=first,cpu=cp,typed_arguments=True)
            else:row['gap']='DirectMusic needs separately typed wrappers'
            calls.append(row)
        for a,b,t in sorted(edits,reverse=True):s=s[:a]+t+s[b:]
        p.write_text(s)
    p=RT/'hle_misc.c';s=p.read_text().replace('#include "hle_com.inc"','#include "monitor_com.inc"\n#include "hle_com.inc"');p.write_text(s)
    for name in ('hle_d3d8.inc','hle_d3d8_device.inc','hle_dinput.inc'):
        p=RT/name;p.write_text('#include "monitor_com.inc"\n'+p.read_text())
    # Typed resource registry: borrowed snapshots only, no extra native refs.
    p=RT/'resources.inc';s=p.read_text()
    anchor='static unsigned d8_resource_used;'
    s=s.replace(anchor,anchor+'''
static void xm_d8_resource(CPU*c,D8Resource*r,const char*event) {
 xm_resource(c,100+r->kind,r->guest,(unsigned)(r-d8_resources)+1,
   (uint64_t)(uintptr_t)r->host,r->refs,r->bindings,event);
 /* Registry-owned scalars; locked/native pointers remain opaque. */
 {XmValue v[8]={{XM_U32,4,r->staging},{XM_U32,4,r->bytes},{XM_U32,4,r->rows},
 {XM_U32,4,r->rowbytes},{XM_U32,4,r->level},{XM_U32,4,r->flags},
 {XM_I32,4,(uint32_t)r->pitch},{XM_OPAQUE,8,(uint64_t)(uintptr_t)r->locked}};
 xm_values(c,"resource.map",8,v);}
}
''')
    s=s.replace('r->refs++;return r->guest;','r->refs++;xm_d8_resource(c,r,"reference-acquired");return r->guest;')
    s=s.replace(' return r->guest;\n}', ' xm_d8_resource(c,r,"created");return r->guest;\n}',1)
    s=s.replace('static void d8_resource_retire(D8Resource*r) {','static void d8_resource_retire(D8Resource*r) {\n xm_d8_resource(NULL,r,"retire-before");')
    s=s.replace('r->shadow=r->valid=NULL;}','r->shadow=r->valid=NULL;xm_d8_resource(NULL,r,"destroyed");}')
    s=s.replace('static void d8_resource_bind(D8Resource**binding,D8Resource*r) {','static void d8_resource_bind(D8Resource**binding,D8Resource*r) {\n if(r)xm_d8_resource(NULL,r,"bind-before");if(*binding)xm_d8_resource(NULL,*binding,"unbind-before");')
    s=s.replace('d8_resource_retire(old);}', 'd8_resource_retire(old);xm_d8_resource(NULL,old,"unbound");}if(r)xm_d8_resource(NULL,r,"bound");')
    s=s.replace('static void d8_resource_drop(D8Resource*r) {','static void d8_resource_drop(D8Resource*r) {\n xm_d8_resource(NULL,r,"release-before");')
    s=s.replace('if(!--r->refs){','if(!--r->refs){').replace('d8_device_dead(&d8_device);}\n}', 'd8_device_dead(&d8_device);}\n xm_d8_resource(NULL,r,"released");\n}')
    s=s.replace('r->refs++;d8_semantic_return','r->refs++;xm_d8_resource(c,r,"addref");d8_semantic_return')
    p.write_text(s)
    p=RT/'resource_storage.inc';s=p.read_text()
    # Exact end points of map setup/invalidation, without copying texture contents.
    s=s.replace('wr32(out,r->staging);','wr32(out,r->staging);xm_d8_resource(c,r,"mapped");')
    s=s.replace('r->staging=0;r->locked=NULL;d8_locks=0;', 'r->staging=0;r->locked=NULL;d8_locks=0;xm_d8_resource(c,r,"unlocked");')
    s=s.replace('r->bytes=(unsigned)size;','r->bytes=(unsigned)size;xm_d8_resource(c,r,"mapped");')
    p.write_text(s)
    # Make validated receiver reads produce typed identity before native access.
    replacements=[('hle_d3d8.inc','return &d8_objects[i];','{xm_resource(c,1,p,i+1,(uint64_t)(uintptr_t)d8_objects[i].host,d8_objects[i].refs,0,"receiver");return &d8_objects[i];}'),
      ('hle_d3d8_device.inc','return &d8_device;','{xm_resource(c,2,p,1,(uint64_t)(uintptr_t)d8_device.host,d8_device.refs,0,"receiver");return &d8_device;}'),
      ('hle_dinput.inc','return &di_objects[i];','{xm_resource(c,3,p,i+1,(uint64_t)(uintptr_t)di_objects[i].input,di_objects[i].refs,0,"receiver");return &di_objects[i];}'),
      ('hle_dinput.inc','return &di_devices[i];','{xm_resource(c,4,p,i+1,(uint64_t)(uintptr_t)di_devices[i].input,di_devices[i].refs,0,"receiver");return &di_devices[i];}'),
      ('resources.inc','   return r;','   xm_d8_resource(c,r,"receiver");return r;')]
    for name,a,b in replacements:
        p=RT/name;s=p.read_text();assert a in s,(name,a);p.write_text(s.replace(a,b))
    # Factories are typed free functions, not COM-vtable entries.
    p=RT/'hle_d3d8.inc';s=p.read_text()
    s=s.replace('host=fn(ARG(0));', 'xm_native(c,XM_BEGIN,"D3D8.Direct3DCreate8",0,0);{XmValue v={XM_U32,4,ARG(0)};xm_values(c,"factory.sdk",1,&v);}host=fn(ARG(0));xm_native(c,XM_END,"D3D8.Direct3DCreate8",0,(uint64_t)(uintptr_t)host);')
    s=s.replace('wr32(o->guest,d8_vtable);return o;', 'wr32(o->guest,d8_vtable);xm_resource(c,1,o->guest,(unsigned)(o-d8_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,0,"created");return o;')
    p.write_text(s)
    p=RT/'hle_d3d8_device.inc';s=p.read_text()
    s=s.replace('o->host=host;o->refs=1;p->children++;','o->host=host;o->refs=1;p->children++;xm_resource(c,2,o->guest,1,(uint64_t)(uintptr_t)o->host,o->refs,0,"created");')
    p.write_text(s)
    p=RT/'hle_dinput.inc';s=p.read_text()
    s=s.replace('hr=fn(instance,version,&iid,&input,NULL);','''xm_native(c,XM_BEGIN,"DINPUT8.DirectInput8Create",0,0);
    {XmValue v[3]={{XM_OPAQUE,8,(uint64_t)(uintptr_t)instance},{XM_U32,4,version},{XM_GUEST_ADDRESS,4,owner}};
     xm_values(c,"dinput.factory.inputs",3,v);xm_blob(c,"dinput.factory.iid",&iid,16);}
    hr=fn(instance,version,&iid,&input,NULL);xm_blob(c,"dinput.factory.output-address",&input,sizeof input);
    xm_native(c,XM_END,"DINPUT8.DirectInput8Create",0,(uint32_t)hr);''')
    s=s.replace('wr32(o->guest,did_vtable);return o;','wr32(o->guest,did_vtable);xm_resource(c,4,o->guest,(unsigned)(o-di_devices)+1,(uint64_t)(uintptr_t)o->input,o->refs,0,"created");return o;')
    s=s.replace('    wr32(o->guest,di_vtable);','    wr32(o->guest,di_vtable);xm_resource(c,3,o->guest,(unsigned)(o-di_objects)+1,(uint64_t)(uintptr_t)o->input,o->refs,0,"created");')
    s=s.replace('static void di_result(const char*method,DiObject*o,HRESULT hr) {','static void di_result(const char*method,DiObject*o,HRESULT hr) {\n xm_resource(NULL,3,o->guest,(unsigned)(o-di_objects)+1,(uint64_t)(uintptr_t)o->input,o->refs,0,method);')
    s=s.replace('static void did_result(const char*method,DiDevice*o,HRESULT hr) {','static void did_result(const char*method,DiDevice*o,HRESULT hr) {\n xm_resource(NULL,4,o->guest,(unsigned)(o-di_devices)+1,(uint64_t)(uintptr_t)o->input,o->refs,0,method);')
    s=s.replace('hr=XM_SetProperty(c,o->input,(const GUID*)(uintptr_t)property,&value.diph);','xm_blob(c,"DID.SetProperty.DIPROPDWORD",&value,sizeof value);hr=XM_SetProperty(c,o->input,(const GUID*)(uintptr_t)property,&value.diph);')
    p.write_text(s)
    p=RT/'dinput_lifecycle.inc';s=p.read_text()
    anchor='    did_lifecycle_active=0;xrt_gui_callback_leave(previous);'
    s=s.replace(anchor,anchor+'\n    xm_resource(c,4,o->guest,(unsigned)(o-di_devices)+1,(uint64_t)(uintptr_t)o->input,o->refs,0,"lifecycle-return");\n    {XmValue v[2]={{XM_GUEST_ADDRESS,4,o->window},{XM_U32,4,o->cooperative_flags}};xm_values(c,"DID.window-association",2,v);}')
    p.write_text(s)
    save(O/'native-sites.json',dict(calls=calls,instrumented=sum(r['instrumented'] for r in calls),
        total=len(calls),complete=False,untyped_imports=True,source=core.tree(RT)))
    print('Native COM statements',sum(r['instrumented'] for r in calls),'/',len(calls),'(typed coverage remains explicit)',flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
