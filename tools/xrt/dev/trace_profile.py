"""Install small, checked hooks in the isolated editable developer runtime."""
from pathlib import Path


def install(runtime):
    runtime = Path(runtime)
    append = '''    r.sequence=++serial;r.previous_crc=chain;r.crc=crc32(&r,offsetof(XmRecord,crc));
    xm_pending=r;MemoryBarrier();
    if(xm_buffer_count>=4096)xm_failure(22);
    xm_buffer[xm_buffer_count]=r;MemoryBarrier();xm_buffer_count++;
    chain=r.crc;xm_recorded=r.sequence;MemoryBarrier();'''
    def edit(name, replacements, marker):
        path = runtime / name
        text = path.read_text()
        if marker in text:
            return
        for old, new in replacements:
            if text.count(old) != 1:
                raise RuntimeError(f'trace hook needs review in {path}: {old[:80]}')
            text = text.replace(old, new)
        path.write_text(text)

    loader = runtime / 'xrt_loader.c'
    text = loader.read_text()
    if '#include "dev_calibration_trace.inc"' in text:
        text = text.replace('#include "dev_calibration_trace.inc"', '/* Routine tracing is centralized in the developer monitor. */')
        old = '''            int calibration = dev_calibration_match(site,stubs[i].name);
            int trace = !calibration || dev_calibration_begin();
            if (!calibration) dev_calibration_flush(c);
            if (trace) xm_scope(c,XM_BEGIN,XM_ADAPTER,stubs[i].name,0);'''
        if text.count(old) != 1:
            raise RuntimeError('calibration hook changed; review before replacing')
        text = text.replace(old, '            xm_scope(c,XM_BEGIN,XM_ADAPTER,stubs[i].name,0);')
        text = text.replace('            if (trace) xm_scope(c,XM_END,XM_ADAPTER,stubs[i].name,c->r[EAX]);\n            if (calibration) dev_calibration_end(c);',
                            '            xm_scope(c,XM_END,XM_ADAPTER,stubs[i].name,c->r[EAX]);')
        loader.write_text(text)
    edit('monitor.c', [
        ('/* Only xm_probe calls this.', '#include "routine_trace.inc"\n\n/* Only xm_probe calls this.'),
        ('r.version=3;', 'r.version=xm_profile?4:3;'),
        ('    if(serial>=XM_LIMIT)bad=5;', '    if(!xm_profile && serial>=XM_LIMIT)bad=5;'),
        (append, '    if(xm_profile){\n'
         '        if(xd_route(&r,bad))goto finished;\n        xd_append(&r);\n'
         '        if(xd_force_flush){drain();xd_flush();}\n'
         '    }else{\n' + append + '\n    }'),
        ('    if(q->event==XM_END||q->event==XM_ABORT){tls.depth--;',
         'finished:\n    if(q->event==XM_END||q->event==XM_ABORT){tls.depth--;'),
        ('    SetLastError(saved);\n    {XmRequest q={0};q.event=XM_OPEN;',
         '    xd_init(path);\n    SetLastError(saved);\n    {XmRequest q={0};q.event=XM_OPEN;'),
        ('q.name=xm_profile?"xrt.monitor.v3.development"', 'q.name=xm_profile?"xrt.monitor.v4.development"'),
        ('    if(!CloseHandle(sink))xm_failure(14);',
         '    if(xm_profile&&!CloseHandle(xd_sink))xm_failure(25);\n    if(!CloseHandle(sink))xm_failure(14);'),
    ], '#include "routine_trace.inc"')
    # Upgrade only the private development schema. The forensic branch is v3.
    monitor = runtime / 'monitor.c'
    text = monitor.read_text().replace('r.version=xm_profile?4:3;', 'r.version=xm_profile?5:3;')
    text = text.replace('xrt.monitor.v4.development', 'xrt.monitor.v5.development')
    text = text.replace('if(xm_profile && (!strcmp(name,"resource.map.download")',
                        'if(xm_profile && !xd_selected_name(name) && '
                        '!(tls.depth&&xd_tls.frames[tls.depth-1].selected) && (!strcmp(name,"resource.map.download")')
    if text != monitor.read_text():
        monitor.write_text(text)
