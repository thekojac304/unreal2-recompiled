"""Owner rejection and raw evidence tests; no process launch path is called."""
import copy
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
DEST=ROOT/'out/recovery/semantic-physical-20261030-01/continuation-proposal'
sys.path.insert(0,str(DEST))
import common
import owner
import identity
import continuation_audit as audit

def pair(value):
    frame=[common.GUEST,0x1000,640,480,0,32]
    before=bytes(416);after=bytearray(before);struct.pack_into('<I',after,0,value)
    entry=dict(raw=before.hex(),cpu=dict(registers=dict(eax=0)))
    returned=dict(raw=after.hex(),cpu=dict(registers=dict(eax=value)))
    events=[]
    for phase,raw,esp,eax in [('entry',before,0x2000,0),('return',after,0x2018,value)]:
        events.append(dict(kind='setres_boundary',phase=phase,id=1,site=0x11104bf5,target=0x696e890,return_=common.GUEST,esp=esp,eax=eax,rv=common.GUEST))
        events[-1]['return']=events[-1].pop('return_')
        for offset in (0,128,256,384):events.append(dict(kind='setres_raw',id=1,phase=phase,area='cpu',offset=offset,size=416,hex=raw[offset:offset+128].hex()))
    events.append(dict(kind='setres_raw',id=1,phase='entry',area='frame',hex=struct.pack('<6I',*frame).hex()))
    return events,entry,returned,frame

class Evidence(unittest.TestCase):
    def test_noncanonical_success_and_zero_failure(self):
        for value in (0,1,32,0xffffffff):
            self.assertEqual(audit.runtime_pair(*pair(value)),'initial-setres-complete' if value else 'initial-setres-failed')
    def test_missing_cpu_chunk(self):
        args=pair(1);del args[0][2]
        with self.assertRaises(common.core.Rejected):audit.runtime_pair(*args)
    def test_altered_cpu(self):
        args=pair(1);args[2]['raw']='ff'+args[2]['raw'][2:]
        with self.assertRaises(common.core.Rejected):audit.runtime_pair(*args)
    def test_wrong_initial_caller(self):
        args=pair(1);args[0][0]['site']=0x696d2ca
        with self.assertRaises(common.core.Rejected):audit.runtime_pair(*args)
    def test_wrong_runtime_outcome(self):
        args=pair(1);args[0][5]['eax']=0
        with self.assertRaises(common.core.Rejected):audit.runtime_pair(*args)
    def test_wrong_frame(self):
        args=pair(1);args[3][2]=800
        with self.assertRaises(common.core.Rejected):audit.runtime_pair(*args)

class OwnerGates(unittest.TestCase):
    def test_noninteractive_rejects_before_seal_or_launch(self):
        with patch.object(sys.stdin,'isatty',return_value=False),patch.object(owner,'validate_seal') as gate:
            with self.assertRaises(common.core.Rejected):owner.run_once()
            gate.assert_not_called()
    def test_scoped_hold_readonly(self):
        path=common.core.HOME/'ledger.jsonl';before=common.core.sha(path);real=owner.read
        def read(p):
            if p==common.O/'physical-qualification.json':return dict(functional_qualified=True)
            return real(p)
        with patch.object(owner,'read',side_effect=read),patch.object(identity,'consumed',return_value={'unconsumed':True}) as consumed:
            ledger=owner.execution_gate();self.assertEqual(ledger.rows[-1]['sequence'],92);consumed.assert_called_once()
        self.assertEqual(common.core.sha(path),before)
    def test_changed_ledger_and_unrelated_hold_reject(self):
        real=owner.read;baseline=real(common.O/'resolved-hold.json')
        for key in ('ledger','hold'):
            changed=copy.deepcopy(baseline)
            if key=='ledger':changed['ledger_sha256']='0'*64
            else:changed['transition']['hold']['reason']='unrelated failure'
            with patch.object(owner,'read',side_effect=lambda p:changed if p==common.O/'resolved-hold.json' else real(p)),patch.object(identity,'consumed') as consumed:
                with self.assertRaises(common.core.Rejected):owner.execution_gate()
                consumed.assert_not_called()
    def test_incomplete_physical_qualification_rejects(self):
        real=owner.read
        with patch.object(owner,'read',side_effect=lambda p:dict(functional_qualified=False) if p==common.O/'physical-qualification.json' else real(p)),patch.object(identity,'consumed') as consumed:
            with self.assertRaises(common.core.Rejected):owner.execution_gate()
            consumed.assert_not_called()
    def test_stop_file_rejects(self):
        original=Path.exists
        with patch.object(Path,'exists',lambda p:True if p==common.O/'STOP' else original(p)),patch.object(identity,'consumed') as consumed:
            with self.assertRaises(common.core.Rejected):owner.execution_gate()
            consumed.assert_not_called()
    def test_candidate_consumption_rejects(self):
        real=owner.read
        with patch.object(owner,'read',side_effect=lambda p:dict(functional_qualified=True) if p==common.O/'physical-qualification.json' else real(p)),patch.object(identity,'consumed',side_effect=common.core.Rejected('consumed')):
            with self.assertRaisesRegex(common.core.Rejected,'consumed'):owner.execution_gate()

if __name__=='__main__':unittest.main()
