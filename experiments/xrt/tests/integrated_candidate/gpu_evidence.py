"""Strict saved-output supplement; never replaces physical collector evidence."""
import importlib.util,sys,struct,copy,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('prior_resources_evidence',Path(__file__).resolve().parent.parent/'resource_frame/gpu_evidence.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
base=prior.base;need=prior.need;read_rows=prior.read_rows
TRANSFER=[(16,4),(302,1),(27,5),(27,5),(25,7),(26,6),(41,2),(31,3),(36,7),(31,3),(40,2),(316,4),(317,1),(28,6),(28,6),(28,6),(316,4),(317,1),(30,2)]+[(302,1)]*4

def expected_copy_hash():
    value=2166136261
    for y in range(8):
        for x in range(8):
            sx,sy=(x-4,y-4) if x>=4 and y>=4 else (x,y)
            value=((value^(0xff300000|(sy<<8)|sx))*16777619)&0xffffffff
    return value
def audit(rows,arch,translated):
    for row in rows:
        if row['kind']=='resource-call':
            need(type(row['nonnull']) is bool,'resource output boolean')
            if row['slot'] in (20,23,24,32,33,300,303,315):need(row['nonnull'],'required owned resource output absent')
            if row['slot']==313:need(row['hr']==4,'four texture mip levels')
    calls=[r for r in rows if r['kind']=='transfer-call']
    need([(r['slot'],r['nargs']) for r in calls]==TRANSFER,'transfer operation sequence/arity')
    expected_kinds=['resource-call']*(len(prior.SLOTS)-11)+['transfer-call']*len(TRANSFER)+['resource-call']*11
    need([r['kind'] for r in rows if r['kind'] in ('resource-call','transfer-call')]==expected_kinds,'interleaved resource/transfer order')
    total=len(prior.SLOTS)+len(TRANSFER)
    for kind in ('resource-summary','semantic-summary'):need(base.one(rows,kind)['calls']==total,'whole batch call count')
    for r in calls:
        need(type(r['nargs']) is int and type(r['slot']) is int,'transfer integer arity/slot')
        base.abi(r,arch)
        need(type(r['hr']) is int,'transfer HRESULT integer')
        if r['slot']==302:need(0<=r['hr']<0x80000000,'transfer reference count')
        else:need(r['hr']==(0x8876086c if r['slot']==30 else 0),'transfer HRESULT')
        need(type(r['last_error']) is int and 0<=r['last_error']<=0xffffffff,'transfer last-error')
        need(type(r['nonnull']) is bool,'transfer output presence')
        if r['slot'] in (16,25,26,27):need(r['nonnull'],'created surface absent')
        before,after=[bytes.fromhex(r[k]) for k in ('cpu_before','cpu_after')]
        need(len(before)==len(after)==416,'transfer raw CPU size');expected=bytearray(before)
        if translated:
            struct.pack_into('<I',expected,0,r['hr']);struct.pack_into('<I',expected,16,struct.unpack_from('<I',before,16)[0]+4*(r['nargs']+1));struct.pack_into('<I',expected,64,0x98765432)
        need(after==expected,'transfer CPU/ABI')
    pixels=base.one(rows,'transfer-pixels');hash=expected_copy_hash()
    need(pixels['pixels']==64 and pixels['hash']==hash,'surface copy/readback pixels')
    retained=copy.deepcopy([r for r in rows if r['kind'] not in ('transfer-call','transfer-pixels')])
    for kind in ('resource-summary','semantic-summary'):base.one(retained,kind)['calls']=len(prior.SLOTS)
    old=prior.audit(retained,arch,translated)
    return dict(resources=old,transfers=[(r['slot'],r['nargs'],r['hr'],r['last_error'],r['nonnull']) for r in calls],pixels=pixels)
def compare(groups):
    need(len(groups)==3,'exactly three outputs required')
    measured=[audit(r,a,t) for r,a,t in zip(groups,('x86','x64','x64'),(False,False,True))]
    need(measured[0]==measured[1]==measured[2],'native/translated mismatch')
    return dict(raw_comparison_passed=True,formal_physical_acceptance=False,game_scene_verified=False,measurements=measured,
        limitation='Synthetic-only geometry. Outer ABI; unchanged physical collector, module, process, Job and desktop evidence required. GetFrontBuffer negative-only; successful front capture unqualified. Strict historical failures retained.')
if __name__=='__main__':
    need(len(sys.argv)==4,'three saved stdout files required');print(json.dumps(compare([read_rows(p) for p in sys.argv[1:]]),indent=2))
