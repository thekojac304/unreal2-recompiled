"""Seal the prepared package and write one milestone report. No launches."""
import importlib.util,sys
from pathlib import Path
sys.dont_write_bytecode=True
_spec=importlib.util.spec_from_file_location('viewport_final_preparation_isolated',Path(__file__).resolve().parent/'prepare.py')
Q=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(Q);P=Q.P
def main():
    O=P.O;Q.integrity()
    final=P.read(O/'final-integrity.json');assert final['passed'] and final['ready_for_owner']
    P.check(P.W,P.read(O/'current-sources.json'))
    package=P.load('viewport_final_owner_verify',O/'bounded_owner.py');package.verify()
    fixture=P.read(O/'fixture-audit.json');plan=P.read(O/'candidate-debugger-plan.json');build=P.read(O/'build.json')
    assert P.read(O/'observer-tests.json')['passed']
    assert not Q.SB.exists() and not (O/'genuine-owner-run').exists() and not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    report=f'''Unreal II viewport WM_GETOBJECT recovery — October 28, 2026 (US Eastern)

READY for one fresh owner-launched bounded continuation. Genuine games launched: zero.
The consumed attempt, exact EXE/PDB/build, sources, raw evidence, complete sandbox
and metadata remain preserved and hash-verified. No consumed session is reusable.

Measured native x86 / native x64 / translated registered-window results:
  18 samples and 40 callback records each agree exactly after newline decoding.
  Actual registered WNDPROC executes; real Windows DefWindowProcW returns 0.
  Last-error 0x1234 is preserved, or 0x5678 propagates from the callback.
  HWND identity and nested WM_GETTEXTLENGTH (8 characters) agree.
  Both x64 OBJID_CLIENT representations pass. Fourteen real Windows default
  calls are separately observed with full-width active-frame arguments intact.
  18 host ABI/x87/MXCSR checks per side pass; native x64 also checks XMM6–15.
  42 guest callback ABI/FPU checks, 18 full suspended-CPU comparisons and an
  independent full suspended-CPU comparison around real SetFocus pass,
  using nonempty, nondefault x87 state. Real SetFocus contains two requests
  injected by a disposable host-only CBT hook; spontaneous OS emission is not claimed.

Accessibility: native x86/x64 each obtain and release three real Windows generic
window IAccessible objects (S_OK, role 10, state 1081344, zero children, matching HWND).
Actual acquisition additionally sends WM_GETOBJECT(0, OBJID_QUERYCLASSNAMEIDX).
Translation executes the OBJID_CLIENT callback/default return 0, then intentionally
stops at that separate unsupported request. Successful translated acquisition is
not claimed. No object, cookie, return value or default-processing success is fabricated.
This differs from the validated dialog protocol (DLGPROC FALSE + dialog manager,
native role 18). All other object IDs/argument combinations remain guarded.

Fix: only a live, Unicode registered class whose actual class WNDPROC and module
generation match the explicit guest procedure may admit the existing exact tuple.
Guest dispatch and its validated-frame DefWindowProcW delegation remain real.
Nonzero guest results stay unsupported. Production edits are confined to
hle_gui.c and hle_gui_classes.inc; no renderer/audio/x87 implementation changed.

Regressions: 12 registered-window rejection cases; prior dialog's 18 samples,
three real accessibility queries and four rejections; all 18 focused GUI suites;
Unicode/ANSI DPI96 matrices and 18 DPI rejections; ten observer unit tests pass.
Fresh non-game observer fatal probes and independent terminate-before-instruction
hardware-stop selftest pass. Historical fixture setup failures and source versions
remain retained with their raw logs; no production APIs were added for them.

Fresh serial client build: 279 compiled objects, zero reused; PE/PDB, link-object
list, generated/runtime sources, protected original assets, pinned compiler/system
headers/libraries, DXVK 3.1.1 x86/x64, helper and driver files all verify.
  EXE: {plan['executable']}
  SHA-256: {build['binary_sha256']}
  PDB SHA-256: {build['pdb_sha256']}
Permanent stop: native RVA {plan['stop_rva']:#x}, bytes {plan['stop_bytes']}, before
guest 0x0696f292 and its LEA effect. The retained hardware-slot/readback algorithm,
callback/stack, CreateDevice, Clear/Present and eight scalar-state assertions are
unchanged. One session, 60-second watchdog, no retry; any fatal stops the attempt.

Strict compatibility remains FAILED: historical x87 and complete WNDPROC equality
failures are preserved separately in strict-failures-retained.json, without waivers.
This preparation advances no genuine renderer, engine tick or world tick milestone.

Next owner PowerShell command:
  & "{O / 'owner-genuine-viewport.cmd'}"

Reserved fresh sandbox: {Q.SB}
Only the owner's command may create it. Environment gates are rechecked before and
during the attempt. Preserve the whole package/run after any stop; never retry it.
No automatic continuation, remote push, release or original installation/save edit.

Audit: fixture-audit.json, implementation.patch, gui-regressions.json,
dialog-regression.json, build.json, dependency-verification.json, observer-tests.json,
candidate-debugger-plan.json, readiness.json, final-integrity.json and artifact-manifest.json.
'''
    (O/'REPORT.txt').open('x',encoding='utf-8').write(report)
    P.save(O/'artifact-manifest.json',P.tree(O))
    print('SEALED / READY FOR OWNER / NO GAME LAUNCHED')
if __name__=='__main__':main()
