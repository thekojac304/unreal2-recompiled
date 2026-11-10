"""Optional evidence-only adapter. No launcher, runtime edit, or continue operation.

For a separately prepared observer, call install(capture, fresh_session_directory)
after construction and before run(). The original consumed launcher is untouched.
"""
import json
import time
from pathlib import Path
from types import MethodType

DIALOG_FORMAT = 'dialog callback message 0x%x unsupported (wp=%llx lp=%llx)'

def capture_cstring(capture, address, limit=4096):
    """Copy bytes while the debug event is pending, never after termination."""
    data=bytearray()
    for offset in range(limit):
        value=capture.mem(address+offset,1)
        if value==b'\0':
            return dict(address=address,raw_hex=data.hex(),terminated=True,
                utf8_display=bytes(data).decode('utf-8',errors='backslashreplace'))
        data.extend(value)
    return dict(address=address,raw_hex=data.hex(),terminated=False,
        utf8_display=bytes(data).decode('utf-8',errors='backslashreplace'),limit=limit)


def fatal_record(capture, ctx, tid):
    """Read MS x64 varargs directly while still at xrt_fatal's first instruction."""
    rsp = ctx.get('rsp')
    result = dict(thread=tid, host=ctx.snapshot(), code=ctx.get('rdx') & 0xffffffff,
                  format=capture.cstring(ctx.get('r8')), cpu=None,
                  raw_integer_arguments=[ctx.get('r9')], host_stack_address=rsp,
                  diagnostic_read_errors=[], runtime_fatal_body_executed=False)
    try:
        result['host_stack_64_bytes'] = capture.mem(rsp, 64).hex()
        result['native_caller_return'] = capture.u64(rsp)
        result['raw_integer_arguments'] += [capture.u64(rsp+40), capture.u64(rsp+48)]
    except Exception as error:
        result['diagnostic_read_errors'].append('host stack: ' + repr(error))
    p = ctx.get('rcx')
    if p:
        try:
            result['cpu'] = capture.cpu_state(p)
            # A startup fatal can precede CreateDevice, when capture.cpu is None.
            guest_base = capture.u64(capture.sym('xrt_g'))
            esp = result['cpu']['registers']['esp']
            count = 40
            if result['cpu'].get('fs_base'):
                high, low = capture.words(guest_base + result['cpu']['fs_base'] + 4, 2)
                assert low <= esp < high, ('guest stack outside TEB bounds', esp, low, high)
                count = min(count, (high - esp) // 4)
                result['guest_stack_bounds'] = dict(low=low, high=high, esp=esp,
                    requested_words=40, captured_words=count, bounded_at_stack_top=count<40)
            result['guest_stack'] = capture.words(guest_base + esp, count)
        except Exception as error:
            result['diagnostic_read_errors'].append('guest CPU/stack: ' + repr(error))
    if result['format'] == DIALOG_FORMAT and len(result['raw_integer_arguments']) == 3:
        msg, wp, lp = result['raw_integer_arguments']
        result['decoded_arguments'] = dict(message=msg & 0xffffffff, wp=wp, lp=lp)
        result['formatted_message'] = 'dialog callback message 0x%x unsupported (wp=%x lp=%x)' % (msg & 0xffffffff, wp, lp)
    elif result['format'] == 'WM_GETOBJECT: unmeasured dialog/arguments (wp=%llx lp=%llx)' and len(result['raw_integer_arguments']) >= 2:
        wp, lp = result['raw_integer_arguments'][:2]
        result['decoded_arguments'] = dict(message=61, wp=wp, lp=lp)
        result['formatted_message'] = 'WM_GETOBJECT: unmeasured dialog/arguments (wp=%x lp=%x)' % (wp, lp)
    elif result['format'] == '%s':
        # Treat the copied string as data, even if it contains percent signs.
        # Do not invent a value when the pointer is unreadable or unterminated.
        try:
            value=capture_cstring(capture,result['raw_integer_arguments'][0])
            result['string_arguments']=[value]
            if value['terminated']:result['formatted_message']=value['utf8_display']
            else:result['diagnostic_read_errors'].append('string argument exceeds 4096-byte capture bound')
        except Exception as error:
            result['diagnostic_read_errors'].append('string argument: '+repr(error))
    return result


def install(capture, out):
    """Bind logs to this instance, and enrich fatal capture without resuming it."""
    assert capture.created == 0 and not capture.rows, 'install before execution'
    assert not getattr(capture, '_fatal_evidence_installed', False)
    out = Path(out)
    assert out.is_dir(), 'caller must supply an isolated, already-created session'
    target = out / 'debug-observations.jsonl'
    with target.open('x', encoding='utf-8'):
        pass
    original_hit = capture.hit

    def log(self, kind, **values):
        row = dict(index=len(self.rows)+1, kind=kind, monotonic=time.monotonic(), output_directory=str(out.resolve()), **values)
        # Write first; a write error must stop observation before any continue.
        with target.open('a', encoding='utf-8') as f:
            f.write(json.dumps(row) + '\n')
        self.rows.append(row)

    def hit(self, tag, ctx, tid):
        if tag != 'fatal_entry':
            return original_hit(tag, ctx, tid)
        row = fatal_record(self, ctx, tid)
        self.log('fatal_entry', **row)
        self.snapshot_events()
        raise RuntimeError('fatal before required stop; no continuation: ' + row.get('formatted_message', row['format']))

    capture.log = MethodType(log, capture)
    capture.hit = MethodType(hit, capture)
    capture._fatal_evidence_installed = True
    capture._fatal_evidence_directory = str(out.resolve())
    return capture
