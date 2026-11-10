"""Experimental ownership correction; production source/policy are read-only.

Windows owns CREATE_* debug-event process/thread handles and closes them when
EXIT_* events are continued. The observer owns DUPLICATES, which it may close.
See https://learn.microsoft.com/windows/win32/api/debugapi/nf-debugapi-continuedebugevent
"""
import ctypes as C,inspect,textwrap
from ctypes import wintypes as T
from supervisor import windows as target

def owned_thread(handle):
    current=target.api(target.K,'GetCurrentProcess',[],T.HANDLE)()
    duplicate=T.HANDLE()
    target.checked(target.api(target.K,'DuplicateHandle',
        [T.HANDLE,T.HANDLE,T.HANDLE,C.POINTER(T.HANDLE),T.DWORD,T.BOOL,T.DWORD])(
        current,handle,current,C.byref(duplicate),0,False,2))
    return duplicate.value

def source():
    original=inspect.getsource(target.BoundedLoop.run)
    edits={
        'event_process = ev.u.process.process':'event_process = None  # borrowed debug handle: Windows closes it',
        '(ev.u.process.thread, ev.u.process.teb)':'(_owned_debug_thread(ev.u.process.thread), ev.u.process.teb)',
        '(ev.u.thread.thread, ev.u.thread.teb)':'(_owned_debug_thread(ev.u.thread.thread), ev.u.thread.teb)',
    }
    for before,after in edits.items():
        if original.count(before)!=1:raise RuntimeError('unexpected debugger source: '+before)
        original=original.replace(before,after)
    return textwrap.dedent(original)

def install():
    if getattr(target.BoundedLoop,'experimental_owned_handles',False):return
    namespace=dict(vars(target));namespace['_owned_debug_thread']=owned_thread
    generated=source()
    exec(compile(generated,__file__+':isolated-run','exec'),namespace)
    target.BoundedLoop.run=namespace['run']
    target.BoundedLoop.experimental_owned_handles=True
    target.BoundedLoop.experimental_run_source=generated
