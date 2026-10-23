"""Probe explicitly loaded, isolated official backends. No global DLL changes."""
import hashlib,json,os,re,shutil,subprocess,uuid
from pathlib import Path
WS=Path(__file__).resolve().parents[4]
BUILD=WS/'experiments/xrt/build/d3d8_boundary'
TP=WS/'third_party/graphics'
DX=TP/'dxvk-v3.1.1/dxvk-3.1.1'
DG=TP/'dgVoodoo2-v2.87.5/extracted'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def decode(stdout):
    lines={line.split()[0]:line for line in stdout.splitlines() if ' log ' in line}
    line=lines.get('probe_queries','')
    if not line:return {}
    values=[int(x)&0xffffffff for x in line.split(' log ')[1].split()]
    if not values or not values[0]:return {'factory':False,'values':values}
    n=values[1];offset=2;ids=[]
    for a in range(n):
        hr=values[offset];raw=b''.join(v.to_bytes(4,'little') for v in values[offset+1:offset+268]);offset+=268
        ids.append(dict(adapter=a,hresult=f'{hr:08x}',driver=raw[:512].split(b'\0')[0].decode(errors='replace'),
                        description=raw[512:1024].split(b'\0')[0].decode(errors='replace'),raw=raw.hex()))
    return dict(factory=True,adapter_count=n,identifiers=ids,caps_hresult=f'{values[offset]:08x}',
                caps=[f'{v:08x}' for v in values[offset+1:offset+54]],release=values[offset+54],values=values)
def main():
    out=WS/'experiments/xrt/results/raw/d3d8-native'/uuid.uuid4().hex[:12];out.mkdir(parents=True)
    expected='40565b4a724aadc4433fa4e010b4b23916d9b1f1baeee64e17186db94f54e608'
    assert sha(TP/'dxvk-v3.1.1/dxvk-3.1.1.tar.gz')==expected
    results=[]
    for arch,backend in [('x86','system'),('x64','system'),('x86','d3d8to9'),('x86','dgvoodoo'),('x86','dxvk'),('x64','dxvk')]:
        case=out/(arch+'-'+backend);case.mkdir()
        if backend=='system': dll=Path('C:/Windows')/('SysWOW64' if arch=='x86' else 'System32')/'d3d8.dll'
        else:
            dll=case/'d3d8.dll'
            source={'dxvk':DX/('x32' if arch=='x86' else 'x64')/'d3d8.dll',
                    'dgvoodoo':DG/'MS/x86/D3D8.dll','d3d8to9':TP/'d3d8to9-v1.16.0/d3d8.dll'}[backend]
            shutil.copy2(source,dll)
            if backend=='dxvk':shutil.copy2(source.with_name('d3d9.dll'),case/'d3d9.dll')
            if backend=='dgvoodoo':
                cfg=(DG/'dgVoodoo.conf').read_text()
                for k,v in [('OutputAPI','d3d11_fl11_0'),('FullScreenMode','false'),('CaptureMouse','false')]:
                    cfg,n=re.subn(r'(?m)^'+k+r'\s*=.*$',k+' = '+v,cfg);assert n==1
                (case/'dgVoodoo.conf').write_text(cfg)
        (case/'dxvk.conf').write_text('')
        env=dict(os.environ,DXVK_LOG_PATH=str(case),DXVK_CONFIG_FILE=str(case/'dxvk.conf'),DXVK_CONFIG='',DXVK_SHADER_CACHE='0')
        cmd=[str(BUILD/arch/'native.exe'),str(dll),str(BUILD/arch/'d3dprobe.dll'),'probe_queries','probe_lifetime','probe_formats','probe_errors','probe_guards']
        r=subprocess.run(cmd,cwd=case,env=env,capture_output=True,text=True,timeout=30)
        (case/'stdout.txt').write_text(r.stdout);(case/'stderr.txt').write_text(r.stderr)
        entry=dict(arch=arch,backend=backend,command=cmd,exit=r.returncode,decoded=decode(r.stdout),
                   files={str(p):sha(p) if p.exists() else None for p in [dll,BUILD/arch/'native.exe',BUILD/arch/'d3dprobe.dll',*case.glob('*.dll')]},
                   environment={k:v for k,v in env.items() if k.startswith('DXVK_')})
        results.append(entry)
        print(arch,backend,'exit',r.returncode,{k:v for k,v in entry['decoded'].items() if k in ['factory','adapter_count','caps_hresult']},flush=True)
    dx=[r for r in results if r['backend']=='dxvk']
    same=dx[0]['decoded'].get('values')==dx[1]['decoded'].get('values')
    left,right=[r['decoded'] for r in dx]
    except_driver=left['adapter_count']==right['adapter_count'] and all(a['raw'][1024:]==b['raw'][1024:] for a,b in zip(left['identifiers'],right['identifiers']))
    differences=[dict(word=i,x86=f'{a:08x}',x64=f'{b:08x}') for i,(a,b) in enumerate(zip(left['values'],right['values'])) if a!=b]
    dg=next(r['decoded'] for r in results if r['backend']=='dgvoodoo')
    cap_differences=[dict(word=i,dgvoodoo=a,dxvk=b) for i,(a,b) in enumerate(zip(dg['caps'],left['caps'])) if a!=b]
    (out/'results.json').write_text(json.dumps(dict(results=results,dxvk_x86_x64_queries_identical=same,
        dxvk_caps_identical=left['caps']==right['caps'],dxvk_identifiers_identical_except_driver=except_driver,
        dxvk_architecture_differences=differences,dgvoodoo_dxvk_cap_differences=cap_differences),indent=2))
    print('DXVK x86/x64 query bytes identical:',same);print(out)
if __name__=='__main__':main()
