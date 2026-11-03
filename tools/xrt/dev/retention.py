"""What `dev.py run` keeps once a run is over: the per-run asset sandbox is disposable, routine screenshots are thinned.

The sandbox is a full copy of the game assets (~2 GiB) that equals the install apart from what the game itself wrote.
After the run ends, files the game wrote (logs, ini, saves, dumps) are copied to <run>/sandbox-kept with their hashes and
the rest is deleted. Anything doubtful keeps the whole sandbox: a link or hard link inside it, a name that is not this
run's, a process still using it, an over-budget or failed preservation.
"""
import hashlib
import os
import re
import shutil
import stat
import struct
import zlib
from pathlib import Path

REPARSE = stat.FILE_ATTRIBUTE_REPARSE_POINT
SANDBOX_NAME = re.compile(r'dev-init-\d{8}-\d{6}-[0-9a-f]{8}')
FRAME = re.compile(r'(?:scene-frame|present|startup-present)-\d+\.bmp')
KEEP_BYTES = 512 << 20   # game-written files preserved per run; more than this keeps the sandbox
MAX_FRAMES = 12          # frames kept per run (first, last, evenly spaced; the last 3 more after a failure)


def scan(root):
    """({relative path: (size, mtime_ns)}, [links and hard-linked files]) of a tree, never following a link."""
    files, unsafe = {}, []
    stack = [(Path(root), '')]
    while stack:
        folder, prefix = stack.pop()
        with os.scandir(folder) as entries:
            for e in entries:
                rel = prefix + e.name
                st = e.stat(follow_symlinks=False)
                if st.st_file_attributes & REPARSE or e.is_symlink():
                    unsafe.append(rel)
                elif e.is_dir(follow_symlinks=False):
                    stack.append((Path(e.path), rel + '/'))
                else:
                    st = os.lstat(e.path)   # DirEntry.stat() has no link count on Windows
                    if st.st_nlink > 1:
                        unsafe.append(rel)
                    else:
                        files[rel] = (st.st_size, st.st_mtime_ns)
    return files, unsafe


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            h.update(block)
    return h.hexdigest()


def _is_link(path):
    st = os.lstat(path)
    return bool(st.st_file_attributes & REPARSE) or stat.S_ISLNK(st.st_mode)


def retire_sandbox(root, name, baseline, keep):
    """Preserve what the game wrote in root/name (files that differ from `baseline`, the scan taken just before launch),
    then delete the sandbox. Returns the record to store with the run; action is 'removed' or 'kept' (with the reason)."""
    sandbox = Path(root) / name
    rec = {'sandbox': str(sandbox), 'action': 'kept'}
    if not SANDBOX_NAME.fullmatch(name) or not Path(root).is_absolute():
        return {**rec, 'reason': 'not a run sandbox name'}
    if not sandbox.is_dir() or _is_link(root) or _is_link(sandbox):
        return {**rec, 'reason': 'missing, or the sandbox/its parent is a link'}
    files, unsafe = scan(sandbox)
    if unsafe:
        return {**rec, 'reason': 'links or hard links inside the sandbox', 'links': unsafe[:20]}
    changed = [] if baseline is None else sorted(rel for rel, v in files.items() if baseline.get(rel) != v)
    if sum(files[rel][0] for rel in changed) > KEEP_BYTES:
        return {**rec, 'reason': 'game-written files exceed the preservation budget'}
    # A directory with an open handle or a process working inside it cannot be renamed: that is the in-use check.
    retiring = sandbox.with_name(name + '.retiring')
    try:
        os.rename(sandbox, retiring)
    except OSError as error:
        return {**rec, 'reason': f'in use or not renamable ({error.strerror})'}
    kept = []
    try:
        for rel in changed:
            dest = Path(keep) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(retiring / rel, dest)
            digest = _sha256(dest)
            if dest.stat().st_size != files[rel][0] or digest != _sha256(retiring / rel):
                raise OSError(f'preserved copy differs: {rel}')
            kept.append({'path': rel, 'size': files[rel][0], 'sha256': digest})
    except BaseException as error:
        os.rename(retiring, sandbox)
        if isinstance(error, Exception):
            return {**rec, 'reason': f'preserving game-written files failed ({error})'}
        raise
    removed = size = 0
    try:
        for folder, dirs, names in os.walk(retiring, topdown=False, followlinks=False):
            for n in names:
                p = os.path.join(folder, n)
                size += os.lstat(p).st_size
                os.unlink(p)
                removed += 1
            for d in dirs:
                os.rmdir(os.path.join(folder, d))
        os.rmdir(retiring)
    except OSError as error:
        return {**rec, 'reason': f'removal stopped ({error.strerror}); remainder at {retiring}',
                'preserved': kept, 'removed_files': removed}
    return {'sandbox': str(sandbox), 'action': 'removed', 'removed_files': removed, 'removed_bytes': size,
            'preserved': kept, 'baseline_files': len(baseline or {})}


def _png(bmp):
    """Lossless PNG next to a 24-bit uncompressed bottom-up BMP (what dev_support.c writes), standard library only. The BMP
    is removed only after the PNG decodes to the same pixels; any other BMP stays as it is."""
    png = bmp.with_suffix('.png')
    try:
        data = bmp.read_bytes()
        off, = struct.unpack_from('<I', data, 10)
        width, height, planes, bpp, comp = struct.unpack_from('<iiHHI', data, 18)
        if data[:2] != b'BM' or bpp != 24 or comp != 0 or width <= 0 or height <= 0:
            return bmp
        stride = (width * 3 + 3) & ~3
        if off + stride * height > len(data):
            return bmp
        raw = bytearray()
        for y in range(height - 1, -1, -1):                       # BMP rows are bottom-up BGR; PNG rows top-down RGB
            row = data[off + y * stride: off + y * stride + width * 3]
            rgb = bytearray(width * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = row[2::3], row[1::3], row[0::3]
            raw += b'\0' + rgb                                      # filter type 0

        def chunk(kind, body):
            return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
        png.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                        + chunk(b'IDAT', zlib.compress(bytes(raw), 6)) + chunk(b'IEND', b''))
        back = png.read_bytes()
        same = back[:8] == b'\x89PNG\r\n\x1a\n' and zlib.decompress(back[back.index(b'IDAT') + 4:-16]) == raw
    except (OSError, struct.error, ValueError, zlib.error):
        png.unlink(missing_ok=True)
        return bmp
    if same:
        bmp.unlink()
        return png
    png.unlink()
    return bmp


def thin_frames(run, failed=False):
    """Keep the first and last frame, evenly spaced ones up to MAX_FRAMES (the last 3 as well after a failure) as
    lossless PNG; delete the other routine BMP frames of the run. Returns what was kept and how much was dropped."""
    frames = sorted((p for p in Path(run).iterdir() if FRAME.fullmatch(p.name) and p.is_file() and not _is_link(p)),
                    key=lambda p: (p.stat().st_mtime_ns, p.name))
    n = len(frames)
    pick = set(range(n)) if n <= MAX_FRAMES else {round(i * (n - 1) / (MAX_FRAMES - 1)) for i in range(MAX_FRAMES)}
    if failed:
        pick |= set(range(max(0, n - 3), n))
    dropped = 0
    kept = []
    for i, p in enumerate(frames):
        if i in pick:
            kept.append(_png(p).name)
        else:
            dropped += p.stat().st_size
            p.unlink()
    return {'frames_seen': n, 'frames_kept': kept, 'frames_dropped': n - len(kept), 'bytes_dropped': dropped}
