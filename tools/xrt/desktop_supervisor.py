"""Owner startup/queue utility. The request queue never supplies executable commands."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from supervisor.service import main

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in (
        'serve-fixtures', 'fixture-status', 'stop-fixtures', 'qualify-fixtures',
        'build-test', 'checkout-test', 'submit-test', 'submit-acceptance', 'cancel-test', 'test-result', 'audit-fixtures', 'review-fixtures'):
        from supervisor.development import cli
        cli(sys.argv[1:])
    else:
        main()
