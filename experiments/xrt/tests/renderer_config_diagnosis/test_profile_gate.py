import copy
import unittest
from test_observer import Target,Context
from common import *
from profile_gate import capture,require_exact


class ProfileEvidence(unittest.TestCase):
    def read(self,t,renderer=0x10000):return capture(t.cap,renderer,t.cap.configuration_profile,t.cs,[0x696f323,t.obj['guest'],0x50000],t.obj,Context())
    def test_exact32_only(self):
        t=Target();r=self.read(t);require_exact(r);self.assertEqual(r['fields'][0]['observed'],32)
        t.u32(t.cap.guest_base+0x140d0,1)
        with self.assertRaises(core.Rejected):require_exact(self.read(t))
    def test_multiple_mismatches_all_fields_recorded(self):
        t=Target();t.u32(t.cap.guest_base+0x140d0,1);t.u32(t.cap.guest_base+0x14124,2)
        r=self.read(t);self.assertEqual(len(r['fields']),10);self.assertEqual(len(r['mismatches']),2)
        self.assertEqual(r['profile_digest'],core.digest(t.cap.configuration_profile))
        with self.assertRaisesRegex(core.Rejected,'0x40d0.*0x4124'):require_exact(r)
        self.assertTrue(any(x['offset']=='0x60' for x in r['fields']))
    def test_invalid_bases_record_inventory_without_invalid_reads(self):
        for base in (0,1,-4,0xfffffff0,0x100000004,None):
            with self.subTest(base=base):
                t=Target();r=self.read(t,base);self.assertEqual(len(r['fields']),10)
                self.assertTrue(all(x.get('error') for x in r['fields']))
                with self.assertRaises(core.Rejected):require_exact(r)
    def test_unreadable_field_does_not_short_circuit_later_fields(self):
        t=Target();mem=t.cap.mem
        def fail(p,n):
            if p==t.cap.guest_base+0x14124:raise OSError('fixture unreadable field')
            return mem(p,n)
        t.cap.mem=fail;r=self.read(t)
        self.assertEqual(r['fields'][-1]['offset'],'0x60');self.assertTrue(r['fields'][-1]['match'])
        with self.assertRaisesRegex(core.Rejected,'0x4124.*unreadable'):require_exact(r)
    def test_evidence_write_failure_rejects_before_any_acceptance(self):
        t=Target();original=t.cap.log
        def fail(kind,**v):
            if kind=='renderer_profile_field' and v['offset']=='0x4124':raise OSError('fixture evidence write error')
            original(kind,**v)
        t.cap.log=fail
        with self.assertRaises(OSError):self.read(t)
        self.assertTrue(any(r['kind']=='renderer_profile_context' for r in t.cap.rows))
        self.assertFalse(any(r['kind']=='renderer_profile_evaluation' for r in t.cap.rows))
    def test_guest_translation_not_narrowed_and_target_memory_unchanged(self):
        t=Target();c=t.cap;base=0xfff00000;c.setres_entry['renderer']=base;c.setres_entry['cpu']['registers']['ecx']=base
        for offset,value in c.configuration_profile['fields'].items():t.u32(c.guest_base+base+int(offset,0),value)
        for i,value in enumerate(c.configuration_profile['caps']['caps']):t.u32(c.guest_base+base+0x4134+4*i,value)
        t.u32(c.guest_base+base+0x4698,t.obj['guest']);t.u32(c.guest_base+0x1805c,base)
        before=t.memory.copy();r=self.read(t,base);require_exact(r)
        self.assertGreater(r['fields'][0]['host_address'],0xffffffff);self.assertEqual(before,t.memory)
    def test_renderer_vtable_bound_to_recorded_entry_identity(self):
        t=Target();t.cap.setres_entry['sources']={'renderer_raw':'e8e39706'}
        with self.assertRaisesRegex(core.Rejected,'renderer_vtable'):require_exact(self.read(t))
        t.u32(t.cap.guest_base+0x10000,0x697e3e8);require_exact(self.read(t))


if __name__=='__main__':unittest.main()
