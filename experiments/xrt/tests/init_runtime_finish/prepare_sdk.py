"""Read-only SDK preprocessing with retained tool/source identities."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    out=O/('sdk-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    src=out/'sdk.c';src.write_text('#define COBJMACROS\n#define WIN32_LEAN_AND_MEAN\n#include <windows.h>\n#include <imm.h>\n#include <objbase.h>\n')
    h.run(['cl','/nologo','/EP',src],'preprocess',environment=h.env())
    output=out/'preprocess.stdout.txt'
    old=O/'sdk-prototypes/preprocess.stdout.txt'
    if old.exists():core.require(core.sha(old)==core.sha(output),'SDK preprocessing changed; review before regenerating wrappers')
    receipt=read(out/'preprocess.json')
    save(O/'sdk-prototypes.json',dict(passed=True,root=str(out),preprocessed=str(output),sha256=core.sha(output),
        tool_sha256=core.sha(receipt['command'][0]),source_sha256=core.sha(src),receipt_sha256=core.sha(out/'preprocess.json')))
    print('SDK prototype reproduction and tool identity PASS',flush=True)

if __name__=='__main__':main()
