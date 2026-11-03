"""retention.py: python -m unittest test_retention (from tools/xrt/dev). Uses temporary folders only."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import retention

NAME = 'dev-init-20261103-120000-0a1b2c3d'


def junction(link, target):
    subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], check=True, capture_output=True)


def unlink_junction(link):
    os.rmdir(link)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        self.root = self.tmp / 'sandbox_cmp'
        self.sb = self.root / NAME
        (self.sb / 'System').mkdir(parents=True)
        (self.sb / 'Textures').mkdir()
        (self.sb / 'System' / 'Unreal2.exe').write_bytes(b'exe' * 1000)
        (self.sb / 'System' / 'Unreal2.ini').write_bytes(b'[WinDrv]\nX=1\n')
        (self.sb / 'Textures' / 'a.utx').write_bytes(b'tex' * 5000)
        self.keep = self.tmp / 'runs' / 'run' / 'sandbox-kept'
        self.baseline = retention.scan(self.sb)[0]

    def game_writes(self):
        (self.sb / 'System' / 'Unreal2.log').write_text('log')
        (self.sb / 'Save').mkdir(exist_ok=True)
        (self.sb / 'Save' / 'Save1.usa').write_bytes(b'save')
        (self.sb / 'System' / 'Unreal2.ini').write_bytes(b'[WinDrv]\nX=2\n')

    def retire(self, name=NAME, baseline='base'):
        return retention.retire_sandbox(self.root, name, self.baseline if baseline == 'base' else baseline, self.keep)

    def test_success_keeps_game_written_files_and_removes_the_sandbox(self):
        self.game_writes()
        rec = self.retire()
        self.assertEqual(rec['action'], 'removed')
        self.assertFalse(self.sb.exists())
        self.assertFalse(self.sb.with_name(NAME + '.retiring').exists())
        self.assertEqual({p['path'] for p in rec['preserved']}, {'System/Unreal2.log', 'Save/Save1.usa', 'System/Unreal2.ini'})
        self.assertEqual((self.keep / 'Save' / 'Save1.usa').read_bytes(), b'save')
        self.assertFalse((self.keep / 'Textures').exists())          # unchanged assets are not copied
        self.assertTrue(all(len(p['sha256']) == 64 for p in rec['preserved']))

    def test_failure_preserves_crash_dump_before_removal(self):
        (self.sb / 'System' / 'crash.dmp').write_bytes(b'dump' * 100)
        rec = self.retire()
        self.assertEqual(rec['action'], 'removed')
        self.assertEqual((self.keep / 'System' / 'crash.dmp').read_bytes(), b'dump' * 100)

    def test_over_budget_keeps_the_whole_sandbox(self):
        (self.sb / 'System' / 'big.dmp').write_bytes(b'x' * 100)
        with mock.patch.object(retention, 'KEEP_BYTES', 50):
            rec = self.retire()
        self.assertEqual(rec['action'], 'kept')
        self.assertTrue((self.sb / 'System' / 'big.dmp').exists())
        self.assertTrue((self.sb / 'Textures' / 'a.utx').exists())

    def test_never_launched_run_without_baseline_just_removes_copies(self):
        rec = self.retire(baseline=None)
        self.assertEqual(rec['action'], 'removed')
        self.assertEqual(rec['preserved'], [])
        self.assertFalse(self.sb.exists())

    @unittest.skipUnless(os.name == 'nt', 'directory rename lock is Windows behaviour')
    def test_active_sandbox_is_kept(self):
        self.game_writes()
        with open(self.sb / 'System' / 'Unreal2.exe', 'rb'):         # a process still using the sandbox
            rec = self.retire()
        self.assertEqual(rec['action'], 'kept')
        self.assertTrue((self.sb / 'System' / 'Unreal2.log').exists())
        self.assertTrue((self.sb / 'Textures' / 'a.utx').exists())

    def test_cancellation_while_preserving_restores_the_sandbox(self):
        self.game_writes()
        with mock.patch.object(retention.shutil, 'copy2', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.retire()
        self.assertTrue((self.sb / 'Textures' / 'a.utx').exists())
        self.assertTrue((self.sb / 'System' / 'Unreal2.log').exists())
        self.assertFalse(self.sb.with_name(NAME + '.retiring').exists())

    def test_failed_preservation_keeps_the_sandbox(self):
        self.game_writes()
        with mock.patch.object(retention.shutil, 'copy2', side_effect=OSError('disk full')):
            rec = self.retire()
        self.assertEqual(rec['action'], 'kept')
        self.assertTrue((self.sb / 'Textures' / 'a.utx').exists())

    def test_interrupted_removal_leaves_a_resumable_remainder_and_preserved_files(self):
        self.game_writes()
        real = os.unlink
        calls = []

        def flaky(path, *a, **k):
            calls.append(path)
            if len(calls) == 2:
                raise PermissionError(13, 'locked')
            return real(path, *a, **k)
        with mock.patch.object(retention.os, 'unlink', flaky):
            rec = self.retire()
        self.assertEqual(rec['action'], 'kept')
        self.assertIn('removal stopped', rec['reason'])
        self.assertTrue((self.keep / 'Save' / 'Save1.usa').exists())

    def test_refuses_names_that_are_not_a_run_sandbox(self):
        other = self.root / 'first-world'
        other.mkdir()
        (other / 'keep.txt').write_text('mine')
        for bad in ('first-world', '..', 'dev-init-latest', NAME + '.retiring', 'dev-init-20261103-120000-0a1b2c3d/..'):
            self.assertEqual(self.retire(bad)['action'], 'kept', bad)
        self.assertTrue((other / 'keep.txt').exists())
        self.assertTrue(self.sb.exists())

    def test_refuses_a_relative_root(self):
        rec = retention.retire_sandbox(Path('sandbox_cmp'), NAME, self.baseline, self.keep)
        self.assertEqual(rec['action'], 'kept')

    @unittest.skipUnless(os.name == 'nt', 'junctions')
    def test_junction_inside_the_sandbox_is_never_followed(self):
        saves = self.tmp / 'personal-saves'
        saves.mkdir()
        (saves / 'Save0.usa').write_bytes(b'personal')
        junction(self.sb / 'Save', saves)                              # like the install's Save junction
        rec = self.retire()
        self.assertEqual(rec['action'], 'kept')
        self.assertIn('Save', rec['links'])
        self.assertEqual((saves / 'Save0.usa').read_bytes(), b'personal')
        self.assertFalse(self.keep.exists())
        unlink_junction(self.sb / 'Save')

    @unittest.skipUnless(os.name == 'nt', 'junctions')
    def test_sandbox_that_is_a_junction_is_refused(self):
        target = self.tmp / 'elsewhere'
        target.mkdir()
        (target / 'precious.txt').write_text('x')
        link = self.root / 'dev-init-20261103-130000-0a1b2c3d'
        junction(link, target)
        rec = retention.retire_sandbox(self.root, link.name, {}, self.keep)
        self.assertEqual(rec['action'], 'kept')
        self.assertTrue((target / 'precious.txt').exists())
        unlink_junction(link)

    def test_hard_link_to_an_original_file_is_never_deleted_or_followed(self):
        original = self.tmp / 'install' / 'Unreal2.exe'
        original.parent.mkdir()
        original.write_bytes(b'original')
        try:
            os.link(original, self.sb / 'System' / 'linked.exe')
        except OSError:
            self.skipTest('hard links unavailable')
        rec = self.retire()
        self.assertEqual(rec['action'], 'kept')
        self.assertEqual(original.read_bytes(), b'original')

    def test_profile_and_other_runs_are_untouched(self):
        profile = self.tmp / 'profiles' / 'owner' / 'Save'
        profile.mkdir(parents=True)
        (profile / 'Save1.usa').write_bytes(b'p')
        other = self.root / 'dev-init-20261103-110000-ffffffff'
        other.mkdir()
        (other / 'x').write_text('other session')
        self.game_writes()
        self.assertEqual(self.retire()['action'], 'removed')
        self.assertTrue((profile / 'Save1.usa').exists())
        self.assertTrue((other / 'x').exists())


class Frames(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)

    def frames(self, n):
        from PIL import Image
        for i in range(n):
            Image.new('RGB', (64, 48), (i, 10, 20)).save(self.run_dir / f'scene-frame-{i:04d}.bmp')
            os.utime(self.run_dir / f'scene-frame-{i:04d}.bmp', (1000 + i, 1000 + i))

    def test_routine_frames_are_thinned_to_png_and_the_rest_deleted(self):
        self.frames(40)
        (self.run_dir / 'frames.csv').write_text('perf')
        (self.run_dir / 'xrt.log').write_text('log')
        rec = retention.thin_frames(self.run_dir)
        left = sorted(p.name for p in self.run_dir.glob('*.png'))
        self.assertEqual(len(left), retention.MAX_FRAMES)
        self.assertIn('scene-frame-0000.png', left)
        self.assertIn('scene-frame-0039.png', left)
        self.assertEqual(list(self.run_dir.glob('*.bmp')), [])
        self.assertEqual(rec['frames_dropped'], 28)
        self.assertTrue((self.run_dir / 'frames.csv').exists() and (self.run_dir / 'xrt.log').exists())

    def test_pixels_survive_the_png_conversion(self):
        from PIL import Image
        self.frames(1)
        retention.thin_frames(self.run_dir)
        with Image.open(self.run_dir / 'scene-frame-0000.png') as im:
            self.assertEqual(im.convert('RGB').getpixel((3, 3)), (0, 10, 20))

    def test_failure_also_keeps_the_last_frames(self):
        self.frames(40)
        retention.thin_frames(self.run_dir, failed=True)
        names = {p.name for p in self.run_dir.glob('*.png')}
        self.assertTrue({'scene-frame-0037.png', 'scene-frame-0038.png', 'scene-frame-0039.png'} <= names)

    def test_non_frame_files_and_links_are_not_touched(self):
        (self.run_dir / 'client.bmp').write_bytes(b'BM')
        self.frames(2)
        retention.thin_frames(self.run_dir)
        self.assertTrue((self.run_dir / 'client.bmp').exists())


if __name__ == '__main__':
    unittest.main()
