"""Owned fixtures only; real Job/watchdog via the unchanged production machinery."""
import sys,uuid,json,ctypes as C
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode,Record
from observer import collect_stopped
from supervisor import fixture
from supervisor.windows import FilePins,Context
class Request(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('event','domain','slot','count')]+[('name',C.c_uint64),('result',C.c_uint64)]+[(n,C.c_uint32) for n in ('guest','generation','interface_id','refs','bindings','blob_size')]+[('blob',C.c_uint64),('host',C.c_uint64),('values',C.c_ubyte*192)]
def main():
    out=O/('live-'+str(uuid.uuid4()));out.mkdir();h=helper(out);env=h.env();exe=out/'monitor-fixture.exe'
    h.run(['ml64','/nologo','/c','/Zi',f'/Fo{out}/monitor_asm.obj',RT/'monitor.asm'],'asm',environment=env)
    h.run(['ml64','/nologo','/c','/Zi',f'/Fo{out}/fpu_oracle.obj',H/'fpu_oracle.asm'],'fpu-oracle',environment=env)
    h.run(['cl','/nologo','/std:c11','/O2','/Zi','/fp:strict','/DXM_QUALIFICATION','/D_CRT_SECURE_NO_WARNINGS',
        f'/I{RT}',f'/Fo{out}/',f'/Fd{out}/fixture.pdb',f'/Fe{exe}',H/'fixture.c',RT/'monitor.c',out/'monitor_asm.obj',out/'fpu_oracle.obj',
        'user32.lib','dxguid.lib','dinput8.lib','/link','/DEBUG'],'build',environment=env)
    results=[]
    for mode,case in enumerate(('success','write-failure','watchdog','nesting-failure','invalid-span','missing-close','fatal','debugger-oracle','debugger-write-failure','unflushed-stop','buffer-exhaustion','flush-failure','partial-write','record-limit','explicit-omission')):
        d=out/case;d.mkdir();sandbox=d/'sandbox';sandbox.mkdir();stream=sandbox/'trace.bin'
        class Probe(fixture.Probe):
            def __init__(self):super().__init__(d,sandbox,case);self.observed=[];self.failure=None
            def on_debugbreak(self,ev):
                if hasattr(self,'target'):
                    symbols={k:{'rva':self.target[v]-self.base} for k,v in [('xm_pending','pending'),('xm_committed','committed')]}
                    symbols.update({k:{'rva':v-self.base} for k,v in read(sandbox/'symbols.json').items()})
                    _,result=collect_stopped(self,stream,symbols,d/'stopped-collector')
                    self.log('independent_stopped_collector',**result);return
                self.target=read(sandbox/'ready.json');core.require(self.target['pid']==self.process_obj.pid,'owned PID')
                self.breakpoints={self.target['failure']:'trace-failure'}
                if mode==7:self.breakpoints[self.target['probe']]='trace-probe'
                for thread,_ in self.threads.values():self.update(Context(thread))
            def hit(self,tag,ctx,tid):
                if tag=='trace-failure':
                    self.failure=dict(reason=ctx.get('rcx'),pending=self.mem(self.target['pending'],C.sizeof(Record)).hex(),
                        committed=int.from_bytes(self.mem(self.target['committed'],8),'little'))
                    self.log('write_failure_before_continue',**self.failure)
                    symbols={k:{'rva':self.target[v]-self.base} for k,v in [('xm_pending','pending'),('xm_committed','committed')]}
                    symbols.update({k:{'rva':v-self.base} for k,v in read(sandbox/'symbols.json').items()})
                    try:collect_stopped(self,stream,symbols,d/'stopped-collector',failure_reason=self.failure['reason'])
                    except ValueError as e:self.log('stopped_collector_rejected_incomplete',reason=str(e))
                    else:self.log('failed_tail_preserved',accepted_as_success=False)
                    raise core.Rejected('instrumentation failure contained before continuation')
                q=Request.from_buffer_copy(self.mem(ctx.get('rdx'),C.sizeof(Request)))
                cpu=self.mem(ctx.get('rcx'),416).hex() if ctx.get('rcx') else ''
                name=self.mem(q.name,128).split(b'\0')[0].decode() if q.name else ''
                row=dict(thread=tid,event=q.event,domain=q.domain,slot=q.slot,name=name,result=q.result,cpu=cpu,
                    error=int.from_bytes(self.mem(self.threads[tid][1]+0x68,4),'little'),context=ctx.snapshot(),
                    return_address=int.from_bytes(self.mem(ctx.get('rsp'),8),'little'))
                self.observed.append(row)
                self.log('independent_probe_state',**row)
        probe=Probe();error=None
        with FilePins() as pins:
            pins.pin(exe,core.sha(exe))
            try:
                with (d/'stdout.txt').open('xb') as stdout,(d/'stderr.txt').open('xb') as stderr:
                    probe.run([str(exe),str(stream),str(mode)],cwd=sandbox,env=fixture.environment(sandbox),
                        stdout=stdout,stderr=stderr,timeout=3 if mode==2 else 45)
            except Exception as e:error=type(e).__name__+': '+str(e)
        parsed=None;rejection=None;rows=[]
        try:rows,parsed=decode(stream)
        except Exception as e:rejection=str(e)
        row=dict(case=case,error=error,parser=parsed,rejection=rejection,cleanup=probe.cleanup)
        save(d/'result.json',row);results.append(row)
        core.require(probe.cleanup['remaining_job_processes']==0,'Job cleanup')
        if mode in (0,7,9,14):
            core.require(error is None and parsed and parsed['closed'],'positive fixture failed '+str(row))
            if mode in (9,14):
                captured=read(d/'stopped-collector/result.json')
                core.require(captured['independent_capture'] and captured['failed']==0,'stopped evidence')
                if mode==9:core.require(captured['unflushed_records']>0 and not captured['guest_tail_durable'],'unflushed durability overstated')
                if mode==14:core.require(captured['omitted_events']==1,'omission missing')
                continue
            oracle=json.loads((d/'stdout.txt').read_text().splitlines()[-1])
            core.require(oracle['record_size']==C.sizeof(Record) and oracle['committed']==len(rows),'native schema/counter oracle')
            native=[r for r in rows if r.event==3 and r.name==b'D8Device.GetViewport']
            core.require(len(native)==1 and native[0].result&0xffffffff==0x80004005 and native[0].error==0xaabbccdd,'native failure oracle')
            core.require(len({r.thread for r in rows})==4 and max(r.depth for r in rows)>=6,'threads/nesting')
            if mode==7:
                by_thread={tid:[r for r in rows if r.thread==tid] for tid in {r.thread for r in rows}}
                for tid,stream_rows in by_thread.items():
                    debug_rows=[r for r in probe.observed if r['thread']==tid]
                    core.require(len(stream_rows)==len(debug_rows),'debugger/stream count')
                    for a,b in zip(stream_rows,debug_rows):
                        core.require((a.event,a.domain,a.slot,a.result,a.error,bytes(a.name).decode())==
                            (b['event'],b['domain'],b['slot'],b['result'],b['error'],b['name']),'debugger semantic fields')
                        core.require(bytes(a.cpu)[:a.cpu_size].hex()==b['cpu'],'independent raw guest CPU')
                        regs=b['context']['registers']
                        for i,reg in enumerate('rax rcx rdx rbx rsp rbp rsi rdi r8 r9 r10 r11 r12 r13 r14 r15'.split()):
                            core.require(a.context.gpr[i]==regs[reg],'host register '+reg)
                        core.require(a.context.rip==b['return_address'],'return address')
                        fx=bytes(a.context.fx);dbg=bytes.fromhex(b['context']['fxsave'])
                        # Windows CONTEXT zeroes/normalizes reserved FXSAVE bytes.
                        for off,n in ((0,5),(24,4),(32,128),(160,256)):
                            core.require(fx[off:off+n]==dbg[off:off+n],'independent FPU/XMM bytes '+str(off))
                save(d/'independent-comparison.json',dict(passed=True,records=len(rows),all_guest_cpu_bytes=True,all_gpr=True,
                    x87_registers_and_control_status=True,mxcsr=True,xmm=True,host_last_error=True))
            raw=stream.read_bytes();neg=[]
            mutations={'truncated':raw[:-1],'missing-tail':raw[:-C.sizeof(Record)],'missing-middle':raw[:C.sizeof(Record)]+raw[2*C.sizeof(Record):],
                'duplicate':raw[:C.sizeof(Record)]+raw,'corruption':raw[:500]+bytes([raw[500]^1])+raw[501:]}
            for name,data in mutations.items():
                p=d/(name+'.bin');p.write_bytes(data)
                try:decode(p)
                except ValueError as e:neg.append(dict(case=name,rejection=str(e)))
                else:raise AssertionError('false completeness: '+name)
            save(d/'reader-negatives.json',neg)
        else:
            core.require(parsed is None and rejection,'negative falsely complete')
            if mode==8:
                core.require(probe.failure and probe.failure['reason']==9,'write failure debugger evidence')
                pending=Record.from_buffer_copy(bytes.fromhex(probe.failure['pending']))
                core.require(pending.sequence>probe.failure['committed'] and pending.name==b'broken-sink-checkpoint','pending uncommitted evidence')
                core.require(any(r['kind']=='terminated_before_continue' for r in probe.rows),'failure resumed')
            if mode in (10,11,12,13):
                core.require(probe.failure and probe.failure['reason']=={10:22,11:23,12:9,13:5}[mode],'failure reason '+str(mode))
                captured=read(d/'stopped-collector/result.json')
                core.require(captured['independent_capture'] and captured['failed'],'failed evidence missing')
                core.require(any(r['kind']=='terminated_before_continue' for r in probe.rows),'failure continued')
    save(O/'live.json',dict(passed=True,root=str(out),results=results,runtime=core.tree(RT),
        source=core.sha(H/'fixture.c'),genuine_launches=0,production_policy_changed=False))
    print('Owned live monitoring and strict reader cases PASS',flush=True)
if __name__=='__main__':main()
