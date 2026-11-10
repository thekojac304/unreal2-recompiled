"""Independent dynamic initial SetRes evidence audit. No launch API."""
import struct
from common import core,read,save,GUEST

TRACKED={18,37,42,50,61,63,76,83,85,36,15,100}

def one(rows,kind):
    found=[r for r in rows if r['kind']==kind]
    core.require(len(found)==1,'missing/duplicate '+kind)
    return found[0]

def runtime_pair(events,entry,returned,frame):
    bounds=[e for e in events if e['kind']=='setres_boundary']
    core.require(len(bounds)==2 and [e['phase'] for e in bounds]==['entry','return'],'one initial runtime invocation')
    a,b=bounds
    core.require(a['id']==b['id'] and a['site']==b['site']==0x11104bf5 and a['return']==b['return']==GUEST and a['target']==b['target']==0x696e890,'runtime initial caller identity')
    for phase,record in [('entry',entry),('return',returned)]:
        chunks=[e for e in events if e['kind']=='setres_raw' and e['phase']==phase and e['area']=='cpu' and e['id']==a['id']]
        core.require([e['offset'] for e in chunks]==[0,128,256,384] and all(e['size']==416 for e in chunks),'complete runtime CPU chunks')
        core.require(''.join(e['hex'] for e in chunks)==record['raw'],'runtime/debugger CPU mismatch')
    frames=[e for e in events if e['kind']=='setres_raw' and e['phase']=='entry' and e['area']=='frame']
    core.require(len(frames)==1 and frames[0]['id']==a['id'] and frames[0]['hex']==struct.pack('<6I',*frame).hex(),'runtime/debugger frame mismatch')
    core.require(b['esp']==a['esp']+24 and b['eax']==returned['cpu']['registers']['eax'] and b['rv']==GUEST,'runtime return transfer')
    return 'initial-setres-complete' if b['eax'] else 'initial-setres-failed'

def audit(out,cap):
    rows=cap.rows;events=read(out/'runtime-events.json')['events']
    core.require(cap.terminated_while_stopped and cap.cleanup['passed'] and cap.cleanup['remaining_job_processes']==0,'stop/containment not verified')
    core.require(not any(r['kind']=='fatal_entry' for r in rows),'fatal boundary before completion')
    stop=read(out/'hard-stop.json')
    core.require(stop['hit'] and stop['instruction_executed'] is False and stop['guest_address']=='0x11104bf8','wrong/unproven hard stop')
    initial=one(rows,'semantic_initial_return')
    core.require(initial['instruction_executed'] is False and all(initial['checks'].values()),'initial return checks')
    raw=[r for r in rows if r['kind']=='semantic_raw_cpu']
    def cpu(tag):
        found=[r for r in raw if r['tag']==tag];core.require(len(found)==1,'raw CPU boundary '+tag);return found[0]
    outcome=runtime_pair(events,cpu('semantic_setres_entry'),cpu('setres_completion_stop'),one(rows,'semantic_setres_frame')['frame'])
    core.require(initial['outcome']==stop['outcome']==outcome and initial['return_value']==stop['return_value']==cpu('setres_completion_stop')['cpu']['registers']['eax'],'observed SetRes outcome')
    core.require(not any(e['kind'] in ('engine_tick_call','level_tick_call') for e in events),'world execution entered')
    # Actual checkpoint order is discovered from evidence. No fixed call count,
    # captured scalar profile, S_OK-only expectation, or canonical BOOL gate.
    checkpoints=[r for r in rows if r['kind']=='semantic_checkpoint_raw' and r['slot'] in TRACKED]
    runtime=[e for e in events if e['kind']=='d3d8_checkpoint' and e['slot'] in TRACKED]
    ops=cap.operations
    core.require(len(checkpoints)==len(runtime)==4*len(ops),'complete paired operation stream')
    for i,op in enumerate(ops):
        rs=checkpoints[i*4:i*4+4];es=runtime[i*4:i*4+4]
        core.require([r['phase'] for r in rs]==[e['phase'] for e in es]==[0,1,2,3],'checkpoint phase order')
        core.require(all(r['slot']==op['slot'] for r in rs+es),'operation slot correspondence')
        for r,e in zip(rs,es):
            core.require((r['size'],r['result'],r['last_error'],r['data_pointer'])==(e['size'],e['result'],e['error'],e['data']),'runtime/debugger native checkpoint mismatch')
        core.require(rs[2]['last_error']==rs[3]['last_error']==op['last_error'],'last-error pairing')
        core.require(op['result'] is None if op['slot']==18 else rs[2]['result']==rs[3]['result']==op['result'],'void/HRESULT pairing')
    for kind in ('semantic_native_arguments','semantic_native_abi','semantic_abi_evaluation'):
        checks=[r for r in rows if r['kind']==kind]
        core.require(len(checks)==len(ops) and all(not r['discrepancies'] for r in checks),'independent '+kind)
    native=[r for r in rows if r['kind']=='semantic_native_result']
    core.require(len(native)==len(ops) and all((n['slot'],n['hresult'],n['last_error'])==(o['slot'],o['result'],o['last_error']) for n,o in zip(native,ops)),'actual native result pairing')
    core.require(initial['operations']==stop['operations']==ops and not cap.entries and cap.native_active is None and not cap.callback_frames,'incomplete operations/callbacks')
    from attach_audit import audit as attach
    attach_result=attach(events)
    save(out/'milestone-audit.json',dict(passed=True,measurement_complete=True,outcome=outcome,operations=ops,operation_count=len(ops),
        attach=attach_result,endpoint='before guest 11104BF8',strict_differences=[r for r in rows if r['kind']=='strict_differential'],
        strict_x87='FAILED retained',strict_WNDPROC='FAILED retained',gameplay_verified=False))
    return outcome
