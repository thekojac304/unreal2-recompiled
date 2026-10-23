"""Safety gates: altered bytes, added files and filesystem aliases must stop runs."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asset_boundary as A


class BoundaryTests(unittest.TestCase):
    def test_changed_added_and_missing_inputs_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'inputs'
            root.mkdir()
            p = root / 'asset'
            p.write_bytes(b'original')
            m = dict(root=str(root), files=A.inventory(root), protected_trees=[], protected_files={})
            manifest = Path(d) / 'manifest.json'
            manifest.write_text(json.dumps(m))
            with patch.dict(os.environ, XRT_ASSET_MANIFEST=str(manifest)):
                A.verify()
                p.write_bytes(b'changed')
                with self.assertRaisesRegex(RuntimeError, 'protected inputs changed'):
                    A.verify()
                p.write_bytes(b'original')
                extra = root / 'extra'
                extra.write_bytes(b'new')
                with self.assertRaises(RuntimeError):
                    A.verify()
                extra.unlink()
                p.unlink()
                with self.assertRaises(RuntimeError):
                    A.verify()

    def test_hardlinked_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'asset'
            p.write_bytes(b'original')
            os.link(p, Path(d) / 'alias')
            with self.assertRaisesRegex(RuntimeError, 'hardlinked input'):
                A.inventory(d)

    def test_missing_manifest_has_no_install_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, XRT_ASSET_MANIFEST=str(Path(d) / 'missing.json')):
                with self.assertRaises(FileNotFoundError):
                    A.source()

    def test_destination_cannot_overwrite_or_nest_in_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            (ws / 'sandbox_cmp').mkdir()
            protected = ws / 'sandbox_cmp/evidence'
            m = dict(root=str(ws / 'sandbox_inputs/content'), protected_files={},
                     protected_trees=[dict(root=str(protected))])
            with patch.object(A, 'WS', ws), patch.object(A, 'manifest', return_value=m):
                for p in [protected, protected / 'child', ws / 'sandbox_cmp']:
                    with self.assertRaisesRegex(RuntimeError, 'overlaps protected input'):
                        A.check_writable(p)
                A.check_writable(ws / 'sandbox_cmp/new-run')
