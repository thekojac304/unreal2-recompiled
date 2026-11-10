"""Compile-time typed COM wrappers. No vtable patching or generic ABI guessing."""
import re

def generate(rt):
    interfaces={};ids={'D8Interface':1,'D8Device':2,'D8Unknown':0,'D8Surface':101,'D8Texture':103,'D8Buffer':106,
                      'IDirectInput8W':3,'IDirectInputDevice8W':4,'IUnknown':0}
    for file in ('d3d8_abi.h','d3d8_device_abi.h','resource_abi.h'):
        s=(rt/file).read_text()
        for vtable,body in re.findall(r'typedef struct (\w+Vtable)\s*\{(.*?)\}\s*\w+;',s,re.S):
            typ={'D8Vtable':'D8Interface'}.get(vtable,vtable.removesuffix('Vtable'))
            if typ not in ids:continue
            common=f'HRESULT(WINAPI*QueryInterface)({typ}*,REFIID,void**);ULONG(WINAPI*AddRef)({typ}*);ULONG(WINAPI*Release)({typ}*);HRESULT(WINAPI*GetDevice)({typ}*,D8Device**)'
            body=re.sub(r'D8_COMMON\(\w+\)',lambda _:common,body)
            body=re.sub(r'D8_RESOURCE\(\w+\)',lambda _:common+f';void*private_data[3];DWORD(WINAPI*SetPriority)({typ}*,DWORD);DWORD(WINAPI*GetPriority)({typ}*);void(WINAPI*PreLoad)({typ}*);DWORD(WINAPI*GetType)({typ}*)',body)
            entries=[];slot=0
            for field in body.split(';'):
                field=field.strip()
                if not field:continue
                m=re.fullmatch(r'(\w+)\s*\(WINAPI\s*\*(\w+)\)\((.*?)\)',field,re.S)
                if m:entries.append((m[1],m[2],[x.strip() for x in m[3].split(',')],slot));slot+=1
                else:
                    n=re.search(r'\[(\d+)\]',field);assert 'void*' in field,(vtable,field)
                    slot+=int(n[1]) if n else 1
            interfaces[typ]=(vtable,'vt',entries)
    def entries(typ,more):
        return [('HRESULT','QueryInterface',[typ+'*','REFIID','void**'],0),('ULONG','AddRef',[typ+'*'],1),('ULONG','Release',[typ+'*'],2)]+more
    interfaces['IUnknown']=('IUnknownVtbl','lpVtbl',entries('IUnknown',[]))
    interfaces['IDirectInput8W']=('IDirectInput8WVtbl','lpVtbl',entries('IDirectInput8W',[
        ('HRESULT','CreateDevice',['IDirectInput8W*','REFGUID','IDirectInputDevice8W**','IUnknown*'],3)]))
    interfaces['IDirectInputDevice8W']=('IDirectInputDevice8WVtbl','lpVtbl',entries('IDirectInputDevice8W',[
        ('HRESULT','SetProperty',['IDirectInputDevice8W*','REFGUID','LPCDIPROPHEADER'],6),
        ('HRESULT','Acquire',['IDirectInputDevice8W*'],7),('HRESULT','Unacquire',['IDirectInputDevice8W*'],8),
        ('HRESULT','GetDeviceData',['IDirectInputDevice8W*','DWORD','LPDIDEVICEOBJECTDATA','LPDWORD','DWORD'],10),
        ('HRESULT','SetDataFormat',['IDirectInputDevice8W*','LPCDIDATAFORMAT'],11),
        ('HRESULT','SetCooperativeLevel',['IDirectInputDevice8W*','HWND','DWORD'],13)]))
    lines=['#ifndef XM_COM_WRAPPERS','#define XM_COM_WRAPPERS','#ifndef DIRECTINPUT_VERSION','#define DIRECTINPUT_VERSION 0x0800','#endif',
           '#include <dinput.h>','#include "d3d8_device_abi.h"','#include "monitor.h"']
    methods={};manifest=[]
    safe={'D8Caps','D8Mode','D8Present','D8Creation','D8SurfaceDesc','D8BufferDesc','D8Locked','D8Material','D8Matrix','D8Viewport','D8Gamma','RECT','D8Rect'}
    for typ,(table,vt,items) in interfaces.items():
        for result,name,args,slot in items:
            fn=f'xm_{typ}_{name}';methods.setdefault(name,[]).append((typ,fn));params=', '.join(t+' a'+str(i) for i,t in enumerate(args))
            label=typ+'.'+name
            lines += [f'typedef char xm_slot_{typ}_{name}[offsetof({table},{name})=={slot}*sizeof(void*)?1:-1];',
                      f'static {result} {fn}(CPU*c,{params}) {{',
                      ' XmRequest q={0};'+(' '+result+' ret;' if result!='void' else ''),
                      f' q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="{label}";q.slot={slot};q.interface_id={ids[typ]};q.host=(uint64_t)(uintptr_t)a0;q.count={len(args)};']
            blobs=[]
            for i,t in enumerate(args):
                pointer='*' in t or t in ('REFIID','REFGUID','LPCDIPROPHEADER','LPDIDEVICEOBJECTDATA','LPDWORD','LPCDIDATAFORMAT','HWND')
                tag='XM_OPAQUE' if pointer else ('XM_I32' if t in ('BOOL','INT','LONG') else 'XM_U32')
                lines.append(f' q.values[{i}].type={tag};q.values[{i}].bytes=sizeof(a{i});')
                if t=='float':lines.append(f' memcpy(&q.values[{i}].value,&a{i},sizeof a{i});')
                else:lines.append(f' q.values[{i}].value=(uint64_t)'+('(uintptr_t)' if pointer else '')+f'a{i};')
                base=t.replace('const ','').rstrip('*').strip()
                size=None
                if i and (t.endswith('**') or t in ('LPDWORD',)):size=f'sizeof(*a{i})'
                elif i and t in ('REFIID',):size='16'
                elif i and t.endswith('*') and base in safe:size=f'sizeof(*a{i})'
                elif t=='LPCDIDATAFORMAT':size='sizeof(DIDATAFORMAT)' # nested array explicitly remains a gap
                elif t=='LPCDIPROPHEADER':size='sizeof(DIPROPHEADER)' # property value requires its own tag
                if size:blobs.append((i,size,'const ' in t or t in ('REFIID','LPCDIDATAFORMAT','LPCDIPROPHEADER')))
            lines.append(' xm_probe(c,&q);')
            # No uninitialized output is read before native; in/out structs on
            # creation are explicitly initialized by the existing adapter.
            for i,size,isinput in blobs:
                if isinput or (typ=='D8Interface' and name=='CreateDevice'):
                    lines.append(f' if(a{i})xm_span(c,"{label}.input{i}",a{i},{size});')
            call=f'a0->{vt}->{name}('+','.join(f'a{i}' for i in range(len(args)))+')'
            lines.append((' ret=' if result!='void' else ' ')+call+';')
            lines.append(' q.event=XM_END;'+('q.result=(uint64_t)ret;' if result!='void' else 'q.result=0;'))
            # Keep output evidence inside invocation, before END and assertions.
            for i,size,isinput in blobs:
                if not isinput:lines.append(f' if(a{i})xm_span(c,"{label}.output{i}",a{i},{size});')
            lines.append(' xm_probe(c,&q);')
            if result!='void':lines.append(' return ret;')
            lines.append('}')
            manifest.append(dict(interface=typ,interface_id=ids[typ],method=name,slot=slot,args=args,result=result,
                bounded_spans=blobs,wrapper=fn))
    for method,choices in methods.items():
        lines.append(f'#define XM_{method}(cpu,self,...) _Generic((self),'+','.join(t+'*:'+fn for t,fn in choices)+')((cpu),(self),##__VA_ARGS__)')
    lines.append('#endif')
    (rt/'monitor_com.inc').write_text('\n'.join(lines)+'\n')
    return manifest
