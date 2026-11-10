"""Focused non-game tests: missing startup evidence, instance routing and fail-stop."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

from observer_evidence import DIALOG_FORMAT, fatal_record, install, capture_cstring


class Context:
    def __init__(self):
        self.regs = dict(rsp=0x1000, rdx=76, r8=0x2000, rcx=0x3000, r9=61)

    def get(self, name):
        return self.regs[name]

    def snapshot(self):
        return dict(registers=self.regs.copy())


class Capture:
    def __init__(self):
        self.created = 0
        self.rows = []
        self.cpu = None
        self.events_snapshotted = False
        self.delegated = []
        self.stack = bytearray(64)
        struct.pack_into('<Q', self.stack, 0, 0x55555555)
        struct.pack_into('<Q', self.stack, 40, 0xffffffff)
        struct.pack_into('<Q', self.stack, 48, 0xfffffffc)

    def mem(self, p, size):
        assert 0x1000 <= p and p + size <= 0x1040
        return bytes(self.stack[p-0x1000:p-0x1000+size])

    def u64(self, p):
        if p == 0x4000:
            return 0x70000000
        return struct.unpack('<Q', self.mem(p, 8))[0]

    def cstring(self, p):
        assert p == 0x2000
        return DIALOG_FORMAT

    def cpu_state(self, p):
        assert p == 0x3000
        return dict(pc=0x1090437f, registers=dict(esp=0x120fa60))

    def sym(self, name):
        assert name == 'xrt_g'
        return 0x4000

    def words(self, p, size):
        assert p == 0x7120fa60 and size == 40
        return list(range(size))

    def snapshot_events(self):
        self.events_snapshotted = True

    def hit(self, tag, ctx, tid):
        self.delegated.append(tag)
        if tag == 'original_assertion':
            raise AssertionError('strict assertion retained')


class EvidenceTests(unittest.TestCase):
    def test_string_pointer_is_copied_before_termination_and_is_not_reformatted(self):
        c=Capture();ctx=Context();ctx.regs['r9']=0x8000
        c.cstring=lambda p:'%s'
        text=b'DirectMusic fixture value 100% %x (Win32 123)\0'
        original=c.mem
        c.mem=lambda p,n:text[p-0x8000:p-0x8000+n] if 0x8000<=p<0x8000+len(text) else original(p,n)
        r=fatal_record(c,ctx,53072)
        self.assertEqual(r['formatted_message'],text[:-1].decode())
        self.assertEqual(bytes.fromhex(r['string_arguments'][0]['raw_hex']),text[:-1])
        self.assertTrue(r['string_arguments'][0]['terminated'])

    def test_unreadable_string_keeps_format_pointer_and_cpu_without_fabrication(self):
        c=Capture();ctx=Context();ctx.regs['r9']=0x8000;c.cstring=lambda p:'%s'
        r=fatal_record(c,ctx,53072)
        self.assertNotIn('formatted_message',r)
        self.assertIn('string argument:',r['diagnostic_read_errors'][0])
        self.assertEqual(r['raw_integer_arguments'][0],0x8000)
        self.assertEqual(r['cpu']['pc'],0x1090437f)

    def test_bounded_string_is_retained_without_claiming_termination(self):
        c=Capture();c.mem=lambda p,n:b'X'*n
        r=capture_cstring(c,0x8000,8)
        self.assertFalse(r['terminated']);self.assertEqual(r['raw_hex'],'58'*8)

    def test_stack_top_captures_every_available_word_without_crossing_mapping(self):
        c = Capture()
        c.cpu_state = lambda p: dict(pc=0x1090437f, fs_base=0x12000, registers=dict(esp=0x120fff0))
        def bounded(p,n):
            if p==0x70012004 and n==2:return [0x1210000,0x1200000]
            assert p==0x7120fff0 and n==4
            return [1,2,3,4]
        c.words=bounded
        r=fatal_record(c,Context(),53072)
        self.assertEqual(r['guest_stack'],[1,2,3,4])
        self.assertEqual(r['diagnostic_read_errors'],[])
        self.assertTrue(r['guest_stack_bounds']['bounded_at_stack_top'])

    def test_pre_device_fatal_has_arguments_cpu_and_stack(self):
        c = Capture()
        self.assertIsNone(c.cpu)
        r = fatal_record(c, Context(), 53072)
        self.assertEqual(r['raw_integer_arguments'], [61, 0xffffffff, 0xfffffffc])
        self.assertEqual(r['formatted_message'], 'dialog callback message 0x3d unsupported (wp=ffffffff lp=fffffffc)')
        self.assertEqual(r['cpu']['pc'], 0x1090437f)
        self.assertEqual(len(r['guest_stack']), 40)
        self.assertEqual(r['diagnostic_read_errors'], [])
        self.assertFalse(r['runtime_fatal_body_executed'])

    def test_fatal_is_recorded_in_fresh_instance_directory_before_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = install(Capture(), tmp)
            with self.assertRaisesRegex(RuntimeError, 'no continuation.*0x3d'):
                c.hit('fatal_entry', Context(), 53072)
            self.assertTrue(c.events_snapshotted)
            self.assertEqual(c.delegated, [])
            rows = [json.loads(s) for s in (Path(tmp)/'debug-observations.jsonl').read_text().splitlines()]
            self.assertEqual(rows, c.rows)
            self.assertEqual(rows[0]['decoded_arguments'], dict(message=61, wp=0xffffffff, lp=0xfffffffc))

    def test_independent_instances_do_not_share_global_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'a', Path(tmp)/'b'
            a.mkdir(); b.mkdir()
            ca, cb = install(Capture(), a), install(Capture(), b)
            ca.log('first'); cb.log('second')
            self.assertEqual(json.loads((a/'debug-observations.jsonl').read_text())['kind'], 'first')
            self.assertEqual(json.loads((b/'debug-observations.jsonl').read_text())['kind'], 'second')

    def test_existing_logs_cannot_be_appended_to_by_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'debug-observations.jsonl'
            p.write_bytes(b'original failure\n')
            with self.assertRaises(FileExistsError):
                install(Capture(), tmp)
            self.assertEqual(p.read_bytes(), b'original failure\n')

    def test_nonfatal_strict_assertions_are_delegated_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = install(Capture(), tmp)
            with self.assertRaisesRegex(AssertionError, 'strict assertion retained'):
                c.hit('original_assertion', Context(), 53072)

    def test_unreadable_guest_stack_does_not_destroy_fatal_arguments(self):
        c = Capture()
        def no_words(*args):
            raise OSError('unreadable')
        c.words = no_words
        r = fatal_record(c, Context(), 53072)
        self.assertEqual(r['decoded_arguments']['message'], 61)
        self.assertIn('unreadable', r['diagnostic_read_errors'][0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
