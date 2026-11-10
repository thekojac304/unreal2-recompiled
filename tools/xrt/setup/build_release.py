"""Assemble the downloadable Unreal II Enhanced release (tools/xrt/setup/README.md).

  python -I tools/xrt/setup/build_release.py --version 0.1.0-alpha.1 [--llvm "C:\\Program Files\\LLVM"]

Needs (release builder's machine only): Visual Studio 2026 C++ tools (the player is built with MSVC, as before), the
venv from requirements.txt plus PyInstaller (requirements-release.txt), LLVM 23.1.4 for Windows x64 (its clang-cl and
lld-link are bundled), network access once (DXVK and LLVM's license text). The game is NOT needed: the release
contains no translated game code; that is made on the player's machine by setup\\u2gen.exe.

Output: out/release/UnrealII-Enhanced-<version>-win-x64.zip and SHA256SUMS.txt.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / 'tools/xrt/dev'))
import dev  # noqa: E402

LLVM_VERSION = '23.1.4'
LLVM_LICENSE_URL = f'https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-{LLVM_VERSION}/llvm/LICENSE.TXT'
NAME = 'Unreal II Enhanced'


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode:
        raise SystemExit(f'failed: {cmd[0]}\n{r.stdout[-3000:]}{r.stderr[-3000:]}')
    return r.stdout


def layout_asserts(stage):
    """The runtime compiler's view of the shared structures, as C11 assertions u2gen compiles with clang-cl."""
    env = dev.compiler_environment()
    out = stage / 'probe'
    out.mkdir(parents=True, exist_ok=True)
    cl = shutil.which('cl', path=next(v for k, v in env.items() if k.upper() == 'PATH'))
    opts = set(dev.read(dev.MANIFEST)['player']['lift_options'])
    run([cl, '/nologo', '/std:c11', '/DXRT_WITH_UNREAL2', '/DXRT_WITH_AUDIO'] + (['/DXRT_RV_ABI'] if 'rv' in opts else []) +
        (['/DXRT_EH_FRAMES'] if 'ehframe' in opts else []) + [f'/I{dev.RT}', HERE / 'layout_probe.c', f'/Fe:{out / "probe.exe"}',
        f'/Fo:{out / "probe.obj"}'], env=env, cwd=out)
    text = run([out / 'probe.exe'])
    assert text.count('_Static_assert') >= 30
    return text


def freeze_generator(stage):
    """setup\\u2gen.exe: the generator with the project's translator and build steps (PyInstaller, one folder)."""
    data = stage / 'u2gen-data'
    if data.exists():
        shutil.rmtree(data)
    for rel, pattern in [('tools/xrt', '*.py'), ('tools/xrt', '*.json'), ('tools/xrt/dev', '*.py'), ('tools/xrt/dev', '*.json'),
                         ('tools/xrt/dev', 'order-r4-multi.txt'), ('tools/xrt/dev/port/U2Port/Classes', '*.uc'),
                         ('tools/xrt/setup', 'glue.c'), ('tools/xrt/setup/include', '*')]:
        (data / rel).mkdir(parents=True, exist_ok=True)
        for f in (WS / rel).glob(pattern):
            if f.is_file():
                shutil.copy2(f, data / rel / f.name)
    (data / 'tools/xrt/setup/runtime-include').mkdir(parents=True, exist_ok=True)
    for h in ('xrt.h', 'world_observer.h'):
        shutil.copy2(dev.PLAYER_SRC / 'runtime' / h, data / 'tools/xrt/setup/runtime-include' / h)
    (data / 'tools/xrt/setup/layout_asserts.c').write_text(layout_asserts(stage))
    pyi = stage / 'pyi'
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console', '--name', 'u2gen',
         '--distpath', pyi / 'dist', '--workpath', pyi / 'work', '--specpath', pyi,
         '--paths', WS / 'tools/xrt', '--paths', WS / 'tools/xrt/dev',
         *sum((['--hidden-import', m] for m in ('xlift', 'discover', 'peimage', 'lift_sse2', 'dev', 'port', 'pefile')), []),
         '--collect-all', 'capstone', '--add-data', f'{data / "tools"}{";"}tools', HERE / 'u2gen.py'])
    return pyi / 'dist' / 'u2gen'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--llvm', default=r'C:\Program Files\LLVM')
    a = ap.parse_args()
    llvm = Path(a.llvm)
    ver = run([llvm / 'bin' / 'clang-cl.exe', '--version'])
    if f'clang version {LLVM_VERSION}' not in ver:
        raise SystemExit(f'LLVM {LLVM_VERSION} is pinned for the bundled toolchain; found: {ver.splitlines()[0]}')
    stage = WS / 'out/release/stage'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    pb = dev.player_build_split()
    gen = freeze_generator(stage)
    dxvk = dev.fetch_dxvk()
    dist = stage / NAME
    (dist / 'dxvk').mkdir(parents=True)
    for f in ('Unreal II Enhanced.exe', 'dmusic_helper.exe'):
        shutil.copy2(pb / f, dist / f)
    for f in ('d3d8.dll', 'd3d9.dll'):
        shutil.copy2(dxvk / f, dist / 'dxvk' / f)
    shutil.copy2(dev.HERE / 'player' / 'DXVK-LICENSE.txt', dist / 'dxvk' / 'LICENSE.txt')
    shutil.copytree(gen, dist / 'setup')
    shutil.copy2(pb / 'UnrealIIEnhanced.lib', dist / 'setup' / 'UnrealIIEnhanced.lib')
    tc = dist / 'toolchain'
    (tc / 'bin').mkdir(parents=True)
    for f in ('clang-cl.exe', 'lld-link.exe'):
        shutil.copy2(llvm / 'bin' / f, tc / 'bin' / f)
    shutil.copytree(llvm / 'lib' / 'clang', tc / 'lib' / 'clang')
    (tc / 'LICENSE-LLVM.txt').write_bytes(urllib.request.urlopen(LLVM_LICENSE_URL, timeout=120).read())
    (tc / 'VERSION.txt').write_text(f'LLVM {LLVM_VERSION} (clang-cl, lld-link and the clang resource headers), unmodified\n')
    shutil.copy2(HERE / 'README-player.txt', dist / 'README.txt')
    shutil.copy2(HERE / 'THIRD-PARTY-NOTICES.txt', dist / 'THIRD-PARTY-NOTICES.txt')
    lic = dist / 'LICENSES'
    lic.mkdir()
    shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', lic / 'Python-LICENSE.txt')
    import importlib.metadata as md
    for pkg in ('capstone', 'pefile', 'pyinstaller'):
        files = [f for f in (md.files(pkg) or []) if 'LICENSE' in f.name.upper() or 'COPYING' in f.name.upper()]
        if not files:
            raise SystemExit(f'no license file found for {pkg}')
        for f in files:
            shutil.copy2(f.locate(), lic / f'{pkg}-{f.name}')
    out = WS / 'out/release'
    zname = f'UnrealII-Enhanced-{a.version}-win-x64.zip'
    with zipfile.ZipFile(out / zname, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(dist.rglob('*')):
            if p.is_file():
                z.write(p, Path(NAME) / p.relative_to(dist))
    digest = hashlib.sha256((out / zname).read_bytes()).hexdigest()
    (out / 'SHA256SUMS.txt').write_text(f'{digest}  {zname}\n')
    print(f'{out / zname}  {(out / zname).stat().st_size // 1048576} MB  sha256 {digest}')


if __name__ == '__main__':
    main()
