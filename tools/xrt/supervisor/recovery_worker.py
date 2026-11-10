"""Internal fixed non-game entry point; never launches a genuine candidate."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from supervisor import core
from supervisor.windows import FilePins
from supervisor.qualify import direct
from supervisor import fixture
from supervisor.helper_checks import qualify as helper_qualify
from supervisor.observer_checks import qualify as observer_qualify


def main():
    out=core.independent(Path(sys.argv[1]))
    core.require(out.resolve().is_relative_to(core.HOME.resolve()),'validator evidence outside supervisor tree')
    payload=core.read(out/'validation-input.json')
    exe=core.ROOT/'experiments/xrt/build/desktop-supervisor/fixture.exe'
    with FilePins() as pins:
        pins.pin(exe,payload['fixture_sha256'])
        pins.pin(core.ROOT/payload['helper']['path'],payload['helper']['sha256'])
        rechecks = payload['fixture_rechecks'] + [dict(case=c,expected_stop=dict(
                    kind='fixture-breakpoint' if c=='hard-stop' else 'fixture-complete')) for c in ('ok-a','hard-stop')]
        for i,check in enumerate(rechecks):
            case=check['case']
            core.require(case in ('ok-a','ok-b','hard-stop','routine-failure'),'validator fixture case allowlist')
            core.require(check['expected_stop'] in (dict(kind='fixture-breakpoint'),dict(kind='fixture-complete')),'validator stop allowlist')
            dest=out/(str(i)+'-'+case);dest.mkdir();sandbox=dest/'sandbox';sandbox.mkdir()
            result=fixture.run(dict(executable=exe.relative_to(core.ROOT).as_posix(),fixture_case=case),
                               dict(expected_stop=check['expected_stop'],timeout_seconds=10),
                               dest,sandbox,lambda:False)
            core.require(result['passed'],'recovery diagnostic failed')
        live=[direct(exe,out,'hang'),direct(exe,out,'tree'),direct(exe,out,'fatal-stop')]
        helper=helper_qualify(out,helper=core.ROOT/payload['helper']['path'])
        observer=observer_qualify(out)
    core.atomic(out/'independent-result.json',dict(passed=True,bindings=payload,genuine_sessions=0,
                helper_guard=helper,observer=observer,watchdog_and_cleanup=live))


if __name__=='__main__':
    try:
        main()
    except BaseException as error:
        dest=core.independent(Path(sys.argv[1]))
        if dest.resolve().is_relative_to(core.HOME.resolve()):
            core.atomic(dest/'independent-failure.json',dict(passed=False,safety_halt=isinstance(error,core.IntegrityFailure),
                        exception_type=type(error).__name__,reason=str(error)))
        raise
