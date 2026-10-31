"""Local build/debug loop. No supervisor imports, queues, seals or ledger access."""
import argparse
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
BASE = WS / 'out/recovery/practical-init-20261031-01'
DEV = WS / 'out/dev-init'
RT = DEV / 'runtime'
BUILD = DEV / 'build'
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

def compiler_environment():
    script = BUILD / 'compiler-env.cmd'
    script.write_text(f'@echo off\ncall "{VC}" x64 >nul\nif errorlevel 1 exit /b 1\nset\n')
    result = subprocess.run(['cmd', '/d', '/c', str(script)],
                            capture_output=True, text=True, check=True)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line and not line.startswith('='))

def command(args, env, name):
    path = next(value for key, value in env.items() if key.upper() == 'PATH')
    args = [shutil.which(str(args[0]), path=path) or str(args[0]), *args[1:]]
    with (BUILD / (name + '.txt')).open('w') as log:
        result = subprocess.run([str(x) for x in args], cwd=BUILD, env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode:
        raise RuntimeError(f'{name} failed; see {BUILD / (name + ".txt")}')

def compile_one(src, obj, env, includes=(), flags=()):
    obj.parent.mkdir(parents=True, exist_ok=True)
    command(['cl', '/nologo', '/c', '/Z7', '/fp:strict', '/W3', '/D_CRT_SECURE_NO_WARNINGS',
             '/DXRT_WITH_UNREAL2', *flags, *[f'/I{x}' for x in includes], f'/Fo{obj}', src], env, obj.stem)

def build(full=False, fixtures_only=False):
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
    for rel, row in lineage.items():
        if rel.startswith('obj/rt/'):
            continue
        obj = BUILD / rel
        src = Path(row['source'])
        endpoint = src.name == 'Unreal2_001.c'
        if endpoint:
            src = DEV / 'generated/Unreal2_001.c'
        if full or endpoint:
            if full or not obj.exists() or obj.stat().st_mtime < max(src.stat().st_mtime, (RT / 'xrt.h').stat().st_mtime):
                flags = ['/O1', '/wd4102', '/wd4146']
                if '/FIworld_observer.h' in row.get('command', []):
                    flags.append('/FIworld_observer.h')
                compile_one(src, obj, env, [RT, Path(row['source']).parent], flags)
        elif not obj.exists():
            obj.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old / rel, obj)
        objects.append(obj)
    headers = [*RT.glob('*.h'), *RT.glob('*.inc'), *HERE.glob('*.inc'), HERE / 'dev_support.h']
    header_time = max(p.stat().st_mtime for p in headers)
    for src in [*RT.glob('*.c'), HERE / 'dev_support.c']:
        obj = BUILD / 'obj/rt' / (src.stem + '.obj')
        if full or not obj.exists() or obj.stat().st_mtime < max(src.stat().st_mtime, header_time):
            print('Compiling', src.name, flush=True)
            # Same optimisation as the production client runtime (build_client.cmd: /O2 /fp:strict); /Z7 keeps symbols.
            compile_one(src, obj, env, [RT, HERE], ['/O2', '/std:c11'])
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
    write(BUILD / 'build-state.json', {'ok': True, 'executable': str(BUILD / 'unreal2-dev.exe')})
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


def run(args):
    if not args.authorize_init:
        raise RuntimeError('No launch: separate explicit owner authorization is required; then use --authorize-init')
    if not args.question.strip() or not args.change.strip():
        raise RuntimeError('Provide one concrete --question and --change')
    exe = BUILD / 'unreal2-dev.exe'
    if not exe.is_file():
        raise RuntimeError('Build the developer executable first')
    if not read(BUILD / 'build-state.json')['ok']:
        raise RuntimeError('Last build failed; rebuild before running')
    sources = [*RT.iterdir(), *HERE.glob('*.c'), *HERE.glob('*.h'), *HERE.glob('*.inc'), *HERE.glob('*.py'), * (DEV / 'generated').iterdir()]
    if any(p.is_file() and p.stat().st_mtime > exe.stat().st_mtime for p in sources):
        raise RuntimeError('Development sources changed: build before run')
    independent(exe)
    # Use only the snapshot asset utility and pinned graphics helper, never the supervisor.
    sys.path.insert(0, str(HERE.parent))
    import asset_boundary as assets
    import graphics_backend as graphics
    assets.verify()
    out = fresh_run()
    sandbox = WS / 'sandbox_cmp' / ('dev-init-' + out.name)
    assets.check_writable(sandbox)
    shutil.copytree(assets.source(), sandbox)
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
    graphics.environment(env, out)
    write(out / 'trace-profile.json', {'profile': args.trace_profile, 'full': args.trace_full,
                                     'addresses': [hex(a) for a in args.trace_address]})
    if args.attach:
        env['XRT_DEV_ATTACH'] = '1'
    command_args = ['--guest', sandbox / 'System/Unreal2.exe', '--log', out / 'xrt.log',
                    '--report', out / 'runtime-report.json', '--run-id', out.name,
                    '--timeout-ms', str(args.timeout * 1000), '--', 'CS_Intro.un2',
                    '-windowed', '-nosound', '-NOMMX', '-NOSSE']
    print('Run output:', out, flush=True)
    try:
        code = launch(exe, command_args, out, sandbox / 'System', env, args.timeout)
        reached = endpoint_proven(out, code)
        outcome = read(out / 'runtime-report.json').get('outcome') if (out / 'runtime-report.json').exists() else 'No runtime report; inspect console.txt'
        report(out, args.change, args.question,
               'Init returned; main loop not entered' if reached else 'See console.txt, xrt.log and runtime-report.json',
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
    sub.add_parser('selftest')
    sub.add_parser('observe')
    r = sub.add_parser('run')
    r.add_argument('--authorize-init', action='store_true', help='acknowledge separately granted owner authorization for this development Init run')
    r.add_argument('--question', required=True); r.add_argument('--change', required=True)
    r.add_argument('--timeout', type=int, choices=range(1, 301), default=60, metavar='1..300')
    r.add_argument('--attach', action='store_true')
    r.add_argument('--trace-profile', choices=('development', 'forensic'), default='development')
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
    elif args.action == 'build': build(args.full)
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
