"""Independent stopped debugger capture; no guest launch or continuation API."""
import ctypes as C, os, json, zlib
from pathlib import Path
from reader import Record,decode,require

def collect_stopped(capture,stream,symbols,out,*,failure_reason=0):
    # The Windows debug event suspends all debuggee threads. Raw bytes are saved
    # and fsync'd before parsing, including on failed or partial sink writes.
    out=Path(out);out.mkdir(exist_ok=False)
    def mem(name,n):return capture.mem(capture.base+symbols[name]['rva'],n)
    def preserve(name,data):
        with (out/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    counters={}
    for name,n in [('xm_committed',8),('xm_recorded',8),('xm_written',8),('xm_buffer_count',4),('xm_profile',4),('xm_failed',4)]:
        raw=mem(name,n);preserve(name+'.bin',raw);counters[name]=int.from_bytes(raw,'little')
    counters['stopped_failure_reason']=failure_reason
    pending=mem('xm_pending',C.sizeof(Record));preserve('pending.bin',pending)
    count=counters['xm_buffer_count'];require(count<=4096,'unbounded tail count')
    tail=mem('xm_buffer',count*C.sizeof(Record)) if count else b'';preserve('tail.bin',tail)
    raw=Path(stream).read_bytes() if Path(stream).exists() else b'';preserve('stream.bin',raw)
    (out/'counters.json').write_text(json.dumps(counters,indent=2))
    durable=counters['xm_committed'];recorded=counters['xm_recorded'];written=counters['xm_written'];size=C.sizeof(Record)
    require(durable<=written<=recorded,'impossible counter ordering')
    require(recorded-durable==count,'counter/tail gap at stop')
    require(len(raw)>=durable*size,'durable prefix missing')
    require(len(raw)<=recorded*size,'unaccounted bytes beyond accepted records')
    prefix=raw[:durable*size];combined=prefix+tail;preserve('recovered.bin',combined)
    # fsync of the independent copy preserves captured memory as evidence. It
    # cannot retroactively make the debuggee's unflushed records durable.
    rows,valid=decode(out/'recovered.bin',closed=False,committed=recorded,allow_failure=True)
    if durable:
        require(rows[durable-1].sequence==durable,'durable boundary sequence')
    p=Record.from_buffer_copy(pending)
    require(p.crc==zlib.crc32(pending[:Record.crc.offset]),'partially constructed pending record')
    if p.sequence==recorded:
        require(pending==combined[-size:],'pending does not match accepted tail')
    else:
        require((counters['xm_failed'] or failure_reason) and p.sequence==recorded+1,'unaccounted pending attempt')
    # Complete written-but-unflushed records must agree with memory, partial
    # WriteFile residue is retained and rejected as a complete disk stream.
    require(raw[:min(len(raw),len(combined))]==combined[:min(len(raw),len(combined))],'disk/memory disagreement')
    valid.update(recorded=recorded,written=written,durable_through=durable,
        unflushed_records=recorded-durable,independent_capture=True,
        debugger_copy_fsync=True,guest_tail_durable=False if count else True,
        failed=counters['xm_failed'] or failure_reason,complete_coverage=False)
    with (out/'result.json').open('x') as f:json.dump(valid,f,indent=2);f.flush();os.fsync(f.fileno())
    return rows,valid

def require_genuine_readiness(readiness):
    require(readiness.get('experimental_policy_review')=='APPROVED','experimental policy requires separate review')
    require(readiness.get('focused_init_qualification') is True,'focused Init gates incomplete')
    require(readiness.get('candidate_containment_qualified') is True,'candidate containment incomplete')
    require(readiness.get('owner_authorization') is True,'new bounded owner authorization absent')
