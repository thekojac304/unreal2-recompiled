"""Mutation tests: synthetic evidence must never qualify a physical run."""
import sys,copy,struct,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import gpu_evidence as G
from milestones import analyze,capture

def group(arch,translated):
    regs=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else [
        0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,
        0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
    fp=bytearray(512);fp[:2]=b'\x7f\x02';struct.pack_into('<I',fp,24,0x3f80)
    rows=[dict(kind='semantic-create',hr=0,width=800,height=600),
        dict(kind='semantic-ownership',same_parent=True,same_window=True,parent_hr=0,creation_hr=0,add=2,balance=1,flags=0x42)]
    for slot in G.SLOTS:
        before=bytes(416);after=bytearray(before)
        if translated:
            struct.pack_into('<I',after,16,4*(G.NARGS[slot]+1));struct.pack_into('<I',after,64,0x98765432)
        rows.append(dict(kind='bringup-scene-call',slot=slot,hr=0,last_error=0,regs=regs[:],stack_delta=0,
            pre=fp.hex(),post=fp.hex(),xmm=(bytes(160) if arch=='x86' else
                struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10).hex(),
            cpu_before=before.hex(),cpu_after=after.hex()))
    rows.append(dict(kind='bringup-viewport',bytes=struct.pack('<6I',0,0,800,600,0,0x3f800000).hex()))
    for mode in range(3):
        rows.extend([dict(kind='bringup-pixels',mode=mode,get_hr=0,lock_hr=0,unlock_hr=0,changed_pixels=1000,rgb_hash=123),
            dict(kind='bringup-present',mode=mode,hr=0)])
    rows.extend([dict(kind='semantic-cleanup',device_release=0,parent_release=0,destroyed=True,unregistered=True,
        free_d3d8=True,free_d3d9=True,guest_freed=True,window_valid=False,d3d8_loaded=False,d3d9_loaded=False),
        dict(kind='semantic-summary',calls=16,translated=translated)])
    return rows

class Evidence(unittest.TestCase):
    def setUp(self):self.groups=[group('x86',False),group('x64',False),group('x64',True)]
    def test_good_synthetic_still_not_acceptance(self):
        result=G.compare(self.groups);self.assertTrue(result['raw_comparison_passed']);self.assertFalse(result['formal_physical_acceptance'])
    def test_mutations_rejected(self):
        changes=[
            ('bringup-scene-call','hr',0x80004005),('bringup-scene-call','last_error',5),
            ('bringup-scene-call','stack_delta',8),('bringup-scene-call','regs',[0]*8),
            ('bringup-scene-call','post','00'*512),('bringup-scene-call','xmm','00'*160),
            ('bringup-scene-call','cpu_after','00'*416),('bringup-viewport','bytes','00'*24),
            ('bringup-pixels','changed_pixels',0),('bringup-pixels','rgb_hash',456),
            ('bringup-present','hr',0x80004005),('semantic-cleanup','device_release',1),
            ('semantic-cleanup','window_valid',True),('semantic-summary','calls',15)]
        for kind,key,value in changes:
            with self.subTest(kind=kind,key=key):
                gs=copy.deepcopy(self.groups);next(r for r in gs[2] if r['kind']==kind)[key]=value
                with self.assertRaises(G.Invalid):G.compare(gs)
    def test_missing_and_duplicate(self):
        for duplicate in (False,True):
            gs=copy.deepcopy(self.groups)
            if duplicate:gs[0].append(gs[0][-1])
            else:gs[0].pop()
            with self.assertRaises(G.Invalid):G.compare(gs)
    def test_pairing_and_selected_world(self):
        rows=[dict(kind='level_tick_call',seq=1,thread=0,this=123,world=123,esp=1000,**{'return':9}),
            dict(kind='level_tick_return',seq=2,thread=0,this=123,world=123,esp_before=1000,esp_after=1012,actual_return=9,**{'return':9})]
        self.assertTrue(analyze(rows,123)['evidence_consistent'])
        self.assertFalse(analyze(rows,124)['evidence_consistent'])
        self.assertFalse(analyze(rows)['evidence_consistent'])
        self.assertFalse(analyze(rows[1:],123)['evidence_consistent'])
        rows[1]['esp_after']=1016;self.assertFalse(analyze(rows,123)['evidence_consistent'])
    def test_incomplete_init_does_not_claim_return(self):
        result=analyze([dict(kind='engine_init_call',seq=1,thread=0,this=123,esp=1000,**{'return':9})])
        self.assertFalse(result['engine_init_return_seen']);self.assertEqual(len(result['pending']),1)
    def test_capture_precedes_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'invalid.json';source.write_bytes(b'invalid')
            with self.assertRaises(Exception):capture(source,root/'evidence')
            self.assertEqual((root/'evidence/raw-events.json').read_bytes(),b'invalid')
            self.assertTrue((root/'evidence/analysis-error.json').exists())
if __name__=='__main__':unittest.main()
