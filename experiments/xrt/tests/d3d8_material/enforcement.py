"""Prepare a separately qualified supervisor preview. Never alters live policy."""
import difflib,re,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
W,O=P.W,P.O
E=O/'enforcement';S=E/'supervisor'

def stage():
    E.mkdir();shutil.copytree(W/'tools/xrt/supervisor',S,ignore=shutil.ignore_patterns('__pycache__'))
    # Fixed preview identity; no environment variable can redirect its queue or runtime.
    p=S/'core.py';s=p.read_text().replace('ROOT = Path(__file__).resolve().parents[3]','ROOT = Path('+repr(str(W))+')').replace('HOME = ROOT / "out/desktop-supervisor"','HOME = ROOT / "out/material-preview"')
    s=s.replace('renderer-init-before-0696f292','renderer-init-before-0696f323').replace('0x0696f292','0x0696f323')
    s=s.replace('"experiments/xrt/tests", "experiments/xrt/gen"','"experiments/xrt/tests", "experiments/xrt/gen", "out/recovery/d3d8-material-20261029-01/runtime"')
    s=s.replace('require(m["executable"] == "experiments/xrt/build/desktop-supervisor/fixture.exe",','require(m["executable"] in ("experiments/xrt/build/desktop-supervisor/fixture.exe", "experiments/xrt/build/d3d8-material-supervisor-preview/fixture.exe"),')
    s=s.replace('actual = tree(root / ("experiments/xrt/runtime" if folder == "runtime" else "experiments/xrt/gen"))','actual = tree(root / ("out/recovery/d3d8-material-20261029-01/runtime" if folder == "runtime" else "experiments/xrt/gen"))')
    p.write_text(s)
    # Exact next guest marker, checked xrt_icall and resulting first PC store.
    p=S/'plan.py';s=p.read_text().replace('0x696f292','0x696f323').replace('0x0696f292','0x0696f323').replace('/* lea edx, [ebp - 0xbc] */','/* mov eax, dword ptr [ebp - 0x14] */')
    start=s.index('    expected=[');end=s.index('    actual=',start)
    s=s[:start]+'''    expected=[('cmp','dword ptr [rsi + 0x40], edi'),('jne',None),
              ('mov','dword ptr [rsi + 0x44], edi'),('lea','rcx, [rbp + 0xde8]'),
              ('mov','edx, dword ptr [rsi + 0x14]'),('mov','edi, 0x14'),
              ('sub','edx, edi'),('mov','r8, r15')]
'''+s[end:]
    s=s.replace('before its LEA writes guest EDX','before its MOV reads the next renderer field')
    p.write_text(s)
    for p in S.rglob('*'):
        if p.suffix in ['.py','.json'] and p.name not in ['core.py','plan.py']:
            s=p.read_text().replace('0x0696f292','0x0696f323').replace('0x696f292','0x696f323').replace('hard_stop_0696f292','hard_stop_0696f323')
            if p.name=='genuine.py':s=s.replace('core.ROOT / "out/recovery/viewport-getobject-20261028-01/bounded_genuine.py"','Path(__file__).with_name("bounded_material.py")')
            if p.name=='observer_checks.py':s=s.replace('core.ROOT / "out/recovery/viewport-getobject-20261028-01/bounded_genuine.py"','Path(__file__).with_name("bounded_material.py")')
            if p.name=='qualify.py':
                s=s.replace('"experiments/xrt/build/desktop-supervisor"','"experiments/xrt/build/d3d8-material-supervisor-preview"')
                s=s.replace('core.ROOT / "tools/xrt/supervisor/tests"','Path(__file__).parent / "tests"')
                s=s.replace("core.ROOT / 'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py'","Path(__file__).with_name('bounded_material.py')")
                s=s.replace("'out/recovery/queryclass-20261029-01/build.json'","'out/recovery/d3d8-material-20261029-01/build.json'")
            if p.name=='recovery.py':s=s.replace("str(core.ROOT/'tools/xrt/supervisor/recovery_worker.py')","str(Path(__file__).with_name('recovery_worker.py'))")
            if p.name=='recovery_worker.py':s=s.replace("'experiments/xrt/build/desktop-supervisor/fixture.exe'","'experiments/xrt/build/d3d8-material-supervisor-preview/fixture.exe'")
            p.write_text(s)
    p=S/'service.py';s=p.read_text();s=s.replace('    return {p.relative_to(core.ROOT)', '    paths += list(Path(__file__).parent.rglob("*.py"))\n    return {p.relative_to(core.ROOT)',1);p.write_text(s)
    # Import the fixed historical helpers, but replace only the observer definition.
    src=(W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py').read_text()
    src=src.replace('O=Path(__file__).resolve().parent','O=Path('+repr(str(W/'out/recovery/viewport-getobject-20261028-01'))+')')
    src=src.replace("0x0696f292","0x0696f323").replace('0x696f292','0x696f323').replace('hard_stop_0696f292','hard_stop_0696f323')
    src=src.replace("in ['bridge_return','render_bridge_return','state_bridge_return']","in ['bridge_return','render_bridge_return','state_bridge_return','material_bridge_return']")
    src=src.replace("else ('d8_device_SetRenderState','state_entry'))","else (('d8_device_SetMaterial','material_entry') if len([r for r in self.rows if r['kind']=='state_bridge_return'])==8 else ('d8_device_SetRenderState','state_entry')))")
    src=src.replace("assert cpu['rv']==0x696f323 and cpu['pc']==0x696f28c","assert cpu['rv']==0x696f323 and cpu['pc']==0x696f31d\n                assert len([r for r in self.rows if r['kind']=='material_bridge_return'])==1")
    src=src.replace('SetMaterial_reached=False','SetMaterial_reached=True')
    src=src.replace("            if tag=='fatal_entry':",MATERIAL_HIT+"            if tag=='fatal_entry':",1)
    # Audit the complete old contract on a disposable filtered copy; additionally
    # audit the new method against independently captured native and guest records.
    src=src.replace('def audit(out):','def audit_prior(out):',1)
    src+=MATERIAL_AUDIT
    (S/'bounded_material.py').write_text(src)
    # The preview qualification main can only launch fixed non-game fixtures.
    (E/'qualify.py').write_text('import sys\nfrom pathlib import Path\nsys.dont_write_bytecode=True\nsys.path.insert(0,str(Path(__file__).parent))\nfrom supervisor.qualify import main\nmain()\n')
    patch=''
    for name in ['core.py','plan.py','genuine.py','observer_checks.py','qualify.py','service.py']:
        patch+=''.join(difflib.unified_diff((W/'tools/xrt/supervisor'/name).read_text().splitlines(True),(S/name).read_text().splitlines(True),fromfile='active/'+name,tofile='preview/'+name))
    (O/'enforcement.patch').write_text(patch)
    P.save('enforcement-staging.json',dict(passed=True,scope='renderer-init-before-0696f323',guest_stop='0x0696f323',files=P.core.tree(E),
        active_code_changed=False,live_policy_advanced=False,authorization_reused=False,genuine_launches=0))

def revise():
    p=S/'core.py';s=p.read_text().replace('out/recovery/d3d8-material-20261029-01/preview-home','out/material-preview')
    preserved=P.read(O/'preservation.json');rows=P.core.Ledger(P.core.HOME/'ledger.jsonl').rows
    consumed=sorted({r['sha256']for r in rows if r['kind']=='launch-claimed'})
    s=s.replace('        if manifest["kind"] == "genuine":','        if manifest["kind"] == "genuine":\n            require(sha(ROOT/"out/desktop-supervisor/ledger.jsonl")=='+repr(preserved['ledger_sha256'])+', "production history changed; owner review and requalification required")\n            require(manifest["sha256"] not in '+repr(consumed)+', "historically consumed genuine binary")')
    p.write_text(s)
    p=S/'service.py';s=p.read_text();needle='    if current != known:\n        raise core.IntegrityFailure("supervisor inventory changed; requalify")'
    assert needle in s
    s=s.replace(needle,needle+'\n    preview = Path(__file__).parent\n    known_preview={n for n in seal["files"] if n.startswith(preview.relative_to(core.ROOT).as_posix()+"/")}\n    actual_preview={p.relative_to(core.ROOT).as_posix() for p in preview.rglob("*.py")}\n    if known_preview!=actual_preview:\n        raise core.IntegrityFailure("preview supervisor inventory changed; requalify")')
    p.write_text(s)
    P.save('consumed-denylist.json',dict(production_ledger_sha256=preserved['ledger_sha256'],consumed=consumed,old_batch_reused=False))

def finalize_stage():
    for p in S.rglob('*.py'):
        s=p.read_text().replace('out/desktop-supervisor/candidates','out/material-preview/candidates')
        if p.name=='service.py':
            s=s.replace('core.ROOT / "experiments/xrt/build/desktop-supervisor/fixture.exe"','core.ROOT / "experiments/xrt/build/d3d8-material-supervisor-preview/fixture.exe"')
            s=s.replace('(core.ROOT / "experiments/xrt/runtime").rglob','(core.ROOT / "out/recovery/d3d8-material-20261029-01/runtime").rglob')
            s=s.replace('    paths += list(Path(__file__).parent.rglob("*.py"))','    paths += list(Path(__file__).parent.rglob("*.py"))\n    paths += list(Path(__file__).parent.parent.glob("*.py"))')
        p.write_text(s)
    (S/'tests/test_material_policy.py').write_text(POLICY_TEST)
    (E/'command.py').write_text('import sys\nfrom pathlib import Path\nsys.dont_write_bytecode=True\nsys.path.insert(0,str(Path(__file__).parent))\nfrom supervisor.service import main\nmain()\n')
    (E/'owner_start.py').write_text(OWNER_START)

POLICY_TEST='''import sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from supervisor import core
class MaterialPolicy(unittest.TestCase):
    def test_fixed_material_stop_rejects_old_and_later(self):
        from test_policy import Policy
        p=Policy();p.setUp();p.parse()
        for value in ['0x0696f292','0x0696f324','0x0696f336']:
            p.r['expected_stop']['guest_address']=value
            with self.assertRaises(core.Rejected):p.parse()
    def test_old_batch_scope_is_rejected(self):
        from test_policy import Policy
        p=Policy();p.setUp();p.r['scope']='renderer-init-before-0696f292'
        with self.assertRaises(core.Rejected):p.parse()
    def test_all_historical_genuine_hashes_remain_consumed(self):
        rows=core.Ledger(core.ROOT/'out/desktop-supervisor/ledger.jsonl').rows
        consumed={r['sha256']for r in rows if r['kind']=='launch-claimed'}
        self.assertGreaterEqual(len(consumed),4)
        with tempfile.TemporaryDirectory(dir=core.ROOT/'out') as d:
            ledger=core.Ledger(Path(d)/'ledger.jsonl')
            for sha in consumed:
                with self.assertRaisesRegex(core.Rejected,'historically consumed'):
                    ledger.claim(dict(id=str(uuid.uuid4())),dict(kind='genuine',sha256=sha),dict(id='fixture',genuine_limit=1))
            self.assertFalse(ledger.rows)
'''

OWNER_START='''"""OWNER ONLY: invoke after reviewing the material candidate and new policy.
Starts a fresh one-attempt batch; never submits a renderer request by itself.
"""
import shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent))
from supervisor import core,service
from supervisor.windows import Exclusive
from supervisor.environment import ordinary_user
ordinary_user()
core.require(sys.stdin.isatty(),'owner local interactive console required')
seal=core.read_large(core.HOME/'qualification.json');service.verify_seal(seal)
baseline=core.read_large(core.ROOT/'out/recovery/d3d8-material-20261029-01/preservation.json')
original=core.ROOT/'out/desktop-supervisor'
# Keep the original global exclusion lock for the entire new supervisor life.
with Exclusive(original/'supervisor.lock'):
    core.require(core.sha(original/'ledger.jsonl')==baseline['ledger_sha256'],'production history changed; requalify')
    target=core.HOME/'ledger.jsonl'
    if not target.exists():shutil.copy2(original/'ledger.jsonl',target)
    else:core.require(target.read_bytes().startswith((original/'ledger.jsonl').read_bytes()),'history prefix mismatch')
    core.Ledger(target)
    sys.argv=[sys.argv[0],'serve','--authorize-genuine-attempts','1','--recovery-policy','contained-development-v1']
    service.main()
'''

MATERIAL_HIT='''            if tag=='material_entry':
                self.cpu=ctx.get('rcx');self.guest_base=self.u64(self.sym('xrt_g'))
                cpu=self.cpu_state(self.cpu);self.material_esp=cpu['registers']['esp'];frame=self.words(self.guest_base+self.material_esp,3)
                objects=self.object_state();data=self.guest(frame[2],68)
                assert frame[0]==plan['guest_stop'] and frame[1]==objects['guest'] and data==MATERIAL_BYTES
                self.material_frame=frame;self.material_return=self.u64(ctx.get('rsp'))
                native=self.u64(objects['native_vtable']+42*8)
                self.log(tag,thread=tid,host=ctx.snapshot(),cpu=cpu,guest_stack=frame,material=data.hex(),objects=objects)
                self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',native:'material_native_entry',self.material_return:'material_bridge_return',self.sym('invoke_gui_proc'):'material_callback'}
                return
            if tag=='material_native_entry':
                self.material_cpu=self.mem(self.cpu,416);self.material_stack=self.guest(self.material_esp,12)
                self.material_host=ctx.snapshot();self.material_native_return=self.u64(ctx.get('rsp'))
                objects=self.object_state();assert ctx.get('rcx')==objects['host'] and self.mem(ctx.get('rdx'),68)==MATERIAL_BYTES
                self.log(tag,thread=tid,host=ctx.snapshot(),cpu=self.cpu_state(self.cpu),native_material=self.mem(ctx.get('rdx'),68).hex(),objects=objects)
                del self.breakpoints[ctx.get('rip')];self.breakpoints[self.material_native_return]='material_native_return'
                return
            if tag=='material_native_return':
                hr=ctx.get('rax')&0xffffffff
                assert hr==0 and self.material_cpu==self.mem(self.cpu,416) and self.material_stack==self.guest(self.material_esp,12) and self.guest(self.material_frame[2],68)==MATERIAL_BYTES
                host=ctx.snapshot()
                assert all(host['registers'][n]==self.material_host['registers'][n] for n in ['rbx','rbp','rsi','rdi','r12','r13','r14','r15'])
                assert bytes.fromhex(host['fxsave'])[256:416]==bytes.fromhex(self.material_host['fxsave'])[256:416] and host['mxcsr']==self.material_host['mxcsr']
                self.log(tag,thread=tid,host=host,cpu=self.cpu_state(self.cpu),hresult=hr,last_error=self.u32(self.threads[tid][1]+0x68),suspended_cpu_unchanged=True,guest_frame_unchanged=True,material_unchanged=True,objects=self.object_state())
                del self.breakpoints[ctx.get('rip')];self.breakpoints[self.material_return]='material_bridge_return'
                return
            if tag=='material_bridge_return':
                self.log(tag,thread=tid,host=ctx.snapshot(),cpu=self.cpu_state(self.cpu),objects=self.object_state())
                self.breakpoints={self.sym('xrt_fatal'):'fatal_entry'}
                return
            if tag=='material_callback':
                raise RuntimeError('unexpected genuine callback within SetMaterial')
'''
MATERIAL_AUDIT='''
MATERIAL_BYTES=struct.pack('<17I',*[0x3f000000]*3,*[0x3f800000]*5,*[0]*9)

def audit(out):
    import tempfile,shutil
    debug=[json.loads(s)for s in (out/'debug-observations.jsonl').read_text().splitlines()]
    events=E.read(out/'runtime-events.json')['events']
    def ds(k):return [r for r in debug if r['kind']==k]
    calls=[r for r in events if r['kind']=='d3d8_material_call'];returns=[r for r in events if r['kind']=='d3d8_material_return']
    assert len(calls)==len(returns)==len(ds('material_entry'))==len(ds('material_native_entry'))==len(ds('material_native_return'))==len(ds('material_bridge_return'))==1
    a,n,b=[ds(k)[0]for k in ['material_entry','material_native_return','material_bridge_return']];c,r=calls[0],returns[0]
    assert a['material']==MATERIAL_BYTES.hex() and n['suspended_cpu_unchanged'] and n['guest_frame_unchanged'] and n['material_unchanged']
    assert a['cpu']['x87']==b['cpu']['x87'] and a['cpu']['flags']==b['cpu']['flags']
    assert b['cpu']['registers']['esp']==a['cpu']['registers']['esp']+12 and b['cpu']['rv']==0x696f323
    assert all(a['cpu']['registers'][k]==b['cpu']['registers'][k]for k in ['ebx','ebp','esi','edi'])
    assert c['this']==r['this']==a['objects']['guest']==b['objects']['guest'] and a['objects']['host']==b['objects']['host']
    assert r['result']==n['hresult']==b['cpu']['registers']['eax']==0 and r['last_error']==n['last_error'] and r['esp_after']==r['esp_before']+12 and r['actual_return']==r['return']==0x696f323
    assert len(ds('hard_stop_0696f323'))==len(ds('terminated_before_continue'))==1 and not ds('fatal_entry')
    assert [[x['state'],x['value']]for x in events if x['kind']=='d3d8_state_call']==PAIRS
    # Prior audit expects the old stop tag and no material events, but all of its
    # CreateDevice/Clear/Present/eight-state assertions must still hold.
    with tempfile.TemporaryDirectory(dir=out) as temp:
        d=Path(temp)
        filtered=[dict(x,kind='hard_stop_0696f323')if x['kind']=='hard_stop_0696f323' else x for x in debug if not x['kind'].startswith('material_')]
        (d/'debug-observations.jsonl').write_text(''.join(json.dumps(x)+'\\n'for x in filtered))
        E.save(d/'runtime-events.json',dict(events=events))
        shutil.copy2(out/'hard-stop.json',d/'hard-stop.json');audit_prior(d)
    E.save(out/'result.json',dict(passed=True,experimental_only=True,strict_native_x86_compatibility='FAILED',SetMaterial_pairs=1,prior_eight_states_verified=True,hard_stop=E.read(out/'hard-stop.json'),genuine_cleanup='terminated before pending event continued'))
'''

if __name__=='__main__':globals()[sys.argv[1]]()
