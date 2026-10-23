/* Process-local NT disk-open guard. Windows component/device access remains
 * available; game data opens are read-only and confined to the isolated tree.
 * No installed file, ACL, COM registration or other process is changed. */
#include <winternl.h>
typedef NTSTATUS (NTAPI *DmbNtCreate)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,PIO_STATUS_BLOCK,PLARGE_INTEGER,ULONG,ULONG,ULONG,ULONG,PVOID,ULONG);
typedef NTSTATUS (NTAPI *DmbNtOpen)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,PIO_STATUS_BLOCK,ULONG,ULONG);
static DmbNtCreate dmb_ntcreate;static DmbNtOpen dmb_ntopen;
static WCHAR guard_root[600],guard_windows[600],guard_exe[600],guard_defender[600];
static int guard_prefix(const WCHAR*p,const WCHAR*root){size_t n=wcslen(root);return !_wcsnicmp(p,root,n)&&(p[n]==0||p[n]==L'\\');}
static int guard_path(POBJECT_ATTRIBUTES a,ACCESS_MASK access) {
 WCHAR raw[1200],full[1200],base[600];const WCHAR*p;size_t n;DWORD attr;unsigned i;
 if(!a||!a->ObjectName||!a->ObjectName->Buffer)return 0;
 n=a->ObjectName->Length/2;if(n>=1000)return 0;
 memcpy(raw,a->ObjectName->Buffer,n*2);raw[n]=0;p=raw;
 if(a->RootDirectory){
  DWORD k=GetFinalPathNameByHandleW(a->RootDirectory,base,600,FILE_NAME_NORMALIZED|VOLUME_NAME_DOS);
  if(!k||k>=600)return 0;
  if(swprintf(full,1200,L"%s\\%s",base,raw)<0)return 0;wcscpy(raw,full);p=raw;
 }
 if(!_wcsnicmp(p,L"\\??\\",4)||!wcsncmp(p,L"\\\\?\\",4))p+=4;
 /* Native audio endpoint handles are devices, not disk paths. */
 if(!_wcsnicmp(p,L"SWD#MMDEVAPI#",12)||!_wcsnicmp(p,L"\\Device\\MM",10)||!_wcsnicmp(p,L"\\Device\\Audio",13)||!_wcsicmp(p,L"\\Device\\CNG")||!_wcsnicmp(p,L"\\Device\\DeviceApi\\",18)||!_wcsicmp(p,L"MountPointManager"))return 1;
 if((!_wcsnicmp(p,L"root#",5)||!_wcsnicmp(p,L"usb#",4)||!_wcsnicmp(p,L"bthhfenum#",10)||!_wcsnicmp(p,L"bthenum#",8)||!_wcsnicmp(p,L"hdaudio#",8))&&wcsstr(p,L"#{6994ad04-93ef-11d0-a3cc-00a0c9223196}\\"))return 1;
 if(wcslen(p)<3||p[1]!=L':'||p[2]!=L'\\'||wcschr(p+2,L':'))goto denied;
 if(!GetFullPathNameW(p,1200,full,NULL))goto denied;
 if(!guard_prefix(full,guard_root)&&!guard_prefix(full,guard_windows)&&_wcsicmp(full,guard_exe)&&!(guard_prefix(full,guard_defender)&&wcsrchr(full,L'\\')&&!_wcsicmp(wcsrchr(full,L'\\'),L"\\MpOav.dll")))goto denied;
 if(access&(FILE_WRITE_DATA|FILE_APPEND_DATA|FILE_WRITE_EA|FILE_WRITE_ATTRIBUTES|FILE_DELETE_CHILD|DELETE|WRITE_DAC|WRITE_OWNER|GENERIC_WRITE|GENERIC_ALL|MAXIMUM_ALLOWED))goto denied;
 /* Reject every reparse component, including directory junctions and the leaf. */
 for(i=3;full[i];i++)if(full[i]==L'\\'){
  full[i]=0;attr=GetFileAttributesW(full);full[i]=L'\\';
  if(attr!=INVALID_FILE_ATTRIBUTES&&(attr&FILE_ATTRIBUTE_REPARSE_POINT))goto denied;
 }
 attr=GetFileAttributesW(full);
 if(attr!=INVALID_FILE_ATTRIBUTES&&(attr&FILE_ATTRIBUTE_REPARSE_POINT))goto denied;
 if(guard_prefix(full,guard_root)){fwprintf(stderr,L"DirectMusic asset open: %s\n",full);fflush(stderr);}
 return 1;
denied:
 fwprintf(stderr,L"DirectMusic sandbox denied disk open: %s access %08lx\n",p,(unsigned long)access);fflush(stderr);return 0;
}
static NTSTATUS NTAPI guard_create(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES o,PIO_STATUS_BLOCK s,PLARGE_INTEGER z,ULONG f,ULONG share,ULONG disposition,ULONG options,PVOID ea,ULONG len) {
 if(!guard_path(o,a)||disposition!=FILE_OPEN)return (NTSTATUS)0xc0000022;
 return dmb_ntcreate(h,a,o,s,z,f,share,disposition,options,ea,len);
}
static NTSTATUS NTAPI guard_open(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES o,PIO_STATUS_BLOCK s,ULONG share,ULONG options) {
 if(!guard_path(o,a))return (NTSTATUS)0xc0000022;
 return dmb_ntopen(h,a,o,s,share,options);
}
static void*guard_hook(const char*name,FARPROC hook) {
 BYTE*p=(BYTE*)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),name),*t;DWORD old,unused;
 /* Supported installed WoW64 stubs start with a complete five-byte MOV EAX.
  * Refuse any different prologue; never guess an instruction boundary. */
 if(!p||p[0]!=0xb8){fprintf(stderr,"unsupported NT guard prologue: %s\n",name);return NULL;}
 t=(BYTE*)VirtualAlloc(NULL,10,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!t)return NULL;
 memcpy(t,p,5);t[5]=0xe9;*(DWORD*)(t+6)=(DWORD)(p+5-(t+10));
 if(!VirtualProtect(t,10,PAGE_EXECUTE_READ,&old)||!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old))return NULL;
 p[0]=0xe9;*(DWORD*)(p+1)=(DWORD)((BYTE*)hook-(p+5));
 VirtualProtect(p,5,old,&unused);FlushInstructionCache(GetCurrentProcess(),p,5);return t;
}
static int guard_install(const WCHAR*root) {
 DWORD n=GetFullPathNameW(root,600,guard_root,NULL);
 if(!n||n>=600||!wcsstr(guard_root,L"sandbox")||!GetWindowsDirectoryW(guard_windows,600)||!GetModuleFileNameW(NULL,guard_exe,600))return 0;
 if(!GetEnvironmentVariableW(L"ProgramData",guard_defender,500))return 0;
 wcscat(guard_defender,L"\\Microsoft\\Windows Defender\\Platform");
 dmb_ntcreate=(DmbNtCreate)guard_hook("NtCreateFile",(FARPROC)guard_create);
 dmb_ntopen=(DmbNtOpen)guard_hook("NtOpenFile",(FARPROC)guard_open);
 return dmb_ntcreate&&dmb_ntopen;
}

