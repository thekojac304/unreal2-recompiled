"""SDK-declared Windows calls in initialization adapters; no ABI inference.

Preprocessing removes SAL. Each wrapper retains the SDK types and the compiler
checks the actual call. The manifest lists pointer evidence separately.
"""
import re
from pathlib import Path

FILES = ('hle_gui.c', 'hle_gui_classes.inc', 'window_transitions.inc',
         'hle_gui_diag.inc', 'hle_dmusic.inc', 'hle_dmusic_guest.inc',
         'dmusic_backend_pipe.inc')
EXCLUDED = {'GetLastError', 'SetLastError', 'VirtualQuery',
            'RtlCaptureContext', 'InterlockedIncrement'}


def generate(rt, sdk):
    from integrate import masked, matching
    declarations = {}
    for m in re.finditer(r'(\w+(?:\s*\*)?)\s+__stdcall\s+(\w+)\s*\(', sdk):
        result, name = m[1], m[2]
        end = matching(sdk, m.end()-1)
        if sdk[end+1:].lstrip()[:1] != ';':
            continue
        args = sdk[m.end():end].strip()
        if args in ('', 'void', 'VOID'):
            params = []
        else:
            params = [re.sub(r'\s+', ' ', x.strip()) for x in args.split(',')]
        declarations[name] = (result, params)
    sources = {name: (rt/name).read_text() for name in FILES}
    calls = sorted({m[1] for s in sources.values()
                    for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', masked(s))}
                   & declarations.keys() - EXCLUDED)
    support={m[1] for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', masked(sources['hle_gui_diag.inc']))} & set(calls)
    lines = ['#ifndef XM_WINDOWS_WRAPPERS', '#define XM_WINDOWS_WRAPPERS',
             '#include <windows.h>', '#include <imm.h>', '#include <objbase.h>',
             '#include "monitor.h"']
    manifest = []
    # Only fixed typed structs are copied. Numeric handles and generic message
    # LPARAMs stay opaque; message-specific translation still validates them.
    fixed = {'AdjustWindowRect': [(0, 'RECT', True, True)],
             'GetClientRect': [(1, 'RECT', False, True)],
             'GetWindowRect': [(1, 'RECT', False, True)],
             'RegisterClassExA': [(0, 'WNDCLASSEXA', True, False)],
             'RegisterClassExW': [(0, 'WNDCLASSEXW', True, False)],
             'GetClassInfoExA': [(2, 'WNDCLASSEXA', False, True)],
             'GetClassInfoExW': [(2, 'WNDCLASSEXW', False, True)],
             'CoCreateInstance': [(0, 'GUID', True, False), (3, 'GUID', True, False),
                                  (4, 'void*', False, True)]}
    for name in calls:
        body_start=len(lines)
        result, params = declarations[name]
        args, types = [], []
        for param in params:
            if param.endswith('*') or re.fullmatch(r'[A-Z][A-Z0-9_]*', param):
                args.append('unnamed');types.append(param);continue
            m = re.fullmatch(r'(.*?)\b([A-Za-z_]\w*)\s*(\[[^]]*\])?', param)
            if not m:
                raise ValueError((name, param))
            typ = m[1].strip()
            if m[3]: typ += '*'
            args.append(m[2]); types.append(typ)
        if len(args) > 12: raise ValueError((name, 'argument bound'))
        renamed = ', '.join(t+' a'+str(i) for i, t in enumerate(types)) or 'void'
        lines += [f'static {result} xm_win_{name}({renamed}) {{',
                  ' CPU*c=xm_current_cpu();XmRequest q={0};' +
                  (f'{result} ret;' if result not in ('void', 'VOID') else ''),
                  f' q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.{name}";q.count={len(args)};']
        for i, typ in enumerate(types):
            # Values are compiler-converted parameters at the wrapper boundary.
            # sizeof, rather than a guessed guest signature, fixes their width.
            lines += [f' q.values[{i}].type=XM_OPAQUE;q.values[{i}].bytes=sizeof(a{i});',
                      f' q.values[{i}].value=(uint64_t)(uintptr_t)a{i};']
        lines.append(' xm_probe(c,&q);')
        for i, typ, before, after in fixed.get(name, []):
            if before: lines.append(f' if(a{i})xm_span(c,"WIN.{name}.input{i}",a{i},sizeof({typ}));')
        lines.append((' ret=' if result not in ('void', 'VOID') else ' ')+name+'('+','.join('a'+str(i) for i in range(len(args)))+');')
        lines.append(' q.event=XM_END;q.result='+('(uint64_t)(uintptr_t)ret;' if result not in ('void', 'VOID') else '0;'))
        for i, typ, before, after in fixed.get(name, []):
            # Failed outputs can be uninitialized. Only successful results have
            # a typed output contract. Native error is preserved by xm_span.
            if after: lines.append(f' if(ret && a{i})xm_span(c,"WIN.{name}.output{i}",a{i},sizeof({typ}));' if name != 'CoCreateInstance' else f' if(SUCCEEDED(ret) && a{i})xm_span(c,"WIN.{name}.output{i}",a{i},sizeof({typ}));')
        lines.append(' xm_probe(c,&q);')
        if result not in ('void', 'VOID'): lines.append(' return ret;')
        lines.append('}')
        if name in support:
            lines += [line.replace('xm_win_'+name, 'xm_support_'+name)
                      .replace('q.domain=XM_NATIVE', 'q.domain=XM_SUPPORT')
                      .replace('"WIN.'+name, '"PROBE.'+name)
                      for line in lines[body_start:]]
        manifest.append(dict(name=name, result=result, parameters=types, fixed_spans=fixed.get(name, [])))
    lines.append('#endif')
    (rt/'monitor_windows.inc').write_text('\n'.join(lines)+'\n')
    sites = []
    for file, s in sources.items():
        mask = masked(s)
        edits = []
        for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', mask):
            if m[1] in calls:
                is_support=file=='hle_gui_diag.inc'
                edits.append((m.start(1), m.end(1), ('xm_support_' if is_support else 'xm_win_')+m[1]))
                sites.append(dict(file=file, line=s.count('\n', 0, m.start())+1, name=m[1],domain='probe-support' if is_support else 'native'))
        for a, b, t in reversed(edits): s = s[:a]+t+s[b:]
        (rt/file).write_text(s)
    for file in ('hle_gui.c', 'hle_misc.c'):
        p=rt/file;s=p.read_text();s=s.replace('#include "xrt_internal.h"', '#include "xrt_internal.h"\n#include "monitor_windows.inc"', 1);p.write_text(s)
    return dict(methods=manifest, sites=sites, excluded_support_calls=sorted(EXCLUDED),
                complete_pointer_payloads=False)
