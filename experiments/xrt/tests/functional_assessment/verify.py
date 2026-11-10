"""No-process checks of assessment rejection rules and staged monitor coverage."""
import copy
import importlib.util
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as A

CAPTURE=A.W/'out/desktop-fixtures/evidence/a142a8f3-c5db-4b9a-acb1-50bc0efb2a6c/captures/post-material-states-x64-translated'
ROWS=A.E.read_rows(CAPTURE/'stdout.txt')
ROW=next(r for r in ROWS if r['kind']=='resource-call' and r['slot']==36)


class Rejections(unittest.TestCase):
    def mutate(self, field, offset, bit):
        row=copy.deepcopy(ROW); raw=bytearray.fromhex(row[field]);raw[offset]^=bit;row[field]=raw.hex()
        with self.assertRaises(ValueError): A.call_audit(row,'x64',True)

    def test_precision_is_still_strict_failure(self):
        self.assertEqual(A.call_audit(ROW,'x64',True)['strict_error'],'strict outer x87/MXCSR difference')
        with self.assertRaises(A.E.base.Invalid):A.E.base.abi(ROW,'x64')

    def test_control_change_rejected(self):self.mutate('post',1,4)
    def test_rounding_change_rejected(self):self.mutate('post',25,0x20)
    def test_extra_exception_rejected(self):self.mutate('post',24,1)
    def test_top_change_rejected(self):self.mutate('post',3,8)
    def test_live_register_change_rejected(self):self.mutate('post',32,1)
    def test_guest_precision_mutation_rejected(self):self.mutate('cpu_after',142,0x20)
    def test_guest_tail_mutation_rejected(self):self.mutate('cpu_after',415,1)
    def test_guest_wrong_size_rejected(self):
        r=copy.deepcopy(ROW);r['cpu_after']=r['cpu_after'][:-16]
        with self.assertRaises(ValueError):A.call_audit(r,'x64',True)


def monitor_coverage():
    # Exercise the actual staged installer with a non-process in-memory stand-in.
    from continuation import install
    plan=A.read(A.I/'stop-mapping.json')
    class Fake:
        base=0
        breakpoints={}
        def hit(self,*args):raise AssertionError('retained nonfatal handler unexpectedly reached')
        def sym(self,name):return {'xrt_fatal':0x100,'d8_CreateDevice':0x200}[name]
        def mem(self,address,size):
            return bytes.fromhex(plan['stop_bytes'] if address==plan['stop_rva'] else plan['entry_bytes'])
    checks=[];capture=install(Fake(),plan,checks.append);capture.on_create(None)
    tags=list(capture.breakpoints.values())
    A.require(set(tags)=={'init_entry','init_return','fatal_entry','init_create_device'},'staged breakpoint coverage changed')
    missing=[]
    for tag in ('semantic_checkpoint','native_return','bridge_return','wndproc_entry'):
        try:capture.hit(tag,None,1)
        except A.core.Rejected as error:missing.append(dict(tag=tag,error=str(error)))
        else:raise AssertionError('unexpected supported detailed tag: '+tag)
    A.save('monitor-coverage.json',dict(no_process_created=True,staged_tags=tags,rejected_detail_tags=missing,
        endpoint_handler_qualified_separately=True,complete_boundary_callback_monitoring=False,
        source=str(A.H/'continuation.py'),sha256=A.sha(A.H/'continuation.py'),
        limitation='This is a constructed handler coverage check, not a live debugger/GPU test. Retained runtime entry/return telemetry exists, but it does not supply complete host FPU and callback snapshots at all four native phases.'))


def original_crosscheck():
    raw=A.read(A.OUT/'original-code-audit.json')
    generated=list((A.W/'experiments/xrt/gen/d3ddrv').glob('*.c'))
    text='\n'.join(p.read_text() for p in generated)
    sites=[r['site'] for r in raw['texture_calls']+raw['fpu_readers']]
    A.require(all(f'P({site}u)' in text for site in sites),'original/generated marker correspondence')
    import pefile
    imports={}
    # Broader dependency presence is a warning against a whole-game no-reader claim.
    for name in ('Unreal2.exe','Core.dll','Engine.dll','WinDrv.dll','Window.dll','D3DDrv.dll'):
        path=A.W/'sandbox_inputs/first-world/content/System'/name
        pe=pefile.PE(str(path));found=[]
        for d in pe.DIRECTORY_ENTRY_IMPORT:
            for x in d.imports:
                if x.name and x.name.decode() in ('GetLastError','_statusfp','_clearfp','_controlfp'):
                    found.append(dict(dll=d.dll.decode(),name=x.name.decode(),iat=hex(x.address)))
        imports[name]=dict(sha256=A.sha(path),readers=found)
    A.save('reader-crosscheck.json',dict(original_generated_sites_verified=sites,
        generated={str(p):A.sha(p) for p in generated},dependency_imports=imports,
        direct_fs_operands=sorted(set(r['instruction'].split('fs:')[-1] for r in raw['fs_segment_instructions'])),
        whole_program_noninterference_proven=False))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Rejections))
    A.require(result.wasSuccessful(),'rejection tests')
    monitor_coverage();original_crosscheck()
    A.save('assessment-tests.json',dict(passed=True,tests=result.testsRun,genuine_launches=0,physical_launches=0,
        monitor_gap_reproduced_without_process=True,original_generated_crosscheck=True))
