"""Evidence-first exact renderer profile: unknown values always stop diagnostically."""
import struct
from common import *


def capture(cap,renderer,profile,cpu,frame,objects,ctx):
    result=dict(renderer=renderer,guest_base=cap.guest_base,cpu=cpu,cpu_raw=cap.mem(cap.cpu,416).hex(),
        frame=frame,frame_raw=struct.pack('<'+'I'*len(frame),*frame).hex(),objects=objects,host=ctx.snapshot(),
        expected_fields=profile['fields'],fields=[],caps=[],identity={},errors=[])
    result['profile_digest']=core.digest(profile)
    result['expectation_provenance']=profile.get('measurement_revision',{})
    cap.log('renderer_profile_context',**{k:v for k,v in result.items() if k not in ('fields','caps','identity','errors')})
    valid=isinstance(renderer,int) and renderer>=0x10000 and renderer%4==0 and renderer+0x4700<=0x100000000
    expected_renderer=cap.setres_entry.get('renderer',cap.setres_entry['cpu']['registers']['ecx'])
    if renderer!=expected_renderer:result['errors'].append('renderer base differs from captured SetRes receiver')
    if not valid:result['errors'].append('invalid renderer object base/range/alignment')
    def word(offset,expected,area):
        row=dict(offset=hex(offset),width=4,expected=expected,observed=None,raw_le=None,
                 guest_address=renderer+offset if isinstance(renderer,int) else None,
                 host_address=cap.guest_base+renderer+offset if isinstance(renderer,int) else None)
        try:
            if not valid:raise ValueError('invalid object base; no target read attempted')
            raw=cap.mem(row['host_address'],4);row['raw_le']=raw.hex();row['observed']=struct.unpack('<I',raw)[0]
            row['match']=row['observed']==expected
        except Exception as error:row.update(match=False,error=repr(error))
        result[area].append(row)
        cap.log('renderer_profile_field' if area=='fields' else 'renderer_profile_capability',**row)
    # No short-circuit reads: every declared field gets a durable row, even after a read failure.
    for offset,expected in profile['fields'].items():word(int(offset,0),expected,'fields')
    for index,expected in enumerate(profile['caps']['caps']):word(0x4134+4*index,expected,'caps')
    for name,pointer,expected in [('renderer_device',renderer+0x4698 if isinstance(renderer,int) else None,objects['guest']),
             ('viewport_renderer',cap.setres_entry.get('viewport',cap.setres_entry.get('frame',[0,0])[1])+0x5c,renderer)]:
        row=dict(guest_address=pointer,expected=expected,observed=None)
        try:
            if not valid:raise ValueError('invalid object base')
            row['raw_le']=cap.mem(cap.guest_base+pointer,4).hex();row['observed']=int.from_bytes(bytes.fromhex(row['raw_le']),'little')
            row['match']=row['observed']==expected
        except Exception as error:row.update(match=False,error=repr(error))
        result['identity'][name]=row;cap.log('renderer_profile_identity',name=name,**row)
    raw_entry=cap.setres_entry.get('sources',{}).get('renderer_raw','')
    expected_vtable=int.from_bytes(bytes.fromhex(raw_entry[:8]),'little') if len(raw_entry)>=8 else None
    row=dict(guest_address=renderer,expected=expected_vtable,observed=None)
    try:
        if not valid:raise ValueError('invalid object base')
        raw=cap.mem(cap.guest_base+renderer,4);row.update(raw_le=raw.hex(),observed=int.from_bytes(raw,'little'))
        row['match']=expected_vtable is None or row['observed']==expected_vtable
    except Exception as error:row.update(match=False,error=repr(error))
    result['identity']['renderer_vtable']=row;cap.log('renderer_profile_identity',name='renderer_vtable',**row)
    result['mismatches']=[r for r in result['fields'] if not r['match']]
    result['passed']=not result['errors'] and not result['mismatches'] and all(r['match'] for r in result['caps']) and all(r['match'] for r in result['identity'].values())
    cap.log('renderer_profile_evaluation',**result)
    return result


def require_exact(result):
    reasons=list(result['errors'])
    for row in result['fields']+result['caps']:
        if row['match']:continue
        actual='unreadable: '+row['error'] if row.get('error') else f"0x{row['observed']:08x}"
        reasons.append(f"{row['offset']} expected 0x{row['expected']:08x}, observed {actual}")
    reasons += [name+' identity mismatch/read failure' for name,row in result['identity'].items() if not row['match']]
    core.require(result['passed'],'renderer configuration diagnostic stop: '+'; '.join(reasons))
