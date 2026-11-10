"""u2gen - builds the game-specific part of Unreal II Enhanced on the player's machine.

The player (tools/xrt/dev/player.c, split build) runs this once per installation and player version:

  u2gen --game <singleplayer folder> --out <folder> [--jobs N]

It checks the installation against tools/xrt/dev/build_manifest.json, translates the game's own modules with the
project's translator exactly as the reference build does (dev.py regenerate / lift / lift-audio, reused unchanged),
compiles the result with the bundled clang-cl and links it with lld-link into UnrealII-game.dll, which the player
loads. It also compiles the Enhanced settings package U2Port.u with the installation's own UCC.exe (port.py). Nothing
is sent anywhere; everything stays in --out. Progress lines on stdout: "PROGRESS <percent> <text>".

Frozen with PyInstaller (tools/xrt/setup/build_release.py): the executable also accepts "-I script.py args", so the
existing tools that start the translator as a Python subprocess work unchanged inside the frozen program.
"""
import argparse
import hashlib
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GENERATOR_VERSION = '1'
DLL_NAME = 'UnrealII-game.dll'
# translated module tables, in the order of the runtime's static list (xrt_main.c lifted_all)
MODULE_TABLES = ['UCC', 'Core', 'Engine', 'GlmLib', 'Editor', 'Window', 'UnrImp', 'Fire', 'Unreal2', 'WinDrv', 'D3DDrv',
                 'ParticleSystems', 'Legend', 'UI', 'U2', 'U2Dialog', 'U2AI', 'vorbisfile', 'ogg', 'vorbis', 'ALAudio']
GEN_FLAGS = ['/O2', '/fp:strict', '/w', '/GS-', '/X', '/DXRT_GAME_DLL', '/DXRT_WITH_UNREAL2', '/D_CRT_SECURE_NO_WARNINGS',
             '/DXRT_PCLINES', '/DXRT_LEAN_ENTER',
             # the shared lift's tables declare void functions while XRT_RV_ABI builds return uint32_t: MSVC warns,
             # clang errors by default; the reference build compiled the same tables, so keep MSVC's behaviour
             '/clang:-Wno-error=incompatible-function-pointer-types']


if os.name == 'nt':   # the player starts us without a console: keep the translator subprocesses windowless too
    _Popen = subprocess.Popen

    class _QuietPopen(_Popen):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault('creationflags', 0x08000000)   # CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)
    subprocess.Popen = _QuietPopen


def progress(pct, text):
    print(f'PROGRESS {int(pct)} {text}', flush=True)


def bundle_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))


def load_dev(work, game):
    """tools/xrt/dev/dev.py and port.py as modules, with their workspace paths pointed at the work folder."""
    root = bundle_root()
    # the translator scripts are started as subprocesses from <WS>/tools/xrt: give the work folder its own copy
    for rel in ('tools/xrt', 'tools/xrt/dev', 'tools/xrt/dev/port/U2Port/Classes'):
        (work / rel).mkdir(parents=True, exist_ok=True)
        for f in (root / rel).iterdir():
            if f.is_file() and f.suffix in ('.py', '.json', '.txt', '.uc'):
                shutil.copy2(f, work / rel / f.name)
    os.environ['U2_GAME_INSTALL'] = str(game)
    sys.path.insert(0, str(work / 'tools/xrt/dev'))
    sys.path.insert(0, str(work / 'tools/xrt'))
    import dev  # noqa: E402  (the copy in the work folder: its WS is the work folder)
    import port  # noqa: E402
    dev.LIFT_SYSTEM = Path(game) / 'System'
    return dev, port


def compile_all(dev, toolchain, runtime_inc, compat_inc, objdir, jobs):
    manifest = dev.read(dev.MANIFEST)
    opts = set(manifest['player']['lift_options'])
    flags = list(GEN_FLAGS) + (['/DXRT_RV_ABI'] if 'rv' in opts else []) + (['/DXRT_EH_FRAMES'] if 'ehframe' in opts else [])
    clang = str(toolchain / 'bin' / 'clang-cl.exe')
    units = []
    for obj, u in manifest['units'].items():
        src = dev.DEV / 'generated' / Path(u['source']).name
        if not src.is_file():
            src = dev.WS / u['source']
        extra = ['/FIworld_observer.h'] if u['observer'] or src.name in dev.DEV_OBSERVED_UNITS else []
        if src.name in dev.PORT:   # Enhanced hooks: the translated function keeps its body under a new name
            text = src.read_text(encoding='latin-1')
            for fn, _ in dev.PORT[src.name]:
                head = re.compile(r'^((?:XRT_EH_FN )?(?:void|uint32_t)) ' + fn + r'\((CPU\*(?: __restrict)?) c\) \{$', re.M)
                if len(head.findall(text)) != 1:
                    raise RuntimeError(f'{src.name}: definition of {fn} found {len(head.findall(text))} times')
                text = head.sub(lambda m: f'{m.group(1)} {fn}_translated({m.group(2)} c) {{', text)
            port_src = objdir / 'port-src' / src.name
            port_src.parent.mkdir(parents=True, exist_ok=True)
            port_src.write_text(text, encoding='latin-1')
            units.append((port_src, src.parent, extra))
        else:
            units.append((src, src.parent, extra))
    for src in sorted(dev.AUDIO_LIFT.glob('*/*.c')):
        units.append((src, src.parent, []))
    units.append((bundle_root() / 'tools/xrt/setup/glue.c', None, []))
    units.append((objdir.parent / 'layout_asserts.c', None, []))
    done = [0]

    def one(job):
        src, unit_dir, extra = job
        obj = objdir / (src.parent.name + '_' + src.stem + '.obj')
        inc = [f'-I{compat_inc}', f'-I{runtime_inc}'] + ([f'-I{unit_dir}'] if unit_dir else [])
        r = subprocess.run([clang, '/nologo', '/c', *flags, *extra, *inc, str(src), f'/Fo{obj}'],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f'compiling {src.name} failed:\n{r.stdout}{r.stderr}'[-3000:])
        done[0] += 1
        progress(40 + 45 * done[0] / len(units), f'Compiling game code ({done[0]} of {len(units)})')
        return obj
    objdir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(one, units)), manifest


def link(toolchain, objs, player_lib, order, out_dll, exports):
    rsp = out_dll.with_suffix('.rsp')
    rsp.write_text('\n'.join('"' + str(o) + '"' for o in objs))
    cmd = [str(toolchain / 'bin' / 'lld-link.exe'), '/nologo', '/DLL', '/NOENTRY', '/NODEFAULTLIB', '/OPT:REF', '/OPT:ICF',
           f'/OUT:{out_dll}', '@' + str(rsp), str(player_lib), *[f'/EXPORT:{e}' for e in exports]]
    if order and order.is_file():
        cmd.append(f'/ORDER:@{order}')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'linking failed:\n{r.stdout}{r.stderr}'[-4000:])


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '-I':   # "python -I script.py args" for the reused tools
        script = sys.argv[2]
        sys.argv = [script] + sys.argv[3:]
        sys.path.insert(0, str(Path(script).parent))
        runpy.run_path(script, run_name='__main__')
        return 0
    ap = argparse.ArgumentParser(prog='u2gen')
    ap.add_argument('--game', required=True, help="the installation's singleplayer folder")
    ap.add_argument('--out', required=True)
    ap.add_argument('--toolchain', default=None, help='folder with bin/clang-cl.exe and bin/lld-link.exe')
    ap.add_argument('--player-lib', required=True, help="the player's import library (exports for the game code)")
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--keep-work', action='store_true', help='keep the intermediate files (troubleshooting)')
    a = ap.parse_args()
    out, root = Path(a.out), bundle_root()
    toolchain = Path(a.toolchain) if a.toolchain else root / 'toolchain'
    work = out / 'work'
    t0 = time.time()
    progress(1, 'Checking the game files')
    dev, port = load_dev(work, Path(a.game))
    manifest = dev.read(dev.MANIFEST)
    try:
        dev.check_install(manifest)
    except RuntimeError as e:
        print('ERROR ' + str(e), flush=True)
        return 3
    progress(5, 'Translating the game program (this takes a few minutes)')
    dev.regenerate()
    progress(20, 'Preparing the translation for the player')
    (dev.DEV / 'generated').mkdir(parents=True, exist_ok=True)
    opts = manifest['player']
    dev.lift([m['dir'] for m in manifest['translator']['modules']], set(opts['lift_options']))
    dev.lift_audio(set(opts['audio_lift_options']))
    check = dev.compare_reference()
    shutil.copy2(root / 'tools/xrt/setup/layout_asserts.c', work / 'layout_asserts.c')
    progress(40, 'Compiling game code')
    objs, _ = compile_all(dev, toolchain, root / 'tools/xrt/setup/runtime-include', root / 'tools/xrt/setup/include',
                          work / 'obj', a.jobs)
    progress(86, 'Linking game code')
    tmp_dll = work / DLL_NAME
    exports = [fn + '_translated' for units in dev.PORT.values() for fn, _ in units] + ['xrt_msvcr70_pow_sse2']
    link(toolchain, objs, Path(a.player_lib), root / opts['order'], tmp_dll, exports)
    progress(90, 'Building the Enhanced settings package')
    port.OUT = work / 'port'
    port.PACKAGE = port.OUT / 'U2Port.u'
    port.OUT.mkdir(parents=True, exist_ok=True)
    package = port.build(Path(a.game) / 'System')
    shutil.copy2(tmp_dll, out / DLL_NAME)
    shutil.copy2(package, out / 'U2Port.u')
    (out / 'gamecode.json').write_text(json.dumps({
        'generator': GENERATOR_VERSION, 'built': time.strftime('%Y-%m-%d %H:%M:%S'), 'seconds': round(time.time() - t0),
        'dll_sha256': hashlib.sha256((out / DLL_NAME).read_bytes()).hexdigest(), 'reference_check': check}, indent=1))
    if not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    progress(100, 'Done')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:  # reported to the player, which shows it
        print('ERROR ' + str(e).replace('\n', ' | ')[:2000], flush=True)
        sys.exit(1)
