"""Read-only milestone analysis. This is not a launcher or authorization gate."""
import sys,json,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

PAIRS={'viewport_try_render':20,'viewport_open':28,'engine_init':4,'engine_tick':8,'level_tick':12}

def analyze(events,selected_world=None):
    pending={};completed=[];scene=[];errors=[];last=0
    for row in events:
        seq=row.get('seq',0);kind=row.get('kind','')
        if seq<=last:errors.append(dict(seq=seq,error='non-monotonic sequence'))
        last=seq
        if row.get('truncated'):errors.append(dict(seq=seq,error='truncated event'))
        if kind=='d3d8_semantic_entry' and row.get('slot') in (3,34,35,40,41,70,71,72,73):
            scene.append(row) # An entry is an attempt, never proof of rendered pixels.
        if not kind.endswith(('_call','_return')):continue
        stem,phase=kind.rsplit('_',1)
        if stem not in PAIRS:continue
        key=(row.get('thread'),stem);stack=pending.setdefault(key,[])
        if phase=='call':stack.append(row);continue
        if not stack:
            errors.append(dict(seq=seq,error='unpaired return',kind=kind));continue
        call=stack.pop()
        checks={
            'object':bool(call.get('this')) and row.get('this')==call.get('this'),
            'return':row.get('actual_return')==row.get('return')==call.get('return'),
            'stack':row.get('esp_before')==call.get('esp') and row.get('esp_after')==call.get('esp',0)+PAIRS[stem],
            'target':row.get('target')==call.get('target'),
        }
        if stem=='level_tick':
            checks['selected_world']=bool(selected_world) and row.get('world')==call.get('world')==row.get('this')==selected_world
        completed.append(dict(milestone=stem,call=call,returned=row,checks=checks,verified=all(checks.values())))
        if not all(checks.values()):errors.append(dict(seq=seq,error='paired milestone mismatch',checks=checks))
    outstanding=[row for stack in pending.values() for row in stack]
    return dict(evidence_consistent=not errors,errors=errors,completed=completed,pending=outstanding,
        scene_attempts=scene,scene_pixels_verified=False,selected_world=selected_world,
        engine_init_return_seen=any(r['milestone']=='engine_init' and r['verified'] for r in completed),
        main_loop_tick_seen=any(r['milestone'] in ('engine_tick','level_tick') for r in completed),
        scope='Runtime evidence pairing only; independent hardware/object/CPU corroboration is still required.')

def capture(source,destination,selected_world=None):
    destination.mkdir() # Never overwrite a historical analysis.
    raw=destination/'raw-events.json';shutil.copyfile(source,raw)
    # Evidence is retained before decoding or assertions.
    try:
        data=read(raw);result=analyze(data['events'] if isinstance(data,dict) else data,selected_world)
    except Exception as error:
        save(destination/'analysis-error.json',dict(error=str(error),source_sha256=core.sha(raw)));raise
    result['source_sha256']=core.sha(raw);save(destination/'milestones.json',result);return result

if __name__=='__main__':
    result=capture(Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3],0) if len(sys.argv)>3 else None)
    print(json.dumps({k:result[k] for k in ('evidence_consistent','engine_init_return_seen','main_loop_tick_seen')}))
