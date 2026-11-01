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
import json
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
        rows.append((float(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5]) if len(p) > 5 else 0))
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
            'draws': sum(r[2] for r in sel) / len(sel), 'prims': sum(r[3] for r in sel) / len(sel),
            'cap_wait_share': sum(r[4] for r in sel[:-1]) / 1000 / span}


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


def thread_csv(run):
    """threads.csv: ({ms: {tid: (role, user, kernel, sleeps, preemptions)}}, init_filetime, ['# baton ...' lines])."""
    snaps, init, notes = {}, None, []
    for line in (run / 'threads.csv').read_text().splitlines():
        if line.startswith('# init_filetime='):
            init = int(line.split('=')[1])
        elif line.startswith('#'):
            notes.append(line[2:])
        elif not line.startswith('why,'):
            why, ms, tid, role, u, k, sl, pr = line.split(',')
            snaps.setdefault(float(ms), {})[int(tid)] = (role, float(u), float(k), int(sl), int(pr))
    return snaps, init, notes


def window_cpu(snaps, lo, hi):
    """CPU of each thread between the snapshots bounding [lo, hi]: (wall ms, [(share of one core, kernel share, tid,
    role, Sleep calls/s, preemptions/s)]) - tid 0 is the whole process."""
    keys = sorted(snaps)
    a = [k for k in keys if k <= lo + 50]
    b = [k for k in keys if k >= hi - 50]
    if not a or not b or a[-1] >= b[0]:
        return None
    s0, s1, wall = snaps[a[-1]], snaps[b[0]], b[0] - a[-1]
    out = []
    for tid, (role, u, k, sl, pr) in s1.items():
        _, u0, k0, sl0, pr0 = s0.get(tid, (role, 0, 0, 0, 0))
        out.append(((u - u0 + k - k0) / wall, (k - k0) / wall, tid, role, (sl - sl0) * 1000 / wall, (pr - pr0) * 1000 / wall))
    return wall, sorted(out, reverse=True)


def monitor(run, init_filetime, lo, hi):
    """Mean of the -Monitor CSVs (power.csv: typeperf, gpu.csv: nvidia-smi; local wall-clock rows) over [lo, hi] ms
    after Init."""
    import csv
    from datetime import datetime, timedelta, timezone
    if init_filetime is None:
        return {}
    t0 = (datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=init_filetime / 10)).astimezone().replace(tzinfo=None)
    a, b = t0 + timedelta(milliseconds=lo), t0 + timedelta(milliseconds=hi)
    out = {}
    for name, fmt in (('power.csv', '%m/%d/%Y %H:%M:%S.%f'), ('gpu.csv', '%Y/%m/%d %H:%M:%S.%f')):
        p = run / name
        if not p.exists():
            continue
        rows = list(csv.reader(p.read_text(errors='replace').splitlines()))
        head, cols = rows[0], {}
        for r in rows[1:]:
            try:
                t = datetime.strptime(r[0].strip(), fmt)
            except ValueError:
                continue
            if a <= t <= b:
                for h, v in zip(head[1:], r[1:]):
                    try:
                        cols.setdefault(h.strip(), []).append(float(v.strip().split()[0]))
                    except (ValueError, IndexError):
                        pass
        for h, v in cols.items():
            out[h] = (sum(v) / len(v), len(v))
    return out


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
    ap.add_argument('--json', type=Path, help='also write the per-window frame/CPU/monitor figures to this file')
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
    tsnaps, init_ft, notes = thread_csv(a.run) if (a.run / 'threads.csv').exists() else ({}, None, [])
    sm = samples(a.run) if (a.run / 'samples.bin').exists() else []
    sym = Symbols(a.run) if sm else None
    summary = {'run': a.run.name, 'baton': notes, 'windows': {}}
    for w in a.window:
        lo, hi = map(float, w.split(':'))
        s = frame_stats(rows, lo, hi)
        print(f'\n== window {lo:.0f}..{hi:.0f} ms ==')
        entry = summary['windows'][w] = {'frames': s}
        if s:
            print('presents {presents} world {world} | avg {fps:.1f} fps | frame ms median {median_ms:.2f} '
                  'p95 {p95_ms:.2f} p99 {p99_ms:.2f} max {max_ms:.1f} | draws/frame {draws:.0f} prims/frame {prims:.0f} '
                  '| limiter wait {cap_wait_share:.1%}'.format(**s))
        c = window_cpu(tsnaps, lo, hi) if tsnaps else None
        if c:
            wall, threads = c
            entry['cpu_wall_ms'] = wall
            entry['threads'] = [dict(tid=t, role=r, core=sh, kernel=k, sleeps_per_s=sl, preempt_per_s=pr)
                                for sh, k, t, r, sl, pr in threads if sh > 0.001 or r == 'guest1']
            print(f'CPU over {wall:.0f} ms (threads.csv snapshots bounding the window; % of one core):')
            for sh, k, t, r, sl, pr in threads:
                if sh > 0.005 or r in ('process', 'guest0', 'guest1'):
                    extra = (f', {sl:.0f} Sleep/s' if sl else '') + (f', {pr:.0f} preemptions/s' if pr else '')
                    print(f'  {r:8} tid {t:>6}: {100 * sh:6.1f}% ({100 * k:.1f}% kernel{extra})')
        m = monitor(a.run, init_ft, lo, hi)
        if m:
            entry['monitor'] = m
            print('monitor means:', '; '.join(f'{h.split(chr(92))[-1]} {v:.1f} (n={n})' for h, (v, n) in m.items()))
        c = cpu_share(snaps, lo, hi) if not tsnaps else None
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
    if a.json:
        a.json.write_text(json.dumps(summary, indent=1) + '\n')


if __name__ == '__main__':
    main()
