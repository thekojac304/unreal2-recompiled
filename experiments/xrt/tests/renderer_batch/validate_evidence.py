"""One preparation validation entry point; no physical or game execution path."""
import io, json, sys, unittest
sys.dont_write_bytecode=True
import prepare_evidence as E
import test_evidence, test_audit, test_module_identity
from evidence_capture import save

def main():
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(m) for m in [test_audit,test_evidence,test_module_identity]])
    output=io.StringIO();result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    (E.O/'validation-output.txt').write_text(output.getvalue())
    print(output.getvalue(),end='')
    contracts=E.P.core.read_large(E.O/'contract-results.json')
    E.preserve()
    root=test_evidence.CollectorTests.root
    (root/'test-output.txt').write_text(output.getvalue())
    raw=E.P.core.read_large(root/'actual-abi-results.json') if (root/'actual-abi-results.json').exists() else []
    report=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        original_parser_tests=10,non_graphical_contract_fixtures=len(contracts),contract_assertions=sum(r['checks'] for r in contracts),
        contract_abi_calls=sum(r['calls'] for r in contracts),actual_raw_abi_processes=len(raw),actual_raw_abi_calls=sum(r['calls'] for r in raw),
        actual_runtime_events=sum(r['runtime_events'] for r in raw),disposable_os_evidence=str(root),
        graphics_devices_created=0,genuine_launches=0,historical_delivery_and_audit_unchanged=True,
        strict_x87='FAILED',strict_wndproc='FAILED',strict_native_x86='FAILED',production_accepted=False,
        graphics_runtime_capture='PREPARED_NOT_EXECUTED',limitations='Synthetic rows and COM doubles do not constitute physical GPU evidence.')
    save(E.O/'validation-results.json',report)
    save(root/'test-result.json',report)
    if not result.wasSuccessful():sys.exit(1)

if __name__=='__main__':main()
