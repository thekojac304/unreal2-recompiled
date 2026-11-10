"""Measured native x86 vs actual translated adapter; exhaustive C-locale int32 returns."""
import argparse, hashlib, json, subprocess, sys, time, uuid
from pathlib import Path
WS = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(WS/'tools/xrt'))
import asset_boundary as A

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path)
    a=ap.parse_args()
    out=a.out or WS/'experiments/xrt/results/raw/tolower'/uuid.uuid4().hex[:12]
    out.mkdir(parents=True,exist_ok=False)
    build=WS/'experiments/xrt/build/tolower_boundary'
    native=build/'native.exe';cand=build/'cand.exe';dll=A.source()/'System/msvcr70.dll'
    record=dict(identities={str(p.relative_to(WS)):A.sha(p) for p in [native,cand,dll]},runs=[],passed=False)
    def save(): (out/'result.json').write_text(json.dumps(record,indent=2))
    def run(name,cmd,expected=0):
        before=A.verify();start=time.monotonic()
        p=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=900)
        after=A.verify();assert before==after,'STOP protected input drift'
        (out/(name+'.log')).write_bytes(p.stdout+p.stderr)
        row=dict(name=name,command=list(map(str,cmd)),exit=p.returncode,seconds=time.monotonic()-start,
                 integrity_before=before,integrity_after=after,output=(p.stdout+p.stderr).decode(errors='replace'))
        record['runs'].append(row);save();print(name,p.returncode,round(row['seconds'],2),flush=True)
        assert p.returncode==expected,row
        return row
    for name,locale,cp in [('C','C',0),('C932','C',932),('C1254','C',1254),
                            ('en1252','English_United States.1252',1252),
                            ('tr1254','Turkish_T\u00fcrkiye.1254',1254),('ja932','Japanese_Japan.932',932)]:
        run(name,[native,dll,out/(name+'.txt'),locale,cp])
    run('candidate',[cand,out/'candidate.txt'])
    candidate=(out/'candidate.txt').read_bytes()
    record['state_cases']=397314
    record['c_locale_differences']={name:sum(x!=y for x,y in zip((out/(name+'.txt')).read_bytes().splitlines(),candidate.splitlines()))
                                    for name in ['C','C932','C1254']}
    assert all((out/(name+'.txt')).read_bytes()==candidate for name in ['C','C932','C1254'])
    locale_results={}
    for name in ['en1252','tr1254','ja932']:
        rows=[[int(s,16) for s in l.split()] for l in (out/(name+'.txt')).read_text().splitlines()]
        locale_results[name]=dict(byte_changes={hex(x):hex(r) for x,r,exc,e,le,cc in rows if x<=255 and r!=x},
            faults=sum(bool(row[2]) for row in rows),errno_changes=sum(row[3]!=0x5a5a for row in rows),
            last_error_changes=sum(row[4]!=0x12345678 for row in rows),calling_convention_failures=sum(row[5]!=1 for row in rows),
            selected={hex(x):dict(result=hex(r),exception=hex(exc),errno=hex(e),last_error=hex(le))
                      for x,r,exc,e,le,cc in rows if x in [0xffffffff,0xc0,0x49,0xdd,0x10041,0x8260,0x824f,0x7fffffff,0x80000000]})
    record['native_non_C_measurements']=locale_results
    for op in ['setlocale','_setmbcp']:
        r=run('unsupported-'+op,[cand,out/'unused',op],75)
        assert 'unsupported' in r['output']
    # Full 2**32 return sweep on each side; state/ABI is checked separately above.
    r=run('native-full-int',[native,dll,out/'unused','sweep',0])
    assert 'sweep 4294967296 differences 0' in r['output']
    r=run('candidate-full-int',[cand,out/'unused','--sweep'])
    assert 'sweep 4294967296 differences 0' in r['output']
    record.update(passed=True,full_signed_int_return_cases_per_side=4294967296,
                  supported_locale='C; setlocale and _setmbcp remain explicitly unbound',
                  output_hashes={p.name:A.sha(p) for p in out.glob('*.txt')})
    save();print(out,flush=True)
    return 0
if __name__=='__main__':sys.exit(main())
