"""Coverage inventory: source presence is never a qualification claim."""
import sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    methods=read(O/'typed-methods.json');sites=read(O/'native-sites.json');imports=[];native=[];transitions=[]
    for p in sorted(RT.iterdir()):
        if p.suffix not in ('.c','.inc') or p.name.startswith('monitor'):continue
        for line,text in enumerate(p.read_text().splitlines(),1):
            for dll,name,fn in re.findall(r'\{\s*"([^"\n]+)"\s*,\s*"([^"\n]+)"\s*,\s*(\w+)',text):
                imports.append(dict(file=p.name,line=line,dll=dll,name=name,adapter=fn,
                    central_entry_return=True,typed_native_contract='see typed-methods.json; otherwise incomplete'))
            if '->vt->' in text or '->lpVtbl->' in text:
                native.append(dict(file=p.name,line=line,source=text.strip(),coverage='not wrapped'))
            if re.search(r'\b(longjmp|setjmp|xrt_call_guest|xrt_call_funclet|xrt_call_continuation|xrt_baton_acquire|xrt_baton_release)\(',text):
                transitions.append(dict(file=p.name,line=line,source=text.strip()))
    gui_calls=[]
    for name in ('hle_gui.c','hle_gui_classes.inc','window_transitions.inc','hle_misc.c','hle_kernel32.c','hle_msvcr70.c'):
        for line,text in enumerate((RT/name).read_text().splitlines(),1):
            names=re.findall(r'(?<![\w.])([A-Z][A-Za-z0-9]+[AW]?)\(',text)
            names=[n for n in names if n not in ('ARG','RET_STD','RET_C','RET_C_VOID','G2H','SUCCEEDED','FAILED','LOWORD','HIWORD')]
            if names:gui_calls.append(dict(file=name,line=line,candidates=names,source=text.strip(),
                note='Lexical candidate inventory includes macros; direct and dynamically resolved calls require review.'))
    gaps=[
      'Windows imports have common guest adapter entry/return, but no complete per-import native signature/conversion catalog. GUI begin/end scopes lack actual native return values and typed converted arguments.',
      'Seven native DirectMusic IUnknown calls and helper IPC/backend boundaries remain outside typed native wrappers; outer import scopes alone are insufficient.',
      'Variable-sized nested inputs remain partial: DirectInput DIDATAFORMAT object/GUID arrays and GetDeviceData arrays; D3D shader declarations, UP vertices/indices, CopyRects arrays and complete map transport bytes. Pointer values remain opaque; no arbitrary object serialization is used.',
      'Some resource prerequisite/cleanup helpers have no direct CPU argument. Their own native record has cpu_size=0 and relies on the enclosing invocation; autonomous cleanup identity coverage is incomplete.',
      'Resource binding records identify resource counts but do not yet encode every binding location; parent/device cleanup and all window/handle generations need a complete lifecycle audit.',
      'Guest C++ longjmp/ExitThread nonlocal exits have no qualified scope-unwind records. Normal returned thread procedures are qualified; exceptional/nonreturning paths must not be called complete.',
      'Only legacy x87/SSE state is captured. This candidate is compiled without AVX; upper YMM/ZMM state is not qualified. Host context is at the common probe boundary, not the exact machine API entry/return.',
      'Actual reached guest last-error and FPU-status consumers remain unqualified; historical native-x86 FPU/WNDPROC and DirectInput differences remain FAILED.',
      'Production supervisor has not adopted this sink/collector or a reduced breakpoint profile. Preserve its existing enforcement until a separately reviewed integrated observer is qualified.',
      'Init paired runtime CPU records and the new endpoint are implemented/mapped, but the genuine candidate has never executed. No claim of completed genuine Init or gameplay is made.'
    ]
    result=dict(complete=False,complete_typed_coverage=False,genuine_execution_ready=False,
        supported_typed_descriptors=len(methods),native_com_sites=sites['total'],wrapped_com_sites=sites['instrumented'],
        factories_instrumented=['D3D8.Direct3DCreate8','DINPUT8.DirectInput8Create'],methods=methods,imports=imports,
        unwrapped_com_sites=native,transition_inventory=transitions,windows_native_candidates=gui_calls,blocking_requirements=gaps,
        runtime=core.tree(RT),production_policy_changed=False,genuine_launches=0)
    save(O/'coverage.json',result)
    print('Host COM inventory:',sites['instrumented'],'/',sites['total'],'; base typed descriptors:',len(methods),'; overall NOT READY',flush=True)
if __name__=='__main__':main()
