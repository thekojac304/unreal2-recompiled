"""Read-only kernel-mapping/file identities. No filename search or guessed hashes."""
import contextlib
import ctypes as C
from ctypes import wintypes as T
import hashlib
import os
from pathlib import Path
import struct


class IdentityIncomplete(ValueError):
    pass


def pe_fields(header):
    if len(header)<88 or header[:4]!=b'PE\0\0':
        raise IdentityIncomplete('invalid PE header')
    return dict(machine=struct.unpack_from('<H',header,4)[0],
                timestamp=struct.unpack_from('<I',header,8)[0],
                size_of_image=struct.unpack_from('<I',header,80)[0])


def error_record(error):
    code=getattr(error,'winerror',None)
    if code is None: code=getattr(error,'errno',None)
    category={2:'missing-file',3:'missing-path',5:'access-denied',13:'access-denied',
              32:'sharing-denied',299:'partial-copy'}.get(code,'identity-error')
    return dict(category=category,code=code,type=type(error).__name__,message=str(error))


def same_mapping(a,b):
    keys=['base','allocation_base','mapped_path','machine','timestamp','size_of_image']
    return a.get('mapped') is True and b.get('mapped') is True and all(a.get(k)==b.get(k) for k in keys)


def collect(provider,reported,*,pre_resume=False,attempts=3):
    """Bounded stable enumeration. Departures need independent absence proof.

    Providers are injectable for race/error regression tests; production uses
    WindowsProcess below and always hashes the file named by the kernel mapping.
    """
    history=[]; departed=[]; initial={m['base']:m for m in reported}
    for attempt in range(attempts):
        try: bases=sorted(provider.enumerate())
        except (OSError,IdentityIncomplete) as error:
            detail=error_record(error)
            # A never-resumed CreateProcess target has no initialized loader list.
            # This exception is stage-specific, not valid at a loaded checkpoint.
            if pre_resume and not reported and detail['code']==299:
                return [],dict(schema=1,complete=False,status='pre-resume-loader-unavailable',
                    creation_filetime=provider.creation,rounds=[dict(error=detail)],unloaded=[],unresolved=[])
            history.append(dict(error=detail));continue
        if not bases:
            if pre_resume and not reported:
                return [],dict(schema=1,complete=False,status='pre-resume-loader-unavailable',
                    creation_filetime=provider.creation,rounds=[dict(before=[],status='loader-list-empty')],unloaded=[],unresolved=[])
            history.append(dict(before=[],unresolved=[dict(category='empty-loader-list')]));continue
        modules=[]; failures=[]; probes={}
        for base in bases:
            observed=initial.get(base,{})
            try:
                before=provider.probe(base); probes[base]=before
                if not before.get('mapped'): raise IdentityIncomplete('enumerated base is not a committed MEM_IMAGE allocation')
                with provider.pin_image(before) as disk:
                    if any(before[k]!=disk[k] for k in ['machine','timestamp','size_of_image']):
                        raise IdentityIncomplete('mapped PE metadata differs from opened image')
                    after=provider.probe(base)
                    if not same_mapping(before,after): raise IdentityIncomplete('mapping changed while hashing image')
                    modules.append(dict(base=base,reported_path=observed.get('path') or before.get('reported_path',''),
                        mapped_path=before['mapped_path'],memory_image=before,mapping_after=after,
                        identity_status='verified',identity_source='kernel-mapped-image',**disk))
            except (OSError,IdentityIncomplete) as error:
                failures.append(dict(base=base,reported_path=observed.get('path',''),memory_image=probes.get(base),
                    status='unresolved',**error_record(error)))
        try:
            final=sorted(provider.enumerate());provider.check_creation()
        except (OSError,IdentityIncomplete) as error:
            history.append(dict(before=bases,error=error_record(error)));continue
        # Preserve observations which disappeared, never attach a cached hash.
        gone=(set(bases)|set(initial))-set(final)
        unresolved_departures=[];proven_gone=set()
        for base in sorted(gone):
            try:
                probe=provider.probe(base)
                if probe.get('mapped'):
                    raise IdentityIncomplete('absent from loader enumeration but still mapped')
                departed.append(dict(base=base,reported_path=initial.get(base,{}).get('path',''),
                    status='unloaded',enumeration_absent=True,mapped_after=False,probe=probe,attempt=attempt))
                proven_gone.add(base)
            except (OSError,IdentityIncomplete) as error:
                unresolved_departures.append(dict(base=base,status='unresolved',**error_record(error)))
        failures=[f for f in failures if f['base'] in final]+unresolved_departures
        history.append(dict(before=bases,after=final,unresolved=failures))
        if bases==final and not failures and len(modules)==len(final):
            return modules,dict(schema=1,complete=True,status='verified',creation_filetime=provider.creation,
                final_bases=final,rounds=history,unloaded=departed,unresolved=[])
        # An unproven departure must survive every retry; a later successful
        # enumeration cannot erase an image which remains mapped off-list.
        initial={b:initial.get(b,{}) for b in (set(initial)|set(final))-proven_gone}
    return modules if 'modules' in locals() else [],dict(schema=1,complete=False,status='unresolved',
        creation_filetime=provider.creation,rounds=history,unloaded=departed,
        unresolved=(history[-1].get('unresolved') or [dict(category='enumeration-unstable')]) if history else [])


class MEMORY_BASIC_INFORMATION(C.Structure):
    _fields_=[('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),('AllocationProtect',T.DWORD),
              ('PartitionId',T.WORD),('RegionSize',C.c_size_t),('State',T.DWORD),('Protect',T.DWORD),('Type',T.DWORD)]


class BY_HANDLE_FILE_INFORMATION(C.Structure):
    _fields_=[('attributes',T.DWORD),('creation',T.FILETIME),('access',T.FILETIME),('write',T.FILETIME),
              ('volume',T.DWORD),('size_high',T.DWORD),('size_low',T.DWORD),('links',T.DWORD),
              ('index_high',T.DWORD),('index_low',T.DWORD)]


def api(lib,name,args,result):
    fn=getattr(lib,name);fn.argtypes=args;fn.restype=result;return fn


def checked(value):
    if not value: raise C.WinError(C.get_last_error())
    return value


def filetime(t): return (t.dwHighDateTime<<32)|t.dwLowDateTime


class WindowsFiles:
    def __init__(self):
        self.k=C.WinDLL('kernel32',use_last_error=True)
        self.close=api(self.k,'CloseHandle',[T.HANDLE],T.BOOL)
        self.open=api(self.k,'CreateFileW',[T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE],T.HANDLE)
        self.final=api(self.k,'GetFinalPathNameByHandleW',[T.HANDLE,T.LPWSTR,T.DWORD,T.DWORD],T.DWORD)
        self.info=api(self.k,'GetFileInformationByHandle',[T.HANDLE,C.POINTER(BY_HANDLE_FILE_INFORMATION)],T.BOOL)

    def final_name(self,handle,flags):
        b=C.create_unicode_buffer(32768);n=checked(self.final(handle,b,len(b),flags))
        if n>=len(b): raise IdentityIncomplete('final file path truncated')
        return b.value

    @contextlib.contextmanager
    def pin(self,path,*,mapped_path=None):
        # Sharing permits reads only, so rename/content replacement cannot race hashing.
        h=self.open(str(path),0x80000000,1,None,3,0,None)
        if h==C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
        fd=None
        try:
            native=self.final_name(h,2)
            if mapped_path is not None and native.casefold()!=mapped_path.casefold():
                raise IdentityIncomplete('opened file does not name the kernel mapped image')
            canonical=self.final_name(h,0)
            if canonical.startswith('\\\\?\\UNC\\'): canonical='\\\\'+canonical[8:]
            elif canonical.startswith('\\\\?\\'): canonical=canonical[4:]
            info=BY_HANDLE_FILE_INFORMATION();checked(self.info(h,C.byref(info)))
            import msvcrt
            fd=msvcrt.open_osfhandle(int(h),os.O_RDONLY|os.O_BINARY);h=None
            with os.fdopen(fd,'rb') as f:
                fd=None;dos=f.read(64)
                if len(dos)!=64 or dos[:2]!=b'MZ':raise IdentityIncomplete('invalid image DOS header')
                offset=struct.unpack_from('<I',dos,60)[0]
                if offset>0x100000:raise IdentityIncomplete('PE header offset outside limit')
                f.seek(offset);fields=pe_fields(f.read(88));f.seek(0)
                digest=hashlib.file_digest(f,'sha256').hexdigest()
                yield dict(path=canonical,sha256=digest,**fields,
                    file_id=dict(volume=info.volume,index=(info.index_high<<32)|info.index_low,
                                 size=(info.size_high<<32)|info.size_low,write_filetime=filetime(info.write)),
                    final_nt_path=native,**self.version(canonical))
        finally:
            if h: self.close(h)
            if fd is not None: os.close(fd)

    def version(self,path):
        v=C.WinDLL('version',use_last_error=True)
        size=api(v,'GetFileVersionInfoSizeW',[T.LPCWSTR,C.POINTER(T.DWORD)],T.DWORD)(str(path),None)
        result=dict(version_ok=False,version_ms=0,version_ls=0,company='')
        if not size:return result
        b=C.create_string_buffer(size)
        if not api(v,'GetFileVersionInfoW',[T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p],T.BOOL)(str(path),0,size,b):return result
        query=api(v,'VerQueryValueW',[C.c_void_p,T.LPCWSTR,C.POINTER(C.c_void_p),C.POINTER(T.UINT)],T.BOOL)
        p=C.c_void_p();n=T.UINT()
        if query(b,'\\',C.byref(p),C.byref(n)) and n.value>=52:
            values=C.cast(p,C.POINTER(T.DWORD));result.update(version_ok=True,version_ms=values[2],version_ls=values[3])
        if query(b,'\\VarFileInfo\\Translation',C.byref(p),C.byref(n)) and n.value>=4:
            lang=C.cast(p,C.POINTER(T.WORD));key=f'\\StringFileInfo\\{lang[0]:04x}{lang[1]:04x}\\CompanyName'
            if query(b,key,C.byref(p),C.byref(n)):result['company']=C.wstring_at(p)
        return result


class WindowsProcess(WindowsFiles):
    def __init__(self,pid,creation):
        super().__init__()
        if C.sizeof(C.c_void_p)!=8: raise IdentityIncomplete('64-bit collector required')
        self.pid=pid;self.creation=creation
        self.h=checked(api(self.k,'OpenProcess',[T.DWORD,T.BOOL,T.DWORD],T.HANDLE)(0x410,False,pid))
        self.ps=C.WinDLL('psapi',use_last_error=True)
        self.enum=api(self.ps,'EnumProcessModulesEx',[T.HANDLE,C.POINTER(T.HMODULE),T.DWORD,C.POINTER(T.DWORD),T.DWORD],T.BOOL)
        self.mapped=api(self.ps,'GetMappedFileNameW',[T.HANDLE,C.c_void_p,T.LPWSTR,T.DWORD],T.DWORD)
        self.loader=api(self.ps,'GetModuleFileNameExW',[T.HANDLE,T.HMODULE,T.LPWSTR,T.DWORD],T.DWORD)
        self.vquery=api(self.k,'VirtualQueryEx',[T.HANDLE,C.c_void_p,C.POINTER(MEMORY_BASIC_INFORMATION),C.c_size_t],C.c_size_t)
        self.rpm=api(self.k,'ReadProcessMemory',[T.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],T.BOOL)
        self.times=api(self.k,'GetProcessTimes',[T.HANDLE,*([C.POINTER(T.FILETIME)]*4)],T.BOOL)
        try:
            pm=T.WORD();nm=T.WORD();checked(api(self.k,'IsWow64Process2',[T.HANDLE,C.POINTER(T.WORD),C.POINTER(T.WORD)],T.BOOL)(self.h,C.byref(pm),C.byref(nm)))
            self.wow64=pm.value!=0
            self.check_creation()
        except BaseException:
            self.close(self.h);raise

    def __enter__(self):return self
    def __exit__(self,*_):self.close(self.h)

    def check_creation(self):
        ts=[T.FILETIME() for _ in range(4)];checked(self.times(self.h,*[C.byref(t) for t in ts]))
        if filetime(ts[0])!=self.creation:raise IdentityIncomplete('process creation identity changed')

    def enumerate(self):
        capacity=256
        for _ in range(4):
            ms=(T.HMODULE*capacity)();n=T.DWORD()
            checked(self.enum(self.h,ms,C.sizeof(ms),C.byref(n),3))
            if n.value<=C.sizeof(ms):return [int(m) for m in ms[:n.value//C.sizeof(T.HMODULE)]]
            capacity=n.value//C.sizeof(T.HMODULE)+64
        raise IdentityIncomplete('module enumeration did not fit bounded buffer')

    def memory(self,base,size):
        b=C.create_string_buffer(size);n=C.c_size_t();checked(self.rpm(self.h,C.c_void_p(base),b,size,C.byref(n)))
        if n.value!=size:raise IdentityIncomplete('partial image header read')
        return b.raw

    def probe(self,base):
        mbi=MEMORY_BASIC_INFORMATION();checked(self.vquery(self.h,C.c_void_p(base),C.byref(mbi),C.sizeof(mbi)))
        result=dict(base=base,allocation_base=mbi.AllocationBase,state=mbi.State,type=mbi.Type,
                    mapped=mbi.State==0x1000 and mbi.Type==0x1000000 and mbi.AllocationBase==base,wow64=self.wow64)
        if not result['mapped']:return result
        mapped=C.create_unicode_buffer(32768);n=checked(self.mapped(self.h,C.c_void_p(base),mapped,len(mapped)))
        if n>=len(mapped)-1:raise IdentityIncomplete('mapped filename truncated')
        loader=C.create_unicode_buffer(32768);ln=self.loader(self.h,T.HMODULE(base),loader,len(loader))
        dos=self.memory(base,64)
        if dos[:2]!=b'MZ':raise IdentityIncomplete('mapped image DOS header missing')
        off=struct.unpack_from('<I',dos,60)[0]
        if off>0x100000:raise IdentityIncomplete('mapped PE header offset outside limit')
        result.update(mapped_path=mapped.value,reported_path=loader.value if ln else '',**pe_fields(self.memory(base+off,88)))
        return result

    @contextlib.contextmanager
    def pin_image(self,probe):
        # A kernel NT mapping path is authoritative, never the loader's WOW64 alias.
        nt=probe['mapped_path']
        if not nt.startswith('\\Device\\'):raise IdentityIncomplete('unexpected kernel mapped path namespace')
        with self.pin('\\\\?\\GLOBALROOT'+nt,mapped_path=nt) as identity:
            yield identity


def verify_snapshot(snapshot,*,pre_resume=False):
    """Independent saved-evidence gate. A vanished module has no invented hash."""
    receipt=snapshot.get('module_identity',{})
    if receipt.get('schema')!=1 or receipt.get('creation_filetime')!=snapshot['creation_filetime']:
        raise IdentityIncomplete('module receipt missing or wrong process lifetime')
    if not snapshot['filetime']<=receipt.get('start_filetime',0)<=receipt.get('finish_filetime',0):
        raise IdentityIncomplete('module collection time evidence missing')
    if pre_resume and receipt.get('status')=='pre-resume-loader-unavailable':
        if snapshot['modules'] or receipt.get('complete') is not False or receipt.get('unresolved'):
            raise IdentityIncomplete('invalid pre-resume loader receipt')
        return
    modules=snapshot['modules']
    if not receipt.get('complete') or receipt.get('status')!='verified' or receipt.get('unresolved') or not snapshot['modules_complete'] or not modules:
        raise IdentityIncomplete('unresolved loaded-module identity')
    if sorted(m['base'] for m in modules)!=receipt.get('final_bases'):
        raise IdentityIncomplete('module inventory differs from final enumeration')
    if len({m['base'] for m in modules})!=len(modules):
        raise IdentityIncomplete('duplicate loaded-module base')
    files=WindowsFiles()
    for m in modules:
        if m.get('identity_status')!='verified' or m.get('identity_source')!='kernel-mapped-image':
            raise IdentityIncomplete('module was not independently identified')
        if not same_mapping(m['memory_image'],m['mapping_after']) or m['memory_image']['mapped_path']!=m['mapped_path']:
            raise IdentityIncomplete('module mapping changed')
        for observation in [m['memory_image'],m['mapping_after']]:
            if observation['base']!=m['base'] or observation['allocation_base']!=m['base'] or observation['state']!=0x1000 or observation['type']!=0x1000000:
                raise IdentityIncomplete('module is not its reported committed MEM_IMAGE allocation')
        with files.pin(m['path'],mapped_path=m['mapped_path']) as disk:
            if any(disk[k]!=m[k] for k in ['sha256','machine','timestamp','size_of_image','file_id','final_nt_path','version_ok','version_ms','version_ls','company']):
                raise IdentityIncomplete('saved loaded image differs from actual file')
            if any(disk[k]!=m['memory_image'][k] for k in ['machine','timestamp','size_of_image']):
                raise IdentityIncomplete('mapped and disk PE identities differ')
    for departed in receipt.get('unloaded',[]):
        if departed.get('status')!='unloaded' or not departed.get('enumeration_absent') or departed.get('mapped_after') is not False or departed.get('probe',{}).get('mapped') is not False:
            raise IdentityIncomplete('unproven module departure')
