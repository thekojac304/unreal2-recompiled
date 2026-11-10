"""Final source-bound owned evidence; no candidate execution."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

if __name__=='__main__':
    out=O/('final-checks-'+str(uuid.uuid4()));out.mkdir();h=helper(out);receipts=[]
    for name in ('composed_live','prepare_candidate','record_checks','support_checks'):
        h.run([W/'.venv/Scripts/python.exe','-B','-I',H/(name+'.py')],name,timeout=180)
        receipts.append(dict(name=name,receipt=str(out/(name+'.json')),sha256=core.sha(out/(name+'.json'))))
    save(O/'final-checks.json',dict(passed=True,root=str(out),receipts=receipts,runtime=core.tree(RT),sources=core.tree(H)))
