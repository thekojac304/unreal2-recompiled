"""Supplementary numerical comparison only; never replaces physical acceptance."""
import sys,json,struct,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('retained_gpu_evidence',Path(__file__).resolve().parent.parent/'engine_bringup/gpu_evidence.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
need=base.need

def read_rows(path):
    """Reject ambiguous or truncated JSON evidence rather than silently repairing it."""
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate evidence field: '+key)
            result[key]=value
        return result
    rows=[]
    for number,line in enumerate(Path(path).read_bytes().splitlines(),1):
        line=line.lstrip()
        if not line.startswith(b'{'):continue
        try:
            row=json.loads(line,object_pairs_hook=pairs,
                           parse_constant=lambda value:need(False,'nonfinite evidence: '+value))
        except (ValueError,UnicodeError) as error:
            raise base.Invalid(f'{path}:{number}: {error}') from error
        need(isinstance(row,dict) and isinstance(row.get('kind'),str),'untyped evidence record')
        rows.append(row)
    need(bool(rows),'no JSON evidence records')
    return rows

SLOTS=[32,32,302,33,308,301,302,300,302,303,31,40,41,20,313]+[314,316,317]*4+[315,316,317,302,61,23,311,312,83]+[36,34,70,35,316,317,15]+[75,76,77,23,311,312,23,311,312,83,83]+[24,311,312,85,36,34,71,35,316,317,15,85,302]*2+[83,83,78,76,302,302,61,302,302,302,302]
NARGS={15:5,20:8,23:6,24:6,31:3,32:2,33:2,34:1,35:1,36:7,40:2,41:2,
       61:3,70:4,71:6,75:5,76:2,77:2,78:2,83:4,85:3,300:3,301:1,302:1,
       303:2,308:2,311:5,312:1,313:1,314:3,315:3,316:4,317:1}

def nargs(index,slot):
    # Only the four mip uploads use texture LockRect/UnlockRect signatures.
    return {316:5,317:2}.get(slot,NARGS[slot]) if 15 <= index < 27 else NARGS[slot]

def audit(rows,arch,translated):
    create=base.one(rows,'semantic-create')
    need(create['hr']==0 and (create['width'],create['height'])==(800,600),'device create')
    own=base.one(rows,'semantic-ownership')
    need(own['same_parent'] is True and own['same_window'] is True and
         own['parent_hr']==own['creation_hr']==0 and own['add']==own['balance']+1 and
         own['flags']==0x42,'device ownership')
    summary=base.one(rows,'resource-summary');calls=[r for r in rows if r.get('kind')=='resource-call']
    need(summary['calls']==len(calls) and [r['slot'] for r in calls]==SLOTS and summary['synthetic_only'] and not summary['game_scene'],'resource summary/count/sequence')
    need(calls[0]['slot']==32 and calls[-1]['slot']==302,'bounded resource sequence')
    need({20,23,24,31,32,33,34,35,36,40,41,61,70,71,75,76,77,78,83,85,300,301,302,303,308,311,312,313,314,315,316,317}.issubset({r['slot'] for r in calls}),'resource coverage')
    # Retain strict raw ABI failures. A parser cannot normalize them away.
    for index,row in enumerate(calls):
        need(type(row['nargs']) is int and row['nargs']==nargs(index,row['slot']),'resource argument count')
        base.abi(row,arch)
        need(type(row['hr']) is int and 0<=row['hr']<0x80000000,'unexpected native failure/result encoding')
        need(type(row['last_error']) is int and 0<=row['last_error']<=0xffffffff,'last-error encoding')
        before,after=[bytes.fromhex(row[k]) for k in ('cpu_before','cpu_after')]
        need(len(before)==len(after)==416,'complete CPU evidence');expected=bytearray(before)
        if translated:
            struct.pack_into('<I',expected,0,row['hr']);struct.pack_into('<I',expected,16,struct.unpack_from('<I',before,16)[0]+4*(row['nargs']+1));struct.pack_into('<I',expected,64,0x98765432)
            # Fixture seeds guest fsw with PE already set; first Present preserves it.
        need(after==expected,'guest CPU/ABI changed')
    pixels=[r for r in rows if r.get('kind')=='resource-pixels']
    need([r['mode'] for r in pixels]==[0,1,2] and all(100<r['changed']<480000 for r in pixels),'three non-clear readbacks')
    clean=base.one(rows,'semantic-cleanup')
    need(clean['device_release']==clean['parent_release']==0,'COM final release')
    need(all(clean[k] for k in ('destroyed','unregistered','free_d3d8','free_d3d9','guest_freed')) and not any(clean[k] for k in ('window_valid','d3d8_loaded','d3d9_loaded')),'physical cleanup')
    total=base.one(rows,'semantic-summary');need(total['calls']==len(calls) and total['translated'] is translated and total['group']==1,'fixture summary')
    return dict(create=create,ownership=own,calls=[(r['slot'],r['nargs'],r['hr'],r['last_error'],r['nonnull']) for r in calls],pixels=[(r['mode'],r['changed'],r['hash']) for r in pixels])
def compare(groups):
    need(len(groups)==3,'exactly three fixture outputs required')
    measured=[audit(rows,arch,t) for rows,arch,t in zip(groups,('x86','x64','x64'),(False,False,True))]
    need(len(groups)==3 and measured[0]==measured[1]==measured[2],'native/translated result difference')
    return dict(raw_comparison_passed=True,formal_physical_acceptance=False,game_scene_verified=False,measurements=measured,
                limitation='Outer ABI only. Requires unchanged collector desktop/module/GPU/process/Job evidence. Historical strict failures remain.')
if __name__=='__main__':
    need(len(sys.argv)==4,'three saved stdout files required')
    print(json.dumps(compare([read_rows(p) for p in sys.argv[1:]]),indent=2))
