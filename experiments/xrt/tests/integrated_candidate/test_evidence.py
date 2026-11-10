import sys,importlib.util,copy,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import gpu_evidence as E
# Load prior synthetic builders with their own parser, avoiding module-name aliasing.
spec=importlib.util.spec_from_file_location('prior_test_resources',Path(__file__).resolve().parent.parent/'resource_frame/test_evidence.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);old.E=E.prior
def sample(arch,t):
    rows=old.sample(arch,t);calls=[r for r in rows if r['kind']=='resource-call'];extra=[]
    for r in calls:
        r['nonnull']=r['slot'] in (20,23,24,32,33,300,303,315)
        if r['slot']==313:
            r['hr']=4
            if t:
                raw=bytearray.fromhex(r['cpu_after']);struct.pack_into('<I',raw,0,4);r['cpu_after']=raw.hex()
    for slot,n in E.TRANSFER:
        r=copy.deepcopy(calls[0]);r.update(kind='transfer-call',slot=slot,nargs=n,hr=0x8876086c if slot==30 else 0,nonnull=slot in (16,25,26,27))
        raw=bytearray.fromhex(r['cpu_before'])
        if t:struct.pack_into('<I',raw,0,r['hr']);struct.pack_into('<I',raw,16,0x2000+4*(n+1));struct.pack_into('<I',raw,64,0x98765432)
        r['cpu_after']=raw.hex();extra.append(r)
    rows[len(calls)-11:len(calls)-11]=extra
    hash=E.expected_copy_hash()
    rows.append(dict(kind='transfer-pixels',pixels=64,hash=hash))
    for kind in ('resource-summary','semantic-summary'):E.base.one(rows,kind)['calls']+=len(extra)
    return rows
class Tests(unittest.TestCase):
    def test_resource_output_and_mip_corruption(self):
        for slot,key,value in ((20,'nonnull',False),(32,'nonnull',False),(313,'hr',0),(33,'nonnull',1)):
            groups=self.groups()
            for rows in groups:next(r for r in rows if r['kind']=='resource-call' and r['slot']==slot)[key]=value
            with self.assertRaises(E.base.Invalid):E.compare(groups)
    def test_copy_pattern_detects_ignored_or_wrong_destination(self):
        pixels=[[0xff300000|(y<<8)|x for x in range(8)] for y in range(8)]
        def digest(grid):
            value=2166136261
            for row in grid:
                for pixel in row:value=((value^pixel)*16777619)&0xffffffff
            return value
        self.assertNotEqual(digest(pixels),E.expected_copy_hash())
        correct=copy.deepcopy(pixels)
        for y in range(4):
            for x in range(4):correct[y+4][x+4]=pixels[y][x]
        self.assertEqual(digest(correct),E.expected_copy_hash())
        wrong=copy.deepcopy(pixels)
        for y in range(4):
            for x in range(4):wrong[y+3][x+3]=pixels[y][x]
        self.assertNotEqual(digest(wrong),E.expected_copy_hash())
    def groups(self):return [sample('x86',False),sample('x64',False),sample('x64',True)]
    def test_synthetic_not_acceptance(self):
        result=E.compare(self.groups());self.assertTrue(result['raw_comparison_passed']);self.assertFalse(result['formal_physical_acceptance'])
    def test_corruption_even_if_identical(self):
        for mutation in ('missing','duplicate','arity','hr','null','cpu','fx','readback','count','order','native_failure','bool_hr','error'):
            with self.subTest(mutation=mutation):
                groups=self.groups()
                for rows in groups:
                    r=next(r for r in rows if r['kind']=='transfer-call');idx=rows.index(r)
                    if mutation=='missing':rows.remove(r)
                    elif mutation=='duplicate':rows.insert(idx,copy.deepcopy(r))
                    elif mutation=='arity':r['nargs']=1
                    elif mutation=='hr':r['hr']=0x80004005
                    elif mutation=='null':r['nonnull']=False
                    elif mutation=='cpu':r['cpu_after']='00'*416
                    elif mutation=='fx':r['post']='00'*512
                    elif mutation=='readback':E.base.one(rows,'transfer-pixels')['hash']=0
                    elif mutation=='count':E.base.one(rows,'resource-summary')['calls']=0
                    elif mutation=='order':rows[idx],rows[0]=rows[0],rows[idx]
                    elif mutation=='native_failure':next(v for v in rows if v['kind']=='transfer-call' and v['slot']==30)['hr']=0
                    elif mutation=='bool_hr':r['hr']=False
                    else:r['last_error']=-1
                with self.assertRaises(E.base.Invalid):E.compare(groups)
if __name__=='__main__':unittest.main()
