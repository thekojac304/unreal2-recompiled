import copy
import json
import unittest
from common import *
from attach_audit import audit
from evidence import runtime_pair


class PairAudits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=OLD/'owner-fa3b112f-189a-422b-ac3c-ea197a910de6/runtime-events.json'
        cls.attach=[r for r in read(p)['events'] if r['kind'].startswith('gui_attach_thread_input_')]
        p=pathlib.Path(read(O/'paired-debugger-validation.json')['evidence'])/'initial'
        cls.events=read(p/'runtime-events.json')['events']
        rows=[json.loads(s) for s in (p/'debug-observations.jsonl').read_text().splitlines()]
        cls.entry=next(r for r in rows if r['kind']=='setres_entry_raw')
        cls.returned=next(r for r in rows if r['kind']=='initial_setres_return_raw')
    def test_actual_optional_self_pair(self):
        self.assertEqual(audit(self.attach)['pairs'],2);self.assertEqual(audit([])['pairs'],0)
    def test_attach_pair_negative_guards(self):
        for kind in ('missing','repeat','cross-thread','other-self-thread','flag','result','error','esp','return'):
            with self.subTest(kind=kind):
                rows=copy.deepcopy(self.attach)
                if kind=='missing':rows=rows[:2]
                elif kind=='repeat':rows=rows+rows
                elif kind=='cross-thread':rows[0]['to']+=1
                elif kind=='other-self-thread':
                    for r in rows[2:]:r['from']+=1;r['to']+=1
                elif kind=='flag':rows[-1]['attach']=1
                elif kind=='result':rows[-1]['result']=1
                elif kind=='error':rows[-1]['last_error']=0
                elif kind=='esp':rows[-1]['esp_after']+=4
                else:rows[-1]['actual_return']+=1
                with self.assertRaises(core.Rejected):audit(rows)
    def test_runtime_debugger_actual_raw_match(self):
        runtime_pair(self.events,self.entry,self.returned)
    def test_runtime_pair_negatives(self):
        for kind in ('cpu','frame','missing','caller','id','eax','esp'):
            with self.subTest(kind=kind):
                events=copy.deepcopy(self.events);bounds=[r for r in events if r['kind']=='setres_boundary']
                if kind=='cpu':next(r for r in events if r['kind']=='setres_raw' and r['area']=='cpu')['hex']='ff'*128
                elif kind=='frame':next(r for r in events if r['kind']=='setres_raw' and r['area']=='frame')['hex']='00'*24
                elif kind=='missing':events.remove(bounds[-1])
                elif kind=='caller':bounds[0]['site']=0x696d2ca
                elif kind=='id':bounds[-1]['id']+=1
                elif kind=='eax':bounds[-1]['eax']=0
                else:bounds[-1]['esp']+=4
                with self.assertRaises(core.Rejected):runtime_pair(events,self.entry,self.returned)


if __name__=='__main__':unittest.main()
