"""port_overlay - focused test of tools/xrt/dev/port.py apply() on scratch copies of the snapshot's U2Menus.ui/.int.

Checks: every anchored edit applies exactly once; files stay CRLF latin-1; the [PortSettings] helper section and its
Component reference exist once; Game row 11 (260) has the Walking Speed slider bound to PortSettings (Range 75,200,
Step 5); Video row 10 (234) keeps the game's Fullscreen checkbox (borderless in this port) and row 12 (286) is the UI
Scale selector with five items; the localized texts exist; a second apply on the edited files is refused (anchors gone) instead of duplicating.
Also checks the compiled out/dev-init/port/U2Port.u is present. Exit 0 when every check passes.
Run: .venv\\Scripts\\python -I experiments\\xrt\\tests\\port_overlay\\test.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(WS / 'tools/xrt/dev'))
sys.path.insert(0, str(WS / 'tools/xrt'))
import asset_boundary  # noqa: E402
import port  # noqa: E402

failures = 0


def check(ok, what):
    global failures
    print(('ok   ' if ok else 'FAIL ') + what)
    failures += not ok


src = Path(asset_boundary.source())
with tempfile.TemporaryDirectory(dir=WS / 'sandbox_cmp') as tmp:
    sb = Path(tmp)
    (sb / 'System').mkdir(); (sb / 'UIScripts').mkdir()
    shutil.copy2(src / 'UIScripts/U2Menus.ui', sb / 'UIScripts/U2Menus.ui')
    shutil.copy2(src / 'System/U2Menus.int', sb / 'System/U2Menus.int')
    port.apply(sb)
    ui = (sb / 'UIScripts/U2Menus.ui').read_bytes()
    text = (sb / 'System/U2Menus.int').read_bytes()
    check(ui.count(b'\n') == ui.count(b'\r\n') and text.count(b'\n') == text.count(b'\r\n'), 'files stay CRLF')
    u = ui.decode('latin-1')
    check(u.count('[PortSettings]\r\nHelper=U2Port$PortSettings\r\nRegisterObj=PortSettings\r\n') == 1, 'helper section once')
    check(u.count('Component=PortSettings\r\n') == 1, 'helper instantiated once in [Main]')
    check('Component=OptionDescription:11/260/WalkingSpeed\r\n' in u, 'Game row 11 description')
    check('Component=U2Slider:260\r\n\tRange=75,200\r\n\tStep=5\r\n\tFormat=ByteFormat\r\n\tObject=PortSettings\r\n'
          '\tVariable=WalkingSpeed\r\nLocation=%0%,%1%\r\nRegister=OptionWidgets_GAME\r\n' in u, 'Game row 11 slider bound to PortSettings')
    check('Component=U2CheckBox:234\r\n\tObject=CodeMonkey\r\n\tVariable=Fullscreen\r\n' in u and
          'Component=OptionDescription:10/234/Fullscreen\r\n' in u, 'Video row 10 Fullscreen checkbox kept')
    check(u.count('PortSettings,SetUIScale') == 5 and 'CurrentAccess=PortSettings,GetUIScaleIndex' in u and
          'Component=U2Selector:286\r\n' in u and 'Component=OptionDescription:12/286/UIScale\r\n' in u,
          'Video row 12 UI Scale selector (5 items)')
    check('\tModifier=PortSettings,SetFullscreenRes\r\n\tCurrentText=PortSettings,GetFullscreenRes\r\n' in u and
          'CodeMonkey,SetRes' not in u, 'Video Resolution selector bound to the fullscreen resolution')
    t = text.decode('latin-1')
    for key in ('OptionDescriptionWalkingSpeed=', 'OptionDescriptionUIScale=', 'UIScaleAuto=', 'UIScale200=', 'MouseOver_GAME_11=Adjust'):
        check(t.count('\r\n' + key) == 1, f'localized {key}')
    try:
        port.edit(sb / 'UIScripts/U2Menus.ui', port.MENU_EDITS); again = False
    except RuntimeError:
        again = True
    check(again, 'second apply refused (no duplicate edits)')
check(port.PACKAGE.is_file(), f'compiled package present ({port.PACKAGE.stat().st_size if port.PACKAGE.is_file() else 0} bytes)')
print('PASS' if not failures else f'FAIL ({failures})')
sys.exit(1 if failures else 0)
