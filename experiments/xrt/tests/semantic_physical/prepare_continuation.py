"""Prepare and qualify the proposed observer; never launch a game."""
import importlib.util
import io
import shutil
import sys
import subprocess
import unittest
from pathlib import Path
from recheck import HERE,OUT,PRIOR,WORK,core

DEST=OUT/'continuation-proposal'
SEM=HERE.parent/'semantic_compat'


def load_named(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    DEST.mkdir(exist_ok=True)
    for name in ('build.json','object-lineage.json','contracts.json'):
        shutil.copy2(PRIOR/name,DEST/name)
    shutil.copy2(OUT/'stop-mapping.json',DEST/'stop-mapping.json')
    source=(SEM/'observer.py').read_text()
    old="    if slot!=18 and after['registers']['eax']!=result:errors.append('native_hresult_transfer')"
    core.require(source.count(old)==1,'expected observer correspondence')
    new=old+"\n    if slot==18 and after['registers']['eax']!=before['registers']['eax']:errors.append('void_eax_preservation')"
    path=DEST/'observer.py';path.write_text(source.replace(old,new))
    import common
    common.O=DEST
    proposed=load_named('observer',path)
    tests=load_named('semantic_continuation_tests',SEM/'test_observer.py')
    class VoidEvidence(unittest.TestCase):
        def test_void_eax_corruption_rejected(self):
            before=dict(registers=dict(eax=0x87654321,esp=0x1000,ebx=1,esi=2,edi=3,ebp=4))
            after=dict(registers=dict(before['registers'],eax=0,esp=0x1010),rv=0x12345678)
            self.assertIn('void_eax_preservation',proposed.discrepancies(before,after,[0x12345678],3,18,0))
            after['registers']['eax']=before['registers']['eax']
            self.assertEqual(proposed.discrepancies(before,after,[0x12345678],3,18,0),[])
    suite=unittest.defaultTestLoader.loadTestsFromModule(tests);suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(VoidEvidence));stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (DEST/'observer-tests.txt').write_text(stream.getvalue());core.require(result.wasSuccessful(),'proposed observer tests failed')
    core.atomic(DEST/'observer-tests.json',dict(passed=True,tests=result.testsRun,source_sha256=core.sha(path)))
    # The retained harness hashes H/observer.py although its imported observer
    # may be the independently proposed module. Bind the actual executed file.
    live_source=(SEM/'live_observer.py').read_text()
    old_binding="core.sha(H/'observer.py')"
    core.require(live_source.count(old_binding)==1,'live receipt binding correspondence')
    previous=DEST/'live-observer-validation.json'
    archived=DEST/'live-observer-validation-original-binding.json'
    if previous.exists() and not archived.exists():shutil.copy2(previous,archived)
    live_path=DEST/'live_observer_qualification.py'
    live_path.write_text(live_source.replace(old_binding,'core.sha(Path(observer.__file__))'))
    load_named('continuation_live_observer',live_path).main()
    # The protocol double intentionally substitutes symbols in retained modules.
    # Qualify the production factory in a fresh interpreter, as production runs.
    subprocess.run([sys.executable,'-B',str(HERE/'qualify_continuation_hardware.py')],check=True,timeout=120)
    core.atomic(DEST/'observer-change.json',dict(passed=True,original_sha256=core.sha(SEM/'observer.py'),proposed_sha256=core.sha(path),
        change='Reject guest EAX corruption after void SetGammaRamp; all other evidence/guard/containment logic retained',
        candidate_unchanged=True,genuine_launches=0,tests=result.testsRun))
    print('Proposed observer qualified:',result.testsRun,'tests plus live protocol/hardware cases; candidate unchanged',flush=True)


if __name__=='__main__':main()
