"""Regression drivers must fail when a comparison or sensitivity check fails."""
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'experiments/xrt/tests/insn_diff' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ValidationGates(unittest.TestCase):
    def test_failed_compare_cannot_use_stale_results(self):
        mod = load('run')
        with tempfile.TemporaryDirectory(dir=ROOT / 'out') as tmp, \
                patch.object(mod, 'BUILD', tmp), patch.object(mod.sys, 'argv', ['run.py']), \
                patch.object(mod, 'step', side_effect=lambda name, cmd: int(name == 'compare')):
            self.assertEqual(mod.main(), 1)

    def test_failed_mutation_step_propagates(self):
        mod = load('run')
        with tempfile.TemporaryDirectory(dir=ROOT / 'out') as tmp, \
                patch.object(mod, 'BUILD', tmp), patch.object(mod.sys, 'argv', ['run.py', '--mutation-check']), \
                patch.object(mod, 'step', side_effect=lambda name, cmd: int(name == 'mutation check')):
            self.assertEqual(mod.main(), 1)

    def check_incomplete_mutations(self, with_patterns):
        mod = load('mutation_check')
        with tempfile.TemporaryDirectory(dir=ROOT / 'out') as tmp:
            src = '\n'.join(old for _, old, _ in mod.MUTATIONS) if with_patterns else ''
            (Path(tmp) / 'id_lifted.c').write_text(src)
            baseline = types.SimpleNamespace(returncode=0, stdout='failed cases: 0; baseline', stderr='')
            failed_build = types.SimpleNamespace(returncode=1, stdout='injected build failure', stderr='')
            responses = [baseline] + [failed_build] * len(mod.MUTATIONS) if with_patterns else [baseline]
            with patch.object(mod, 'BUILD', tmp), patch.object(mod.subprocess, 'run', side_effect=responses):
                self.assertEqual(mod.main(), 1)

    def test_missing_mutation_patterns_fail(self):
        self.check_incomplete_mutations(False)

    def test_mutant_build_failures_fail(self):
        self.check_incomplete_mutations(True)


if __name__ == '__main__':
    unittest.main()
