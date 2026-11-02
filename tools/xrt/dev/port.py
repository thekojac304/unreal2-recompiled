"""Port settings package and menu overlay (walking speed, UI scale).

  build()            compiles tools/xrt/dev/port/U2Port (UnrealScript) into out/dev-init/port/U2Port.u with the ORIGINAL
                     UCC.exe make, in a fresh staging copy of the snapshot System folder (sandbox_cmp/u2port-make; an ini
                     derived from Unreal2.ini whose only EditPackages are Core, Engine, UI, U2Port, so make builds only
                     U2Port). Not a game launch: UCC runs the script compiler commandlet only.
  apply(sandbox)     adds U2Port.u to a run sandbox and edits that sandbox's own copies of UIScripts/U2Menus.ui and
                     System/U2Menus.int (never the install): every edit is anchored on text that must occur exactly once.

Menu changes: Options > Game gets a Walking Speed slider (75..200, step 5, row 11); Options > Video gets a UI Scale
selector (Auto, 100%, 125%, 150%, 200%, row 12). The game's own Fullscreen checkbox (row 10) stays: fullscreen is
borderless in this port (runtime d3d8_borderless.inc), with the chosen resolution scaled to the monitor.
"""
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
SOURCE = HERE / 'port' / 'U2Port'
OUT = WS / 'out' / 'dev-init' / 'port'
PACKAGE = OUT / 'U2Port.u'
STAGE = WS / 'sandbox_cmp' / 'u2port-make'


def build(snapshot_system):
    """Compile U2Port.u; returns its path. Raises RuntimeError with UCC's output on failure."""
    if STAGE.exists():
        shutil.rmtree(STAGE)
    shutil.copytree(snapshot_system, STAGE / 'System')
    shutil.copytree(SOURCE / 'Classes', STAGE / 'U2Port' / 'Classes')
    system = STAGE / 'System'
    text = (system / 'Unreal2.ini').read_bytes().decode('latin-1')
    section = re.search(r'(?ms)^\[Editor\.EditorEngine\]\r?\n(.*?)(?=^\[|\Z)', text)
    if not section or 'EditPackages=' not in section.group(1):
        raise RuntimeError('Unreal2.ini: [Editor.EditorEngine] EditPackages not found')
    body = section.group(1)
    eol = '\r\n' if '\r\n' in body else '\n'
    first = body.index('EditPackages=')
    kept = ''.join(line for line in body[first:].splitlines(True) if not line.startswith('EditPackages='))
    body = body[:first] + ''.join(f'EditPackages={p}{eol}' for p in ('Core', 'Engine', 'UI', 'U2Port')) + kept
    (system / 'U2Port.ini').write_bytes((text[:section.start(1)] + body + text[section.end(1):]).encode('latin-1'))
    (system / 'U2Port.u').unlink(missing_ok=True)
    run = subprocess.run([str(system / 'UCC.exe'), 'make', '-ini=U2Port.ini', '-silent'], cwd=system,
                         capture_output=True, text=True, encoding='latin-1', timeout=300)
    output = run.stdout + run.stderr
    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / 'ucc-make.txt').write_text(output, encoding='utf-8')
    ok = run.returncode == 0 and re.search(r'(?m)^Success - 0 error\(s\)', output) and (system / 'U2Port.u').is_file()
    if not ok:
        raise RuntimeError(f'U2Port make failed (exit {run.returncode}); see {OUT / "ucc-make.txt"}:\n{output[-2000:]}')
    shutil.copy2(system / 'U2Port.u', PACKAGE)
    return PACKAGE


def edit(path, edits):
    """Apply (old, new) replacements to a CRLF latin-1 file; each old text must occur exactly once."""
    text = path.read_bytes().decode('latin-1')
    for old, new in edits:
        old, new = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')
        if text.count(old) != 1:
            raise RuntimeError(f'{path.name}: anchor found {text.count(old)} times: {old[:60]!r}')
        text = text.replace(old, new)
    path.write_bytes(text.encode('latin-1'))


SLIDER = """Component=U2Slider:234
	Range=0,1
	Format=Float2Format
	Object=CodeMonkey
	Variable=Dodging
"""
VSYNC = """Component=U2CheckBox:260
	Object=CodeMonkey
	Variable=UseVSync
"""
MENU_EDITS = [
    ('Component=CodeMonkey\nComponent=Dispatcher\n', 'Component=CodeMonkey\nComponent=PortSettings\nComponent=Dispatcher\n'),
    ('[CodeMonkey]\nHelper=U2$CodeMonkey\nRegisterObj=CodeMonkey\n',
     '[CodeMonkey]\nHelper=U2$CodeMonkey\nRegisterObj=CodeMonkey\n\n'
     '[PortSettings]\nHelper=U2Port$PortSettings\nRegisterObj=PortSettings\n'),
    ('Component=OptionDescription:10/234/Dodging\n',
     'Component=OptionDescription:10/234/Dodging\nComponent=OptionDescription:11/260/WalkingSpeed\n'),
    (SLIDER, SLIDER + 'Component=U2Slider:260\n\tRange=75,200\n\tStep=5\n\tFormat=ByteFormat\n'
                      '\tObject=PortSettings\n\tVariable=WalkingSpeed\n'),
    ('Component=OptionDescription:11/260/VSync\n',
     'Component=OptionDescription:11/260/VSync\nComponent=OptionDescription:12/286/UIScale\n'),
    (VSYNC, VSYNC + 'Component=U2Selector:286\n\tGroup=OptionWidgets_VIDEO\n' +
     ''.join(f'\tListItem=UIScale{v},PortSettings,SetUIScale{v}\n' for v in ('Auto', '100', '125', '150', '200')) +
     '\tCurrentAccess=PortSettings,GetUIScaleIndex\n'),
    # Resolution = the fullscreen resolution (PortSettings.uc): stored at once, applied at once only in fullscreen.
    ('\tModifier=CodeMonkey,SetRes\n\tCurrentText=CodeMonkey,GetRes\n',
     '\tModifier=PortSettings,SetFullscreenRes\n\tCurrentText=PortSettings,GetFullscreenRes\n'),
]
TEXT_EDITS = [
    ('OptionDescriptionDodging=Dodging:\n',
     'OptionDescriptionDodging=Dodging:\nOptionDescriptionWalkingSpeed=Walking Speed:\nOptionDescriptionUIScale=UI Scale:\n'
     'UIScaleAuto=Auto\nUIScale100=100%\nUIScale125=125%\nUIScale150=150%\nUIScale200=200%\n'),
    ('MouseOver_GAME_11=\n', 'MouseOver_GAME_11=Adjust your walking and running speed in percent of the original (100). '
                             'Other characters, cutscenes and jumping height are not changed.\n'),
    ('MouseOver_VIDEO_10=Check this box to run the game full screen.\n',
     'MouseOver_VIDEO_10=Check this box to play full screen (borderless; the resolution above is scaled to fit the '
     'screen). Alt+Enter switches too.\n'),
    ('MouseOver_VIDEO_12=\n', 'MouseOver_VIDEO_12=Scale menus, HUD and subtitles. Auto picks a size for the screen height.\n'),
    ('MouseOver_VIDEO_01=Adjust the video resolution -- lower resolutions will improve performance on older video cards.\n',
     'MouseOver_VIDEO_01=Resolution used in full screen (scaled to fit the screen). In a window the game always renders at '
     'the window size; resize or maximize the window instead.\n'),
]


def apply(sandbox):
    """Install the port package and menu edits into one run sandbox (its own copies of the files)."""
    if not PACKAGE.is_file():
        raise RuntimeError(f'{PACKAGE} missing: run dev.py port-build first')
    shutil.copy2(PACKAGE, sandbox / 'System' / 'U2Port.u')
    edit(sandbox / 'UIScripts' / 'U2Menus.ui', MENU_EDITS)
    edit(sandbox / 'System' / 'U2Menus.int', TEXT_EDITS)
