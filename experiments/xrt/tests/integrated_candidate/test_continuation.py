import sys,struct,copy,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from continuation import verify_pair
from common import core,GUEST

def evidence():
    raw=bytearray(416)
    for off,value in ((4,0x1234),(16,0x100),(68,0x1090ed59)):struct.pack_into('<I',raw,off,value)
    entry=dict(tid=7,cpu=0x10000,raw=raw.hex())
    for off,value in ((16,0x104),(64,GUEST),(68,0x1038fba9)):struct.pack_into('<I',raw,off,value)
    events=[dict(seq=1,thread=0,kind='engine_init_call',this=0x1234,esp=0x100,return_=GUEST),
            dict(seq=2,thread=0,kind='engine_init_return',this=0x1234,esp_before=0x100,esp_after=0x104,return_=GUEST,actual_return=GUEST)]
    for r in events:r['return']=r.pop('return_')
    return entry,raw,events

class Tests(unittest.TestCase):
    def test_pair(self):
        e,r,ev=evidence();self.assertTrue(verify_pair(e,r,ev,7,0x10000)['passed'])
    def test_reject_corruption(self):
        for case in ('entry','cpu','tid','esp','rv','pc','nonvolatile','object','duplicate','missing','thread','gap','truncated','tick','fatal','return'):
            with self.subTest(case=case):
                e,r,ev=evidence();tid=7;ptr=0x10000
                if case=='entry':e=None
                elif case=='cpu':ptr+=4
                elif case=='tid':tid+=1
                elif case in ('esp','rv','pc','nonvolatile'):r[dict(esp=16,rv=64,pc=68,nonvolatile=12)[case]]^=1
                elif case=='object':ev[1]['this']+=4
                elif case=='duplicate':ev.append(dict(ev[-1],seq=3))
                elif case=='missing':ev.pop()
                elif case=='thread':ev[1]['thread']=1
                elif case=='gap':ev[1]['seq']=3
                elif case=='truncated':ev[1]['truncated']=True
                elif case in ('tick','fatal'):ev.append(dict(seq=3,thread=0,kind='engine_tick_call' if case=='tick' else 'fatal'))
                else:ev[1]['actual_return']+=1
                with self.assertRaises(core.Rejected):verify_pair(e,r,ev,tid,ptr)

if __name__=='__main__':unittest.main()
