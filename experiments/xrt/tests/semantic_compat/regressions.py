import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def attach():
    m=load('semantic_attach_regression',H.parent/'attachthread_boundary/work.py');m.O=O/('attach-'+str(uuid.uuid4()));m.O.mkdir();m.RT=RT;m.fixtures()
    save(O/'attach-regressions.json',read(m.O/'fixture-validation.json'))
def registered():
    m=load('semantic_registered_regression',H.parent/'renderer_prerequisites/phase.py');m.O=O/('registered-'+str(uuid.uuid4()));m.O.mkdir();m.RT=RT;m.regressions()
    save(O/'registered-regressions.json',read(m.O/'focused-gui-regressions.json'))
def resize():
    m=load('semantic_resize_regression',H.parent/'renderer_prerequisites/phase.py');m.O=O/('resize-'+str(uuid.uuid4()));m.O.mkdir();m.RT=RT;m.extract_resize();m.resize()
    save(O/'resize-regressions.json',read(m.O/'resize-local.json'))
if __name__=='__main__':
    assert sys.argv[1:] in (['attach'],['registered'],['resize']);globals()[sys.argv[1]]()
