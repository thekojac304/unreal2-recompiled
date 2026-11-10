"""Measured scalar 0xae(9,0), retaining 0xae(8,0); no game launcher."""
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W / 'out/recovery/windowae9-20261029-01'
B = W / 'experiments/xrt/build/windowae9-20261029-01'
spec = importlib.util.spec_from_file_location('ae9_helpers', H/'../getobject_boundary/phase.py')
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
F.O = O


def native():
    B.mkdir(); d = B/'x86'; d.mkdir(); e = F.env('x86')
    F.run(['cl','/nologo','/c','/O2','/GS-','/W4',f'/Fo{d}/',H/'aeprobe.c'], 'native-object', environment=e)
    F.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/BASE:0x12000000','/DYNAMICBASE:NO',
           f'/OUT:{B}/aeprobe.dll',d/'aeprobe.obj','user32.lib','kernel32.lib','imm32.lib'], 'native-dll', environment=e)
    F.run(['cl','/nologo','/O2','/W4',f'/Fo{d}/',f'/Fe{B}/native.exe',H/'native.c','user32.lib','imm32.lib'], 'native-host', environment=e)
    for case in ['positive','wp9']:
        F.run([B/'native.exe',B/'aeprobe.dll',case],'native-'+case,timeout=30)
    F.run([F.PY,'-B','-I',W/'tools/xrt/xlift.py',B/'aeprobe.dll','--out',B/'gen'],'lift',timeout=60)


def translated(stage):
    d=B/stage; d.mkdir(); e=F.env(); rt=W/'experiments/xrt/runtime'
    sources=['hle_kernel32.c','hle_misc.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c',
             'xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    cmd=['cl','/nologo','/O1','/fp:strict','/W3','/wd4102','/wd4146','/wd4100','/D_CRT_SECURE_NO_WARNINGS',
         '/DSTUB_LOADLIB','/DSTUB_POW',f'/I{rt}',f'/Fo{d}/',f'/Fe{d}/translated.exe',H/'host.c',
         *sorted((B/'gen').glob('*.c')),*[rt/n for n in sources],W/'experiments/xrt/tests/common/xrt_test_stubs.c',
         'winmm.lib','advapi32.lib','ole32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/STACK:0x10000000']
    F.run(cmd,stage+'-build',environment=e,timeout=180)
    cases=['wp9'] if stage=='baseline' else ['positive','wp9','wrong-wp','wrong-wp10','wrong-lp']
    for case in cases:
        report=O/(stage+'-'+case+'-report.json')
        F.run([d/'translated.exe',B/'aeprobe.dll',case,report],stage+'-'+case,timeout=30,
              expected=76 if stage=='baseline' or case.startswith('wrong') else 0)


def audit():
    baseline=F.read(O/'baseline-wp9-report.json')
    assert baseline['exit_code']==76 and not baseline['events_dropped']
    assert any(e['kind']=='fatal' and 'window callback 0xae: unmeasured arguments' in e['message'] for e in baseline['events'])
    for case,wp in [('positive',8),('wp9',9)]:
        assert (O/('native-'+case+'.stdout.txt')).read_text()==(O/('fixed-'+case+'.stdout.txt')).read_text()
        assert (O/('fixed-'+case+'.stdout.txt')).read_text().endswith('failures=0\n')
        report=F.read(O/('fixed-'+case+'-report.json'));assert report['exit_code']==0 and not report['events_dropped']
        callbacks=[e for e in report['events'] if e['kind']=='gui_ae_callback_return']
        assert len(callbacks)==24 and all(e['wparam']==wp and e['lparam']==0 for e in callbacks)
    for case in ['wrong-wp','wrong-wp10','wrong-lp']:
        report=F.read(O/('fixed-'+case+'-report.json'));assert report['exit_code']==76 and not report['events_dropped']
        assert not any(e['kind']=='gui_ae_callback_return' for e in report['events'])
        assert any(e['kind']=='fatal' and 'window callback 0xae: unmeasured arguments' in e['message'] for e in report['events'])
    F.save(O/'fixture-audit.json',dict(passed=True,baseline_rejected_wp9=True,scalar_tuples=[[8,0],[9,0]],
           samples_per_tuple=24,native_x86_translated_stdout_equal=True,actual_default_processing=True,
           guest_stdcall_nonvolatile_registers=True,ansi_unicode=True,popup_overlapped=True,last_error_seeds=3,
           negative_cases=['wp0','wp10','nonzero-lp'],genuine_launches=0))
    print('0xae(8,0)/(9,0): 48 native/translated samples and 3 guards PASS')


if __name__=='__main__':
    globals()[sys.argv[1]](*sys.argv[2:])
