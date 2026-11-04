"""One-off compaction of historical run screenshots (player batch 2026-11-03). Not a framework: it reuses retention.py's
verified lossless BMP->PNG conversion and frame-selection rule for runs made before the retention policy existed.

  python -I frames_cleanup.py plan      -> plan.json (nothing changed)
  python -I frames_cleanup.py apply     -> applies plan.json, writes deleted-manifest.jsonl and converted-manifest.jsonl

Scope: frame files only (scene-frame-N.bmp, present-N.bmp, startup-present-N.bmp) directly inside
  E:\\Unreal2-Port-Investigation\\out\\dev-init\\runs\\<run id>\\ and its overflow counterpart
  C:\\Users\\lawma\\Unreal2-dev-sandbox-overflow\\run-<run id>\\ (frames moved off E: during earlier batches).
Never: run directories as a whole, logs, reports, dumps, saves, anything else; links/hard links; runs newer than the
retention policy (they are already thinned); a run whose classification is unclear (kept, reported).

Classes (from the project's own documents: reports, READMEs, journals, batch notes, save point READMEs, memory notes):
  explicit   a frame file named in a document is never deleted or converted
  milestone  the run id appears in a document on a line that speaks of visual evidence (frame, shot, capture,
             screenshot, png, bmp, sheet, visible, confirmed, subtitle, view): every frame kept; BMPs converted to
             pixel-identical PNG (the BMP is deleted only after the PNG decodes to the same pixels)
  failure    the run ended in a fatal/unexpected outcome or left crash.dmp: first, last 3 and evenly spaced frames up
             to 12, converted to PNG; the rest deleted
  routine    the rest: first, last and evenly spaced frames up to 12 (retention.MAX_FRAMES) as PNG; the rest deleted
"""
import hashlib, json, os, re, stat, sys
from pathlib import Path

WS = Path(r'E:\Unreal2-Port-Investigation')
RUNS = WS / 'out/dev-init/runs'
OVERFLOW = Path(r'C:\Users\lawma\Unreal2-dev-sandbox-overflow')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(WS / 'tools/xrt/dev'))
import retention

RUN_ID = re.compile(r'(20261\d{3}-\d{6})(?:-([0-9a-f]{8}))?')
FRAME_NAME = re.compile(r'(?:scene-frame|startup-present|present)-\d+(?:\.bmp|\.png)?')
VISUAL = re.compile(r'frame|shot|captur|screenshot|png|bmp|sheet|visib|confirm|subtitle|view|image|picture', re.I)
POLICY_START = '20261103-012018'   # first run made with the retention policy (thinned at run end)
REPARSE = stat.FILE_ATTRIBUTE_REPARSE_POINT


def documents():
    roots = [WS / 'tools', WS / 'experiments/xrt', WS / 'out/dev-init', WS / 'out/dev-init-savepoints', WS / 'notes',
             Path(r'C:\Users\lawma\.claude\projects\E--Launchbox-Games-PC-Games-Unreal-2---The-Awakening\memory')]
    docs = [p for p in WS.glob('*.md')]
    for root in roots:
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in ('runs', 'generated', 'build', 'runtime', 'gen', 'audio-lift', 'obj', '__pycache__')
                     and not os.stat(os.path.join(dp, d), follow_symlinks=False).st_file_attributes & REPARSE]
            for f in fn:
                if f.lower().endswith(('.md', '.txt', '.py', '.ps1')) and os.path.getsize(os.path.join(dp, f)) < 8 << 20:
                    docs.append(Path(dp) / f)
    return docs


def frames_of(folder):
    out = []
    if folder.is_dir() and not os.stat(folder, follow_symlinks=False).st_file_attributes & REPARSE:
        for p in folder.iterdir():
            if retention.FRAME.fullmatch(p.name) and p.is_file():
                st = os.lstat(p)
                if st.st_file_attributes & REPARSE or st.st_nlink != 1:
                    continue
                out.append(p)
    return out


def outcome(run):
    rr = run / 'runtime-report.json'
    try:
        o = json.loads(rr.read_text(errors='replace')).get('outcome', '') if rr.is_file() else ''
    except ValueError:
        o = 'unreadable report'
    return o


def plan():
    milestone, explicit, mentioned = {}, set(), set()
    for d in documents():
        try:
            text = d.read_text(errors='replace')
        except OSError:
            continue
        for line in text.splitlines():
            ids = {m.group(1) for m in RUN_ID.finditer(line)}
            if not ids:
                if FRAME_NAME.search(line):
                    explicit |= {m.group(0).rsplit('.', 1)[0] for m in FRAME_NAME.finditer(line)}
                continue
            mentioned |= ids
            for m in FRAME_NAME.finditer(line):
                explicit.add(m.group(0).rsplit('.', 1)[0])
            narrative = d.name in ('README.txt', 'CURRENT_STATUS.md') or d.parent.name == 'memory'
            if VISUAL.search(line) or narrative:   # narrative documents: every run they name is a milestone
                for i in ids:
                    milestone.setdefault(i, str(d.relative_to(d.anchor)))
    runs = {}
    for run in sorted(RUNS.iterdir()):
        if run.is_dir():
            runs.setdefault(run.name, {})['e'] = run
    for o in sorted(OVERFLOW.glob('run-*')):
        runs.setdefault(o.name[4:], {})['c'] = o
    result = {'explicit_frame_names': sorted(explicit), 'runs': []}
    for name, where in sorted(runs.items()):
        short = name[:15]
        frames = frames_of(where.get('e', Path('-'))) + frames_of(where.get('c', Path('-')))
        if not frames:
            continue
        rec = {'run': name, 'frames': len(frames), 'bytes': sum(p.stat().st_size for p in frames),
               'bmp': sum(p.suffix == '.bmp' for p in frames)}
        e = where.get('e')
        out = outcome(e) if e else ''
        failed = bool(e and ((e / 'crash.dmp').exists() or (out and not re.search(r'^exited|first-scene stop|Init-return stop', out))))
        if short >= POLICY_START:
            rec['class'] = 'skip: retention policy run'
        elif not e:
            rec['class'] = 'skip: no run directory on E: (cannot classify)'
        elif short in milestone:
            rec['class'], rec['reason'] = 'milestone', milestone[short]
        elif failed:
            rec['class'], rec['reason'] = 'failure', out or 'crash.dmp'
        else:
            rec['class'] = 'routine'
        frames.sort(key=lambda p: (p.stat().st_mtime_ns, p.name))
        n = len(frames)
        if rec['class'] in ('routine', 'failure'):
            pick = set(range(n)) if n <= retention.MAX_FRAMES else {round(i * (n - 1) / (retention.MAX_FRAMES - 1)) for i in range(retention.MAX_FRAMES)}
            if rec['class'] == 'failure':
                pick |= set(range(max(0, n - 3), n))
        elif rec['class'] == 'milestone':
            pick = set(range(n))
        else:
            pick = set(range(n))
        keep, convert, delete = [], [], []
        for i, p in enumerate(frames):
            if p.stem in explicit:
                keep.append(str(p))                 # named in a document: untouched
            elif i in pick:
                (convert if p.suffix == '.bmp' and rec['class'] in ('routine', 'failure', 'milestone') else keep).append(str(p))
            else:
                delete.append(str(p))
        rec.update(keep=keep, convert=convert, delete=delete,
                   delete_bytes=sum(os.path.getsize(p) for p in delete))
        result['runs'].append(rec)
    return result


def apply(p):
    sys.path.insert(0, str(WS / 'tools/xrt'))
    import asset_boundary
    before = asset_boundary.verify()
    data = json.loads(p.read_text())
    deleted = (HERE / 'deleted-manifest.jsonl').open('a', encoding='utf-8')
    converted = (HERE / 'converted-manifest.jsonl').open('a', encoding='utf-8')
    freed = 0
    for rec in data['runs']:
        if rec['class'] not in ('routine', 'failure', 'milestone'):
            continue
        for f in rec['delete']:
            f = Path(f)
            st = os.lstat(f)
            if st.st_file_attributes & REPARSE or st.st_nlink != 1 or not retention.FRAME.fullmatch(f.name):
                continue
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            f.unlink()
            freed += st.st_size
            deleted.write(json.dumps({'path': str(f), 'run': rec['run'], 'class': rec['class'], 'size': st.st_size,
                                      'mtime_ns': st.st_mtime_ns, 'sha256': h}) + '\n')
        for f in rec['convert']:
            f = Path(f)
            if not f.exists():
                continue
            size = f.stat().st_size
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            result = retention._png(f)
            if result.suffix == '.png':
                freed += size - result.stat().st_size
            converted.write(json.dumps({'bmp': str(f), 'bmp_size': size, 'bmp_sha256': h, 'run': rec['run'], 'class': rec['class'],
                                        'result': str(result), 'result_size': result.stat().st_size,
                                        'verified_lossless': result.suffix == '.png'}) + '\n')
        deleted.flush(); converted.flush()
        print(rec['run'], rec['class'], 'freed so far %.1f GiB' % (freed / 2**30), flush=True)
    after = asset_boundary.verify()
    print('asset boundary before == after:', before == after, 'freed bytes', freed)


if __name__ == '__main__':
    if sys.argv[1:] == ['plan']:
        r = plan()
        (HERE / 'plan.json').write_text(json.dumps(r, indent=1))
        tot = {}
        for rec in r['runs']:
            c = rec['class'].split(':')[0]
            t = tot.setdefault(c, [0, 0, 0, 0])
            t[0] += 1; t[1] += rec['bytes']; t[2] += rec['delete_bytes']; t[3] += len(rec['delete'])
        for c, t in tot.items():
            print(f'{c:10s} runs {t[0]:4d}  frame bytes {t[1] / 2**30:6.1f} GiB  delete {t[3]:5d} files {t[2] / 2**30:6.1f} GiB')
        print('explicitly named frames:', len(r['explicit_frame_names']))
    elif sys.argv[1:] == ['apply']:
        apply(HERE / 'plan.json')
