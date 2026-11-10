import sys,unittest,copy,struct,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import gpu_evidence as E
def sample(arch,translated):
    rows=[];native_regs=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else [0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
    fx=bytearray(512);fx[:2]=b'\x7f\x02';struct.pack_into('<I',fx,24,0x3f80)
    for index,slot in enumerate(E.SLOTS):
        nargs=E.nargs(index,slot)
        before=bytearray(416);struct.pack_into('<I',before,16,0x2000);after=bytearray(before)
        if translated:struct.pack_into('<I',after,16,0x2000+4*(nargs+1));struct.pack_into('<I',after,64,0x98765432)
        rows.append(dict(kind='resource-call',slot=slot,nargs=nargs,hr=0,last_error=0,nonnull=False,stack_delta=0,regs=native_regs.copy(),xmm=(bytes(160) if arch=='x86' else struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10).hex(),pre=fx.hex(),post=fx.hex(),cpu_before=before.hex(),cpu_after=after.hex()))
    rows +=[dict(kind='resource-pixels',mode=i,changed=1234,hash=4321) for i in range(3)]
    rows +=[dict(kind='semantic-create',hr=0,width=800,height=600),dict(kind='semantic-ownership',add=3,balance=2,parent_hr=0,same_parent=True,parent_release=1,creation_hr=0,same_window=True,flags=0x42)]
    rows +=[dict(kind='resource-summary',calls=len(E.SLOTS),synthetic_only=True,game_scene=False),dict(kind='semantic-summary',calls=len(E.SLOTS),translated=translated,group=1),dict(kind='semantic-cleanup',device_release=0,parent_release=0,destroyed=True,unregistered=True,free_d3d8=True,free_d3d9=True,guest_freed=True,window_valid=False,d3d8_loaded=False,d3d9_loaded=False)]
    return rows
class Tests(unittest.TestCase):
    def groups(self):return [sample('x86',False),sample('x64',False),sample('x64',True)]
    def test_valid_synthetic_only(self):
        r=E.compare(self.groups());self.assertTrue(r['raw_comparison_passed']);self.assertFalse(r['formal_physical_acceptance']);self.assertFalse(r['game_scene_verified'])
    def test_corruptions(self):
        for mutation in ('missing','duplicate','order','hr','error','regs','stack','fx','cpu','pixels','cleanup','summary'):
            with self.subTest(mutation=mutation):
                groups=self.groups();rows=groups[2]
                if mutation=='missing':rows.pop(0)
                elif mutation=='duplicate':rows.insert(0,copy.deepcopy(rows[0]))
                elif mutation=='order':rows[0],rows[2]=rows[2],rows[0]
                elif mutation=='hr':rows[0]['hr']=0x80004005
                elif mutation=='error':rows[0]['last_error']=5
                elif mutation=='regs':rows[0]['regs'][0]^=1
                elif mutation=='stack':rows[0]['stack_delta']=4
                elif mutation=='fx':rows[0]['post']='00'*512
                elif mutation=='cpu':rows[0]['cpu_after']='00'*416
                elif mutation=='pixels':next(r for r in rows if r['kind']=='resource-pixels')['changed']=0
                elif mutation=='cleanup':rows[-1]['device_release']=1
                else:rows[-2]['calls']=0
                with self.assertRaises(E.base.Invalid):E.compare(groups)
    def test_creation_ownership_and_argument_corruption(self):
        mutations=[('semantic-create','hr',0x80004005),('semantic-create','width',640),
                   ('semantic-ownership','same_parent',False),('semantic-ownership','same_window',False),
                   ('semantic-ownership','balance',99),('semantic-ownership','flags',0),
                   ('semantic-summary','group',2),('resource-call','nargs',1)]
        for kind,key,value in mutations:
            with self.subTest(kind=kind,key=key):
                groups=self.groups()
                # Even identical corruption across all three outputs must fail.
                for rows in groups:next(r for r in rows if r['kind']==kind)[key]=value
                with self.assertRaises(E.base.Invalid):E.compare(groups)
        for kind in ('semantic-create','semantic-ownership'):
            for duplicate in (False,True):
                groups=self.groups();rows=groups[2];row=next(r for r in rows if r['kind']==kind)
                if duplicate:rows.append(copy.deepcopy(row))
                else:rows.remove(row)
                with self.assertRaises(E.base.Invalid):E.compare(groups)
    def test_group_count(self):
        for count in (0,1,2,4):
            groups=(self.groups()*2)[:count]
            with self.assertRaises(E.base.Invalid):E.compare(groups)
    def test_saved_output_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'stdout.txt'
            rows=self.groups()[2]
            path.write_text('ordinary fixture diagnostic\n'+''.join('  '+json.dumps(r)+'\n' for r in rows))
            self.assertEqual(E.read_rows(path),rows)
            for raw in (b'{"kind":"resource-call","hr":1,"hr":0}\n',
                        b'{"kind":"resource-call","hr":NaN}\n',
                        b'{"kind":"resource-call","hr":Infinity}\n',
                        b'{"kind":"resource-call",\n',b'{"hr":0}\n',b'no evidence\n'):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(E.base.Invalid):E.read_rows(path)
    def test_integer_encodings(self):
        for key,value in [('hr',-1),('hr',False),('hr',0.0),('last_error',-1),('last_error',0x100000000),('last_error',False)]:
            with self.subTest(key=key,value=value):
                groups=self.groups()
                for rows in groups:rows[0][key]=value
                with self.assertRaises(E.base.Invalid):E.compare(groups)
if __name__=='__main__':unittest.main()
