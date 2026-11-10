"""Fresh bounded non-game probes only. No original game entry is reachable."""
import ctypes as C, importlib.util, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
import pefile
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
P=load('post_fixture_preservation',HERE/'preserve.py')
F=load('post_fixture_build_helpers',P.W/'experiments/xrt/tests/getobject_boundary/phase.py')
F.O=P.O/'fixture-build';F.B=P.W/'experiments/xrt/build/postsplash-recovery-20261028-01'
SB=P.W/'sandbox_postsplash_fixture_20261028_01'

def build():
    F.O.mkdir();F.B.mkdir();SB.mkdir();(SB/'System').mkdir()
    pe=pefile.PE(str(P.SB/'System/Engine.dll'))
    (F.B/'guids.bin').write_bytes(b''.join(pe.get_data(r,16) for r in [0x240010,0x23ffb0,0x240020,0x23ffa0]))
    pinned=P.read(P.OLD/'pinned-inputs.json')['inputs']['helper'];assert P.sha(pinned['path'])==pinned['sha256']
    shutil.copy2(pinned['path'],F.B/'dmusic_helper.exe')
    for arch,name in [('x86','native_init'),('x64','ipc_init'),('x64','string_fatal')]:
        d=F.B/arch;d.mkdir(exist_ok=True);env=F.env(arch)
        F.run(['cl','/nologo','/O1','/Zi','/W4','/D_CRT_SECURE_NO_WARNINGS',f'/Fo{d}/',f'/Fd{d}/{name}-compile.pdb',f'/Fe{d}/{name}.exe',HERE/(name+'.c'),'ole32.lib','user32.lib','/link','/DEBUG',f'/PDB:{d}/{name}.pdb'],name+'-build',environment=env,timeout=60)
    P.save(P.O/'fixture-build.json',dict(passed=True,binaries=P.tree(F.B),sources=P.tree(HERE),sandbox=str(SB),genuine_sessions=0))

def characterize():
    d=P.O/'init-audio-characterization';d.mkdir()
    rows=[]
    commands=[('native-unguarded',[F.B/'x86/native_init.exe',F.B/'guids.bin',SB,'0']),
        ('native-guarded',[F.B/'x86/native_init.exe',F.B/'guids.bin',SB,'1']),
        ('ipc-production-helper',[F.B/'x64/ipc_init.exe',F.B/'dmusic_helper.exe',SB])]
    for name,cmd in commands:
        start=time.monotonic();cmd=list(map(str,cmd));env=os.environ.copy()
        for k in list(env):
            if k.startswith(('XRT_','DXVK_','VK_')) or k in ['__COMPAT_LAYER','CL','_CL_','LINK','_LINK_']:env.pop(k)
        try:
            r=subprocess.run(cmd,cwd=SB/'System',env=env,capture_output=True,timeout=14)
            row=dict(case=name,command=cmd,exit=r.returncode,timeout=False,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace'))
        except subprocess.TimeoutExpired as e:
            row=dict(case=name,command=cmd,exit=None,timeout=True,stdout=(e.stdout or b'').decode(errors='replace'),stderr=(e.stderr or b'').decode(errors='replace'),cleanup='subprocess.run killed and waited for this native fixture; normal COM release not claimed')
        row['seconds']=time.monotonic()-start;P.save(d/(name+'.json'),row)
        (d/(name+'.stdout.txt')).write_bytes(row['stdout'].encode());(d/(name+'.stderr.txt')).write_bytes(row['stderr'].encode())
        print(name,row['exit'],'timeout',row['timeout'],round(row['seconds'],2),flush=True);rows.append(row)
    P.save(P.O/'init-audio-characterization.json',dict(runs=rows,genuine_sessions=0,
        guard_or_transport_changed=False,assertions_waived=False,scope='Current executor desktop only; no owner Default-desktop equivalence assumed'))

def debugger():
    d=P.O/'string-observer-debugger';d.mkdir()
    helper=load('post_live_debugger_helpers',P.W/'experiments/xrt/tests/getobject_boundary/debugger_test.py')
    Evidence=load('post_string_observer',HERE/'observer_evidence.py')
    Loop,D=helper.Loop,helper.D
    exe=F.B/'x64/string_fatal.exe';syms=helper.symbols(exe,['xrt_fatal','xrt_g'])
    results=[]
    for case in ['copied-string','unreadable']:
        out=d/case;out.mkdir()
        class Probe(Loop,D.Capture):
            def on_create(self,ev):self.breakpoints={self.sym('xrt_fatal'):'fatal_entry'}
            def update(self,ctx,resume=False):
                ctx.arm(list(self.breakpoints),resume);actual=D.Context(ctx.thread)
                assert C.c_uint64.from_address(actual.ptr+72).value==self.sym('xrt_fatal')
                assert C.c_uint64.from_address(actual.ptr+112).value&0xffff00ff==1
                self.log('breakpoint_readback',verified=True)
            def hit(self,tag,ctx,tid):raise AssertionError('strict delegation retained')
            def snapshot_events(self):self.log('fixture_snapshot',game_executed=False)
        probe=Evidence.install(Probe(syms),out);marker=out/'FORBIDDEN-fatal-body.txt'
        with (out/'child-output.txt').open('wb') as f:
            try:probe.run([str(exe),str(marker),case],cwd=P.W,env=os.environ.copy(),stdout=f,stderr=subprocess.STDOUT,timeout=10)
            except RuntimeError as e:assert 'fatal before required stop; no continuation:' in str(e)
            else:raise AssertionError('observer must stop')
        fatal=next(r for r in probe.rows if r['kind']=='fatal_entry')
        assert not marker.exists() and fatal['cpu']['pc']==0x12345678 and len(fatal['guest_stack'])==40 and fatal['format']=='%s'
        assert probe.cpu is None and Path(fatal['output_directory'])==out.resolve()
        if case=='copied-string':
            expected=b'fixture transport failure 100% %x (Win32 123)'
            assert fatal['formatted_message']==expected.decode() and bytes.fromhex(fatal['string_arguments'][0]['raw_hex'])==expected and not fatal['diagnostic_read_errors']
        else:assert 'formatted_message' not in fatal and any('string argument:' in e for e in fatal['diagnostic_read_errors'])
        results.append(dict(case=case,passed=True,exit=probe.process_obj.returncode))
    hardware=load('post_hardware_selftest',P.W/'out/recovery/session-aware-136-20261026-01/debugger_selftest.py').run(d/'permanent-stop')
    assert hardware['passed']
    P.save(P.O/'observer-tests.json',dict(passed=True,live_cases=results,hardware_stop=hardware,genuine_sessions=0))
    print('LIVE STRING OBSERVER / HARDWARE STOP PASS',flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
