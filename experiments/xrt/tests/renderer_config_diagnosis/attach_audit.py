"""Offline audit of the two original self-thread attach/detach boundaries."""
from common import *


def audit(events):
    calls=[e for e in events if e['kind']=='gui_attach_thread_input_call']
    returns=[e for e in events if e['kind']=='gui_attach_thread_input_return']
    core.require(len(calls)==len(returns) and len(calls) in (0,2),'expected optional original attach/detach pair')
    core.require(not calls or all(e['from']==calls[0]['from'] for e in calls+returns),'same living self-thread throughout original pair')
    for c,r,(attach,ret) in zip(calls,returns,((1,0x11104a4e),(0,0x11104ace))):
        core.require(c['from']==c['to']==r['from']==r['to'] and c['attach']==r['attach']==attach and
            c['return']==r['return']==r['actual_return']==ret and r['result']==0 and r['last_error']==87 and
            r['esp_before']==c['esp'] and r['esp_after']==c['esp']+16,'self-thread USER32 result/ABI differs')
    return dict(passed=True,pairs=len(calls),calls=calls,returns=returns,
         note='Both original callsites preserved: attach=1 then attach=0. This does not qualify cross-thread behavior.')
