"""Write reviewable preparation facts from saved identities; no execution."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def run():
    b=read(O/'build.json');p=read(O/'stop-mapping.json')
    report=f'''Unreal II — Call-aware initial SetRes completion preparation

PREPARATION ONLY. Genuine launches in this preparation: ZERO.
Owner authorization is pending. No consumed candidate was executed or retried.
The exact historical SetRes frame remains unavailable and is not reported as
measured evidence. All new measured frames below come from owned fixtures.

Verified original callers and ABI
Initial: WinDrv 11104BF5, FF 57 78 (CALL [EDI+78]), return 11104BF8,
85 C0 (TEST EAX,EAX).
Recovery: D3DDrv 0696D2CA, FF 52 78 (CALL [EDX+78]), return 0696D2CD,
3B C7 (CMP EAX,EDI).
SetRes: 0696E890, original exported thiscall signature takes viewport and four
integers, renderer in ECX. Entry stack: return, viewport, width, height,
fullscreen, color depth. Original 0696F4E9 is C2 14 00 (RET 20), so ESP +24.
Original binaries and unchanged generated instructions are independently decoded
and bound in stop-mapping.json. Initial and recovery callers are distinct.

Fresh candidate and genuine source justification
EXE: {EXE}
SHA-256: {SHA}
PDB SHA-256: {PDB}
New source: isolated runtime/xrt_loader.c plus setres_evidence.inc.
The dispatcher now records raw SetRes entry CPU/frame bytes before function-entry
debugger assertions, followed by a paired return with the same invocation id.
This closes the missing-frame evidence defect. No guest results, configuration,
CPU/FPU state, argument values, renderer tuples or native operations are changed.
Host last-error is preserved around evidence formatting/writes.
One new xrt_loader.obj is compiled with /fp:strict; 278 hash-verified objects are
inherited, including all 265 generated objects and 13 other runtime objects.
All 279 source/object/header/transitive records, serial compile/link commands,
link inputs, exact PE/PDB GUID/age, toolchain and dependencies verify.
This is not an identity-only rebuild. See source-change.json, runtime.patch,
object-lineage.json, build.json and candidate-identity.json.

Exact proposed hardware stop
Guest continuation: 0x11104BF8, before its first guest instruction TEST EAX,EAX.
Candidate RVA: 0x{p['stop_rva']:08X}.
Preferred-base native VA: 0x{0x140000000+p['stop_rva']:X}; ASLR address is live base + RVA.
Bytes: {p['stop_bytes'].upper()} — MOV DWORD PTR [RDI+44h], EBX.
RDI must be the exact captured CPU pointer; EBX must equal 11104BF8.
The preceding native CALL xrt_icall, CMP [RDI+40h],EBX and JNE bad-return path
are verified. Conservative native CFG constant propagation proves guest caller
11104BF5 and expected return 11104BF8. The pending MOV is P(11104BF8); it must
not execute. Raw PC at this stop must still be SetRes RET at 0696F4E9.
The permanent slot is reserved in the separate milestone observer on initial
and newly created threads with live DR readback. Production supervisor's older
permanent stop is unchanged. This proposed scope is not installed on a game
during preparation; a separate owner stop authorization is mandatory later.

Evidence-first observer and completion checks
Every boundary saves host registers, FXSAVE/MXCSR, host stack, complete 416-byte
guest CPU, raw six-word frame, bounded raw stack and bounds before assertions.
Initial entry additionally saves renderer bytes, viewport bytes and their source
fields before checking dimensions, flags, depth or identities. Initial, Lock
recovery and unknown callers are classified separately; only initial is admitted.
Read errors or evidence-write failures terminate before continuation.
The paired initial return requires EAX=1, ESP+24, identical guest EBX/ESI/EDI/EBP,
same CPU/thread/viewport/renderer, correct caller PC/return, and device binding.
An independent runtime pair must match debugger CPU and frame bytes exactly.
All native renderer entries/returns retain actual HRESULT/last-error, CPU/FPU,
guest/native input memory, callback, HWND and COM identity checks and raw evidence.
Gamma remains a void method with its previously measured effects kept explicit.

Exact renderer and USER32 scope
The original 238 configured tuples and ordering are unchanged. SetMaterial and
ResizeViewport remain separately checked, as do initial CreateDevice, Clear,
Present and eight state returns. Unsupported-method/readiness traps remain in
the exact fresh PE; all renderer runtime sources are byte-identical to the
consumed parent. No allowlist broadening occurred.
The optional original self-thread pair is attach=1 at return 11104A4E, then
attach=0 at 11104ACE. Both must return FALSE/87 with ESP+16 on the same living
self thread. Omission is admitted only as the unchanged original optional branch.
Cross-thread, different-thread, repeated or unpaired calls remain rejected;
the real runtime guards are unchanged and retain their 24 positive/6-negative
measured import qualification.

Qualification results and limits
29 controller/evidence/caller/return/profile/hold/owner tests pass.
81 production supervisor tests pass; its parser still refuses endpoint advance.
5 exact-instrumentation cases pass, including nesting, unknown module and
unreadable frame; complete CPU bytes and host last-error preservation compare.
5 live candidate-mapping/hardware/negative cases plus retained factory/fatal cases
pass. The candidate is mapped SEC_IMAGE_NO_EXECUTE; entrypoint/instructions never
execute. The identical owned stop instruction is halted before its write.
7 live production-handler cases pass: initial pairing plus caller/argument/EAX/
ESP/nonvolatile/return negatives, raw runtime/debugger equality and Job cleanup.
These owned CPU/COM fixtures simulate profile completion; they do not perform
the genuine renderer sequence. The full 239-operation+resize controller exercise
and unchanged measured renderer qualifications are separate evidence.
4 independent native x86 debugger cases verify real ECX thiscall, six words,
both fullscreen sources and RET 20/ESP+24. Strict native-x86 compatibility is
not inferred from these narrow ABI tests.
195 unchanged generated-cache calls pass in exact order. The pinned DirectMusic
helper passes its positive/negative isolation qualification.
Development-only fixture/mapping failures are retained separately; no genuine
failure was relabeled or consumed marker reset.

Preservation
All six globally consumed SHA identities and nine historical launched candidate
paths are accounted for. Original consumed builds, complete sandboxes, raw
debugger/runtime records, original failure, global ledger, source state and
strict failure evidence are preserved with full inventories. The complete latest
consumed attempt also has an independent copy here. Existing source files,
production runtime/generated code/supervisor, original installation and saves
are unchanged. Global ledger remains at its diagnosed hold, sequence 84.
Strict x87, WNDPROC and native-x86 compatibility remain FAILED, separately kept
under preserved/strict-failures. No remote push or release occurred.

Remaining genuine risks
The fresh candidate has not run the genuine game. Its actual initial arguments,
full native renderer sequence, HRESULT/error effects, callbacks and completion
remain unverified. Unmeasured calls, callback behavior, identity/memory/FPU
differences, driver failures or the 60-second deadline must stop the attempt.
Preparation establishes containment/observation readiness, not game correctness
or gameplay. It does not fill in the missing historical argument frame.

Owner action, only after seal-validation.json says passed
Use an ordinary local owner console on the signed-in physical desktop. Release
an existing supervisor's locks locally first. Do not reset its ledger or holds.

& '{W / '.venv/Scripts/python.exe'}' -B -I '{H / 'owner.py'}' launch-once

The console verifies sealed files, unconsumed identity, exact diagnosed hold,
exclusive locks and desktop state. It requires these TWO independent new phrases:
1. {STOP_PHRASE}
2. {PHRASE}
The first separately authorizes the proposed stop scope. Both expire within
five minutes as enforced by the launcher. Only then may one fixed launch claim
be durably recorded, for at most 60 seconds with an independent watchdog, unique
sandbox, module/file pins, permanent hardware stop, terminate-before-continue,
Job cleanup and parent-owned input/desktop-gamma restoration. No retry.
Ctrl+C or a top-level STOP file in this preparation/global supervisor cancels it.
No owner command or game launch was executed during this preparation.
'''
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    save(O/'development-repairs.json',dict(genuine_failures_reclassified=0,repairs=[
        dict(issue='Native compiler derives initial return through LEA constants and spills CPU pointer',evidence=str(O/'mapping-diagnostic.json'),repair='Conservative CFG/stack-slot constant propagation, exact callsite and checked return path verified'),
        dict(issue='Owned stop fixture initially passed the historical Lock return literal',evidence=str(O/'non-game-4ef15165-8787-4ded-ab1c-e6f8569d56ed'),repair='Owned fixture now supplies the initial return; original failed cleanup and event records retained'),
        dict(issue='Unit test assumed stop_requested exists before debugger loop initialization',repair='Use absent-as-false test expectation; observer behavior unchanged'),
        dict(issue='Refreshed qualification evidence correctly invalidated scoped hold receipt during development',repair='Preserved prior receipt in resolved-hold-history and rebound the same unchanged global hold to final qualification evidence')]))


if __name__=='__main__':run()
