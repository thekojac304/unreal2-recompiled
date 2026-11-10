"""Recover and hash-check additive fixture source revisions against build records."""
import hashlib,json
from pathlib import Path
from run import W,HERE,sha,write
def raw(s):return s.encode()if isinstance(s,str)else s
def digest(s):return hashlib.sha256(raw(s)).hexdigest()
def save_sources(out,contents,expected):
    dest=out/'source-snapshot/verified'
    for path,text in contents.items():assert digest(text)==expected[str(path)],str(path)
    dest.mkdir(parents=True,exist_ok=True)
    for path,text in contents.items():
        assert digest(text)==expected[str(path)],str(path)
        target=dest/path.name
        if target.exists():assert target.read_bytes()==raw(text)
        else:target.write_bytes(raw(text))
    write(dest/'verified.json',dict(passed=True,source_sha256={str(p):digest(s)for p,s in contents.items()}))
def main():
    latest=(HERE/'native.c').read_text()
    old=latest.replace('BOOL useabi=!strncmp(name,"abi",3);','BOOL useabi=!strcmp(name,"abi")||!strcmp(name,"abi_no_preserve");')
    old='\n'.join(line for line in old.split('\n')if 'abi_invalid_adapter'not in line and 'abi_invalid_depth'not in line)
    versions={'03':old,'04':latest}
    old='\n'.join(line for line in old.split('\n')if 'separate_zero'not in line and 'pointer_context'not in line and 'typedef struct Worker'not in line and 'static DWORD WINAPI worker'not in line and 'client_dimensions'not in line and 'if(!strcmp(name,"cross_thread"))'not in line)
    old=old.replace('    else for(i=0;i<reps;i++)','    for(i=0;i<reps;i++)')
    versions['02']=old
    old=old.replace('    pp.window=focus;','    pp.window=device;',1).replace('if(!strcmp(name,"separate_window"))pp.window=device;','if(!strcmp(name,"separate_window"))pp.window=device;else if(pp.window==device)pp.window=focus;')
    versions['01']=old
    for suffix,source in versions.items():
        out=W/('experiments/xrt/build/d3d8-device-fixture-20261025-'+suffix)
        expected=json.loads((out/'build-inputs.json').read_text());content={HERE/'native.c':source}
        content.update({Path(p):Path(p).read_bytes()for p in expected if not p.endswith('native.c')})
        if suffix=='03'and str(HERE/'probe.c')in expected:
            content[HERE/'probe.c']='\n'.join(line for line in(HERE/'probe.c').read_text().split('\n')if 'int probe_fixture_bad_parameters'not in line and 'int probe_fixture_bad_output'not in line)
        save_sources(out,content,expected)
    for suffix in ['02','03','04']:
        out=W/('experiments/xrt/build/d3d8-device-translated-20261025-'+suffix)
        expected=json.loads((out/'source-identities.json').read_text());content={}
        for name in ['probe.c','fixture.inc','abi32.asm','abi64.asm','slots.py']:
            text=(HERE/name).read_text()
            if suffix!='04'and name=='probe.c':text='\n'.join(line for line in text.split('\n')if 'int probe_fixture_bad_parameters'not in line and 'int probe_fixture_bad_output'not in line)
            if suffix=='02'and name=='probe.c':text='\n'.join(line for line in text.split('\n')if 'int probe_device_guard'not in line)
            if suffix!='04'and name=='fixture.inc':text='\n'.join(line for line in text.split('\n')if 'fixture_device_audit'not in line)
            content[HERE/name]=text
        save_sources(out,content,expected)
    print('BUILD SOURCE SNAPSHOTS PASS: all native revisions and completed translated builds match their recorded hashes')
if __name__=='__main__':main()
