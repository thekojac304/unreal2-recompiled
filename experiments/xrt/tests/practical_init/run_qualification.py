"""Focused owned suites only. No genuine launch/queue API."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

if __name__=='__main__':
    out=O/('qualification-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    suites=[('live.py',[]),('profiles.py',[]),('adapter_checks.py',['contracts']),('adapter_checks.py',['gui']),
        ('resource_trace.py',[]),('dinput_trace.py',[]),('guest_threads.py',[]),
        ('nonlocal.py',['eh']),('nonlocal.py',['dmusic']),('nonlocal.py',['ipc']),('audio.py',[]),
        ('composed_live.py',[]),('qualify.py',[])]
    done=read(O/'qualification-progress.json')['completed'] if '--resume' in sys.argv else []
    previous_names={r['name'] for r in done}
    for script,args in suites:
        name=Path(script).stem+'-'+('-'.join(args) or 'main')
        if name in previous_names:continue
        h.run([W/'.venv/Scripts/python.exe','-B','-I',H/script,*args],name,timeout=240)
        done.append(dict(name=name,receipt=str(out/(name+'.json'))))
        save(O/'qualification-progress.json',dict(root=str(out),completed=done,runtime=core.tree(RT)))
    save(O/'qualification.json',dict(passed=True,root=str(out),suites=done,runtime=core.tree(RT),genuine_launches=0,profile='development'))
