"""Fixed disposable helper qualification, using the unmodified pinned helper."""
import os
import shutil
import subprocess
from . import core, fixture
from .environment import load
from .windows import FilePins


def qualify(out, *, helper=None):
    directory = out / 'helper-guard'; directory.mkdir()
    if helper is None:
        pinned = core.read_large(core.ROOT / 'out/recovery/viewport-getobject-20261028-01/pinned-inputs.json')
        from pathlib import Path
        helper = Path(pinned['inputs']['helper']['path'])
    helper = core.independent(helper)
    compiler = load('supervisor_guard_compiler', core.ROOT / 'experiments/xrt/tests/getobject_boundary/phase.py')
    compiler.O = directory
    env = compiler.env()
    exe = directory / 'guard-probe.exe'
    cmd = [shutil.which('cl', path=env.get('Path', env.get('PATH'))), '/nologo', '/O1', '/W4', '/MT',
           '/Fe'+str(exe), '/Fo'+str(directory/'guard-probe.obj'),
           str(core.ROOT/'tools/xrt/supervisor/helper_probe.c'), '/link', 'ole32.lib', '/DYNAMICBASE']
    p = subprocess.run(cmd, cwd=directory, env=env, capture_output=True, timeout=60)
    (directory/'build.stdout.bin').write_bytes(p.stdout); (directory/'build.stderr.bin').write_bytes(p.stderr)
    core.require(p.returncode == 0, 'helper guard probe build failed')
    rows = []
    with FilePins() as pins:
        pins.pin(helper, core.sha(helper)); pins.pin(exe, core.sha(exe))
        for missing in (True, False):
            dest = directory / ('missing-ProgramData' if missing else 'verified-environment'); dest.mkdir()
            (dest/'outside.txt').write_text('disposable outside marker')
            sandbox = dest/'sandbox'; (sandbox/'System').mkdir(parents=True)
            (sandbox/'marker.txt').write_text('disposable inside marker')
            before = core.tree(dest)
            child_env = fixture.environment(sandbox)
            if missing:
                child_env = {k:v for k,v in child_env.items() if k.upper()!='PROGRAMDATA'}
            core.require(missing or any(k.upper()=='PROGRAMDATA' for k in child_env), 'ProgramData must be independently available')
            probe = fixture.Probe(dest, sandbox, 'helper-startup')
            with (dest/'stdout.bin').open('xb') as stdout, (dest/'stderr.bin').open('xb') as stderr:
                result = probe.run([str(exe), str(helper), str(sandbox)], cwd=sandbox/'System', env=child_env,
                                   stdout=stdout, stderr=stderr, timeout=15)
            stderr = (dest/'stderr.bin').read_text()
            if missing:
                core.require(result.returncode==3 and 'DirectMusic helper fatal: cannot install isolated disk-open guard' in stderr
                             and 'DirectMusic IPC seq' not in stderr, 'guard failure did not fail closed before IPC')
            else:
                if result.returncode in (41,42,43):
                    raise core.IntegrityFailure('isolated helper permitted a prohibited disk open')
                core.require(result.returncode==0 and b'guard verified:' in (dest/'stdout.bin').read_bytes(), 'guard enforcement unverified')
            core.require(all(core.sha(dest/p)==h for p,h in before.items()), 'disposable guard inputs changed')
            core.require(probe.cleanup['passed'], 'helper probe cleanup failed')
            rows.append(dict(missing_programdata=missing, passed=True, exit=result.returncode, cleanup=probe.cleanup))
    result = dict(passed=True, guard_verified=True, failure_closed_before_ipc=True,
                  helper_sha256=core.sha(helper), helper=str(helper), cases=rows, genuine_sessions=0)
    core.atomic(directory/'result.json', result)
    return result
