"""Prepare a fixed isolated adaptation of the existing genuine launch workflow.

Nothing runs on import. The owner console is the only authorized caller. All
asset/sandbox/module/Job/watchdog/cleanup logic remains in the existing workflow.
"""
import inspect,difflib
from types import MethodType
from physical_audit import core,read,O,require
from staged_observer import install
from composition import _construct

def compose(legacy,out,p,check_environment,allowed_modules):
    cap=_construct(out,p,out/'monitor.bin',check_environment);cap.allowed_modules=allowed_modules
    retained_log=cap.log
    def log(self,kind,**values):
        if kind=='composed_prepared_observer':
            values.update(genuine_activation=not p.get('owned_fixture',False),production_policy_changed=False)
        return retained_log(kind,**values)
    cap.log=MethodType(log,cap)
    return install(cap,p,out/'monitor.bin',out/'runtime-stream.raw.bin')

def prepare():
    from supervisor import genuine
    original=inspect.getsource(genuine.run)
    edits={
      'plan = resolve(legacy.S, legacy.E, legacy.V, m["pdb_sha256"])': 'plan = _review_plan()',
      'core.require(plan["static_mapping_verified"] and plan["guest_stop"] == 0x696f292, "permanent mapping gate")': 'core.require(plan["sha256"] == m["sha256"] and plan["stop_rva"] == 0x6a0160f and plan["stop_bytes"] == "895f44", "experimental exact mapping gate")',
      '# Keep all strict x87, WNDPROC and renderer parameter assertions in the observer.': '# Scoped experimental disposition; historical strict verdicts remain FAILED. All runtime safety checks remain.',
      'capture = construct(legacy, out, plan, lambda tag: desktop.check(out, tag),': 'capture = _review_construct(legacy, out, plan, lambda tag: desktop.check(out, tag),',
      'XRT_EVENT_STREAM=str(out / "runtime-stream.raw.bin"),': 'XRT_EVENT_STREAM=str(out / "runtime-stream.raw.bin"), XRT_MONITOR_STREAM=str(out / "monitor.bin"), XRT_MONITOR_PROFILE="development",',
      'legacy.audit(out)': 'core.require(core.read(out / "experimental-endpoint-review.json")["passed"] is True, "experimental endpoint acceptance")',
      '(out / "result.json").rename(out / "renderer-audit.json")': '# Experimental acceptance has its own evidence; old renderer strict audit is not relabeled.',
      'passed=classification in ("expected-unsupported-method", "permanent-stop")': 'passed=classification == "permanent-stop"',
    }
    generated=original
    for before,after in edits.items():
        require(generated.count(before)==1,'unexpected retained launch source: '+before)
        generated=generated.replace(before,after)
    def plan():
        p=read(O/'candidate-plan.json');p['review_only']=False
        return p
    namespace=dict(vars(genuine));namespace.update(_review_plan=plan,_review_construct=compose)
    exec(compile(generated,__file__+':isolated-launch-profile','exec'),namespace)
    return namespace['run'],generated,''.join(difflib.unified_diff(original.splitlines(True),generated.splitlines(True),fromfile='unchanged-supervisor/genuine.run',tofile='isolated-experimental/genuine.run'))
