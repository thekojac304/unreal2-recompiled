"""Init-relevant closure ledger; instrumentation presence is not readiness."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    from audit import main as inventory
    inventory()
    c=read(O/'coverage.json');win=read(O/'windows-methods.json');dm=read(O/'dmusic-methods.json')
    blockers=[
      dict(gap='Bounded pointer payload coverage',relevance='Init window/class strings, nested message structures and variable graphics declarations/transfers are not all typed byte contracts. Numeric converted arguments/results are recorded, but opaque pointers are not full payload evidence.'),
      dict(gap='Resource map span capacity',relevance='Full download/upload bytes now recorded up to 16,384 bytes. Larger startup texture maps stop safely; typical texture extents can exceed this. Monitor and adapter capacities are intentionally distinct.'),
      dict(gap='Remaining registry and exceptional-cleanup audit',relevance='Binding locations, resource maps, selected reference transitions and destruction are observed and tested. This is not yet a complete audit of every parent/device/window generation and reference transition. Guest EH and ordinary worker ExitThread pass; native exceptional exits and nested native-callback thread exits remain unqualified/fail-closed.'),
      dict(gap='DirectMusic helper-side native COM and script/audio callbacks',relevance='Host COM and real Loader8 IPC frames pass. The existing x86 helper is pinned and contained, but its internal native calls are not part of the new binary stream; InitAudio and tool/script callback traffic have not been qualified with the new monitor.'),
      dict(gap='Actual native machine-state consumers',relevance='Complete independent state comparison covers the probe. A native-double FPU precision-status and CreateTexture last-error oracle passes. This does not qualify every real guest last-error/x87 consumer or exact volatile machine registers at actual API entry/RET.'),
      dict(gap='Production candidate observer activation',relevance='Owned composition with the production factory, four critical slots, all-thread readbacks and evidence-first failures passes. The exact candidate CreateDevice/environment gate, graphics profile and differential consumers have not been qualified as one genuine observer; production policy remains unchanged.'),
      dict(gap='60-second throughput budget',relevance='Strict per-record durable writes are expensive; see performance and stress receipts. The genuine Init event count and engine work are unknown. A bounded timeout revision would need separate review and does not close the other gaps.'),
      dict(gap='Retained strict compatibility failures',relevance='Historical strict x87, WNDPROC and DirectInput differences remain FAILED. They have not been waived or translated into success by monitor qualification.'),
    ]
    c.update(complete=False,complete_typed_coverage=False,genuine_execution_ready=False,
        supported_typed_descriptors=c['supported_typed_descriptors']+len(dm),
        windows_signatures=len(win['methods']),windows_sites=len(win['sites']),
        windows_native_sites=sum(r['domain']=='native' for r in win['sites']),
        windows_probe_support_sites=sum(r['domain']=='probe-support' for r in win['sites']),
        closed_gaps=['Actual typed GUI native arguments and returns for inventoried SDK calls; diagnostic calls explicitly separated into support domain 5.',
          'All 145 inventoried host native COM sites wrapped with interface identity, generation and method slot; includes seven former DirectMusic gaps.',
          'DirectInput format object/GUID arrays, property values and data buffers recorded under existing 256-object bounds.',
          'Resource binding kind/index, offsets, reference and destruction updates; full bounded map byte transport.',
          'Version-2 explicit aborted invocation records for guest EH/nonlocal ExitThread, preserving generated landing-pad ABI.',
          'Production debugger factory composed with runtime collector on owned code; no candidate activation or policy changes.',
          'Independent native-double error/FPU oracle and measured durable tracing throughput.'],
        blocking_requirements=[r['gap']+': '+r['relevance'] for r in blockers],init_relevance=blockers,
        strict_native_x86_compatibility='FAILED retained',record_version=2,
        actual_native_state_vs_probe='XmRecord.context is the monitoring probe snapshot. Native-double FXSAVE/error is separately captured inside the owned native function; no exact machine API-entry/RET claim.',
        runtime=core.tree(RT))
    save(O/'coverage.json',c)
    print('Coverage ledger:',c['wrapped_com_sites'],'/',c['native_com_sites'],'COM sites;',c['windows_signatures'],'Windows signatures; genuine NOT_READY',flush=True)

if __name__=='__main__':main()
