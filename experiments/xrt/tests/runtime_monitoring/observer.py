"""Read-only stopped-stream collector. No launcher or policy activation exists."""
import os,ctypes as C,zlib,json
from pathlib import Path
from reader import Record,decode,require

def collect_stopped(capture,stream,symbols,out):
    """All debuggee threads must be suspended by the existing debug event loop.

    Preserve raw observations before validation. An interrupted/incomplete write
    cannot be accepted. This never continues any thread or changes breakpoints.
    """
    out=Path(out);out.mkdir(exist_ok=False)
    committed=int.from_bytes(capture.mem(capture.base+symbols['xm_committed']['rva'],8),'little')
    pending=capture.mem(capture.base+symbols['xm_pending']['rva'],C.sizeof(Record))
    raw=Path(stream).read_bytes()
    for name,data in [('stream.bin',raw),('pending.bin',pending),('counter.bin',committed.to_bytes(8,'little'))]:
        with (out/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    rows,valid=decode(out/'stream.bin',closed=False,committed=committed)
    r=Record.from_buffer_copy(pending)
    require(r.crc==zlib.crc32(pending[:Record.crc.offset]),'pending record partially constructed')
    require(r.sequence==committed and pending==raw[-C.sizeof(Record):],'uncommitted or unequal pending evidence')
    valid.update(stopped_counter_matched=True,pending_matched=True,complete_coverage=False)
    with (out/'result.json').open('x') as f:json.dump(valid,f,indent=2)
    return rows,valid

def require_genuine_readiness(readiness):
    # No request data can turn instrumentation integrity into coverage approval.
    require(readiness.get('complete_typed_coverage') is True,'typed coverage incomplete')
    require(readiness.get('production_monitor_qualified') is True,'production monitor not activated/qualified')
    require(readiness.get('strict_compatibility')=='PASS','retained compatibility failures unresolved')
    require(readiness.get('owner_authorization') is True,'separate genuine authorization absent')
