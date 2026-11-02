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
# Port behaviour wrappers, always linked: walking speed setting (native/walk_speed.c). Unlike NATIVE (a /D rename of
# every use), only the DEFINITION is renamed to <name>_translated, in a build copy of the unit (obj/port-src), so
# calls inside the same unit (physWalking -> calcVelocity in Engine_025.c) reach the wrapper too.
PORT = {'Engine_025.c': [('f_103e24d0', HERE / 'native/walk_speed.c')]}
DEV = WS / 'out/dev-init'
RT = DEV / 'runtime'
BUILD = DEV / 'build'
GAME_INSTALL = r'E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening\singleplayer'  # read-only content source
VC = Path(r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat')
# build --cc clang-cl: the generated (and sound) units compiled by LLVM's MSVC-compatible driver, linked by the MSVC linker
# as usual; the runtime stays cl. Measured on experiments/xrt/tests/perf_kernels (2026-11-01): clang-cl 23 /O2 /fp:strict
# runs the same lifted C 10% faster than cl on the full option set and 40% faster on a plain lift, bit-identical results.
COMPILERS = {'cl': 'cl', 'clang-cl': r'C:\Program Files\LLVM\bin\clang-cl.exe'}
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

# xlift --opt lazypc: a chunk ends with its source-line -> guest-address table (xrt.h XrtPcLine). The endpoint hooks
# inserted above add lines to Unreal2_001.c, so the table is regenerated from the instruction header lines afterwards
# (the same pattern xlift uses: a pc store, or the comment that replaced it).
PCLINE = re.compile(r'^\s+(?:P\(0x([0-9a-f]+)u\);|/\* 0x([0-9a-f]+): )|^(?:XRT_EH_FN )?(?:void|uint32_t) f_([0-9a-f]+)\(CPU\*(?: __restrict)? c\) \{')
PCLINE_ENTRY = re.compile(r'^\s+\{\d+u, 0x[0-9a-f]+u\},$')

def renumber_pclines(path):
    lines = path.read_text().split('\n')
    first = next((i for i, l in enumerate(lines) if PCLINE_ENTRY.match(l)), None)
    if first is None:
        return
    last = max(i for i, l in enumerate(lines) if PCLINE_ENTRY.match(l))
    table = [f'    {{{i + 1}u, 0x{int(m.group(1) or m.group(2) or m.group(3), 16):x}u}},' for i, l in enumerate(lines[:first]) for m in [PCLINE.match(l)] if m]
    if len(table) != last - first + 1:
        raise RuntimeError(f'{path.name}: {len(table)} instruction lines but {last - first + 1} line-table entries')
    path.write_text('\n'.join(lines[:first] + table + lines[last + 1:]))

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
# Sound (developer-owned lifts, not in the shared gen/ or the object lineage): Core's and ALAudio's Ogg Vorbis
# libraries and ALAudio.dll. All prefer 0x10000000; these bases fill the gap below U2.dll (0x10060000) in load order.
AUDIO_LIFT = DEV / 'audio-lift'
AUDIO_MODULES = [('vorbisfile', 'vorbisfile.dll', '0x10000000'), ('ogg', 'ogg.dll', '0x10010000'),
                 ('vorbis', 'vorbis.dll', '0x10020000'), ('alaudio', 'ALAudio.dll', '0x10040000')]

def lift_audio(opt):
    """Lift the sound modules (tools/xrt/xlift.py) into out/dev-init/audio-lift/<name>; build compiles them and
    defines XRT_WITH_AUDIO (runtime xrt_main.c registers them; ALAudio's OpenAL driver is runtime hle_openal.c)."""
    for name, module, base in AUDIO_MODULES:
        out = AUDIO_LIFT / name
        shutil.rmtree(out, ignore_errors=True)
        cmd = [sys.executable, '-I', str(WS / 'tools/xrt/xlift.py'), str(LIFT_SYSTEM / module), '--out', str(out), '--base', base]
        if opt:
            cmd += ['--opt', ','.join(sorted(opt))]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f'xlift {module} failed:\n{result.stdout}{result.stderr}')
        print(result.stdout.splitlines()[0], flush=True)


def lift(names, opt):
    """Re-lift shared generated modules (tools/xrt/xlift.py, --opt) into developer copies in out/dev-init/generated,
    which build compiles instead of the shared units. Chunks identical to the shared unit are not copied (a stale copy
    is removed); protos/table are copied only when the discovered function set differs from the shared lift (the delta
    is printed). Unreal2_001.c gets the endpoint hooks."""
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
        for line in result.stdout.splitlines()[1:]:
            if line.startswith('  cflags') or line.startswith('    f_'):
                print(line)                        # cflags audit findings (the module then keeps the iflags rules)
        out = tmp / name
        copied = 0
        for path in sorted(out.iterdir()):
            if path.suffix == '.json':
                continue
            if path.name.endswith(('_protos.h', '_table.c')):
                # the static-trap count (evidence only) may differ: D3DDrv's ffree fix removed 8 traps
                ntraps = lambda b: re.sub(rb'(funcs, \d+u, )\d+u', rb'\1Nu', b)
                if ntraps(path.read_bytes()) != ntraps((shared / path.name).read_bytes()):
                    # The discovered function set changed since the shared lift (discovery improvements: e.g. the static-CRT
                    # memcpy jump-table slots of fb06f2a). The developer copies of the protos and the table are then used
                    # as a pair with the chunks (build compiles any lineage source that has a copy here, and a chunk's
                    # quoted #include finds the protos in its own directory first); the delta is reported. A function
                    # that is still called by translated code but missing from the table would fail at link time.
                    fnset = lambda b: set(re.findall(rb'(?:void|uint32_t) (f_[0-9a-f]+)\(CPU', b))   # rv lifts return uint32_t
                    if path.name.endswith('_protos.h'):
                        old_set, new_set = fnset((shared / path.name).read_bytes()), fnset(path.read_bytes())
                        print(f'  {name}: function set changed vs the shared lift: {len(old_set)} -> {len(new_set)}; dropped '
                              f'{sorted(x.decode() for x in old_set - new_set)[:40]}; added {sorted(x.decode() for x in new_set - old_set)[:40]}',
                              flush=True)
                    dest = gen / path.name
                    if not dest.exists() or dest.read_bytes() != path.read_bytes():
                        shutil.copyfile(path, dest)
                        copied += 1
                    continue
                (gen / path.name).unlink(missing_ok=True)   # identical again: the shared protos/table are used
                continue
            dest = gen / path.name
            if path.name == 'Unreal2_001.c':
                replace_once(path, '#include "Unreal2_protos.h"', '#include "Unreal2_protos.h"\nvoid xrt_dev_init_return(CPU*);')
                replace_once(path, STOP, '    xrt_dev_init_return(c); /* developer endpoint, never returns */\n' + STOP)
                renumber_pclines(path)
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

def compile_one(src, obj, env, includes=(), flags=(), timeout=600, cc='cl'):
    obj.parent.mkdir(parents=True, exist_ok=True)
    warn = '/W3' if cc == 'cl' else '/w'   # clang-cl: MSVC warning numbers do not apply; the generated code is not hand-written
    command([COMPILERS[cc], '/nologo', '/c', '/Z7', '/fp:strict', warn, '/D_CRT_SECURE_NO_WARNINGS',
             '/DXRT_WITH_UNREAL2', *flags, *[f'/I{x}' for x in includes], f'/Fo{obj}', src], env, obj.stem, timeout)

def lift_options():
    """The xlift --opt list the developer copies were lifted with (the header of Unreal2_001.c), or []."""
    head = (DEV / 'generated' / 'Unreal2_001.c').read_text(encoding='latin-1', errors='replace')[:400]
    m = re.search(r'\(--opt ([a-z0-9,]+)\)', head)
    return m.group(1).split(',') if m else []


def audio_lift_options():
    """The xlift --opt list of the sound-module lift (header of its first unit), or None when there is no sound lift."""
    first = sorted(AUDIO_LIFT.glob('*/*.c'))[:1] if AUDIO_LIFT.is_dir() else []
    if not first:
        return None
    m = re.search(r'\(--opt ([a-z0-9,]+)\)', first[0].read_text(encoding='latin-1', errors='replace')[:400])
    return m.group(1).split(',') if m else []


def build(full=False, fixtures_only=False, native=False, diag_move=False, lean=False, cc='cl', ltcg=False, order=None):
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
    # xlift --opt rv: every unit that sees xrt.h must agree on the lifted-function type. The protos header defines
    # XRT_RV_ABI before including xrt.h, but a forced include (world_observer.h) reads xrt.h first, so the define
    # goes on the command line of the generated units as well as the runtime's and the natives'.
    rv_abi = 'rv' in lift_options()
    # xlift --opt ehframe: the landing-pad layout and landing protocol (xrt.h XRT_EH_FRAMES, runtime xrt_eh.c and
    # xrt_eh_land.asm) must be the same in every module and in the runtime: refuse a mixed build.
    eh_frames = 'ehframe' in lift_options()
    audio_opts = audio_lift_options()
    if audio_opts is not None and ('ehframe' in audio_opts) != eh_frames:
        raise RuntimeError('the generated and the sound lifts disagree on --opt ehframe: re-lift one of them (lift / lift-audio)')
    eh_define = ['/DXRT_EH_FRAMES'] if eh_frames else []
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
        opt_text += ' /DXRT_LEAN_ENTER' if lean else ''   # build --lean: no per-entry history ring (xrt.h XRT_ENTER)
        opt_text += f' cc={cc}' if cc != 'cl' else ''        # build --cc: a compiler switch recompiles every unit
        opt_text += ' /GL' if ltcg else ''                   # build --ltcg: whole-program optimization of the generated units
        opt_text += ' /DXRT_RV_ABI' if rv_abi else ''
        opt_text += ' /DXRT_EH_FRAMES' if eh_frames else ''
        opt_text += ''.join(f' port:{fn}' for fn, _ in PORT.get(src.name, []))
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
            flags = [GEN_OPT, '/wd4102', '/wd4146', '/DXRT_PCLINES']   # XRT_PCLINES: lazypc line tables register (xrt.h)
            if lean:
                flags.append('/DXRT_LEAN_ENTER')
            if ltcg:
                flags.append('/GL')
            if rv_abi:
                flags.append('/DXRT_RV_ABI')
            flags += eh_define
            if src.name in GEN_NO_FORCE_INLINE:
                flags.append('/DXRT_NO_FORCE_INLINE')
            flags += renames
            if observed or '/FIworld_observer.h' in row.get('command', []):
                flags.append('/FIworld_observer.h')
            # Shared generated sources must be the ones the baseline objects came from.
            expected = None if endpoint else row.get('source_sha256')
            # Include path: the unit's own directory, so a developer copy (and the port-src copy of one, which has no
            # protos header beside it) sees the developer lift's protos header, not the shared lift's (--opt rv changes it).
            jobs.append((src, obj, [RT, src.parent], flags, observed, marker, opt, expected, origin,
                         opt_text, cc))
        objects.append(obj)
    def compile_job(job):
        src, obj, includes, flags, observed, marker, opt, expected, origin, opt_text, cc = job
        if expected and hashlib.sha256(src.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'{src} differs from the lineage source hash; refusing to recompile it')
        opt.unlink(missing_ok=True)
        origin.unlink(missing_ok=True)
        unit = src
        if src.name in PORT:
            text = src.read_text(encoding='latin-1')
            for fn, _ in PORT[src.name]:
                # the definition's header as xlift writes it: void or (--opt rv) uint32_t, CPU* or (--opt restrict) CPU* __restrict
                head = re.compile(r'^((?:XRT_EH_FN )?(?:void|uint32_t)) ' + fn + r'\((CPU\*(?: __restrict)?) c\) \{$', re.M)
                if len(head.findall(text)) != 1:
                    raise RuntimeError(f'{src.name}: definition of {fn} found {len(head.findall(text))} times')
                text = head.sub(lambda m: f'{m.group(1)} {fn}_translated({m.group(2)} c) {{', text)
            unit = BUILD / 'obj' / 'port-src' / src.name
            unit.parent.mkdir(parents=True, exist_ok=True)
            unit.write_text(text, encoding='latin-1')
        compile_one(unit, obj, env, includes, flags, GEN_SLOW_UNITS.get(src.name, 600), cc)
        if observed:
            marker.write_text('compiled with /FIworld_observer.h\n')
        opt.write_text(opt_text)
        origin.write_text(str(src))
    if jobs:
        print(f'Compiling {len(jobs)} generated units {GEN_OPT} ({cc})', flush=True)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
            list(pool.map(compile_job, jobs))
    audio = sorted(AUDIO_LIFT.glob('*/*.c')) if AUDIO_LIFT.is_dir() else []
    audio_jobs = []
    audio_stamp = BUILD / 'obj/audio/compiler.txt'
    audio_cc_changed = audio and (not audio_stamp.exists() or audio_stamp.read_text() != cc + (' /GL' if ltcg else '') + (' /DXRT_RV_ABI' if rv_abi else '') + ''.join(' ' + d for d in eh_define))
    for src in audio:
        obj = BUILD / 'obj/audio' / (src.stem + '.obj')
        if full or audio_cc_changed or not obj.exists() or obj.stat().st_mtime < max(src.stat().st_mtime, (RT / 'xrt.h').stat().st_mtime):
            audio_jobs.append((src, obj))
        objects.append(obj)
    if audio_jobs:
        print(f'Compiling {len(audio_jobs)} sound units {GEN_OPT} ({cc})', flush=True)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
            list(pool.map(lambda j: compile_one(j[0], j[1], env, [RT, j[0].parent], [GEN_OPT, '/wd4102', '/wd4146', '/DXRT_PCLINES'] + (['/GL'] if ltcg else []) + (['/DXRT_RV_ABI'] if rv_abi else []) + eh_define, 600, cc), audio_jobs))
        audio_stamp.parent.mkdir(parents=True, exist_ok=True)
        audio_stamp.write_text(cc + (' /GL' if ltcg else '') + (' /DXRT_RV_ABI' if rv_abi else '') + ''.join(' ' + d for d in eh_define))
    rt_flags = ['/O2', '/std:c11'] + (['/DXRT_WITH_AUDIO'] if audio else []) + (['/DXRT_RV_ABI'] if rv_abi else []) + eh_define
    rt_stamp = BUILD / 'rt-flags.txt'
    rt_flags_changed = not rt_stamp.exists() or rt_stamp.read_text() != ' '.join(rt_flags)
    headers = [*RT.glob('*.h'), *RT.glob('*.inc'), *HERE.glob('*.inc'), HERE / 'dev_support.h']
    header_time = max(p.stat().st_mtime for p in headers)
    for src in [*RT.glob('*.c'), HERE / 'dev_support.c']:
        obj = BUILD / 'obj/rt' / (src.stem + '.obj')
        if full or rt_flags_changed or not obj.exists() or obj.stat().st_mtime < max(src.stat().st_mtime, header_time):
            print('Compiling', src.name, flush=True)
            # Same optimisation as the production client runtime (build_client.cmd: /O2 /fp:strict); /Z7 keeps symbols.
            compile_one(src, obj, env, [RT, HERE], rt_flags)
        objects.append(obj)
    natives = [src for units in NATIVE.values() for _, src in units] if native else []
    natives += [src for units in PORT.values() for _, src in units]
    native_stamp = BUILD / 'obj/native/flags.txt'
    native_flags = ['/O2', '/std:c11'] + (['/DXRT_RV_ABI'] if rv_abi else []) + (['/GL'] if ltcg else []) + eh_define
    native_changed = not native_stamp.exists() or native_stamp.read_text() != ' '.join(native_flags)
    for src in natives:
        obj = BUILD / 'obj/native' / (src.stem + '.obj')
        if full or native_changed or not obj.exists() or obj.stat().st_mtime < max(src.stat().st_mtime, (RT / 'xrt.h').stat().st_mtime):
            print('Compiling native', src.name, flush=True)
            compile_one(src, obj, env, [RT], native_flags)
        objects.append(obj)
    native_stamp.parent.mkdir(parents=True, exist_ok=True)
    native_stamp.write_text(' '.join(native_flags))
    asm = BUILD / 'obj/rt/monitor_asm.obj'
    if full or not asm.exists() or asm.stat().st_mtime < (RT / 'monitor.asm').stat().st_mtime:
        command(['ml64', '/nologo', '/c', '/Zi', f'/Fo{asm}', RT / 'monitor.asm'], env, 'monitor-asm')
    objects.append(asm)
    if eh_frames:   # the ehframe landing trampoline (runtime xrt_eh.c land_frame)
        land = BUILD / 'obj/rt/xrt_eh_land_asm.obj'
        if full or not land.exists() or land.stat().st_mtime < (RT / 'xrt_eh_land.asm').stat().st_mtime:
            command(['ml64', '/nologo', '/c', '/Zi', f'/Fo{land}', RT / 'xrt_eh_land.asm'], env, 'eh-land-asm')
        objects.append(land)
    rt_stamp.write_text(' '.join(rt_flags))
    rsp = BUILD / 'objects.rsp'
    rsp.write_text('\n'.join('"' + str(p) + '"' for p in objects))
    # Inherited generated objects may refer to their existing compiler PDBs.
    # build --order FILE: link-time function order (/ORDER, one public function name per line; the generated units are
    # /O2, which implies /Gy, so every translated function is its own COMDAT). Names not in the image are ignored (LNK4037).
    order_args = [f'/ORDER:@{Path(order).resolve()}', '/IGNORE:4037'] if order else []
    command(['link', '/nologo', '/DEBUG', '/INCREMENTAL:NO', '/STACK:0x10000000', *(['/LTCG'] if ltcg else []), *order_args,
             f'/OUT:{BUILD / "unreal2-dev.exe"}', f'/PDB:{BUILD / "unreal2-dev.pdb"}', '@' + str(rsp),
             'winmm.lib', 'advapi32.lib', 'ole32.lib', 'bcrypt.lib', 'user32.lib', 'gdi32.lib', 'dbghelp.lib', 'xaudio2.lib'], env, 'link',
            timeout=7200 if ltcg else 600)
    stamp.write_bytes(abi)
    write(BUILD / 'build-state.json', {'ok': True, 'executable': str(BUILD / 'unreal2-dev.exe'),
                                      'generated_optimization': GEN_OPT, 'generated_units': len(lineage) - sum(
                                          1 for rel in lineage if rel.startswith('obj/rt/')),
                                      'native': [fn for units in NATIVE.values() for fn, _ in units] if native else [],
                                      'port': [fn for units in PORT.values() for fn, _ in units],
                                      'audio_units': len(audio), 'lean': bool(lean), 'generated_compiler': cc,
                                      'ltcg': bool(ltcg), 'rv_abi': rv_abi, 'lift_options': lift_options(),
                                      'order': {'file': str(Path(order).resolve()), 'sha256': hashlib.sha256(Path(order).read_bytes()).hexdigest()}
                                      if order else None})
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


def _ini_section_span(text, name):
    m = re.search(rb'(?m)^\[' + re.escape(name) + rb'\]\r?\n', text)
    if not m:
        return None
    end = re.search(rb'(?m)^\[', text[m.end():])
    return m.end(), m.end() + end.start() if end else len(text)

def ini_section(text, name):
    """The body lines of [name] (bytes, line endings kept), or b'' when absent."""
    span = _ini_section_span(text, name)
    return text[span[0]:span[1]] if span else b''

def replace_ini_section(text, name, body):
    span = _ini_section_span(text, name)
    if not span:
        raise RuntimeError(f'Unreal2.ini: section [{name.decode()}] not found')
    return text[:span[0]] + body + text[span[1]:]

def play_defaults(args):
    """--play: the settings of the owner's interactive runs (e.g. 20261101-222923) as one switch. Only fills in what the
    command line left at its developer default; the developer defaults themselves (benchmarks, scripted batches) are
    unchanged."""
    if args.background or args.input:
        raise RuntimeError('No launch: --play is interactive (real input); it cannot be combined with --background/--input')
    args.allow_input = True
    args.profile = args.profile or 'owner'
    if args.sound == 'off':
        args.sound = 'on'
    args.first_scene = args.first_scene or 100000
    if args.timeout == 60:
        args.timeout = 600
    args.scene_seconds = args.scene_seconds or max(1, args.timeout - 10)
    args.campaign_assets = True
    if args.capture == 'periodic':
        args.capture = 'shots'          # periodic 4K captures cost GB of disk per session and frame hitches
    if args.trace_profile == 'development':
        args.trace_profile = 'quiet'
    maps = Path(GAME_INSTALL) / 'Maps'
    args.allow_map = sorted(set(args.allow_map) | {m.name for m in maps.glob('*.un2')})
    args.question = args.question or 'Personal play session (--play)'
    args.change = args.change or 'none (personal play)'

def run(args):
    if args.play:
        play_defaults(args)
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
    # Port settings (tools/xrt/dev/port.py): U2Port.u and this sandbox's own U2Menus.ui/.int edits (Walking Speed, UI Scale).
    sys.path.insert(0, str(HERE))
    import port
    port.apply(sandbox)
    # --profile NAME (interactive play): the player's User.ini (bindings, preferences, [U2Port.PortSettings]) and the
    # display section of Unreal2.ini ([WinDrv.WindowsClient]: resolution, StartupFullscreen, brightness, detail) carried
    # from one run to the next in out/dev-init/profiles/NAME; copied back after the game ends. --windowed-res still wins.
    profile = None
    if args.profile:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', args.profile):
            raise RuntimeError('--profile: letters, digits, _ and - only')
        profile = DEV / 'profiles' / args.profile
        if (profile / 'User.ini').is_file():
            shutil.copy2(profile / 'User.ini', sandbox / 'System' / 'User.ini')
            print(f'dev: profile {args.profile}: User.ini restored', flush=True)
        if (profile / 'WindowsClient.ini').is_file():
            ini = sandbox / 'System' / 'Unreal2.ini'
            text = ini.read_bytes()
            keep = re.findall(rb'(?m)^WindowedViewport[XY]=\d+\r?\n', ini_section(text, b'WinDrv.WindowsClient')) if args.windowed_res else []
            body = (profile / 'WindowsClient.ini').read_bytes()
            for line in keep:
                body = re.sub(rb'(?m)^' + re.escape(line.split(b'=')[0]) + rb'=\d+\r?\n', line, body)
            ini.write_bytes(replace_ini_section(text, b'WinDrv.WindowsClient', body))
            print(f'dev: profile {args.profile}: display settings restored', flush=True)
    # The game starts fullscreen (borderless) when the player left it so; otherwise -windowed, as always.
    startup_fullscreen = bool(profile) and re.search(rb'(?mi)^StartupFullscreen=true\r?$', ini_section(
        (sandbox / 'System' / 'Unreal2.ini').read_bytes(), b'WinDrv.WindowsClient')) is not None
    if startup_fullscreen:
        print(f'dev: profile {args.profile}: starting full screen (borderless)', flush=True)
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
        if args.staging in ('reuse', 'guard'):
            env['XRT_DEV_STAGING'] = args.staging   # buffer staging mode (runtime resource_storage.inc)
        if args.capture == 'shots':
            env['XRT_DEV_CAPTURE'] = 'shots'   # no periodic/cue/startup readbacks (dev_support.c)
        if args.fps_cap:
            env['XRT_DEV_FPS_CAP'] = str(args.fps_cap)
        if args.affinity:
            env['XRT_DEV_AFFINITY'] = hex(args.affinity)   # dev_support.c dev_start: SetProcessAffinityMask at start-up
        if args.borderless:
            env['XRT_DEV_BORDERLESS'] = '1'   # opt-in borderless viewport window (runtime hle_gui_classes.inc create_window)   # development frame limiter (dev_support.c perf_cap_wait)
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
                                     'affinity': hex(args.affinity) if args.affinity else None,
                                     'native': read(BUILD / 'build-state.json').get('native', []), 'sound': args.sound})
    if args.attach:
        env['XRT_DEV_ATTACH'] = '1'
    if args.sound != 'off':
        if not read(BUILD / 'build-state.json').get('audio_units'):
            raise RuntimeError('No launch: --sound needs a build with the sound modules (dev.py lift-audio, then build)')
        env['XRT_DEV_SOUND'] = args.sound   # muted: full ALAudio/OpenAL/XAudio2 path, mastering volume 0 (hle_openal.c)
    command_args = ['--guest', sandbox / 'System/Unreal2.exe', '--log', out / 'xrt.log',
                    '--report', out / 'runtime-report.json', '--run-id', out.name,
                    '--timeout-ms', str(args.timeout * 1000), '--', 'CS_Intro.un2',
                    *([] if startup_fullscreen else ['-windowed']), *([] if args.sound != 'off' else ['-nosound']), '-NOMMX', '-NOSSE']
    print('Run output:', out, flush=True)
    try:
        code = launch(exe, command_args, out, sandbox / 'System', env, args.timeout)
        reached = scene_proven(out, code) if args.first_scene else endpoint_proven(out, code)
        outcome = read(out / 'runtime-report.json').get('outcome') if (out / 'runtime-report.json').exists() else 'No runtime report; inspect console.txt'
        if profile and (sandbox / 'System' / 'User.ini').is_file():
            profile.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sandbox / 'System' / 'User.ini', profile / 'User.ini')
            section = ini_section((sandbox / 'System' / 'Unreal2.ini').read_bytes(), b'WinDrv.WindowsClient')
            if section:
                (profile / 'WindowsClient.ini').write_bytes(section)
            print(f'dev: profile {args.profile}: User.ini and display settings saved', flush=True)
        if code == 0 and outcome == 'exited':
            print('dev: the game exited normally (its own shutdown, ExitProcess(0))', flush=True)
        done = ('Init returned; world frames presented to the first-scene stop (console.txt names it; inspect scene-frame-*.bmp)'
                if args.first_scene else 'Init returned; main loop not entered')
        report(out, args.change, args.question,
               done if reached else 'See console.txt, xrt.log and runtime-report.json',
               'None observed before endpoint' if reached else f'{outcome}; exit {code:#x}; 124=deadline, 125=harness, 130=cancel',
               'Review Init return; separately scope first scene/tick' if reached else 'Fix the first fatal/unsupported call; keep the same milestone')
        observe(out)
        return 0 if reached else 1
    finally:
        print('dev: verifying the snapshot assets (read-only check, about a minute; the game has ended)', flush=True)
        assets.verify()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('setup')
    b = sub.add_parser('build'); b.add_argument('--full', action='store_true')
    b.add_argument('--diag-move', action='store_true', help='also observe ULevel::MoveActor/AActor::moveSmooth (blocking-hit log; slower)')
    b.add_argument('--native', action='store_true', help='link the native C replacements in NATIVE instead of their translations')
    b.add_argument('--lean', action='store_true', help='generated code without the per-entry function history ring (xrt.h XRT_LEAN_ENTER); '
                                                       'fatal dumps keep the guest-stack scan, the preemption check stays')
    b.add_argument('--cc', choices=sorted(COMPILERS), default='cl', help='compiler for the generated and sound units (the runtime stays cl)')
    b.add_argument('--order', metavar='FILE', help='link-time function order (/ORDER:@FILE): hot translated functions first')
    b.add_argument('--ltcg', action='store_true', help='generated and native units /GL, link /LTCG (whole-program optimization across the '
                                                       'translated units; long link); the runtime units stay as they are')
    lp = sub.add_parser('lift', help='re-lift shared generated modules into developer copies (then build)')
    lp.add_argument('--opt', default='', help='xlift --opt list (flags,pc); empty = plain lift')
    lp.add_argument('modules', nargs='+', help='gen/ directory names, e.g. fire engine core')
    la = sub.add_parser('lift-audio', help='lift ALAudio.dll and the Ogg Vorbis DLLs into out/dev-init/audio-lift')
    la.add_argument('--opt', default='', help='xlift --opt list; empty = plain lift')
    sub.add_parser('port-build', help='compile the port settings package U2Port.u (original UCC make, staging copy)')
    sub.add_parser('selftest')
    sub.add_parser('observe')
    r = sub.add_parser('run')
    r.add_argument('--authorize-init', action='store_true', help='acknowledge separately granted owner authorization for this development Init run')
    r.add_argument('--question', default=''); r.add_argument('--change', default='')
    r.add_argument('--play', action='store_true',
                   help='personal play (owner): the interactive defaults of the owner\'s own runs - real keyboard/mouse '
                        '(--allow-input), --profile owner, --sound on, past Init for the longest contained run (--first-scene, '
                        '--timeout 600), every retail single-player map allowed, install campaign content, no periodic '
                        'back-buffer captures, quiet trace; explicit options still win. The owner authorization flags stay '
                        'explicit (--authorize-init --authorize-first-scene)')
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
                   help='first-scene: short explicit input script "T:verb[:args];..." (key/move/click/rclick/shot/cpu/size), '
                        'T in ms after Init; delivered to the game window only, isolation stays on')
    # guard is the play default since round 4 (owner decision 2026-11-02, after the strict-vs-guard differential test and the
    # game regressions of PERF_REPORT_20261102_R4.md section B); strict stays available as the diagnostic/reference mode
    # (bench_tuta.ps1 still passes --staging strict unless told otherwise, so benchmarks stay comparable with earlier rounds)
    r.add_argument('--staging', choices=('strict', 'reuse', 'guard'), default='guard',
                   help='D3D8 buffer Lock staging: guard (default; block PAGE_NOACCESS between uses, stale pointers fault as in '
                        'strict), strict (reference: decommitted at Unlock, stale pointers fault) or reuse (diagnostics only: '
                        'stale pointers into a warm block are not trapped)')
    r.add_argument('--capture', choices=('periodic', 'shots'), default='periodic',
                   help='first-scene back-buffer captures: periodic (default; powers of two, every 256th world frame, cues) or shots (scripted shots only)')
    r.add_argument('--diag-move', action='store_true',
                   help='log what blocks the player (needs a build --diag-move executable)')
    r.add_argument('--seed-save', action='append', default=[], metavar='FILE.usa',
                   help='copy a save written by an earlier developer run (its sandbox Save folder) into this run\'s Save')
    r.add_argument('--background', action='store_true',
                   help="developer background mode: the game runs behind the owner's foreground application and never "
                        'takes focus; only --input reaches it (needs isolation; dev_support.c xrt_dev_background)')
    r.add_argument('--profile', default='', metavar='NAME',
                   help="interactive play: keep the player's User.ini (settings, Walking Speed, UI Scale) between runs in out/dev-init/profiles/NAME")
    r.add_argument('--borderless', action='store_true',
                   help='opt-in borderless viewport window at the monitor origin (use --windowed-res = monitor size for borderless full screen)')
    r.add_argument('--sound', choices=('off', 'muted', 'on'), default='off',
                   help='off: -nosound (default); muted/on: ALAudio through runtime hle_openal.c (XAudio2); muted keeps the '
                        'whole path running with the mastering volume at 0 (mix levels are still measured)')
    r.add_argument('--fps-cap', type=int, choices=range(0, 1001), default=0, metavar='0..1000',
                   help='first-scene: development frame limiter after each post-Init Present (waitable timer, baton released; 0 = uncapped)')
    r.add_argument('--affinity', type=lambda v: int(v, 0), default=0, metavar='MASK',
                   help='first-scene: pin the game process (and the helpers it starts) to these logical CPUs, e.g. 0xFFFF for '
                        'the first 16 (the 9950X3D V-cache CCD: 15-23%% faster than unpinned, measured 2026-11-02); per-process only')
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
    elif args.action == 'build': build(args.full, native=args.native, diag_move=args.diag_move, lean=args.lean, cc=args.cc, ltcg=args.ltcg, order=args.order)
    elif args.action == 'lift': lift(args.modules, {x for x in args.opt.split(',') if x})
    elif args.action == 'lift-audio': lift_audio({x for x in args.opt.split(',') if x})
    elif args.action == 'port-build':
        sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
        import port, asset_boundary
        print('Built', port.build(Path(asset_boundary.source()) / 'System'))
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
