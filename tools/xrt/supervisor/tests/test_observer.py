"""Retained production observer integration; only disposable non-game debuggees."""
import ast
import inspect
import os
from pathlib import Path
import sys
from types import MethodType
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from supervisor import core, observer_checks
from supervisor.windows import BoundedLoop


class ObserverIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = Path(os.environ.get('SUPERVISOR_TEST_OUTPUT', core.ROOT / 'out'))
        cls.out = parent / ('observer-regression-' + str(uuid.uuid4()))
        cls.out.mkdir()

    def directory(self):
        out = self.out / self._testMethodName; out.mkdir()
        return out

    def test_original_partial_binding_fails_at_create_event(self):
        out = self.directory()
        capture, _, _ = observer_checks.prepare(out, integrated=False)
        # Reproduce precisely the original adapter, without inheriting the mixin.
        capture.run = MethodType(BoundedLoop.run, capture)
        capture.on_debugbreak = MethodType(BoundedLoop.on_debugbreak, capture)
        self.assertFalse(hasattr(capture, 'module_record'))
        with self.assertRaisesRegex(AttributeError, "has no attribute 'module_record'"):
            observer_checks.execute(capture, out, [str(observer_checks.STREAM_EXE)])
        self.assertTrue(capture.cleanup['passed'])
        self.assertEqual(capture.cleanup['remaining_job_processes'], 0)
        self.assertFalse(any(r['kind'] == 'process_created' for r in capture.rows))
        self.assertTrue(any(r['kind'] == 'terminated_before_continue' and r.get('observation_failed') for r in capture.rows))
        core.atomic(out / 'result.json', dict(passed=True, original_AttributeError_reproduced=True,
                    terminated_before_first_continue=True, cleanup=capture.cleanup, genuine_sessions=0))

    def test_complete_binding_and_retained_interface(self):
        capture, _, _ = observer_checks.prepare(self.directory())
        for name, method in vars(BoundedLoop).items():
            if not name.startswith('_') and callable(method):
                self.assertIs(getattr(capture, name).__func__, method, name)
                self.assertIs(getattr(capture, name).__self__, capture, name)
        # Audit every direct self access in the bounded loop against the actual
        # retained instance and attributes assigned by the loop, not a fake Probe.
        tree = ast.parse(inspect.getsource(BoundedLoop))
        reads, writes = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self':
                (writes if isinstance(node.ctx, ast.Store) else reads).add(node.attr)
        self.assertEqual(reads - writes - set(dir(capture)), set())
        core.atomic(self.out / 'interface-audit.json', dict(passed=True, read_attributes=sorted(reads),
                    assigned_by_loop=sorted(writes), missing=[], retained_class_mro=[c.__name__ for c in type(capture).__mro__]))

    def test_unidentifiable_module_handle_rejected(self):
        capture, _, _ = observer_checks.prepare(self.directory())
        with self.assertRaisesRegex(core.IntegrityFailure, 'no verifiable file handle'):
            capture.module_record(None)

if __name__ == '__main__': unittest.main()
