import sys,unittest,types,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from composition import construct,schedule
from supervisor.windows import BoundedLoop

class Tests(unittest.TestCase):
    def test_actual_candidate_construction_is_not_activation(self):
        plan=read(O/'composed-mapping.json')
        out=O/('construction-'+str(uuid.uuid4()));out.mkdir()
        capture=construct(out,plan,lambda _:self.fail('environment invoked during construction'),[])
        self.assertIs(capture.run.__func__,BoundedLoop.run)
        self.assertEqual(capture.created,0)
        self.assertTrue(capture._fatal_evidence_installed)
        # Observe the refusal without starting any process or touching game code.
        rows=[];capture.log=lambda kind,**kw:rows.append(dict(kind=kind,**kw))
        with self.assertRaisesRegex(core.Rejected,'coverage incomplete'):
            capture.on_create(None)
        self.assertEqual(rows[0]['kind'],'monitor_coverage_gate')
        self.assertFalse(rows[0]['genuine_interval_qualified'])

    def test_scheduler_never_drops_fatal_or_endpoint(self):
        cap=types.SimpleNamespace(base=0x1000,breakpoints={0x2000:'fatal_entry',0x3000:'native',0x4000:'callback'},sym=lambda _:0x2000)
        points=schedule(cap,dict(stop_rva=0x4000))
        self.assertEqual(len(points),4)
        self.assertEqual(points[0x5000],'init_return')
        cap.breakpoints[0x6000]='extra'
        with self.assertRaisesRegex(core.Rejected,'four hardware slots'):schedule(cap,dict(stop_rva=0x4000))
        cap.breakpoints={0x2000:'not-fatal'}
        with self.assertRaisesRegex(core.Rejected,'fatal monitoring absent'):schedule(cap,dict(stop_rva=0x4000))

    def test_endpoint_collision_is_rejected(self):
        cap=types.SimpleNamespace(base=0x1000,breakpoints={0x2000:'fatal_entry'},sym=lambda _:0x2000)
        with self.assertRaisesRegex(core.Rejected,'endpoint collision'):schedule(cap,dict(stop_rva=0x1000))

    def test_real_coverage_hold_cannot_be_misread_as_ready(self):
        coverage=read(O/'coverage.json')
        self.assertFalse(coverage['complete'])
        self.assertFalse(coverage['genuine_execution_ready'])
        self.assertIn(20,coverage['unqualified_literal_slots'])
        self.assertEqual(coverage['strict_native_x86_compatibility'],'FAILED')

if __name__=='__main__':unittest.main(verbosity=2)
