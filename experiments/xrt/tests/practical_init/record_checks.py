"""Independent record semantics, including CRC-valid identity substitutions."""
import sys,uuid,ctypes as C,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import Record,decode

def main():
    out=O/('record-checks-'+str(uuid.uuid4()));out.mkdir()
    source=Path(read(O/'live.json')['root'])/'success/sandbox/trace.bin'
    rows,_=decode(source);size=C.sizeof(Record)
    index=next(i for i,r in enumerate(rows) if r.event==3 and r.domain==2 and r.host)
    results=[]
    for field in ['slot','interface_id','guest','generation','host']:
        data=bytearray(source.read_bytes());r=Record.from_buffer_copy(data[index*size:(index+1)*size]);setattr(r,field,getattr(r,field)+1)
        data[index*size:(index+1)*size]=bytes(r)
        # Repair every checksum so rejection proves semantic identity checking,
        # independently of the corruption checks in the live suite.
        chain=0
        for off in range(0,len(data),size):
            r=Record.from_buffer_copy(data[off:off+size]);r.previous_crc=chain;r.crc=zlib.crc32(bytes(r)[:Record.crc.offset]);chain=r.crc
            data[off:off+size]=bytes(r)
        p=out/(field+'.bin');p.write_bytes(data)
        try:decode(p)
        except ValueError as e:
            core.require('receiver/interface/slot changed' in str(e),'wrong semantic rejection')
            results.append(dict(field=field,rejection=str(e),sha256=core.sha(p)))
        else:raise AssertionError('CRC-valid receiver substitution accepted')
    traces=[source,Path(read(O/'resource-trace.json')['root'])/'sandbox/trace.bin',
            Path(read(O/'dinput-trace.json')['root'])/'sandbox/trace.bin',
            Path(read(O/'guest-threads.json')['root'])/'translated-run/trace.bin',
            Path(read(O/'exceptions.json')['root'])/'translated-run/trace.bin',
            Path(read(O/'windows-contracts.json')['root'])/'positive-trace.bin']
    d=Path(read(O/'dmusic.json')['root'])
    traces += [d/(name+'-translated/trace.bin') for name in ['probe_sta','probe_mta','probe_loader','probe_uninitialized','probe_cleanup','probe_worker']]
    d=Path(read(O/'ipc.json')['root']);traces += [d/(name+'/trace.bin') for name in ['probe_loader','probe_cleanup']]
    traces += [Path(read(O/'audio.json')['root'])/(name+'/trace.bin') for name in ('translated-run','translated-tool','translated-script')]
    inventory=[]
    for p in traces:
        r,valid=decode(p)
        core.require(valid['active_invocations']==0,'unpaired completed trace')
        inventory.append(dict(path=str(p),sha256=core.sha(p),integrity=valid,
            native_entries=sum(v.event==2 and v.domain==2 for v in r),native_returns=sum(v.event==3 and v.domain==2 for v in r),
            probe_support_entries=sum(v.event==2 and v.domain==5 for v in r),
            callback_entries=sum(v.event==2 and v.domain==3 for v in r),aborts=sum(v.event==9 for v in r)))
    save(O/'record-checks.json',dict(passed=True,root=str(out),runtime=core.tree(RT),record_size=size,mutations=results,completed_traces=inventory))
    print('CRC-valid receiver/interface/generation/slot substitution rejection and completed invocation inventories PASS',flush=True)

if __name__=='__main__':main()
