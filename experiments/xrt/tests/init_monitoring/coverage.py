"""Conservative coverage inventory; signature presence is never qualification."""
import re, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    known={18,37,42,50,61,63,76,83,85,36,15,100}
    calls=[];arities={}
    for p in RT.glob('*'):
        if p.suffix not in ('.c','.inc'):continue
        for line,text in enumerate(p.read_text().splitlines(),1):
            if 'd8_api_entry(c,' in text:
                slots=re.findall(r'd8_api_entry\(c,\s*(\d+)',text)
                for slot,nargs in re.findall(r'd8_api_entry\(c,\s*(\d+)\s*,\s*(\d+)\s*\)',text):
                    arities.setdefault(int(slot),set()).add(int(nargs))
                calls.append(dict(file=str(p),line=line,text=text.strip(),literal_slots=[int(s) for s in slots],
                    known_signature=bool(slots) and all(int(s) in known for s in slots)))
    missing=sorted({s for r in calls for s in r['literal_slots'] if s not in known})
    blockers=[
        'Complete independently captured native entry/return contracts for resource/surface/scene and parent-COM methods; retained handler supports only 12 signatures.',
        'Slot numbers are not globally unique method identities: checkpoint 300 is used for parent GetAdapterMonitor (1 argument) and resource QueryInterface (3). Domain/receiver identity must disambiguate; extending a slot-only dictionary is unsafe.',
        'DirectInput lifecycle/creation/property operations require an integrated native-call rendezvous and qualified typed COM/last-error/CPU handlers; event records alone are insufficient.',
        'GUI native calls and callbacks outside a monitored renderer native call require complete entry/return integration; four-slot nested/reentrant dispatch coverage is not established.',
        'A phase-zero operation checkpoint inside an active callback is not armed by the retained scheduler: fatal + endpoint + callback entry + callback return already consume four slots. A consolidated rendezvous or separately reviewed scheduling design is required; do not remove a protection.',
        'Renderer resource registry snapshots and lifetime/lock/binding validation are not yet composed into the detailed observer.',
        'CreateDevice prerequisite COM queries and resource helpers can perform additional native calls between existing checkpoints; each must be independently observed.',
        'Actual reached guest last-error and FPU precision-status consumers need monitored dependency tracking or a proved scoped nondependence; fixture resets are not proof.',
        'The staged all-thread breakpoint scheduler requires final full-domain qualification and separate owner activation; production scheduler/policy remains untouched.'
    ]
    save(O/'coverage.json',dict(complete=False,genuine_execution_ready=False,known_renderer_signatures=sorted(known),
        unqualified_literal_slots=missing,ambiguous_literal_arities={str(k):sorted(v) for k,v in arities.items() if len(v)>1},
        source_calls=calls,blocking_requirements=blockers,
        evidence_before_assertions=True,unknown_signature_action='stop before native operation',
        exact_source=core.tree(RT),strict_native_x86_compatibility='FAILED'))
    print('Coverage hold:',len(missing),'additional literal signatures; DirectInput/GUI and consumers unresolved',flush=True)

if __name__=='__main__':main()
