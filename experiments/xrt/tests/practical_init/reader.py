"""Independent strict binary consumer. Integrity is not semantic coverage."""
import ctypes as C, zlib
from pathlib import Path

class Value(C.LittleEndianStructure):
    _fields_=[('type',C.c_uint32),('bytes',C.c_uint32),('value',C.c_uint64)]
class Host(C.LittleEndianStructure):
    _fields_=[('gpr',C.c_uint64*16),('rip',C.c_uint64),('flags',C.c_uint64),('fx',C.c_ubyte*512)]
class Record(C.LittleEndianStructure):
    _fields_=[(n,C.c_uint32) for n in ('magic','version','size','event')]+[(n,C.c_uint64) for n in ('sequence','invocation','parent')]+[(n,C.c_uint32) for n in ('thread','depth','domain','slot','error','guest_error','cpu_size','stack_size','guest','generation','interface_id','refs','bindings','count','blob_size','flags')]+[(n,C.c_uint64) for n in ('result','host')]+[
        ('name',C.c_char*128),('cpu',C.c_ubyte*416),('stack',C.c_ubyte*128),('context',Host),('values',Value*12),('blob',C.c_ubyte*256),('previous_crc',C.c_uint32),('crc',C.c_uint32)]
def require(condition,message):
    if not condition:raise ValueError(message)
def decode(path, *, closed=True, committed=None, allow_failure=False):
    data=Path(path).read_bytes();size=C.sizeof(Record)
    require(len(data)>0 and len(data)%size==0,'empty/truncated record')
    rows=[];chain=0;stacks={};ids=set();close_seen=False
    for off in range(0,len(data),size):
        raw=data[off:off+size];r=Record.from_buffer_copy(raw)
        require(r.magic==0x31544d58 and r.version in (1,2,3) and r.size==size,'schema mismatch')
        require(r.sequence==len(rows)+1,'sequence gap/reorder/duplicate')
        require(r.previous_crc==chain and r.crc==zlib.crc32(raw[:Record.crc.offset]),'checksum/chain failure')
        chain=r.crc
        require(r.event in (1,2,3,4,5,6,7,8,9,10,11),'unknown event')
        require(r.version==rows[0].version if rows else True,'mixed stream versions')
        require(r.version>=2 or (r.event!=9 and r.domain!=5),'version-1 record uses version-2 semantics')
        require(not close_seen,'record after close')
        require((r.event==1)==(off==0),'missing/duplicate open')
        if r.version==3 and off==0:
            require(r.name in (b'xrt.monitor.v3.forensic',b'xrt.monitor.v3.development'),'unknown profile')
            development=r.name==b'xrt.monitor.v3.development'
            require(r.count==4 and [v.value for v in list(r.values)[:4]]==
                    [int(development),4096,256 if development else 1,3 if development else 0],'profile contract mismatch')
        require(r.count<=12 and r.blob_size<=256 and r.cpu_size in (0,408,416) and r.stack_size in (0,128),'invalid lengths')
        require(r.invocation>0,'missing invocation')
        require(allow_failure or r.event!=8,'recorded instrumentation gap')
        require(allow_failure or r.event!=5,'fatal execution is not completed coverage')
        if r.event in (10,11):require(r.version==3,'new event in old schema')
        if r.event==11:
            require(rows[0].name==b'xrt.monitor.v3.development' and r.name in (b'resource.map.download',b'resource.map.upload') and r.blob_size==0 and r.count==1 and r.values[0].value==r.result,'invalid omission')
        for v in list(r.values)[:r.count]:require(v.type in range(1,6) and v.bytes in (1,2,4,8),'invalid typed field')
        stack=stacks.setdefault(r.thread,[])
        if r.event==2:
            require(r.invocation not in ids,'reused invocation');ids.add(r.invocation)
            require(r.parent==(stack[-1][0] if stack else 0),'wrong parent')
            stack.append((r.invocation,r.parent,r.domain,bytes(r.name),(r.slot,r.interface_id,r.guest,r.generation,r.host)))
        if stack:
            require((r.invocation,r.parent)==stack[-1][:2] and r.depth==len(stack),'invocation/depth mismatch')
        else:
            require(r.depth==0 and r.parent==0 and r.invocation not in ids,'orphan record');ids.add(r.invocation)
        if r.event in (3,9):
            require(bool(stack),'unmatched return')
            require((r.domain,bytes(r.name))==stack[-1][2:4],'wrong return method/domain')
            if r.domain==2 and r.event==3:require((r.slot,r.interface_id,r.guest,r.generation,r.host)==stack[-1][4],'native return receiver/interface/slot changed')
            stack.pop()
        if r.event==6:
            require(not any(stacks.values()),'close with active invocations');close_seen=True
        rows.append(r)
    if closed:require(close_seen,'missing close: coverage cannot be complete')
    else:
        require(committed is not None and committed==len(rows),'missing/unequal independent committed counter')
    return rows,dict(integrity=True,records=len(rows),closed=close_seen,threads=len(stacks),
        active_invocations=sum(map(len,stacks.values())),complete_coverage=False,
        aborted_invocations=sum(r.event==9 for r in rows),
        omitted_events=sum(r.event==11 for r in rows),
        durability='Not inferred from file contents; requires independent flush-confirmed counter.',
        reason='Structural accounting only; acceptance requires separate forensic or focused experimental Init policy review.')
