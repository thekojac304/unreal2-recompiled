"""Player setup tests that start NO game process: the launcher half only (--prepare-only, or an installation error that
stops it before the game). Each runs under contain.exe (Job, 60 s deadline). Checks: exit codes, player.log messages,
the prepared data folder, the profile import, and that the installation and the import source are unchanged.
Run: python -I tools/xrt/dev/player/setup_tests.py (needs dev.py player-build; writes out/player/test-data/setup)
U2_GAME_INSTALL: the installation's singleplayer folder (default: the original machine's). U2_TEST_PROFILE: a developer
play profile folder for the two import cases; without one they are skipped (reported, not passed)."""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

WS = Path(__file__).resolve().parents[4]
EXE = WS / 'out/player/dist/Unreal II Enhanced/Unreal II Enhanced.exe'
CONTAIN = WS / 'out/dev-init/build/contain.exe'
INSTALL = Path(os.environ['U2_GAME_INSTALL']).parent if os.environ.get('U2_GAME_INSTALL') else \
    Path(r'E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening')
SP = INSTALL / 'singleplayer'
ROOT = WS / 'out/player/test-data/setup'
PROFILE = Path(os.environ.get('U2_TEST_PROFILE') or WS / 'out/dev-init/profiles/owner')
HAVE_PROFILE = (PROFILE / 'User.ini').is_file()
results = []


def tree_state(root, skip=('Save',)):
    """name -> (size, mtime_ns) of every file, without following links (the install's Save junction is skipped)"""
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not os.path.islink(os.path.join(dirpath, d))
                       and not (os.stat(os.path.join(dirpath, d), follow_symlinks=False).st_file_attributes & 0x400)]
        for f in filenames:
            st = os.stat(os.path.join(dirpath, f), follow_symlinks=False)
            state[os.path.relpath(os.path.join(dirpath, f), root)] = (st.st_size, st.st_mtime_ns)
    return state


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}


def player(name, *args):
    out = ROOT / ('out-' + name)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k.upper() in ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'SYSTEMDRIVE', 'USERPROFILE',
                                                                'USERNAME', 'LOCALAPPDATA', 'APPDATA', 'PATH', 'PROGRAMDATA')}
    cmd = subprocess.list2cmdline([str(EXE), *map(str, args), '--unattended'])
    code = subprocess.run([str(CONTAIN), '60', str(out), str(EXE.parent), cmd], env=env).returncode
    return code


def check(label, ok, detail=''):
    results.append((label, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + label + (': ' + detail if detail else ''), flush=True)


def log_text(data):
    p = data / 'Logs' / 'player.log'
    return p.read_text(encoding='utf-8-sig', errors='replace') if p.exists() else ''


shutil.rmtree(ROOT, ignore_errors=True)
ROOT.mkdir(parents=True)
install_before = tree_state(INSTALL)
profile_before = hashes(PROFILE) if HAVE_PROFILE else None

# 1. missing installation
data = ROOT / 'd-missing'
code = player('missing', '--data', data, '--game', ROOT / 'no-such-folder', '--prepare-only')
check('missing installation -> exit 3 with a readable message', code == 3 and 'No Unreal II installation' in log_text(data),
      f'exit {code}')

# 2. incomplete / wrong-version installation (a scratch copy of System with one byte of Engine.dll changed)
fake = ROOT / 'fake-install'
shutil.copytree(SP / 'System', fake / 'System')
data = ROOT / 'd-incomplete'
code = player('incomplete', '--data', data, '--game', fake, '--prepare-only')
check('incomplete installation -> exit 3 naming the missing file', code == 3 and 'Required game file or folder missing' in log_text(data),
      f'exit {code}')
for rel in ('UIScripts', 'Maps', 'Music', 'Textures', 'Sounds', 'StaticMeshes', 'Meshes', 'Voice', 'Scripts', 'Dialog'):
    (fake / rel).mkdir(exist_ok=True)
for rel in ('UIScripts/U2Menus.ui', 'Maps/CS_Intro.un2', 'Maps/TutA.un2', 'Music/Intro.con'):
    shutil.copy2(SP / rel, fake / rel)
engine = fake / 'System' / 'Engine.dll'
b = bytearray(engine.read_bytes()); b[0x400] ^= 0xFF; engine.write_bytes(bytes(b))
data = ROOT / 'd-version'
code = player('version', '--data', data, '--game', fake, '--prepare-only')
check('wrong module version -> exit 3 naming Engine.dll', code == 3 and 'Engine.dll is not the version' in log_text(data), f'exit {code}')
shutil.rmtree(fake)

# 3. clean data folder, real installation (install root given: singleplayer is found)
data = ROOT / 'd-clean'
code = player('clean', '--data', data, '--game', INSTALL, '--prepare-only')
sysfiles = list((data / 'System').rglob('*'))
ini = (data / 'player.ini').read_bytes().decode('utf-16') if (data / 'player.ini').exists() else ''
menus = (data / 'UIScripts' / 'U2Menus.ui').read_bytes() if (data / 'UIScripts' / 'U2Menus.ui').exists() else b''
check('clean prepare -> exit 0', code == 0, f'exit {code}')
check('player.ini remembers the singleplayer folder', ('GamePath=' + str(SP)) in ini, ini.strip()[:200])
check('System copied (283+ files) without logs', len([p for p in sysfiles if p.is_file()]) >= 283 and
      not (data / 'System' / 'Unreal2.log').exists(), f'{len(sysfiles)} entries')
check('U2Port.u and the menu edits in place', (data / 'System' / 'U2Port.u').is_file() and b'PortSettings' in menus and
      b'Walking Speed' in (data / 'System' / 'U2Menus.int').read_bytes())
check('UIScripts holds only the edited menu file (the rest comes from the installation)',
      [p.name for p in (data / 'UIScripts').iterdir()] == ['U2Menus.ui'])
check('Save is a plain empty folder', (data / 'Save').is_dir() and not any((data / 'Save').iterdir()) and
      not os.stat(data / 'Save', follow_symlinks=False).st_file_attributes & 0x400)

# 4. second prepare: remembered path, nothing re-copied, user ini kept
user_ini = data / 'System' / 'User.ini'
user_ini.write_bytes(user_ini.read_bytes() + b'\r\n[PlayerTest]\r\nKept=1\r\n')
code = player('again', '--data', data, '--prepare-only')
check('second prepare uses the remembered path, keeps User.ini, copies nothing new',
      code == 0 and b'Kept=1' in user_ini.read_bytes() and log_text(data).count('data folder ready: 0 installation file(s)') == 1,
      f'exit {code}')

if HAVE_PROFILE:
    # 5. import of the owner's developer profile into a fresh data folder
    data = ROOT / 'd-import'
    code = player('import', '--data', data, '--game', INSTALL, '--import-profile', PROFILE, '--prepare-only')
    saves = sorted(p.name for p in (data / 'Save').glob('*.usa'))
    src_saves = sorted(p.name for p in (PROFILE / 'Save').glob('*.usa'))
    same = all(hashlib.sha256((data / 'Save' / n).read_bytes()).digest() == hashlib.sha256((PROFILE / 'Save' / n).read_bytes()).digest()
               for n in src_saves)
    uni = (data / 'System' / 'Unreal2.ini').read_bytes()
    check('import -> exit 0, saves copied byte-identical', code == 0 and saves == src_saves and same, f'{saves}')
    check('import: User.ini = profile User.ini; display section from WindowsClient.ini',
          (data / 'System' / 'User.ini').read_bytes() == (PROFILE / 'User.ini').read_bytes() and b'WindowedViewportY=1369' in uni)
    check('import: earlier User.ini/Unreal2.ini backed up', any(p.name.startswith('User.ini.before-import-') for p in (data / 'System').iterdir()))
    # 6. import again: existing saves are not overwritten
    (data / 'Save' / src_saves[0]).write_bytes(b'player-own-save')
    code = player('import2', '--data', data, '--import-profile', PROFILE, '--prepare-only')
    check('second import keeps the player\'s own save of the same name', code == 0 and
          (data / 'Save' / src_saves[0]).read_bytes() == b'player-own-save' and 'not copied because' in log_text(data))

else:
    print('SKIP import cases 5-6: no developer profile (set U2_TEST_PROFILE)', flush=True)

# 7. unknown option
code = player('badopt', '--data', ROOT / 'd-badopt', '--frobnicate')
check('unknown option -> exit 6, nothing started', code == 6, f'exit {code}')

check('installation unchanged (sizes and times of every file, Save junction not entered)', tree_state(INSTALL) == install_before)
if HAVE_PROFILE:
    check('import source profile unchanged', hashes(PROFILE) == profile_before)
json.dump([{'test': a, 'pass': b, 'detail': c} for a, b, c in results], open(ROOT / 'results.json', 'w'), indent=1)
print(sum(r[1] for r in results), 'of', len(results), 'passed')
sys.exit(0 if all(r[1] for r in results) else 1)
