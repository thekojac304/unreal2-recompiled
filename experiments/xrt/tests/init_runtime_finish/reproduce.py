"""Independently regenerate a fresh runtime, compare every compiled input byte."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    import common
    destination=O;expected=read(O/'build.json')['runtime']
    fresh=O/('source-reproduction-'+str(uuid.uuid4()));fresh.mkdir();(fresh/'runtime').mkdir()
    sdk=read(O/'sdk-prototypes.json');core.require(core.sha(sdk['preprocessed'])==sdk['sha256'],'SDK input identity')
    save(fresh/'sdk-prototypes.json',sdk)
    # A fresh interpreter has no integration modules loaded. Redirect only this
    # interpreter's globals; neither final sources nor prior receipts are edited.
    common.O=fresh;common.RT=fresh/'runtime'
    finish=load('fresh_runtime_reproduction',H/'finish.py');finish.main()
    actual=core.tree(fresh/'runtime');core.require(actual==expected,'final runtime is not reproducible from integrated sources')
    save(destination/'source-reproduction.json',dict(passed=True,root=str(fresh),runtime=actual,
        source_templates=core.tree(H),sdk_sha256=sdk['sha256'],prior_runtime=core.tree(PRIOR/'runtime')))
    print('Independent fresh source regeneration exactly matches all compiled runtime inputs PASS',flush=True)

if __name__=='__main__':main()
