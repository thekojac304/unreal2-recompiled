"""Frame-time and sample summary of one developer run (frames.csv, samples.bin, modules.txt, xrt.log).

  python -B -I tools/xrt/dev/perf_report.py RUN_DIR [--window FROM_MS:TO_MS ...] [--top N]

Times are ms after Init return. Every window reports presents, world frames, average FPS and
frame-time percentiles (consecutive present deltas), the game thread's CPU share between the
scripted shots that bound it, and the sampled hot spots (leaf and inclusive, symbolized with the
run's PDB through dbghelp).
"""
import argparse
import bisect
import ctypes
import re
import struct
import sys
from collections import Counter
from ctypes import wintypes
from pathlib import Path


def frames(run):
    rows = []
    for line in (run / 'frames.csv').read_text().splitlines()[1:]:
        p = line.split(',')
        rows.append((float(p[1]), int(p[2]), int(p[3]), int(p[4])))
    return rows


def pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(q * len(v)))] if v else 0.0


def frame_stats(rows, lo, hi):
    sel = [r for r in rows if lo <= r[0] <= hi]
    if len(sel) < 2:
        return None
    dt = [b[0] - a[0] for a, b in zip(sel, sel[1:])]
    span = sel[-1][0] - sel[0][0]
    return {'presents': len(sel), 'world': sum(r[1] for r in sel), 'fps': (len(sel) - 1) * 1000 / span,
            'median_ms': pct(dt, 0.5), 'p95_ms': pct(dt, 0.95), 'p99_ms': pct(dt, 0.99), 'max_ms': max(dt),
            'draws': sum(r[2] for r in sel) / len(sel), 'prims': sum(r[3] for r in sel) / len(sel)}


def thread_times(run):
    """{snapshot ms: {tid: (user, kernel, is_game)}} from DEV threads lines."""
    snaps = {}
    pat = re.compile(r'DEV threads (\w+) at ([\d.]+) ms: tid (\d+)( \(game\))? user ([\d.]+) kernel ([\d.]+)')
    for line in (run / 'xrt.log').read_text(errors='replace').splitlines():
        m = pat.search(line)
        if m:
            snaps.setdefault(float(m.group(2)), {})[int(m.group(3))] = (float(m.group(5)), float(m.group(6)), bool(m.group(4)))
    return snaps


def cpu_share(snaps, lo, hi):
    keys = sorted(snaps)
    a = [k for k in keys if k <= lo + 50]
    b = [k for k in keys if k >= hi - 50]
    if not a or not b or a[-1] >= b[0]:
        return None
    s0, s1, wall = snaps[a[-1]], snaps[b[0]], b[0] - a[-1]
    out = []
    for tid, (u, k, game) in s1.items():
        u0, k0, _ = s0.get(tid, (0, 0, False))
        busy = (u - u0) + (k - k0)
        if busy > 0.01 * wall:
            out.append((busy / wall, tid, game, (k - k0) / wall))
    return wall, sorted(out, reverse=True)


class Symbols:
    class SYMBOL_INFOW(ctypes.Structure):
        _fields_ = [('SizeOfStruct', wintypes.ULONG), ('TypeIndex', wintypes.ULONG), ('Reserved', ctypes.c_uint64 * 2),
                    ('Index', wintypes.ULONG), ('Size', wintypes.ULONG), ('ModBase', ctypes.c_uint64),
                    ('Flags', wintypes.ULONG), ('Value', ctypes.c_uint64), ('Address', ctypes.c_uint64),
                    ('Register', wintypes.ULONG), ('Scope', wintypes.ULONG), ('Tag', wintypes.ULONG),
                    ('NameLen', wintypes.ULONG), ('MaxNameLen', wintypes.ULONG), ('Name', wintypes.WCHAR * 512)]

    def __init__(self, run):
        self.d = ctypes.WinDLL('dbghelp')
        self.h = ctypes.c_void_p(0x5eed)
        self.d.SymSetOptions(0x2 | 0x4)  # UNDNAME | DEFERRED_LOADS
        self.d.SymInitializeW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.BOOL]
        self.d.SymLoadModuleExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                            ctypes.c_uint64, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        self.d.SymLoadModuleExW.restype = ctypes.c_uint64
        self.d.SymFromAddrW.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64),
                                        ctypes.POINTER(self.SYMBOL_INFOW)]
        exe = None
        self.mods = []
        for line in (run / 'modules.txt').read_text(errors='replace').splitlines():
            base, size, path = line.split(' ', 2)
            self.mods.append((int(base, 16), int(size), Path(path).name))
            if path.lower().endswith('unreal2-dev.exe'):
                exe = Path(path)
        self.mods.sort()
        self.d.SymInitializeW(self.h, str(exe.parent) if exe else None, False)
        for line in (run / 'modules.txt').read_text(errors='replace').splitlines():
            base, size, path = line.split(' ', 2)
            self.d.SymLoadModuleExW(self.h, None, path, None, int(base, 16), int(size), None, 0)
        self.cache = {}

    def module(self, a):
        i = bisect.bisect_right(self.mods, (a, 1 << 62, '')) - 1
        if i >= 0 and a < self.mods[i][0] + self.mods[i][1]:
            return self.mods[i][2]
        return '?'

    def name(self, a):
        if a in self.cache:
            return self.cache[a]
        info = self.SYMBOL_INFOW()
        info.SizeOfStruct = 88  # sizeof(SYMBOL_INFOW) with Name[1] on x64
        info.MaxNameLen = 511
        disp = ctypes.c_uint64()
        mod = self.module(a)
        if self.d.SymFromAddrW(self.h, a, ctypes.byref(disp), ctypes.byref(info)):
            n = f'{mod}!{info.Name}'
        else:
            n = f'{mod}+{a:x}'
        self.cache[a] = n
        return n


def samples(run):
    data = (run / 'samples.bin').read_bytes()
    out, at = [], 0
    while at + 16 <= len(data):
        ms, pc, depth = struct.unpack_from('<dII', data, at)
        at += 16
        rips = struct.unpack_from(f'<{depth}Q', data, at)
        at += 8 * depth
        out.append((ms, pc, rips))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    ap.add_argument('--window', action='append', default=[])
    ap.add_argument('--top', type=int, default=30)
    ap.add_argument('--timeline', type=int, default=10000, help='per-interval FPS table step (ms); 0 disables')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    rows = frames(a.run)
    if a.timeline:
        print('ms-after-Init  presents  fps   world')
        end = rows[-1][0]
        t = 0.0
        while t < end:
            s = frame_stats(rows, t, t + a.timeline)
            if s:
                print(f'{t:>9.0f}  {s["presents"]:>6}  {s["fps"]:6.1f}  {s["world"]:>6}')
            t += a.timeline
    snaps = thread_times(a.run)
    sm = samples(a.run) if (a.run / 'samples.bin').exists() else []
    sym = Symbols(a.run) if sm else None
    for w in a.window:
        lo, hi = map(float, w.split(':'))
        s = frame_stats(rows, lo, hi)
        print(f'\n== window {lo:.0f}..{hi:.0f} ms ==')
        if s:
            print('presents {presents} world {world} | avg {fps:.1f} fps | frame ms median {median_ms:.1f} '
                  'p95 {p95_ms:.1f} p99 {p99_ms:.1f} max {max_ms:.1f} | draws/frame {draws:.0f} prims/frame {prims:.0f}'.format(**s))
        c = cpu_share(snaps, lo, hi)
        if c:
            wall, threads = c
            print(f'thread CPU over {wall:.0f} ms (shots bounding the window):')
            for share, tid, game, kern in threads[:8]:
                print(f'  tid {tid}{" (game)" if game else ""}: {100 * share:.0f}% of one core ({100 * kern:.0f}% kernel)')
        win = [x for x in sm if lo <= x[0] <= hi]
        if not win:
            continue
        n = len(win)
        leaf, incl, mods, guest = Counter(), Counter(), Counter(), Counter()
        for _, pc, rips in win:
            names = [sym.name(r) for r in rips]
            leaf[names[0]] += 1
            mods[sym.module(rips[0])] += 1
            for nm in set(names):
                incl[nm] += 1
            # innermost translated guest function on the host stack
            g = next((nm for nm in names if '!f_' in nm), None)
            guest[g.split('!')[1] if g else '(none)'] += 1
        print(f'samples {n}; leaf module:', ', '.join(f'{m} {100 * c / n:.1f}%' for m, c in mods.most_common(8)))
        print('top leaf (self) functions:')
        for nm, cnt in leaf.most_common(a.top):
            print(f'  {100 * cnt / n:5.1f}%  {nm}')
        print('top inclusive functions:')
        for nm, cnt in incl.most_common(a.top):
            print(f'  {100 * cnt / n:5.1f}%  {nm}')
        print('innermost translated guest function:')
        for nm, cnt in guest.most_common(a.top):
            print(f'  {100 * cnt / n:5.1f}%  {nm}')


if __name__ == '__main__':
    main()
