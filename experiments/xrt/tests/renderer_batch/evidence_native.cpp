// Evidence only. No renderer device creation, installation changes or supervisor use.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wtsapi32.h>
#include <sddl.h>
#include <psapi.h>
#include <dxgi1_2.h>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <stdexcept>
static std::string q(const std::wstring& s) {
    int n=WideCharToMultiByte(CP_UTF8,0,s.c_str(),-1,0,0,0,0);
    std::vector<char>b(n);WideCharToMultiByte(CP_UTF8,0,s.c_str(),-1,b.data(),n,0,0);
    std::ostringstream o;o<<'"';for(int i=0;i<n-1;i++){unsigned char c=b[i];
        if(c=='"'||c=='\\')o<<'\\'<<c;else if(c<32){char x[8];sprintf_s(x,"\\u%04x",c);o<<x;}else o<<c;}o<<'"';return o.str();
}
static unsigned long long ft(FILETIME t){return ((unsigned long long)t.dwHighDateTime<<32)|t.dwLowDateTime;}
static std::wstring uname(HANDLE h){wchar_t b[1024]={};DWORD n=0;return GetUserObjectInformationW(h,UOI_NAME,b,sizeof b,&n)?b:L"";}
static std::wstring sid(HANDLE p){HANDLE t=0;DWORD n=0;std::wstring s;
    if(OpenProcessToken(p,TOKEN_QUERY,&t)){GetTokenInformation(t,TokenUser,0,0,&n);std::vector<BYTE>b(n);
        if(GetTokenInformation(t,TokenUser,b.data(),n,&n)){LPWSTR x=0;if(ConvertSidToStringSidW(((TOKEN_USER*)b.data())->User.Sid,&x)){s=x;LocalFree(x);}}CloseHandle(t);}return s;}
static std::wstring wts(DWORD id,WTS_INFO_CLASS k){LPWSTR s=0;DWORD n=0;std::wstring v;
    if(WTSQuerySessionInformationW(WTS_CURRENT_SERVER_HANDLE,id,k,&s,&n)){v=s;WTSFreeMemory(s);}return v;}
static int wtsi(DWORD id,WTS_INFO_CLASS k){LPWSTR s=0;DWORD n=0;int v=-1;
    if(WTSQuerySessionInformationW(WTS_CURRENT_SERVER_HANDLE,id,k,&s,&n)){if(n==2)v=*(USHORT*)s;else if(n==4)v=*(DWORD*)s;WTSFreeMemory(s);}return v;}
static void version(std::ostream&o,const wchar_t*p){DWORD n=GetFileVersionInfoSizeW(p,0);std::vector<BYTE>b(n);VS_FIXEDFILEINFO*f=0;UINT z=0;
    std::wstring company;DWORD a=0,c=0;bool ok=n&&GetFileVersionInfoW(p,0,n,b.data())&&VerQueryValueW(b.data(),L"\\",(void**)&f,&z);
    if(ok){a=f->dwFileVersionMS;c=f->dwFileVersionLS;struct Lang{WORD l,c;};Lang*t=0;
        if(VerQueryValueW(b.data(),L"\\VarFileInfo\\Translation",(void**)&t,&z)&&z>=4){wchar_t key[128],*v=0;
            swprintf_s(key,L"\\StringFileInfo\\%04x%04x\\CompanyName",t->l,t->c);
            if(VerQueryValueW(b.data(),key,(void**)&v,&z))company=v;}}
    o<<",\"version_ok\":"<<(ok?"true":"false")<<",\"version_ms\":"<<a<<",\"version_ls\":"<<c<<",\"company\":"<<q(company);
}
extern "C" __declspec(dllexport) int ev_snapshot(DWORD pid,const wchar_t*path){
    std::ofstream o(path,std::ios::binary);if(!o)return 1;
    HANDLE p=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,pid);if(!p)return 2;
    DWORD session=0,own=0;ProcessIdToSessionId(pid,&session);ProcessIdToSessionId(GetCurrentProcessId(),&own);
    FILETIME now,ct,et,kt,ut;GetSystemTimePreciseAsFileTime(&now);bool times=GetProcessTimes(p,&ct,&et,&kt,&ut)!=0;
    wchar_t image[32768]={};DWORD nc=32768;bool imageok=QueryFullProcessImageNameW(p,0,image,&nc)!=0;
    HDESK input=OpenInputDesktop(0,FALSE,DESKTOP_READOBJECTS);auto in=uname(input);if(input)CloseDesktop(input);
    USEROBJECTFLAGS stationFlags={};DWORD stationBytes=0;BOOL stationOk=GetUserObjectInformationW(GetProcessWindowStation(),UOI_FLAGS,&stationFlags,sizeof stationFlags,&stationBytes);
    o<<"{\"pid\":"<<pid<<",\"collector_pid\":"<<GetCurrentProcessId()<<",\"filetime\":"<<ft(now)
     <<",\"creation_filetime\":"<<(times?ft(ct):0)<<",\"image\":"<<q(imageok?image:L"")<<",\"owner_sid\":"<<q(sid(p))
     <<",\"session\":"<<session<<",\"collector_session\":"<<own<<",\"active_console\":"<<WTSGetActiveConsoleSessionId()
     <<",\"user\":"<<q(wts(session,WTSUserName))<<",\"domain\":"<<q(wts(session,WTSDomainName))
     <<",\"protocol\":"<<wtsi(session,WTSClientProtocolType)<<",\"connect_state\":"<<wtsi(session,WTSConnectState)
     <<",\"remote\":"<<(GetSystemMetrics(SM_REMOTESESSION)?"true":"false")
     <<",\"window_station\":"<<q(uname(GetProcessWindowStation()))<<",\"station_flags_ok\":"<<(stationOk?"true":"false")<<",\"station_flags\":"<<stationFlags.dwFlags<<",\"desktop\":"<<q(uname(GetThreadDesktop(GetCurrentThreadId())))<<",\"input_desktop\":"<<q(in);
    UINT32 np=0,nm=0;LONG dc=GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,&np,&nm);
    std::vector<DISPLAYCONFIG_PATH_INFO>paths;std::vector<DISPLAYCONFIG_MODE_INFO>modes;
    for(int retry=0;dc==ERROR_SUCCESS&&retry<4;retry++){
        paths.resize(np);modes.resize(nm);dc=QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS,&np,paths.data(),&nm,modes.data(),0);
        if(dc!=ERROR_INSUFFICIENT_BUFFER)break;dc=GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,&np,&nm);}
    o<<",\"display_status\":"<<dc<<",\"paths\":[";
    if(dc==0)for(UINT32 i=0;i<np;i++){auto&s=paths[i].sourceInfo;auto&t=paths[i].targetInfo;
        DISPLAYCONFIG_SOURCE_DEVICE_NAME sn={};sn.header={DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME,sizeof sn,s.adapterId,s.id};
        DISPLAYCONFIG_TARGET_DEVICE_NAME tn={};tn.header={DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME,sizeof tn,t.adapterId,t.id};
        LONG sr=DisplayConfigGetDeviceInfo(&sn.header),tr=DisplayConfigGetDeviceInfo(&tn.header);
        o<<(i?",":"")<<"{\"source_luid_low\":"<<s.adapterId.LowPart<<",\"source_luid_high\":"<<s.adapterId.HighPart
         <<",\"target_luid_low\":"<<t.adapterId.LowPart<<",\"target_luid_high\":"<<t.adapterId.HighPart
         <<",\"source_id\":"<<s.id<<",\"target_id\":"<<t.id<<",\"source_status\":"<<sr<<",\"target_status\":"<<tr
         <<",\"gdi_name\":"<<q(sn.viewGdiDeviceName)<<",\"monitor\":"<<q(tn.monitorFriendlyDeviceName)<<",\"monitor_path\":"<<q(tn.monitorDevicePath)
         <<",\"technology\":"<<t.outputTechnology<<",\"rotation\":"<<t.rotation<<",\"scaling\":"<<t.scaling
         <<",\"refresh_n\":"<<t.refreshRate.Numerator<<",\"refresh_d\":"<<t.refreshRate.Denominator;
        if(s.modeInfoIdx<nm){auto&m=modes[s.modeInfoIdx].sourceMode;o<<",\"width\":"<<m.width<<",\"height\":"<<m.height<<",\"x\":"<<m.position.x<<",\"y\":"<<m.position.y;}
        o<<"}";}
    o<<"],\"display_devices\":[";DISPLAY_DEVICEW dd={};dd.cb=sizeof dd;
    for(DWORD i=0;EnumDisplayDevicesW(0,i,&dd,0);i++){o<<(i?",":"")<<"{\"name\":"<<q(dd.DeviceName)<<",\"description\":"<<q(dd.DeviceString)<<",\"pci_id\":"<<q(dd.DeviceID)<<",\"registry_key\":"<<q(dd.DeviceKey)<<",\"flags\":"<<dd.StateFlags<<"}";dd={};dd.cb=sizeof dd;}
    IDXGIFactory1*f=0;HRESULT hr=CreateDXGIFactory1(__uuidof(IDXGIFactory1),(void**)&f);
    o<<"],\"dxgi_hr\":"<<(DWORD)hr<<",\"adapters\":[";
    if(f){for(UINT i=0;;i++){IDXGIAdapter1*a=0;if(f->EnumAdapters1(i,&a)==DXGI_ERROR_NOT_FOUND)break;if(!a)break;DXGI_ADAPTER_DESC1 d={};a->GetDesc1(&d);
        o<<(i?",":"")<<"{\"name\":"<<q(d.Description)<<",\"vendor\":"<<d.VendorId<<",\"device\":"<<d.DeviceId<<",\"subsystem\":"<<d.SubSysId<<",\"revision\":"<<d.Revision<<",\"flags\":"<<d.Flags<<",\"luid_low\":"<<d.AdapterLuid.LowPart<<",\"luid_high\":"<<d.AdapterLuid.HighPart<<"}";a->Release();}f->Release();}
    o<<"],\"modules\":[";std::vector<HMODULE>ms(4096);DWORD needed=0;bool ok=EnumProcessModulesEx(p,ms.data(),(DWORD)(ms.size()*sizeof(HMODULE)),&needed,LIST_MODULES_ALL)!=0;
    ok=ok&&needed<=ms.size()*sizeof(HMODULE);if(ok)for(unsigned i=0;i<needed/sizeof(HMODULE);i++){wchar_t b[32768]={};DWORD n=GetModuleFileNameExW(p,ms[i],b,32768);
        o<<(i?",":"")<<"{\"base\":"<<(unsigned long long)(uintptr_t)ms[i]<<",\"path\":"<<q(n?b:L"");version(o,b);o<<"}";}
    o<<"],\"modules_complete\":"<<(ok?"true":"false")<<"}";CloseHandle(p);return o.good()?0:3;
}
struct Child {HANDLE job=0,p=0,t=0,ready=0,gate=0;DWORD pid=0;};
extern "C" __declspec(dllexport) void ev_close(Child*c){if(!c)return;for(HANDLE h:{c->t,c->p,c->ready,c->gate,c->job})if(h)CloseHandle(h);delete c;}
extern "C" __declspec(dllexport) Child* ev_spawn(const wchar_t*cmd,const wchar_t*cwd,void*env,const wchar_t*out,const wchar_t*err,const wchar_t*ready,const wchar_t*gate){
    Child*c=new Child;c->ready=CreateEventW(0,FALSE,FALSE,ready);c->gate=CreateEventW(0,FALSE,FALSE,gate);c->job=CreateJobObjectW(0,0);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION lim={};lim.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    SECURITY_ATTRIBUTES sa={sizeof sa,0,TRUE};HANDLE oh=CreateFileW(out,GENERIC_WRITE,FILE_SHARE_READ,&sa,CREATE_NEW,0,0),eh=CreateFileW(err,GENERIC_WRITE,FILE_SHARE_READ,&sa,CREATE_NEW,0,0);
    SIZE_T sz=0;InitializeProcThreadAttributeList(0,1,0,&sz);std::vector<BYTE>attr(sz);
    STARTUPINFOEXW si={};si.StartupInfo.cb=sizeof si;si.StartupInfo.dwFlags=STARTF_USESTDHANDLES;si.StartupInfo.hStdOutput=oh;si.StartupInfo.hStdError=eh;
    si.StartupInfo.hStdInput=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_EXISTING,0,0);
    si.lpAttributeList=(LPPROC_THREAD_ATTRIBUTE_LIST)attr.data();HANDLE hs[]={oh,eh,si.StartupInfo.hStdInput};
    BOOL ok=c->ready&&c->gate&&c->job&&oh!=INVALID_HANDLE_VALUE&&eh!=INVALID_HANDLE_VALUE&&SetInformationJobObject(c->job,JobObjectExtendedLimitInformation,&lim,sizeof lim)
      &&InitializeProcThreadAttributeList(si.lpAttributeList,1,0,&sz)&&UpdateProcThreadAttribute(si.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,hs,sizeof hs,0,0);
    PROCESS_INFORMATION pi={};std::wstring command=cmd;
    if(ok)ok=CreateProcessW(0,&command[0],0,0,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED|CREATE_UNICODE_ENVIRONMENT|EXTENDED_STARTUPINFO_PRESENT,env,cwd,&si.StartupInfo,&pi);
    DeleteProcThreadAttributeList(si.lpAttributeList);for(auto h:hs)if(h&&h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    c->p=pi.hProcess;c->t=pi.hThread;c->pid=pi.dwProcessId;
    if(!ok||!AssignProcessToJobObject(c->job,c->p)){if(c->p)TerminateProcess(c->p,99);ev_close(c);return 0;}return c;
}
extern "C" __declspec(dllexport) DWORD ev_pid(Child*c){return c->pid;}
extern "C" __declspec(dllexport) DWORD ev_resume(Child*c){return ResumeThread(c->t);}
extern "C" __declspec(dllexport) DWORD ev_wait(Child*c,DWORD ms){HANDLE hs[]={c->ready,c->p};return WaitForMultipleObjects(2,hs,FALSE,ms);}
extern "C" __declspec(dllexport) BOOL ev_release(Child*c){return SetEvent(c->gate);}
extern "C" __declspec(dllexport) BOOL ev_abort(Child*c){return TerminateJobObject(c->job,98);}
extern "C" __declspec(dllexport) int ev_job(Child*c,const wchar_t*path){
    std::vector<BYTE>b(sizeof(JOBOBJECT_BASIC_PROCESS_ID_LIST)+sizeof(ULONG_PTR)*4096);
    auto*p=(JOBOBJECT_BASIC_PROCESS_ID_LIST*)b.data();DWORD n=0;JOBOBJECT_BASIC_ACCOUNTING_INFORMATION a={};
    BOOL ok=QueryInformationJobObject(c->job,JobObjectBasicProcessIdList,p,(DWORD)b.size(),&n)
      &&QueryInformationJobObject(c->job,JobObjectBasicAccountingInformation,&a,sizeof a,0);
    FILETIME t;GetSystemTimePreciseAsFileTime(&t);std::ofstream o(path);o<<"{\"filetime\":"<<ft(t)<<",\"complete\":"<<(ok?"true":"false")<<",\"assigned\":"<<p->NumberOfAssignedProcesses<<",\"total_processes\":"<<a.TotalProcesses<<",\"pids\":[";
    if(ok)for(DWORD i=0;i<p->NumberOfProcessIdsInList;i++)o<<(i?",":"")<<p->ProcessIdList[i];o<<"],\"processes\":[";
    if(ok)for(DWORD i=0;i<p->NumberOfProcessIdsInList;i++){
        DWORD pid=(DWORD)p->ProcessIdList[i];HANDLE h=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);wchar_t name[32768]={};DWORD n=32768;FILETIME ct={},et={},kt={},ut={};
        BOOL queried=h&&QueryFullProcessImageNameW(h,0,name,&n)&&GetProcessTimes(h,&ct,&et,&kt,&ut);
        o<<(i?",":"")<<"{\"pid\":"<<pid<<",\"query_ok\":"<<(queried?"true":"false")<<",\"image\":"<<q(name)<<",\"creation_filetime\":"<<ft(ct)<<"}";if(h)CloseHandle(h);
    }o<<"]}";return o.good()?0:1;
}
extern "C" __declspec(dllexport) int ev_finish(Child*c,const wchar_t*path,DWORD ms){
    DWORD wait=WaitForSingleObject(c->p,ms),code=STILL_ACTIVE;GetExitCodeProcess(c->p,&code);
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION a={};bool ok=QueryInformationJobObject(c->job,JobObjectBasicAccountingInformation,&a,sizeof a,0)!=0;
    for(int i=0;ok&&a.ActiveProcesses&&i<100;i++){Sleep(10);ok=QueryInformationJobObject(c->job,JobObjectBasicAccountingInformation,&a,sizeof a,0)!=0;}
    FILETIME ct={},et={},kt={},ut={},now;GetProcessTimes(c->p,&ct,&et,&kt,&ut);GetSystemTimePreciseAsFileTime(&now);
    std::ofstream o(path);o<<"{\"pid\":"<<c->pid<<",\"creation_filetime\":"<<ft(ct)<<",\"exit_filetime\":"<<ft(et)<<",\"observed_filetime\":"<<ft(now)<<",\"wait\":"<<wait<<",\"exit\":"<<code<<",\"job_query_ok\":"<<(ok?"true":"false")<<",\"total_processes\":"<<a.TotalProcesses<<",\"active_processes\":"<<a.ActiveProcesses<<",\"terminated_processes\":"<<a.TotalTerminatedProcesses<<",\"assigned_before_resume\":true,\"kill_on_close\":true}";
    return o.good()?0:1;
}
