"""Manifest-bound snapshot inputs; never fall back to the installed game."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

WS = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = WS / 'sandbox_inputs/first-world/manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent(path):
    path = Path(path).absolute()
    for p in [path, *path.parents]:
        s = p.lstat()
        if getattr(s, 'st_file_attributes', 0) & 0x400 or p.is_symlink():
            raise RuntimeError(f'reparse input refused: {p}')
    if path.is_file() and path.stat().st_nlink != 1:
        raise RuntimeError(f'hardlinked input refused: {path}')


def inventory(root):
    root = Path(root)
    independent(root)
    files = {}
    for p in sorted(root.rglob('*')):
        independent(p)
        if p.is_file():
            files[p.relative_to(root).as_posix()] = sha(p)
    return files


def manifest():
    p = Path(os.environ.get('XRT_ASSET_MANIFEST', DEFAULT_MANIFEST))
    independent(p)
    return json.loads(p.read_text())


def source():
    return Path(manifest()['root'])


def check_writable(path):
    path = Path(path).absolute()
    path.relative_to(WS / 'sandbox_cmp')
    m = manifest()
    protected = [Path(m['root']), *[Path(t['root']) for t in m['protected_trees']],
                 *[Path(p) for p in m['protected_files']]]
    for p in protected:
        if path == p or path.is_relative_to(p) or p.is_relative_to(path):
            raise RuntimeError(f'run destination overlaps protected input: {path}')
    ancestor = path
    while not ancestor.exists():
        ancestor = ancestor.parent
    independent(ancestor)


def check_run_inputs(before, after):
    def mutable(p):
        p = p.lower()
        return (p.startswith(('save/', 'cache/')) or p == 'system/golem.u' or
                (p.startswith('system/') and p.endswith(('.ini', '.log'))))
    differences = [p for p, h in before.items() if not mutable(p) and after.get(p) != h]
    if differences:
        raise RuntimeError(f'protected run inputs changed: {differences}')


def verify(system_only=False):
    m = manifest()
    for tree in [dict(root=m['root'], files=m['files']), *m['protected_trees']]:
        expected = tree['files']
        root = Path(tree['root'])
        if system_only and (root / 'System').is_dir():
            root = root / 'System'
            expected = {p[7:]: h for p, h in expected.items() if p.startswith('System/')}
        actual = inventory(root)
        differences = [p for p in actual.keys() | expected.keys() if actual.get(p) != expected.get(p)]
        if differences:
            raise RuntimeError(f"protected inputs changed under {tree['root']}: {differences}")
    for p, digest in m['protected_files'].items():
        independent(p)
        if sha(p) != digest:
            raise RuntimeError(f'protected file changed: {p}')
    return dict(manifest_sha256=sha(os.environ.get('XRT_ASSET_MANIFEST', DEFAULT_MANIFEST)),
                files=len(m['files']), protected_trees=len(m['protected_trees']),
                protected_files=len(m['protected_files']))


@contextlib.contextmanager
def checked():
    before = verify()
    try:
        yield
    finally:
        if verify() != before:
            raise RuntimeError('asset manifest changed during experiment')


def archive(path):
    """Preserve a prior disposable run tree instead of deleting it."""
    p = Path(path).absolute()
    check_writable(p)
    independent(p)
    dest = WS / 'sandbox_archive' / (p.name + '-' + uuid.uuid4().hex[:12])
    dest.parent.mkdir(exist_ok=True)
    p.rename(dest)


def main():
    # Wrap each independent experiment, retaining its before/after verification.
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--log', type=Path, required=True)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.command[1:] if a.command[:1] == ['--'] else a.command
    before = verify()
    with a.log.open('w', encoding='utf-8') as log:
        p = subprocess.run(cmd, cwd=WS, stdout=log, stderr=subprocess.STDOUT)
    after = verify()
    if after != before:
        raise RuntimeError('asset manifest changed during experiment')
    a.log.with_suffix('.integrity.json').write_text(json.dumps(dict(command=cmd, exit=p.returncode,
                                                                  before=before, after=after), indent=2))
    print(a.log, 'exit', p.returncode, 'protected inputs unchanged', flush=True)
    return p.returncode


if __name__ == '__main__':
    sys.exit(main())
