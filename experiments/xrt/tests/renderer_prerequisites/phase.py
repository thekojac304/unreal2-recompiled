"""Offline prerequisites and disposable fixtures. There is no game launch path."""
import configparser
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import uuid

sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W / 'out/recovery/renderer-prerequisites-20261029-01'
OLD = W / 'out/recovery/renderer-acceptance-20261029-01'
RT = O / 'runtime'
sys.path.insert(0, str(W / 'tools/xrt'))
sys.path.insert(0, str(H.parent / 'renderer_batch'))
from supervisor import core
import asset_boundary as A
import prepare as P


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def save(name, value):
    core.atomic(O / name, value)


def preserve():
    O.mkdir()
    accepted = core.read_large(OLD / 'build.json')
    assert core.tree(Path(accepted['root'])) == accepted['outputs']
    roots = [OLD, W / 'experiments/xrt/runtime', W / 'experiments/xrt/gen',
             W / 'tools/xrt/supervisor', core.HOME,
             W / 'out/desktop-fixtures/evidence/a5ba8826-ae1b-4807-8f90-6c22a801f2d3']
    save('preservation.json', dict(trees={str(p): core.tree(p) for p in roots},
         protected=A.verify(), genuine_launches=0, permanent_stop='0x0696f292'))
    print('Preserved accepted measurements, candidate, production and genuine enforcement', flush=True)


def profile():
    ini = A.source() / 'System/Unreal2.ini'
    c = configparser.ConfigParser(strict=False, interpolation=None)
    c.read(ini)
    render = dict(c['D3DDrv.D3DRenderDevice'])
    client = dict(c['WinDrv.WindowsClient'])
    caps_path = W / 'out/desktop-fixtures/evidence/a5ba8826-ae1b-4807-8f90-6c22a801f2d3/captures/initial-samplers-x64-native/stdout.txt'
    caps = next(json.loads(s) for s in caps_path.read_text().splitlines()
                if json.loads(s).get('kind') == 'adapter-identity')
    assert caps['vendor'] == 0x10de and caps['device'] == 0x2b85 and caps['hr'] == caps['caps_hr'] == 0
    # GetDeviceCaps destination is renderer+0x4134, decoded at original RVA da93.
    words = caps['caps']
    assert len(words) == 53
    assert render['levelofanisotropy'] == '1' and render['usetrilinear'].lower() == 'true'
    assert float(render['defaulttexmipbias']) == -.5 and render['usestencil'].lower() == 'false'
    assert client['startupfullscreen'].lower() == 'false'
    assert (int(client['windowedviewportx']), int(client['windowedviewporty'])) == (1540, 945)
    plan = core.read_large(P.PRIOR / 'initialization-plan.json')
    measured = core.read_large(P.O / 'cases.json')['cases']
    calls = []
    def add(group, slot, a=0, b=0, d=0, site=0):
        row = dict(group=group, slot=slot, a=a, b=b, c=d,
                   site=int(site, 16) if isinstance(site, str) else site, config=0)
        candidates = [m for m in measured if all(m[k] == row[k] for k in ('group','slot','a','b','c','site'))]
        assert candidates, ('not independently measured', row)
        calls.append(dict(row, measured_configs=sorted({m['config'] for m in candidates})))
    stages = words[(0x41c8 - 0x4134)//4]
    streams = min(words[(0x41f0 - 0x4134)//4], 16)
    assert stages == 8 and streams == 16 and words[(0x41a0-0x4134)//4] == 16
    for x in plan['post_material_states']: add(1, 50, x['state'], x['value'], site=x['address'])
    for stage in range(stages):
        for (state, value), site in zip([(19,0xbf000000),(16,2),(17,2),(18,2),(21,1)],plan['sampler_loop']['call_addresses']):
            add(2,63,stage,state,value,site)
    for x in plan['cache_calls']:
        slot = x['slot']
        if slot == 50: add(3,slot,x['state'],x['value'] if isinstance(x['value'],int) else 0,site=x['address'])
        elif slot == 37: add(4,slot,x['transform'],site=x['address'])
        elif slot == 63:
            value = x['value'] if isinstance(x['value'],int) else 1 if '4650' in x['value'] else 0
            for stage in range(stages):add(5,slot,stage,x['type'],value,x['address'])
        elif slot == 61:
            for stage in range(stages):add(6,slot,stage,site=x['address'])
        elif slot == 83:
            for stream in range(streams):add(6,slot,stream,site=x['address'])
        elif slot == 85:add(6,slot,site=x['address'])
        elif slot == 76:add(7,slot,2,site=x['address'])
        else:raise AssertionError(slot)
    fields = {0x40d0:1,0x40d4:1,0x4124:1,0x412c:0xbf000000,0x41a0:16,
              0x41c8:8,0x41cc:8,0x41f0:16,0x4650:1,0x60:0}
    # Immutable caps comparison uses the raw measured bytes before game reductions.
    # 0x40d4 is set to one by the real original at RVA df4b; NVIDIA sets 4650=1.
    save('configuration-profile.json', dict(passed=True, ini=str(ini), ini_sha256=core.sha(ini),
         renderer=render, client=client, caps_evidence=str(caps_path), caps_evidence_sha256=core.sha(caps_path),
         caps=caps, caps_destination=0x4134, fields={hex(k):v for k,v in fields.items()},
         stages=stages, streams=streams, calls=calls, total_calls=len(calls),
         gamma_reachable=bool(words[(0x4140-0x4134)//4] & 0x20000),
         gamma_reason='renderer+4140 is D3DCAPS8.Caps2 (word 3), not word 2; bit 0x20000 is set',
         sources={'mipmap_enabled':'D3DDrv RVA df4b','nvidia_address_mode':'D3DDrv RVA e472',
                  'caps_destination':'D3DDrv RVA da93','properties':'D3DDrv StaticConstructor RVA a960'},
         scope='one non-editor windowed initialization; no unrestricted sample matrix'))
    print('Exact production profile:',len(calls),'calls, stages',stages,'streams',streams,'gamma reachable',flush=True)


def stage():
    profile = core.read_large(O / 'configuration-profile.json')
    shutil.copytree(OLD / 'runtime', RT, dirs_exist_ok=True)
    calls = profile['calls']
    header = 'typedef struct BatchCase { unsigned group,slot,a,b,c,site,config; } BatchCase;\n'
    header += 'static const BatchCase batch_cases[]={\n'
    header += ''.join(' {'+','.join(str(x[k])+'u' for k in ('group','slot','a','b','c','site','config'))+'},\n' for x in calls)
    header += '};\n'
    (RT / 'batch_cases.inc').write_text(header)
    guards = '''static uint32_t d8_profile_renderer;
static void d8_production_profile(CPU*c,D8DeviceObject*o,unsigned n) {
    uint32_t r; unsigned i;
    if(c->pc==0x0696f336u || c->pc==0x0696f350u ||
       (c->pc>=0x0696f3acu && c->pc<=0x0696f42eu)) {
        d8_device_memory(c,c->r[EBP]-0x14u,4,0);r=rd32(c->r[EBP]-0x14u);
    } else {
        uint32_t cache;
        d8_device_memory(c,c->r[ESP]+4*n+20,4,0);
        cache=rd32(c->r[ESP]+4*n+20);d8_device_memory(c,cache,4,0);r=rd32(cache);
    }
    d8_device_memory(c,r,0x469c,0);
    if(d8_profile_renderer && r!=d8_profile_renderer)xrt_fatal(c,76,"renderer identity changed");
    if(rd32(r+0x4698)!=o->guest)xrt_fatal(c,76,"renderer device identity mismatch");
    /* The original capability query uses this exact DWORD layout. */
    { static const uint32_t caps[53]={CAPS};
      for(i=0;i<53;i++)if(rd32(r+0x4134+4*i)!=caps[i])
          xrt_fatal(c,76,"renderer unmeasured/reduced capability word %u",i); }
FIELDS
    if(rd32(0x101c9aecu))xrt_fatal(c,76,"renderer editor profile refused");
    d8_profile_renderer=r;
}
'''
    # The cache reads GIsEditor through a relocated Core import; resolve the
    # original import at runtime instead of assuming a global's fixed location.
    import pefile
    pe = pefile.PE(str(A.source()/'System/D3DDrv.dll'))
    editor = next(x.address-0x10000000+0x6960000 for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports
                  if x.name and x.name.decode() == '?GIsEditor@@3HA')
    guards = guards.replace('rd32(0x101c9aecu)',f'rd32(rd32(0x{editor:x}u))')
    guards = guards.replace('CAPS',','.join(str(v)+'u' for v in profile['caps']['caps']))
    guards = guards.replace('FIELDS','\n'.join(f'    if(rd32(r+{k})!={v}u)xrt_fatal(c,76,"renderer profile field {k} refused");' for k,v in profile['fields'].items()))
    p = RT / 'integrated_renderer.inc'
    t = p.read_text().replace('static volatile LONG d8_experimental_fixture_profile = -1;',
                            'static volatile LONG d8_experimental_fixture_profile = -1;\n'+guards)
    # No setter, no choice of sample config. All live calls bind the object,
    # original configuration fields and measured capabilities before matching.
    t = t.replace('    if(d8_experimental_fixture_profile<0 || d8_experimental_fixture_profile>2)\n        xrt_fatal(c,76,"experimental renderer configuration/caps profile unbound");',
                  '    d8_production_profile(c,o,n);')
    t = t.replace('q->config!=(unsigned)d8_experimental_fixture_profile', 'q->config!=0')
    # Preserve the earlier exact state adapter for its distinct eight callsites.
    t = t.replace('if(d8_experimental_fixture_profile==-1){d8_device_AcceptedSetRenderState(c);return;}',
                  'if(c->pc<0x0696f292u){d8_device_AcceptedSetRenderState(c);return;}')
    p.write_text(t)
    gui=RT/'hle_gui.c';t=gui.read_text()
    adapter='''/* Original WWindow::MoveWindow(FRect,TRUE), windowed SetRes only. */
static void hle_MoveWindow(CPU*c) {
    HWND h;RECT old,required={0,0,1540,945};BOOL ok;CPU*previous=callback_cpu;
    DWORD error=xrt_get_last_error(c);LONG style;
    if(c->pc!=0x110018e2u || ARG(5)!=1)
        xrt_fatal(c,76,"MoveWindow: unmeasured callsite/repaint");
    h=xrt_gui_device_window(c,ARG(0));
    if(GetDpiForWindow(h)!=96)xrt_fatal(c,76,"MoveWindow: unmeasured DPI");
    style=GetWindowLongW(h,GWL_STYLE);
    if((style&~(WS_VISIBLE|WS_CLIPSIBLINGS))!=WS_OVERLAPPEDWINDOW || GetMenu(h))
        xrt_fatal(c,76,"MoveWindow: unmeasured style/menu");
    if(!GetWindowRect(h,&old) || !AdjustWindowRect(&required,style,FALSE))
        xrt_fatal(c,76,"MoveWindow: geometry query failed");
    if((int)ARG(1)!=old.left || (int)ARG(2)!=old.top ||
       (int)ARG(3)!=required.right-required.left || (int)ARG(4)!=required.bottom-required.top)
        xrt_fatal(c,76,"MoveWindow: unmeasured geometry");
    callback_cpu=c;SetLastError(error);
    ok=MoveWindow(h,(int)ARG(1),(int)ARG(2),(int)ARG(3),(int)ARG(4),TRUE);
    error=GetLastError();callback_cpu=previous;xrt_set_last_error(c,error);RET_STD(6,ok);
}
'''
    anchor='static void hle_SetWindowPos(CPU *c)'
    assert t.count(anchor)==1;t=t.replace(anchor,adapter+'\n'+anchor)
    anchor='{"user32.dll", "SetWindowPos", hle_SetWindowPos},'
    assert t.count(anchor)==1;t=t.replace(anchor,anchor+'\n                              {"user32.dll", "MoveWindow", hle_MoveWindow},')
    gui.write_text(t)
    save('integration-source.json',dict(passed=True,runtime=core.tree(RT),configuration_bound=True,
         gamma_guard_retained=True,resize_original_body_retained=True,production_sources_changed=False))
    print('Narrow profile bound in a separate staged runtime',flush=True)


def extract_resize():
    import capstone, pefile
    pe = pefile.PE(str(A.source() / 'System/WinDrv.dll'))
    md = capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);md.detail=True
    original = pe.get_data(0x4f20,0x840)
    code = bytearray(original)
    reloc = []
    # Import/global memory slots occupy a zeroed fixture arena. All selected
    # imports are supplied by the fixed harness; unexpected paths terminate.
    for ins in md.disasm(original,0x11104f20):
        off = ins.address-0x11104f20
        if ins.disp_size==4 and 0x11100000<=ins.disp<0x11120000:
            reloc.append([off+ins.disp_offset,ins.disp-0x11100000])
        if ins.mnemonic=='call' and ins.imm_size==4:
            target=ins.operands[0].imm
            if target not in range(0x11104f20,0x11105760):
                # Selected windowed path never calls SetTopness or unwind.
                reloc.append([off+ins.imm_offset,target-0x11100000,'relative',off+ins.size])
    src=W/'experiments/xrt/gen/windrv/WinDrv_000.c'
    t=src.read_text();start=t.index('void f_11104f20(CPU* c) {');end=t.index('\nvoid ',start+1)
    generated=t[start:end].replace('void f_11104f20(CPU* c)', 'static void generated_resize(CPU* c)')
    # Only absolute module addresses are rebased; guest callsite IDs stay exact.
    generated=re.sub(r'0x111([0-9a-f]{5})u',lambda m:hex(0x10000+int(m[1],16))+'u',generated)
    # Generated original uses SEH macros from the full runtime. This fixture has
    # no C++ exception path; unexpected unwind remains fatal in xrt_icall.
    (O/'resize_generated.inc').write_text('static unsigned char resize_bytes[]={'+','.join(map(str,code))+'};\n'+
        'static const unsigned resize_reloc[][4]={'+','.join('{'+','.join(map(str,[r[0],r[1],1 if len(r)>2 else 0,r[3] if len(r)>2 else 0]))+'}' for r in reloc)+'};\n'+generated)
    save('resize-extraction.json',dict(original_sha256=core.sha(A.source()/'System/WinDrv.dll'),
         generated_source_sha256=core.sha(src),generated_fixture_sha256=core.sha(O/'resize_generated.inc'),
         original_rva=[0x4f20,0x5760],relocations=reloc,original_body=True,
         fixture_scope='windowed flags 16; project-owned object dependencies; real USER32'))
    print('Original and generated ResizeViewport extracted without module initialization',flush=True)


def resize():
    root=O/('resize-'+str(uuid.uuid4()));root.mkdir()
    rows=[]
    for arch in ('x86','x64'):
        d=root/arch;d.mkdir()
        P.R.script(d,'build',arch,f'cl /nologo /O1 /Gy /fp:strict /W3 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /I"{O}" /I"{RT}" /Fo"{d}/resize.obj" /Fe"{d}/resize.exe" "{H}/resize.c" user32.lib /link /OPT:REF || exit /b 1')
        r=P.R.execute([d/'resize.exe'],d,'run',timeout=30)
        values=[json.loads(s) for s in r.stdout.splitlines()]
        assert len(values)==16 and sum(x['kind']=='resize' for x in values)==8
        rows.append(values)
    assert rows[0]==rows[1],('actual original/generated ResizeViewport differential',rows)
    save('resize-local.json',dict(passed=True,root=str(root),samples_per_variant=8,rows=rows[0],
         original_x86_body=True,generated_x64_body=True,physical_desktop_qualification=False,
         virtual_object_dependencies='project owned fixtures, same callback graph',
         genuine_launches=0))
    print('Original/native and generated ResizeViewport body matches on local disposable windows',flush=True)


def gui():
    root=O/('gui-'+str(uuid.uuid4()));root.mkdir()
    q=load('prerequisite_queryclass',H.parent/'queryclass_boundary/run.py')
    f=q.F;f.O=root
    old=W/'experiments/xrt/build/queryclass-20261029-01'
    # Reuse only identified project-owned fixture code. No game DLL is loaded.
    host=(H.parent/'queryclass_boundary/host.c').read_text()
    host=host[:host.index('#include "driver.h"')]
    host=host.replace('#include "../../runtime/hle_gui.c"',f'#include "{RT.as_posix()}/hle_gui.c"')
    host=host.replace('#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"',f'#include "{W.as_posix()}/tools/xrt/tests/ehprobe/xrt_probe_host.c"')
    host+='#define GUI_TRANSLATED\n'+(H/'gui_main.inc').read_text()
    (root/'host.c').write_text(host)
    native='''#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
static HMODULE mod;static HWND make(const char*p,const char*r,int a){typedef UINT_PTR(*Fn)(void);(void)r;(void)a;mod=LoadLibraryA(p);return mod?(HWND)((Fn)GetProcAddress(mod,"probe_make"))():NULL;}
static BOOL destroy(HWND h){typedef BOOL(*Fn)(void);(void)h;return ((Fn)GetProcAddress(mod,"probe_destroy"))();}
static void finish(void){FreeLibrary(mod);}
'''+(H/'gui_main.inc').read_text()
    (root/'native.c').write_text(native)
    runs=[]
    for arch in ('x86','x64'):
        d=root/arch;d.mkdir()
        P.R.script(d,'build',arch,f'cl /nologo /O1 /fp:strict /W3 /Fo"{d}/native.obj" /Fe"{d}/native.exe" "{root}/native.c" user32.lib || exit /b 1')
        r=P.R.execute([d/'native.exe',old/arch/'viewportprobe.dll',root/'unused.json'],d,'run',timeout=30)
        runs.append([json.loads(s) for s in r.stdout.splitlines()])
    d=root/'translated';d.mkdir();e=f.env()
    cmd=core.read_large(W/'out/recovery/queryclass-20261029-01/initial-translated-build.json')['command']
    cmd=[str(root/'host.c') if Path(s).name=='host.c' else s.replace(str(old/'translated'),str(d)).replace(str(W/'experiments/xrt/runtime'),str(RT)) for s in cmd]
    # Original fixture root also appears with forward slashes in /Fo arguments.
    cmd=[s.replace(str(old/'translated').replace('\\','/'),str(d).replace('\\','/')) for s in cmd]
    f.run(cmd,'translated-build',environment=e,timeout=180)
    r=P.R.execute([d/'translated.exe',old/'x86/viewportprobe.dll',root/'report.json'],d,'run',timeout=30)
    runs.append([json.loads(s) for s in r.stdout.splitlines()])
    assert runs[0]==runs[1]==runs[2]
    report=core.read_large(root/'report.json');assert report['exit_code']==0 and not report['events_dropped']
    negatives={}
    for case in ('site','size','repaint','identity'):
        f.O=root
        r=f.run([d/'translated.exe',old/'x86/viewportprobe.dll',root/(case+'-report.json'),case],case,timeout=30,expected=76)
        negatives[case]=core.read_large(root/(case+'-report.json'))['exit_code']
    save('gui-regressions.json',dict(passed=True,root=str(root),samples_per_variant=8,native_x86_x64_translated_equal=True,
         rows=runs[0],guards=negatives,real_registered_callbacks=True,full_suspended_cpu_equality=True,
         physical_desktop=False,genuine_launches=0))
    print('Real MoveWindow native/translated callbacks, CPU preservation and guards pass',flush=True)


def contracts():
    root=O/('contracts-'+str(uuid.uuid4()));root.mkdir();src=root/'sources';src.mkdir()
    p=core.read_large(O/'configuration-profile.json')
    import pefile
    pe=pefile.PE(str(A.source()/'System/D3DDrv.dll'))
    editor=next(x.address-0x10000000+0x6960000 for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports
                if x.name and x.name.decode()=='?GIsEditor@@3HA')
    initialize='''static void production_frame(CPU*c){
    unsigned n=batch_case->slot==63||batch_case->slot==83?4:batch_case->slot==76?2:3;
    static const DWORD caps[53]={CAPS};unsigned i;
    c->r[EBP]=0x17000;wr32(0x17000-0x14,0x10000);
    wr32(c->r[ESP]+4*n+20,0x18000);wr32(0x18000,0x10000);
    for(i=0;i<53;i++)wr32(0x10000+0x4134+4*i,caps[i]);
FIELDS
    wr32(0x14698,0x4000);wr32(EDITOR,0x19000);wr32(0x19000,0);
}
'''.replace('CAPS',','.join(str(v)+'u' for v in p['caps']['caps'])).replace('EDITOR',hex(editor)+'u')
    initialize=initialize.replace('FIELDS','\n'.join(f'    wr32(0x10000+{k},{v}u);' for k,v in p['fields'].items()))
    support=(H.parent/'renderer_batch/support.inc').read_text()
    support=support.replace('static void setup(CPU*c){',initialize+'\nstatic void setup(CPU*c){')
    support=support.replace('    active=NULL;enters=leaves=native_calls=0;fatal_code=0;d8_rendering=0;d8_native_failed=0;',
        '    production_frame(c);\n    active=NULL;enters=leaves=native_calls=0;fatal_code=0;d8_rendering=0;d8_native_failed=0;')
    support=support.replace('setup(&c);batch_case=NULL;negative(&c);batch_case=sealed;',
        'setup(&c);c.pc^=1;negative(&c);batch_case=sealed;\n'
        '    setup(&c);wr32(0x141c8,9);negative(&c);\n'
        '    setup(&c);wr32(0x1412c,0);negative(&c);\n'
        '    setup(&c);wr32(0x14698,0x4444);negative(&c);\n'
        '    setup(&c);wr32(0x19000,1);negative(&c);')
    (src/'support.inc').write_text(support)
    fixture=(H.parent/'renderer_batch/fixture.c').read_text().replace('VirtualAlloc(NULL,0x20000,','VirtualAlloc(NULL,0x7000000,')
    # The old physical runner is deliberately excluded; only contracts run here.
    (src/'fixture.c').write_text(fixture)
    mixed=(OLD/'integrated_sequence.c').read_text().replace('VirtualAlloc(NULL,0x20000,','VirtualAlloc(NULL,0x7000000,')
    mixed=mixed.replace('wr32(0x2010,extra);','wr32(0x2010,extra);production_frame(c);')
    (src/'mixed.c').write_text(mixed)
    rows=[]
    for arch in ('x86','x64'):
        for group in range(1,8):
            d=root/f'{arch}-{group}';d.mkdir();abi=P.O/'fixtures'/arch/'abi.obj'
            P.R.script(d,'build',arch,f'cl /nologo /O1 /Gy /fp:strict /W3 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /DBATCH_TRANSLATED=1 /DBATCH_GROUP={group} /I"{RT}" /Fo"{d}/fixture.obj" /Fe"{d}/fixture.exe" "{src}/fixture.c" "{abi}" user32.lib /link /OPT:REF || exit /b 1')
            r=P.R.execute([d/'fixture.exe','--contract-only'],d,'run',timeout=30)
            summary=json.loads(r.stdout.splitlines()[-1]);assert summary['passed'] and not summary['graphics']
            rows.append(dict(arch=arch,group=group,summary=summary))
        d=root/(arch+'-mixed');d.mkdir()
        P.R.script(d,'build',arch,f'cl /nologo /O1 /Gy /fp:strict /W3 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /DBATCH_GROUP=6 /I"{RT}" /Fo"{d}/fixture.obj" /Fe"{d}/fixture.exe" "{src}/mixed.c" user32.lib /link /OPT:REF || exit /b 1')
        r=P.R.execute([d/'fixture.exe'],d,'run',timeout=30)
        summary=json.loads(r.stdout.splitlines()[-1]);assert summary['passed'] and summary['single_device']
        rows.append(dict(arch=arch,mixed=True,summary=summary))
    save('profile-contracts.json',dict(passed=True,root=str(root),processes=len(rows),rows=rows,
         graphics=False,narrow_profile_cases=237,capability_configuration_identity_editor_negatives=True))
    print('Narrow production profile / seven groups / mixed persistent-device contracts pass',flush=True)


def gamma_input():
    source=O/'gamma-sources';source.mkdir()
    shutil.copy2(P.O/'extended-contracts.json',O/'extended-contracts.json')
    text=(H.parent/'renderer_batch/gamma_input.c').read_text()
    text=text.replace('{{1,.5f,.5f}', '{{.996063f,.8f,.7f}')
    (source/'gamma_input.c').write_text(text)
    shutil.copy2(H.parent/'renderer_batch/gamma32.asm',source/'gamma32.asm')
    g=load('prerequisite_gamma_input',H.parent/'renderer_batch/gamma_input.py')
    P.O=O;P.H=source;g.P=P;g.main()
    audit=core.read_large(O/'gamma-input-audit.json')
    audit['gamma_sample_domain']='(gamma,brightness,contrast): (.996063,.8,.7),(2.2,.5,.5),(.5,.5,.5),(1,0,1),(1,1,1)'
    save('gamma-input-audit.json',audit)
    native=core.loads((O/'gamma-input/x86/run.stdout.txt').read_bytes().splitlines()[0])
    translated=core.loads((O/'gamma-input/x64/run.stdout.txt').read_bytes().splitlines()[0])
    assert native==translated
    ramp=bytes.fromhex(native['ramp']);assert len(ramp)==1536
    (O/'actual-gamma-ramp.bin').write_bytes(ramp)
    save('actual-gamma-input.json',dict(passed=True,gamma=.996063,brightness=.8,contrast=.7,
         ramp_sha256=core.sha(O/'actual-gamma-ramp.bin'),bytes=1536,native_original_generated_equal=True,
         physical_gamma_changed=False,strict_x87='FAILED retained'))


def build():
    assert core.read_large(O/'profile-contracts.json')['passed']
    assert core.read_large(O/'gui-regressions.json')['passed']
    assert core.read_large(O/'resize-local.json')['passed']
    before=core.read_large(OLD/'build.json');previous=Path(before['root'])
    assert core.tree(previous)==before['outputs']
    assert core.tree(W/'experiments/xrt/gen')==before['generated']
    ident=str(uuid.uuid4());target=W/'experiments/xrt/build/renderer-prerequisites-20261029-01'/ident
    target.mkdir(parents=True)
    helper=load('prerequisite_compiler_environment',W/'experiments/xrt/tests/getobject_boundary/phase.py')
    helper.O=O/'client-build'/ident;helper.O.mkdir(parents=True);env=helper.env()
    origin=core.read_large(OLD/'object-lineage.json');copied={};commands=[]
    for rel,row in origin.items():
        if rel.startswith('obj/rt/'):continue
        assert core.sha(Path(row['source']))==row['source_sha256'] and core.sha(previous/rel)==row['object_sha256']
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest);copied[rel]=core.sha(dest)
    for row in before['commands']:
        cmd=[s.replace(str(previous),str(target)).replace(str(OLD/'runtime'),str(RT)) for s in row['command']]
        link=Path(cmd[0]).name.lower()=='link.exe'
        if link:
            (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
            name='link'
        else:
            obj=Path(next(s[3:] for s in cmd if s.startswith('/Fo')));obj.parent.mkdir(parents=True,exist_ok=True);name=obj.stem
            assert next(Path(s) for s in cmd if s.lower().endswith('.c')).parent==RT
        P.R.execute(cmd,helper.O,name,env,180,W/'experiments/xrt')
        commands.append(core.read(helper.O/(name+'.json')))
    assert len(copied)==265
    save('build.json',dict(passed=True,root=str(target),outputs=core.tree(target),runtime_root=str(RT),runtime=core.tree(RT),
         generated=before['generated'],binary_sha256=core.sha(target/'xrt_ucc.exe'),pdb_sha256=core.sha(target/'xrt_ucc.pdb'),
         compiled_objects=14,reused_objects=265,reused_object_hashes=copied,commands=commands,
         inherited_build=str(OLD/'build.json'),inherited_build_sha256=core.sha(OLD/'build.json'),execution_authorized=False,
         toolchain={str(p):core.sha(p) for p in {Path(r['command'][0]) for r in commands}|{Path(P.R.VC)}},
         configuration_caps_profile_bound=True,gamma_qualified=False,genuine_launches=0))
    print('Fresh configuration/viewport candidate linked; gamma remains guarded',flush=True)


def verify():
    old=load('prerequisite_integrity_checks',OLD/'integrate.py');old.O=O;old.RT=RT;old.MATERIAL=OLD
    old.verify()
    p=O/'candidate-verification.json';v=core.read_large(p)
    v.update(configuration_caps_profile_bound=True,resize_local_qualified=True,gamma_qualified=False,
             game_qualified=False,physical_gamma_pending=True)
    import graphics_backend as G
    qualification=core.read_large(core.HOME/'qualification.json')
    helper=qualification['helper'];assert core.sha(W/helper['path'])==helper['sha256']
    deps=[G.verified_pair('x64')/'d3d8.dll',G.verified_pair('x64')/'d3d9.dll',W/helper['path']]
    v['dependencies']={str(p):core.sha(p) for p in deps}
    v['inherited_dependencies']=core.sha(OLD/'candidate-verification.json')
    core.atomic(p,v)


def milestones():
    b=core.read_large(O/'build.json')
    legacy=load('prerequisite_passive_observer',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    legacy.V.EXE=Path(b['root'])/'xrt_ucc.exe';legacy.V.EXPECTED=b['binary_sha256']
    from supervisor.plan import resolve
    mapping=resolve(legacy.S,legacy.E,legacy.V,b['pdb_sha256'])
    save('permanent-stop-mapping.json',mapping)
    save('continuation-plan.json',dict(prepared=True,authorized=False,submitted=False,genuine_launches=0,
         current_stop='before 0x0696f292; unchanged and mapped offline',
         prerequisites=['physical restoring gamma fixture and exact void-call/input/readback qualification',
                        'only then integrate the qualified gamma bridge and rerun combined contracts/build identity',
                        'separate review/authorization for any new genuine endpoint and one bounded candidate'],
         proposed_milestones=[
            dict(name='SetMaterial returns',site='0x0696f31d',return_pc='0x0696f323'),
            dict(name='two post-material states and 40 initial samplers return',last_site='0x0696f42e'),
            dict(name='actual ResizeViewport returns nonzero',site='0x0696f48d',return_pc='0x0696f493'),
            dict(name='cache initialization returns after 195 calls',site='0x0696f4bd',return_pc='0x0696f4c2'),
            dict(name='UpdateGamma calls and returns with configured bytes',site='0x0696f4ce',gamma_site='0x0696cb68'),
            dict(name='SetRes returns EAX=1 with ret20',site='0x0696f4e9')],
         enforcement='60-second watchdog; stop on first unsupported/assertion; paired runtime returns and stopped CPU/stack evidence; no gameplay',
         strict_failures={'x87':'FAILED retained','WNDPROC':'FAILED retained','native_x86':'FAILED retained'}))


def regressions():
    root=O/('focused-gui-'+str(uuid.uuid4()));root.mkdir()
    # Existing fixture recipes retain their assertions; compile this staged GUI
    # with the established generated project probe and isolated fresh outputs.
    q=load('prerequisite_queryclass_regression',H.parent/'queryclass_boundary/run.py')
    q.F.O=root
    previous=W/'out/recovery/queryclass-20261029-01'
    cmd=core.read_large(previous/'initial-translated-build.json')['command']
    old_build=W/'experiments/xrt/build/queryclass-20261029-01/translated'
    target=root/'translated';target.mkdir()
    # Host includes production GUI by relative source location. Copy and rewrite
    # that one include to the exact staged runtime, retaining all observations.
    host=(H.parent/'queryclass_boundary/host.c').read_text()
    host=host.replace('#include "../../runtime/hle_gui.c"',f'#include "{RT.as_posix()}/hle_gui.c"')
    host=host.replace('#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"',f'#include "{W.as_posix()}/tools/xrt/tests/ehprobe/xrt_probe_host.c"')
    host=host.replace('#include "driver.h"',f'#include "{(H.parent/"queryclass_boundary/driver.h").as_posix()}"')
    (root/'host.c').write_text(host)
    cmd=[str(root/'host.c') if Path(s).name=='host.c' else s.replace(str(old_build),str(target)).replace(str(W/'experiments/xrt/runtime'),str(RT)) for s in cmd]
    q.F.run(cmd,'build',environment=q.F.env(),timeout=180)
    dll=W/'experiments/xrt/build/queryclass-20261029-01/x86/viewportprobe.dll'
    for case in ('messages','accessibility'):
        q.F.run([target/'translated.exe',dll,root/(case+'-report.json'),case],case,timeout=30)
        assert (root/(case+'.stdout.txt')).read_bytes()==(previous/'candidate'/(case+'.stdout.txt')).read_bytes()
    negatives={}
    for case in ('object','wparam','upper','upperwp','nonzero','ansi','uia','mutated','message','unregistered'):
        q.F.run([target/'translated.exe',dll,root/(case+'-report.json'),case],case,timeout=30,expected=76)
        negatives[case]=76
    save('focused-gui-regressions.json',dict(passed=True,root=str(root),registered_queryclass_accessibility_callbacks=True,
         established_output_unchanged=True,guards=negatives,staged_runtime=core.digest(core.tree(RT)),genuine_launches=0))


if __name__ == '__main__':
    globals()[sys.argv[1]]()
