import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from acceptance import compare
from common import core

class Tests(unittest.TestCase):
    def test_requires_three(self):
        for n in (0,1,2,4):
            with self.assertRaises(core.Rejected):compare([Path('missing')]*n)
    def test_no_success_without_physical_capture(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):compare([Path(d)]*3)

if __name__=='__main__':unittest.main()
