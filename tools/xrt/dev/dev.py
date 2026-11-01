"""Local build/debug loop. No supervisor imports, queues, seals or ledger access."""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
BASE = WS / 'out/recovery/practical-init-20261031-01'
DEV_OBSERVED_UNITS = {'Engine_026.c'}
# build --diag-move: ULevel::MoveActor (Engine_020) and AActor::moveSmooth (Engine_025) also observed, so the runtime can log
# what blocks the player (xrt_events.c, XRT_DEV_MOVE_DIAG). Observed units run slower: diagnostic builds only.
DIAG_MOVE_UNITS = {'Engine_020.c', 'Engine_025.c'}
GEN_OPT = '/O2'
# Units compiled without forcing the xrt.h helpers inline (GlmLib_020 used to be here: forced inline it exceeds
# the default 600 s command limit, so it has its own limit below instead).
GEN_NO_FORCE_INLINE = set()
# Per-unit compile limits (s) above the default 600: GlmLib_020 forced inline took ~11 min under a parallel build.
GEN_SLOW_UNITS = {'GlmLib_020.c': 1800}
# Native C replacements (build --native): generated unit -> [(guest function, native source)]. The unit is compiled
# with the translated function renamed to <name>_translated, so the native definition is what the function table and
# every call reach. Differential test: experiments/xrt/tests/native_glm_xform.
NATIVE = {'GlmLib_008.c': [('f_2fd7d20', HERE / 'native/glm_xform.c')]}
DEV = WS / 'out/dev-init'
RT = DEV / 'runtime'
BUILD = DEV / 'build'
GAME_INSTALL = r'E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening\singleplayer'  # read-only content source
VC = Path(r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat')
STOP = '    P(0x1090ed5cu); /* call 0x10901370 */'

def read(path):
    return json.loads(path.read_text())

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def independent(path):
    """Reject junction/hardlink destinations and inputs before copying/writing."""
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.exists():
            st = p.lstat()
            if st.st_file_attributes & 0x400 or p.is_symlink() or (p.is_file() and st.st_nlink != 1):
                raise RuntimeError(f'linked path refused: {p}')
    return path

def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f'expected one development hook in {path}: {old}')
    path.write_text(text.replace(old, new))

def setup():
    independent(DEV)
    if (DEV / 'setup.json').exists():
        print('Using editable development tree:', DEV)
        return
    if RT.exists():
        raise RuntimeError('partial setup exists; inspect out/dev-init/runtime before proceeding')
    DEV.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BASE / 'runtime', RT)
    # Add diagnostics in the private copy; preserve all runtime safety adapters.
    for name in ('xrt_main.c', 'xrt_diag.c'):
        p = RT / name
        p.write_text('#include "dev_support.h"\n' + p.read_text())
    replace_once(RT / 'xrt_main.c', 'int main(int argc, char** argv) {',
                 'int main(int argc, char** argv) {\n    dev_start();')
    replace_once(RT / 'xrt_diag.c', '    xrt_cleanup_atoms();',
                 '    dev_dump(NULL, "runtime fatal");\n    xrt_cleanup_atoms();')
    replace_once(RT / 'xrt_diag.c', '    DWORD code = ep->ExceptionRecord->ExceptionCode;',
                 '    DWORD code = ep->ExceptionRecord->ExceptionCode;\n'
                 '    if (code == EXCEPTION_ACCESS_VIOLATION || code == EXCEPTION_STACK_OVERFLOW ||\n'
                 '        code == EXCEPTION_ILLEGAL_INSTRUCTION || code == EXCEPTION_INT_DIVIDE_BY_ZERO)\n'
                 '        dev_dump(ep, "host fault");')
    gen = DEV / 'generated'
    gen.mkdir()
    src = WS / 'experiments/xrt/gen/unreal2/Unreal2_001.c'
    shutil.copy2(src, gen / src.name)
    replace_once(gen / src.name, '#include "Unreal2_protos.h"',
                 '#include "Unreal2_protos.h"\nvoid xrt_dev_init_return(CPU*);')
    replace_once(gen / src.name, STOP, '    xrt_dev_init_return(c); /* developer endpoint, never returns */\n' + STOP)
    write(DEV / 'setup.json', {'runtime_origin': str(BASE / 'runtime'),
                              'generated_origin': str(src), 'endpoint': 'before 0x1090ED5C'})
    print('Editable runtime:', RT)

LIFT_SYSTEM = WS / 'sandbox_cmp/level/System'   # module images the shared gen/ units were lifted from

def lift(names, opt):
    """Re-lift shared generated modules (tools/xrt/xlift.py, --opt) into developer copies in out/dev-init/generated,
    which build compiles instead of the shared units. Protos/tables must stay identical to the shared ones; chunks
    identical to the shared unit are not copied (a stale copy is removed). Unreal2_001.c gets the endpoint hooks."""
    import struct
    gen = DEV / 'generated'
    tmp = independent(DEV / 'lift-tmp')
    shutil.rmtree(tmp, ignore_errors=True)
    jobs = []
    for name in names:
        shared = WS / 'experiments/xrt/gen' / name
        meta = read(next(shared.glob('*_meta.json')))
        image = next((p for p in LIFT_SYSTEM.rglob(meta['module'])
                      if hashlib.sha256(p.read_bytes()).hexdigest() == meta['sha256']), None)
        if image is None:
            raise RuntimeError(f'no {meta["module"]} with sha256 {meta["sha256"]} under {LIFT_SYSTEM}')
        raw = image.read_bytes()
        preferred = struct.unpack_from('<I', raw, struct.unpack_from('<I', raw, 0x3C)[0] + 52)[0]
        cmd = [sys.executable, '-I', str(WS / 'tools/xrt/xlift.py'), str(image), '--out', str(tmp / name)]
        if int(meta['base'], 16) != preferred:
            cmd += ['--base', meta['base']]
        if opt:
            cmd += ['--opt', ','.join(sorted(opt))]
        jobs.append((name, shared, cmd))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
        results = list(pool.map(lambda j: subprocess.run(j[2], capture_output=True, text=True), jobs))
    for (name, shared, cmd), result in zip(jobs, results):
        if result.returncode:
            raise RuntimeError(f'xlift {name} failed:\n{result.stdout}{result.stderr}')
        print(result.stdout.splitlines()[0])
        out = tmp / name
        copied = 0
        for path in sorted(out.iterdir()):
            if path.suffix == '.json':
                continue
            if path.name.endswith(('_protos.h', '_table.c')):
                # the static-trap count (evidence only) may differ: D3DDrv's ffree fix removed 8 traps
                ntraps = lambda b: re.sub(rb'(funcs, \d+u, )\d+u', rb'\1Nu', b)
                if ntraps(path.read_bytes()) != ntraps((shared / path.name).read_bytes()):
                    raise RuntimeError(f'{path.name} differs from the shared unit; refusing a partial ABI change')
                continue
            dest = gen / path.name
            if path.name == 'Unreal2_001.c':
                replace_once(path, '#include "Unreal2_protos.h"', '#include "Unreal2_protos.h"\nvoid xrt_dev_init_return(CPU*);')
                replace_once(path, STOP, '    xrt_dev_init_return(c); /* developer endpoint, never returns */\n' + STOP)
            elif path.read_bytes() == (shared / path.name).read_bytes():
                dest.unlink(missing_ok=True)
                continue
            if not dest.exists() or dest.read_bytes() != path.read_bytes():
                shutil.copyfile(path, dest)
                copied += 1
        print(f'  {name}: {copied} developer copies updated', flush=True)
    shutil.rmtree(tmp)

def compiler_environment():
    script = BUILD / 'compiler-env.cmd'
    script.write_text(f'@echo off\ncall "{VC}" x64 >nul\nif errorlevel 1 exit /b 1\nset\n')
    result = subprocess.run(['cmd', '/d', '/c', str(script)],
                            capture_output=True, text=True, check=True)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line and not line.startswith('='))

def command(args, env, name, timeout=600):
    path = next(value for key, value in env.items() if key.upper() == 'PATH')
    args = [shutil.which(str(args[0]), path=path) or str(args[0]), *args[1:]]
    with (BUILD / (name + '.txt')).open('w') as log:
        result = subprocess.run([str(x) for x in args], cwd=BUILD, env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{name} failed; see {BUILD / (name + ".txt")}')

def compile_one(src, obj, env, includes=(), flags=(), timeout=600):
    obj.parent.mkdir(parents=True, exist_ok=True)
    command(['cl', '/nologo', '/c', '/Z7', '/fp:strict', '/W3', '/D_CRT_SECURE_NO_WARNINGS',
             '/DXRT_WITH_UNREAL2', *flags, *[f'/I{x}' for x in includes], f'/Fo{obj}', src], env, obj.stem, timeout)

def build(full=False, fixtures_only=False, native=False, diag_move=False):
    independent(DEV)
    BUILD.mkdir(parents=True, exist_ok=True)
    env = compiler_environment()
    # Always compile the tiny host tools, independent of all game inputs.
    command(['cl', '/nologo', '/Od', '/Z7', '/D_CRT_SECURE_NO_WARNINGS', HERE / 'contain.c',
             f'/Fe{BUILD / "contain.exe"}', f'/Fo{BUILD / "contain.obj"}', '/link', '/DEBUG', 'user32.lib'], env, 'contain-build')
    command(['cl', '/nologo', '/Od', '/Z7', '/DXRT_DEV_FIXTURE', '/D_CRT_SECURE_NO_WARNINGS',
             HERE / 'fixture.c', HERE / 'dev_support.c', f'/Fe{BUILD / "fixture.exe"}', '/link', '/DEBUG', 'dbghelp.lib'], env, 'fixture-build')
    if fixtures_only:
        return
    write(BUILD / 'build-state.json', {'ok': False})
    setup()
    sys.path.insert(0, str(HERE))
    from trace_profile import install
    install(RT)
    baseline = read(BASE / 'build.json')
    lineage = read(BASE / 'object-lineage.json')
    old = Path(baseline['root'])
    abi = (RT / 'xrt.h').read_bytes()
    stamp = BUILD / 'xrt-abi.h'
    # Generated code embeds CPU layout/macros. An ABI edit needs a real rebuild.
    if stamp.exists() and stamp.read_bytes() != abi and not full:
        raise RuntimeError('xrt.h changed: use build --full to rebuild generated code')
    if not stamp.exists() and abi != (BASE / 'runtime/xrt.h').read_bytes() and not full:
        raise RuntimeError('xrt.h differs from object baseline: build --full required')
    objects = []
    jobs = []
    for rel, row in lineage.items():
        if rel.startswith('obj/rt/'):
            continue
        obj = BUILD / rel
        src = Path(row['source'])
        # Developer-owned copies of generated units: Unreal2_001.c (Init-return endpoint) and
        # D3DDrv_002.c (ffree, as tools/xrt/xlift.py now lifts it); shared gen/ stays untouched.
        endpoint = (DEV / 'generated' / src.name).is_file()
        if endpoint:
            src = DEV / 'generated' / src.name
        # Scene-node Render functions (FLevel/FCamera/FPlayerSceneNode) live here; the
        # inherited object lacks the existing world observer, so the dev build adds it.
        observed = src.name in DEV_OBSERVED_UNITS or (diag_move and src.name in DIAG_MOVE_UNITS)
        marker = obj.with_suffix('.observer')
        # Generated code is compiled /O2 like the runtime: under /O1 (no /Oi) MSVC emitted an
        # out-of-line memcpy call for every 4-byte guest load/store. /fp:strict is unchanged.
        opt = obj.with_suffix('.opt')
        renames = [f'/D{fn}={fn}_translated' for fn, _ in NATIVE.get(src.name, [])] if native else []
        opt_text = GEN_OPT + (' /DXRT_NO_FORCE_INLINE' if src.name in GEN_NO_FORCE_INLINE else '') + ''.join(' ' + r for r in renames)
        if observed and src.name in DIAG_MOVE_UNITS:
            opt_text += ' /FIworld_observer.h'   # recompiles the unit again when a later build drops --diag-move
        # The object must come from this source: switching a unit between its developer copy and the shared
        # source cannot be judged by modification times alone (the copy is newer than the shared file).
        origin = obj.with_suffix('.src')
        if (full or not obj.exists() or (observed and not marker.exists()) or
                not origin.exists() or origin.read_text() != str(src) or
                not opt.exists() or opt.read_text() != opt_text or
                obj.stat().st_mtime < max(src.stat().st_mtime, (RT / 'xrt.h').stat().st_mtime,
                                          (RT / 'world_observer.h').stat().st_mtime if observed else 0)):
            flags = [GEN_OPT, '/wd4102', '/wd4146']
            if src.name in GEN_NO_FORCE_INLINE:
                flags.append('/DXRT_NO_FORCE_INLINE')
            flags += renames
            if observed or '/FIworld_observer.h' in row.get('command', []):
                flags.append('/FIworld_observer.h')
            # Shared generated sources must be the ones the baseline objects came from.
            expected = None if endpoint else row.get('source_sha256')
            jobs.append((src, obj, [RT, Path(row['source']).parent], flags, observed, marker, opt, expected, origin,
                         opt_text))
        objects.append(obj)
    def compile_job(job):
        src, obj, includes, flags, observed, marker, opt, expected, origin, opt_text = job
        if expected and hashlib.sha256(src.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'{src} differs from the lineage source hash; refusing to recompile it')
        opt.unlink(missing_ok=True)
        origin.unlink(missing_ok=True)
        compile_one(src, obj, env, includes, flags, GEN_SLOW_UNITS.get(src.name, 600))
        if observed:
            marker.write_text('compiled with /FIworld_observer.h\n')
        opt.write_text(opt_text)
        origin.write_text(str(src))
    if jobs:
        print(f'Compiling {len(jobs)} generated units {GEN_OPT}', flush=True)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
            list(pool.map(compile_job, jobs))
    headers = [*RT.glob('*.h'), *RT.glob('*.inc'), *HERE.glob('*.inc'), HERE / 'dev_support.h']
    header_time = max(p.stat().st_mtime for p in headers)
    for src in [*RT.glob('*.c'), HERE / 'dev_support.c']:
        obj = BUILD / 'obj/rt' / (src.stem + '.obj')
        if full or not obj.exists() or obj.stat().st_mtime < max(src.stat().st_mtime, header_time):
            print('Compiling', src.name, flush=True)
            # Same optimisation as the production client runtime (build_client.cmd: /O2 /fp:strict); /Z7 keeps symbols.
            compile_one(src, obj, env, [RT, HERE], ['/O2', '/std:c11'])
        objects.append(obj)
    natives = [src for units in NATIVE.values() for _, src in units] if native else []
    for src in natives:
        obj = BUILD / 'obj/native' / (src.stem + '.obj')
        if full or not obj.exists() or obj.stat().st_mtime < max(src.stat().st_mtime, (RT / 'xrt.h').stat().st_mtime):
            print('Compiling native', src.name, flush=True)
            compile_one(src, obj, env, [RT], ['/O2', '/std:c11'])
        objects.append(obj)
    asm = BUILD / 'obj/rt/monitor_asm.obj'
    if full or not asm.exists() or asm.stat().st_mtime < (RT / 'monitor.asm').stat().st_mtime:
        command(['ml64', '/nologo', '/c', '/Zi', f'/Fo{asm}', RT / 'monitor.asm'], env, 'monitor-asm')
    objects.append(asm)
    rsp = BUILD / 'objects.rsp'
    rsp.write_text('\n'.join('"' + str(p) + '"' for p in objects))
    # Inherited generated objects may refer to their existing compiler PDBs.
    command(['link', '/nologo', '/DEBUG', '/INCREMENTAL:NO', '/STACK:0x10000000',
             f'/OUT:{BUILD / "unreal2-dev.exe"}', f'/PDB:{BUILD / "unreal2-dev.pdb"}', '@' + str(rsp),
             'winmm.lib', 'advapi32.lib', 'ole32.lib', 'bcrypt.lib', 'user32.lib', 'gdi32.lib', 'dbghelp.lib'], env, 'link')
    stamp.write_bytes(abi)
    write(BUILD / 'build-state.json', {'ok': True, 'executable': str(BUILD / 'unreal2-dev.exe'),
                                      'generated_optimization': GEN_OPT, 'generated_units': len(lineage) - sum(
                                          1 for rel in lineage if rel.startswith('obj/rt/')),
                                      'native': [fn for units in NATIVE.values() for fn, _ in units] if native else []})
    print('Built (not executed):', BUILD / 'unreal2-dev.exe')

def fresh_run():
    root = independent(DEV / 'runs' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]))
    root.mkdir(parents=True)
    return root

def launch(exe, args, out, cwd, env, timeout):
    cmd = [str(BUILD / 'contain.exe'), str(timeout), str(out), str(cwd),
           subprocess.list2cmdline([str(exe), *map(str, args)])]
    write(out / 'command.json', {'command': [str(exe), *map(str, args)], 'cwd': str(cwd), 'timeout': timeout})
    # Parent launcher owns the Job. Its watchdog remains active during debugger stops.
    return subprocess.run(cmd, env=env, check=False).returncode

def report(out, changed, question, worked, failed, next_step):
    (out / 'iteration.txt').write_text(
        f'Question: {question}\n1. What changed: {changed}\n'
        f'2. What was tested: {question}\n3. What worked: {worked}\n'
        f'4. What failed: {failed}\n5. Next: {next_step}\n')

def observe(out=None):
    if out is None:
        out = max((DEV / 'runs').iterdir(), key=lambda p: p.stat().st_mtime)
    print('Output:', out)
    for name in ('iteration.txt', 'console.txt'):
        path = out / name
        if path.exists():
            print('\n'.join(path.read_text(errors='replace').splitlines()[-25:]))
    runtime = out / 'runtime-report.json'
    if runtime.exists():
        value = read(runtime)
        print('Runtime outcome:', value.get('outcome'), 'exit:', value.get('exit_code'))
    monitor = out / 'monitor.bin'
    if monitor.exists():
        # Reuse only the passive record layout, not its qualification workflow.
        spec = importlib.util.spec_from_file_location('dev_trace_layout', WS / 'experiments/xrt/tests/practical_init/reader.py')
        layout = importlib.util.module_from_spec(spec); spec.loader.exec_module(layout)
        size = ctypes.sizeof(layout.Record)
        total, partial = divmod(monitor.stat().st_size, size)
        lines = [f'Diagnostic disk tail: {total} complete records; {partial} trailing bytes. '
                 'Unflushed memory tail may be missing; this is not qualification evidence.']
        with monitor.open('rb') as stream:
            stream.seek(max(0, total - 25) * size)
            for _ in range(min(total, 25)):
                record = layout.Record.from_buffer_copy(stream.read(size))
                if record.magic != 0x31544d58 or record.size != size or record.version not in (3, 4, 5):
                    lines.append('Unsupported/corrupt record header; decoding stopped.'); break
                pc = int.from_bytes(bytes(record.cpu)[68:72], 'little')
                name = record.name.decode('ascii', errors='replace')
                lines.append(f'{record.sequence} tid={record.thread} event={record.event} '
                             f'pc={pc:08x} {name} result={record.result:#x} last_error={record.error}')
        (out / 'monitor-tail.txt').write_text('\n'.join(lines) + '\n')
        print('\n'.join(lines))
        if Path(str(monitor) + '.routine').exists():
            sys.path.insert(0, str(HERE))
            from trace_reader import summary
            try:
                print(json.dumps(summary(Path(str(monitor) + '.routine')), indent=2))
            except ValueError as error:
                print('Diagnostic history unavailable:', error)
        elif (out / 'trace-profile.json').exists() and read(out / 'trace-profile.json').get('profile') == 'development':
            print('Diagnostic history unavailable: no flight-recorder snapshot; unflushed event count UNKNOWN.')
    print('For source debugging: xrt_fatal, xm_failure, xrt_icall, xrt_dev_init_return.')

def selftest():
    build(fixtures_only=True)
    out = fresh_run()
    for mode, expected in [('ok', 0), ('endpoint', 10), ('crash', 0xE0123456), ('tree', 124)]:
        case = out / mode
        case.mkdir()
        env = dict(os.environ, XRT_DEV_OUTPUT=str(case))
        env.pop('XRT_DEV_ATTACH', None)
        env.pop('XRT_DEV_GAME', None)
        actual = launch(BUILD / 'fixture.exe', [mode], case, BUILD, env, 1 if mode == 'tree' else 10)
        result = read(case / 'process.json')
        if actual != expected or result['remaining_processes'] != 0:
            raise RuntimeError(f'{mode} failed: {actual}, {result}')
        if mode == 'crash' and not (case / 'crash.dmp').read_bytes().startswith(b'MDMP'):
            raise RuntimeError('crash dump missing or malformed')
        if mode == 'tree' and 'child=' not in (case / 'console.txt').read_text():
            raise RuntimeError('descendant was not created')
        print('PASS', mode, flush=True)
    case = out / 'attach-timeout'; case.mkdir()
    env = dict(os.environ, XRT_DEV_OUTPUT=str(case), XRT_DEV_ATTACH='1')
    env.pop('XRT_DEV_GAME', None)
    if launch(BUILD / 'fixture.exe', ['ok'], case, BUILD, env, 1) != 124:
        raise RuntimeError('debugger-attach wait escaped deadline')
    print('PASS attach-timeout', flush=True)
    # Kill the launcher itself: its non-inherited Job handle must kill both children.
    case = out / 'launcher-death'; case.mkdir()
    env.pop('XRT_DEV_ATTACH', None); env['XRT_DEV_OUTPUT'] = str(case)
    p = subprocess.Popen([str(BUILD / 'contain.exe'), '30', str(case), str(BUILD),
                          subprocess.list2cmdline([str(BUILD / 'fixture.exe'), 'tree'])], env=env)
    child = None
    try:
        until = time.monotonic() + 10
        while time.monotonic() < until:
            log = case / 'console.txt'
            text = log.read_text() if log.exists() else ''
            if 'child=' in text:
                child = int(text.split('child=')[1].split()[0]); break
            time.sleep(0.05)
        if child is None:
            raise RuntimeError('launcher-death fixture never spawned descendant')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, child)
        if not handle: raise RuntimeError('cannot observe descendant lifetime')
        try:
            p.kill(); p.wait(timeout=10)
            if kernel.WaitForSingleObject(handle, 5000) != 0:
                raise RuntimeError('descendant survived launcher death')
        finally:
            kernel.CloseHandle(handle)
    finally:
        if p.poll() is None: p.kill(); p.wait(timeout=10)
    print('PASS launcher-death', flush=True)
    denied = subprocess.run([sys.executable, '-B', '-I', str(HERE / 'dev.py'), 'run',
                             '--question', 'must not launch', '--change', 'authorization rejection test'],
                            capture_output=True, text=True)
    if denied.returncode != 2 or 'No launch:' not in denied.stderr:
        raise RuntimeError('missing-authorization rejection failed')
    print('PASS missing-authorization (no process creation)', flush=True)
    report(out, 'Independent developer launcher and diagnostics', 'Owned fixtures only: exit, endpoint, crash, child timeout',
           'Seven cases; dump captured; Job cleanup, launcher death and attach deadline passed', 'No game test performed',
           'After separate authorization, observe genuine Init return or first fatal')
    print('Owned tests:', out)
    sys.path.insert(0, str(HERE))
    import trace_test
    trace_test.run(sys.modules[__name__])

def endpoint_proven(out, code):
    """An exit status or orderly monitor close alone never proves game Init."""
    runtime = out / 'runtime-report.json'
    monitor = out / 'monitor.bin'
    if code != 10 or not runtime.exists() or not monitor.exists():
        return False
    report = read(runtime)
    if not any(e.get('kind') == 'dev_init_return' and e.get('guest_next') == '0x1090ed5c'
               for e in report.get('events', [])):
        return False
    sys.path.insert(0, str(HERE))
    from trace_reader import records
    try:
        return any(r.event == 10 and r.name == b'dev.Init.return' for r in records(monitor))
    except ValueError:
        return False


def scene_proven(out, code):
    """First-scene stop: exit 11, the Init-return milestone and the dev.scene.present checkpoint."""
    runtime = out / 'runtime-report.json'
    monitor = out / 'monitor.bin'
    if code != 11 or not runtime.exists() or not monitor.exists():
        return False
    kinds = {e.get('kind') for e in read(runtime).get('events', [])}
    if 'dev_init_return' not in kinds:
        return False
    sys.path.insert(0, str(HERE))
    from trace_reader import records
    try:
        names = {r.name for r in records(monitor) if r.event == 10}
    except ValueError:
        return False
    return {b'dev.Init.return', b'dev.scene.present'} <= names


def run(args):
    if not args.authorize_init:
        raise RuntimeError('No launch: separate explicit owner authorization is required; then use --authorize-init')
    if args.first_scene and not args.authorize_first_scene:
        raise RuntimeError('No launch: --first-scene needs the separately granted --authorize-first-scene scope')
    if args.first_scene and args.timeout > 600:
        raise RuntimeError('First-scene runs are limited to 600 seconds')
    if args.scene_seconds and (not args.first_scene or args.scene_seconds >= args.timeout):
        raise RuntimeError('--scene-seconds needs --first-scene and must end before --timeout')
    if not args.question.strip() or not args.change.strip():
        raise RuntimeError('Provide one concrete --question and --change')
    exe = BUILD / 'unreal2-dev.exe'
    if not exe.is_file():
        raise RuntimeError('Build the developer executable first')
    if not read(BUILD / 'build-state.json')['ok']:
        raise RuntimeError('Last build failed; rebuild before running')
    sources = [*RT.iterdir(), *HERE.glob('*.c'), *HERE.glob('*.h'), *HERE.glob('*.inc'), *HERE.glob('*.py'), * (DEV / 'generated').iterdir(),
               *HERE.glob('native/*.c')]
    if any(p.is_file() and p.stat().st_mtime > exe.stat().st_mtime for p in sources):
        raise RuntimeError('Development sources changed: build before run')
    independent(exe)
    # Use only the snapshot asset utility and pinned graphics helper, never the supervisor.
    sys.path.insert(0, str(HERE.parent))
    import asset_boundary as assets
    import graphics_backend as graphics
    assets.verify()
    # --seed-save: only .usa files written by an earlier developer run - in its sandbox (sandbox_cmp, overflow folder)
    # or preserved from one under out/dev-init/saves. Checked before anything is copied.
    seeds = []
    for spec in args.seed_save:
        src = independent(Path(spec))
        from_sandbox = any(src.is_relative_to(a) for a in (WS / 'sandbox_cmp', Path(os.environ.get('USERPROFILE', '')) / 'Unreal2-dev-sandbox-overflow')) \
            and any(part.startswith('dev-init-') for part in src.parts)
        if src.suffix.lower() != '.usa' or not src.is_file() or not (from_sandbox or src.is_relative_to(DEV / 'saves')):
            raise RuntimeError(f'No launch: --seed-save is not a .usa written by an earlier developer run: {src}')
        seeds.append(src)
    out = fresh_run()
    sandbox = WS / 'sandbox_cmp' / ('dev-init-' + out.name)
    assets.check_writable(sandbox)
    shutil.copytree(assets.source(), sandbox)
    if args.windowed_res:
        # The run's own copy of System/Unreal2.ini (a mutable run input): the windowed viewport the game requests.
        # The actual back buffer is whatever CreateDevice records (xrt.log create_device_parameters, capture size).
        ini = sandbox / 'System' / 'Unreal2.ini'
        text, n = re.subn(rb'(?m)^WindowedViewportX=\d+\r?$', b'WindowedViewportX=%d' % args.windowed_res[0], ini.read_bytes())
        text, k = re.subn(rb'(?m)^WindowedViewportY=\d+\r?$', b'WindowedViewportY=%d' % args.windowed_res[1], text)
        if n != 1 or k != 1:
            raise RuntimeError('--windowed-res: WindowedViewportX/Y not found exactly once in the sandbox Unreal2.ini')
        ini.write_bytes(text)
        print(f'dev: windowed viewport {args.windowed_res[0]}x{args.windowed_res[1]} requested in the sandbox Unreal2.ini', flush=True)
    if args.campaign_assets:
        # Opt-in: add the retail single-player content the first-world snapshot omits (other maps and
        # their packages), read-only from the install. Never Save (a junction to personal saves) or System.
        install = Path(GAME_INSTALL)
        added = 0
        for folder in sorted(install.iterdir()):
            if not folder.is_dir() or folder.is_symlink() or folder.is_junction() or folder.name.lower() in ('save', 'system'):
                continue
            for f in sorted(folder.iterdir()):
                target = sandbox / folder.name / f.name
                if f.is_file() and not target.exists():
                    target.parent.mkdir(exist_ok=True)
                    shutil.copy2(f, target); added += 1
        print(f'dev: campaign assets: {added} install files added to the sandbox', flush=True)
    if seeds:
        # Opt-in: save files the translated game itself wrote in an EARLIER developer run (validated above), copied into
        # this run's own Save folder so the game's QuickLoad/Load menu can restore them. Never the install's Save (a
        # junction to personal saves) and never an externally generated state.
        target = sandbox / 'Save'
        target.mkdir(exist_ok=True)
        for src in seeds:
            shutil.copy2(src, target / src.name)
            print(f'dev: seeded save {src} ({src.stat().st_size} bytes, sha256 {hashlib.sha256(src.read_bytes()).hexdigest()[:16]})', flush=True)
    # Developer helper copy (out/dev-init/dmusic_helper, named CallRoutine admitted); else the shared build.
    helper = BUILD / 'dmusic_helper.exe'
    if not helper.is_file():
        helper = WS / 'experiments/xrt/build/dmusic-ipc/dmusic_helper.exe'
    if not helper.is_file():
        raise RuntimeError(f'DirectMusic helper missing: {helper}')
    env = {k: v for k, v in os.environ.items() if k.upper() in
           ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'SYSTEMDRIVE', 'USERPROFILE', 'USERNAME', 'LOCALAPPDATA', 'APPDATA')}
    folder = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x23, None, 0, folder) != 0:
        raise RuntimeError('Cannot resolve ProgramData')
    env.update(ProgramData=folder.value, PATH=str(Path(os.environ['SystemRoot']) / 'System32'),
               TEMP=str(sandbox), TMP=str(sandbox), XRT_DEV_OUTPUT=str(out), XRT_DEV_GAME='1',
               XRT_MONITOR_PROFILE=args.trace_profile, XRT_DEV_TRACE_FULL=';'.join(args.trace_full),
               XRT_DEV_TRACE_ADDRESS=';'.join(hex(a) for a in args.trace_address),
               XRT_MONITOR_STREAM=str(out / 'monitor.bin'),
               XRT_DMUSIC_BACKEND='ipc', XRT_DMUSIC_HELPER=str(helper),
               XRT_D3D8_DIR=str(graphics.verified_pair('x64')), XRT_STOP_FIRST_LEVEL_TICK='1')
    if args.windowed_res:
        # Lets a window larger than the desktop keep the requested client (runtime hle_gui.c dev_max_track): otherwise
        # Windows clamps it, the back buffer stays at the requested size and DXVK falls back to GDI presentation.
        env['XRT_DEV_MAX_TRACK'] = f'{args.windowed_res[0] + 64}x{args.windowed_res[1] + 128}'
    if args.first_scene:
        # Continue past Init and level ticks; the stop is after N presented world frames.
        del env['XRT_STOP_FIRST_LEVEL_TICK']
        env['XRT_DEV_SCENE'] = str(args.first_scene)
        if args.scene_seconds:
            env['XRT_DEV_SCENE_MS'] = str(args.scene_seconds * 1000)
        if not args.allow_input:
            env['XRT_DEV_NO_INPUT'] = '1'
        if args.allow_map:
            env['XRT_DEV_ALLOW_MAPS'] = ';'.join(args.allow_map)
        if args.background:
            if args.allow_input:
                raise RuntimeError('No launch: --background needs input isolation (drop --allow-input)')
            env['XRT_DEV_BACKGROUND'] = '1'   # never takes focus; scripted input only (dev_support.c xrt_dev_background)
        if args.input:
            if args.allow_input:
                raise RuntimeError('No launch: --input needs input isolation (drop --allow-input)')
            env['XRT_DEV_INPUT'] = args.input
        if args.diag_move:
            env['XRT_DEV_MOVE_DIAG'] = '1'   # needs a build --diag-move executable (xrt_events.c move_diag_return)
        if args.music_script_track:
            # Developer workaround: helper dispatches DirectMusic script-track events
            # (experiments/xrt/DMUSIC_SCRIPT_TRACK_DESIGN.md); native tracks are disabled.
            env['XRT_DMUSIC_SCRIPT_TRACK'] = 'helper'
        if args.draw_dump:
            env['XRT_DEV_DRAW_FRAMES'] = ','.join(map(str, args.draw_dump[:4]))
        if args.sample_hz:
            env['XRT_DEV_SAMPLE_HZ'] = str(args.sample_hz)
        if args.staging == 'reuse':
            env['XRT_DEV_STAGING'] = 'reuse'   # buffer staging kept per buffer (runtime resource_storage.inc)
        if args.capture == 'shots':
            env['XRT_DEV_CAPTURE'] = 'shots'   # no periodic/cue/startup readbacks (dev_support.c)
        if args.fps_cap:
            env['XRT_DEV_FPS_CAP'] = str(args.fps_cap)   # development frame limiter (dev_support.c perf_cap_wait)
        if args.native_verify:
            env['XRT_NATIVE_VERIFY'] = str(args.native_verify)   # tools/xrt/dev/native: compare every Nth call
    graphics.environment(env, out)
    write(out / 'trace-profile.json', {'profile': args.trace_profile, 'full': args.trace_full,
                                     'addresses': [hex(a) for a in args.trace_address],
                                     'first_scene_frames': args.first_scene,
                                     'scene_seconds': args.scene_seconds,
                                     'music_script_track': args.music_script_track,
                                     'input_script': args.input, 'allowed_maps': args.allow_map,
                                     'campaign_assets': args.campaign_assets, 'sample_hz': args.sample_hz,
                                     'windowed_res': args.windowed_res, 'capture': args.capture,
                                     'staging': args.staging, 'fps_cap': args.fps_cap, 'background': args.background, 'seed_save': args.seed_save, 'native_verify': args.native_verify,
                                     'native': read(BUILD / 'build-state.json').get('native', [])})
    if args.attach:
        env['XRT_DEV_ATTACH'] = '1'
    command_args = ['--guest', sandbox / 'System/Unreal2.exe', '--log', out / 'xrt.log',
                    '--report', out / 'runtime-report.json', '--run-id', out.name,
                    '--timeout-ms', str(args.timeout * 1000), '--', 'CS_Intro.un2',
                    '-windowed', '-nosound', '-NOMMX', '-NOSSE']
    print('Run output:', out, flush=True)
    try:
        code = launch(exe, command_args, out, sandbox / 'System', env, args.timeout)
        reached = scene_proven(out, code) if args.first_scene else endpoint_proven(out, code)
        outcome = read(out / 'runtime-report.json').get('outcome') if (out / 'runtime-report.json').exists() else 'No runtime report; inspect console.txt'
        done = ('Init returned; world frames presented to the first-scene stop (console.txt names it; inspect scene-frame-*.bmp)'
                if args.first_scene else 'Init returned; main loop not entered')
        report(out, args.change, args.question,
               done if reached else 'See console.txt, xrt.log and runtime-report.json',
               'None observed before endpoint' if reached else f'{outcome}; exit {code:#x}; 124=deadline, 125=harness, 130=cancel',
               'Review Init return; separately scope first scene/tick' if reached else 'Fix the first fatal/unsupported call; keep the same milestone')
        observe(out)
        return 0 if reached else 1
    finally:
        assets.verify()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('setup')
    b = sub.add_parser('build'); b.add_argument('--full', action='store_true')
    b.add_argument('--diag-move', action='store_true', help='also observe ULevel::MoveActor/AActor::moveSmooth (blocking-hit log; slower)')
    b.add_argument('--native', action='store_true', help='link the native C replacements in NATIVE instead of their translations')
    lp = sub.add_parser('lift', help='re-lift shared generated modules into developer copies (then build)')
    lp.add_argument('--opt', default='', help='xlift --opt list (flags,pc); empty = plain lift')
    lp.add_argument('modules', nargs='+', help='gen/ directory names, e.g. fire engine core')
    sub.add_parser('selftest')
    sub.add_parser('observe')
    r = sub.add_parser('run')
    r.add_argument('--authorize-init', action='store_true', help='acknowledge separately granted owner authorization for this development Init run')
    r.add_argument('--question', required=True); r.add_argument('--change', required=True)
    r.add_argument('--timeout', type=int, choices=range(1, 601), default=60, metavar='1..600')
    r.add_argument('--attach', action='store_true')
    r.add_argument('--authorize-first-scene', action='store_true',
                   help='acknowledge separately granted owner authorization to continue past Init into world frames')
    r.add_argument('--first-scene', type=int, choices=range(1, 100001), default=0, metavar='1..100000',
                   help='continue past Init; stop after this many presented frames with level/camera scene-node draws (exit 11)')
    r.add_argument('--scene-seconds', type=int, default=0, metavar='SECONDS',
                   help='first-scene: also stop cleanly (exit 11) at the first world frame this long after Init')
    r.add_argument('--allow-input', action='store_true',
                   help='first-scene: let physical keyboard/mouse input reach the game (isolated by default)')
    r.add_argument('--allow-map', action='append', default=[], metavar='FILE.un2',
                   help='first-scene: continue (instead of stopping) when this map file is opened post-Init')
    r.add_argument('--input', default='', metavar='SCRIPT',
                   help='first-scene: short explicit input script "T:verb[:args];..." (key/move/click/shot/cpu), '
                        'T in ms after Init; delivered to the game window only, isolation stays on')
    r.add_argument('--staging', choices=('strict', 'reuse'), default='strict',
                   help='D3D8 buffer Lock staging: strict (default; decommitted at Unlock, stale pointers fault) or reuse (per-buffer block, stale pointers into it not trapped)')
    r.add_argument('--capture', choices=('periodic', 'shots'), default='periodic',
                   help='first-scene back-buffer captures: periodic (default; powers of two, every 256th world frame, cues) or shots (scripted shots only)')
    r.add_argument('--diag-move', action='store_true',
                   help='log what blocks the player (needs a build --diag-move executable)')
    r.add_argument('--seed-save', action='append', default=[], metavar='FILE.usa',
                   help='copy a save written by an earlier developer run (its sandbox Save folder) into this run\'s Save')
    r.add_argument('--background', action='store_true',
                   help="developer background mode: the game runs behind the owner's foreground application and never "
                        'takes focus; only --input reaches it (needs isolation; dev_support.c xrt_dev_background)')
    r.add_argument('--fps-cap', type=int, choices=range(0, 1001), default=0, metavar='0..1000',
                   help='first-scene: development frame limiter after each post-Init Present (waitable timer, baton released; 0 = uncapped)')
    r.add_argument('--native-verify', type=int, default=0, metavar='N',
                   help='with a build --native executable: compare every Nth native call against its translation (xrt.log)')
    r.add_argument('--windowed-res', type=lambda v: tuple(int(x) for x in v.lower().split('x')), metavar='WxH',
                   help='windowed viewport the game requests (WindowedViewportX/Y in the run sandbox Unreal2.ini)')
    r.add_argument('--campaign-assets', action='store_true',
                   help='first-scene: also copy the install content missing from the first-world snapshot into the sandbox')
    r.add_argument('--music-script-track', action='store_true',
                   help='first-scene: helper dispatches DirectMusic script-track events (host workaround)')
    r.add_argument('--draw-dump', type=int, action='append', default=[], metavar='WORLD_FRAME',
                   help='first-scene: log every draw of this world frame (up to four)')
    r.add_argument('--trace-profile', choices=('development', 'quiet', 'forensic'), default='development',
                   help='quiet: development stream without routine call/data/resource records (checkpoints, fatal, gaps kept)')
    r.add_argument('--sample-hz', type=int, choices=range(0, 1001), default=0, metavar='0..1000',
                   help='first-scene: sample the game thread stack N times a second (samples.bin; perf_report.py)')
    r.add_argument('--trace-full', action='append', default=[], metavar='DLL!NAME',
                   help='retain full tracing for this exact import name; repeat as needed')
    def guest_address(value):
        address = int(value, 0)
        if not 0 < address <= 0xffffffff:
            raise argparse.ArgumentTypeError('expected a nonzero 32-bit guest address')
        return address
    r.add_argument('--trace-address', action='append', default=[], type=guest_address, metavar='0xADDRESS',
                   help='full detail at this guest PC or stack return address, including nested events')
    args = parser.parse_args()
    independent(DEV)
    if args.action == 'setup': setup()
    elif args.action == 'build': build(args.full, native=args.native, diag_move=args.diag_move)
    elif args.action == 'lift': lift(args.modules, {x for x in args.opt.split(',') if x})
    elif args.action == 'selftest': selftest()
    elif args.action == 'observe': observe()
    else: return run(args)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('dev:', error, file=sys.stderr)
        sys.exit(2)
