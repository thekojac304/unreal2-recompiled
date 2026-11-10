"""Run the retained owned hardware/mapping/failure fixtures on this fresh PE."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    source=(H.parent/'renderer_config_diagnosis/qualify.py').read_text()
    source=source.replace('from common import *','from common import *\nEXE,SHA,PDB=identity()\nRVA=read(O/"stop-mapping.json")["stop_rva"]')
    for suffix in ('.asm','.c'):
        source=source.replace("H/'stop_fixture"+suffix+"'", "H.parent/'renderer_config_diagnosis/stop_fixture"+suffix+"'")
    path=O/'owned_qualification.py';path.write_text(source)
    m=load('semantic_owned_hardware_qualification',path);m.live()
    result=read(O/'debugger-validation.json');result['candidate_sha256']=identity()[1];save(O/'debugger-validation.json',result)
if __name__=='__main__':main()
