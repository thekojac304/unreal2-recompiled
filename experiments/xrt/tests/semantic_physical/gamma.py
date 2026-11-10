"""Prepare/submit only the existing owner-authorized restoring-gamma family.

This helper never starts a service or inherits the ordinary fixture grant.
"""
import argparse
import shutil
import sys
import uuid
from pathlib import Path
from recheck import HERE,OUT,PRIOR,WORK,core
from supervisor import fixture_profiles as F, development as D
from supervisor.environment import load
from supervisor.service import verify_seal

GH=HERE.parent/'renderer_prerequisites'
sys.path.insert(0,str(GH))
service=load('semantic_retained_gamma_service',GH/'service.py')
service.install()
ROWS=[[18,f,0,0,k,0] for k in (0,1) for f in (0,1)]


def sources():
    support=(HERE/'support.inc').read_text().replace('static unsigned char input_data[68];','static unsigned char input_data[1536];\n#include "actual_ramp.inc"')
    support=support.replace('/* SAMPLE_ROWS */','static const Sample samples[]={'+','.join('{'+','.join(str(v)+'u' for v in r)+'}' for r in ROWS)+'};')
    support=support.replace('switch(sample->slot){case 42:','switch(sample->slot){case 18:d8_device_SetGammaRamp(c);break;case 42:')
    support=support.replace('if(input_size)memcpy(G2H(0x5ffd)', '''if(sample->slot==18){input_size=1536;if(sample->input_kind)for(i=0;i<768;i++)((WORD*)input_data)[i]=(WORD)((i%256)*257);else memcpy(input_data,actual_ramp,1536);wr32(0x200c,0x5ffd);}
 if(input_size)memcpy(G2H(0x5ffd)''')
    support=support.replace('expected.r[EAX]=cpu.r[EAX];','if(sample->slot!=18)expected.r[EAX]=cpu.r[EAX];')
    fixture=(HERE/'fixture.c').read_text()
    start=fixture.index('static void readback(void)');end=fixture.index('static void invoke(',start)
    fixture=fixture[:start]+'''static void readback(void){D8Gamma ramp;memset(&ramp,0xa5,sizeof ramp);device->vt->GetGammaRamp(device,&ramp);printf("{\\"kind\\":\\"semantic-readback\\",\\"hr\\":null,\\"value\\":0,\\"extra\\":0,\\"nonnull\\":false,\\"bytes\\":");bytes(&ramp,sizeof ramp);puts("}");}
'''+fixture[end:]
    fixture=fixture.replace('if(sample->slot==37)args.a[2]=','if(sample->slot==18||sample->slot==37)args.a[2]=')
    fixture=fixture.replace('if(rejected)printf("null");','if(rejected||sample->slot==18)printf("null");')
    fixture=fixture.replace('ULONG dr,pr;static const DWORD','D8Gamma saved,restored;ULONG dr,pr;static const DWORD')
    fixture=fixture.replace('if(argc!=3||strcmp(argv[1],"--physical"))','if(argc!=4||strcmp(argv[1],"--physical")||strcmp(argv[3],"--gamma-physical"))')
    fixture=fixture.replace('ev_checkpoint("loaded");record_events=1;', 'ev_checkpoint("loaded");device->vt->GetGammaRamp(device,&saved);printf("{\\"kind\\":\\"gamma-saved\\",\\"bytes\\":");bytes(&saved,1536);puts("}");record_events=1;')
    fixture=fixture.replace('record_events=0;dr=device->vt->Release(device);','record_events=0;device->vt->SetGammaRamp(device,0,&saved);device->vt->GetGammaRamp(device,&restored);printf("{\\"kind\\":\\"gamma-restored\\",\\"bytes\\":");bytes(&restored,1536);puts("}");CHECK(!memcmp(&saved,&restored,1536));dr=device->vt->Release(device);')
    return fixture,support


def build():
    verify_seal(core.read_large(service.HOME/'qualification.json'))
    E,_,_=F.modules();ident=str(uuid.uuid4());root=F.CANDIDATES/ident;src=root/'sources';b=root/'build';src.mkdir(parents=True);b.mkdir()
    # Reuse the already built source-exact semantic runtime expansion, not its
    # executable. The fixed gamma recipe independently compiles all three PEs.
    reference=core.read(OUT/'fixture-ef21fe5a-6d00-480b-9f9f-4ed2bd0e9fa5.json')
    original=F.candidate_path(reference['candidate_id']).parent
    F.verify_identities(core.read_large(original/'candidate.json')['files'])
    shutil.copytree(original/'sources/runtime',src/'runtime')
    shutil.copy2(original/'sources/evidence_fixture.h',src/'evidence_fixture.h')
    raw=(service.P.O/'actual-gamma-ramp.bin').read_bytes()
    (src/'actual_ramp.inc').write_text('static const BYTE actual_ramp[1536]={'+','.join(map(str,raw))+'};\n')
    fixture,support=sources();(src/'fixture.c').write_text(fixture);(src/'support.inc').write_text(support)
    tools=[];commands=[]
    for item in service.plan(service.FAMILY,{},root):
        dest=item['exe'].parent;dest.mkdir();arch=item['arch'];abi=E.P.O/'fixtures'/arch/'abi.obj'
        command=f'cl /nologo /O1 /Gy /fp:strict /W3 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /DBATCH_TRANSLATED={int(item["variant"]=="translated")} /DBATCH_GROUP=8 /I"{src}/runtime" /Fo"{dest}/fixture.obj" /Fe"{dest}/fixture.exe" "{src}/fixture.c" "{abi}" user32.lib /link /OPT:REF /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup || exit /b 1'
        E.P.R.script(dest,'build',arch,command);E.P.R.script(dest,'toolchain',arch,'where cl\nwhere link');commands.append(command)
        tools += [Path(s) for s in (dest/'toolchain.stdout.txt').read_text().splitlines() if s.strip()]
    ins,outs=service.recipe(service.FAMILY,{},root)
    core.atomic(b/'build-record.json',dict(recipe='desktop-fixture-v1',family=service.FAMILY,parameters={},fp='/fp:strict',toolchain=F.identities(tools+[Path(E.P.R.VC)]),inputs=F.identities(ins),outputs=F.identities(outs),commands=commands))
    core.atomic(root/'candidate.json',dict(version=1,id=ident,family=service.FAMILY,parameters={},files=F.identities(service.files(service.FAMILY,{},root)),build_record=str(b/'build-record.json')))
    spec=dict(candidate_id=ident,manifest=str(root/'candidate.json'),manifest_sha256=core.sha(root/'candidate.json'),samples=ROWS,adapter_sources=reference['adapter_sources'],genuine_launches=0,submitted=False,scope='existing restoring-gamma family; new local owner authorization required',configured_ramp_sha256=core.sha(service.P.O/'actual-gamma-ramp.bin'))
    core.atomic(OUT/'prepared-semantic-gamma.json',spec)
    F.validate_candidate(dict(candidate_id=ident,candidate_sha256=spec['manifest_sha256'],family=service.FAMILY,parameters={},profile='fast-development'))
    print('Prepared restoring gamma candidate',ident,'no graphics executed',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['build','submit']);a=p.parse_args()
    if a.command=='build':build()
    else:
        spec=core.read(OUT/'prepared-semantic-gamma.json')
        ident=D.submit(spec['candidate_id'],'Measure exact semantic gamma adapter flags 0/1 and configured/linear ramps on native x86, native x64 and translated x64 with parent-owned restoration; no genuine launch',home=service.HOME)
        core.atomic(OUT/'semantic-gamma-request.json',dict(id=ident,candidate=spec['candidate_id']))
        print(ident)
