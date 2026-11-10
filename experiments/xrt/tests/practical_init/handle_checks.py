"""Stress debug-event ownership with rapid thread exits and watchdog churn."""
import sys,uuid,ctypes as C
from ctypes import wintypes as T
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from supervisor import windows

def main():
    out=O/('handle-ownership-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    src=out/'fixture.c';src.write_text('''#include <windows.h>
static DWORD WINAPI worker(void*p){return (DWORD)(ULONG_PTR)p;}
int main(void){HANDLE threads[12];unsigned i,j;
for(j=0;j<8;j++){for(i=0;i<12;i++){threads[i]=CreateThread(NULL,0,worker,(void*)(ULONG_PTR)i,0,NULL);if(!threads[i])return 3;}
if(WaitForMultipleObjects(12,threads,TRUE,5000)!=WAIT_OBJECT_0)return 4;
for(i=0;i<12;i++)CloseHandle(threads[i]);}return 0;}
''')
    exe=out/'fixture.exe';h.run(['cl','/nologo','/O2',f'/Fo{out}/',f'/Fe{exe}',src],'build',environment=h.env())
    namespace=windows.BoundedLoop.run.__globals__;original=namespace['_owned_debug_thread'];owned={};duplicates=[]
    def duplicate(raw):
        result=original(raw);core.require(result!=raw,'duplicate aliases borrowed debug handle')
        owned[result]=raw;duplicates.append(dict(borrowed=raw,owned=result));return result
    namespace['_owned_debug_thread']=duplicate
    get=windows.api(windows.K,'GetHandleInformation',[T.HANDLE,C.POINTER(T.DWORD)])
    results=[]
    class Probe(fixture.Probe):
        exits=0
        def log(self,kind,**values):
            super().log(kind,**values)
            if kind=='debug_event' and values['code']==4:
                handle=self.threads[values['tid']][0];flags=T.DWORD()
                core.require(handle in owned and get(handle,C.byref(flags)),'thread exit lacks live owned duplicate')
                self.exits+=1
    for i in range(16):
        d=out/str(i);d.mkdir();sb=d/'sandbox';sb.mkdir();probe=Probe(d,sb,'thread-exit-stress')
        with (d/'stdout.txt').open('xb') as stdout,(d/'stderr.txt').open('xb') as stderr:
            p=probe.run([str(exe)],cwd=sb,env=fixture.environment(sb),stdout=stdout,stderr=stderr,timeout=10)
        core.require(p.returncode==0 and probe.cleanup['passed'] and probe.exits>=96,'handle/Job/watchdog stress failed')
        results.append(dict(iteration=i,thread_exits=probe.exits,cleanup=probe.cleanup))
    generated=windows.BoundedLoop.experimental_run_source
    (out/'experimental_run.py').write_text(generated)
    save(O/'handle-ownership.json',dict(passed=True,root=str(out),results=results,duplicate_count=len(duplicates),
        thread_exits=sum(r['thread_exits'] for r in results),production_source_sha256=core.sha(W/'tools/xrt/supervisor/windows.py'),
        correction_sha256=core.sha(H/'debugger_handles.py'),generated_run_sha256=core.sha(out/'experimental_run.py'),
        production_source_changed=False,production_policy_changed=False,
        documentation='https://learn.microsoft.com/windows/win32/api/debugapi/nf-debugapi-continuedebugevent'))
    print('16 independent Jobs / 1536 rapid worker exits / owned duplicate readbacks PASS',flush=True)

if __name__=='__main__':main()
