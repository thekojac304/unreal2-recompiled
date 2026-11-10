#include "common.h"
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR args,int show) {
 Identity own,child;FILE*f;HANDLE exe=NULL,collector=NULL,job=NULL;STARTUPINFOW si={0};PROCESS_INFORMATION pi={0};
 JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={0};JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting={0};
 DWORD wait=WAIT_FAILED,code=999,error=0;ULONGLONG start=GetTickCount64();FILETIME created,exited,kernel,user;int rc=1;
 wchar_t command[]=L"\"" CHILD L"\"";
 (void)instance;(void)previous;(void)show;
 if(args&&*args)return 2;
 if(!identity(GetCurrentProcess(),GetCurrentProcessId(),&own))return 3;
 if(!owner(&own)) {
  f=output(ROOT L"/sandbox-refusal.json");if(f){fprintf(f,"{\"child_created\":false,\"reason\":\"owner identity required\",");emit_identity(f,&own);fprintf(f,"}\n");fclose(f);}return 23;
 }
 if(!CreateDirectoryW(ROOT L"/run",NULL))return 4; /* Never reuse an attempt. */
 f=output(ROOT L"/run/launcher.json");if(!f)return 5;
 fprintf(f,"{\"pid\":%lu,",GetCurrentProcessId());emit_identity(f,&own);fprintf(f,"}\n");fclose(f);
 exe=pin(CHILD,CHILD_SHA);collector=pin(COLLECTOR,COLLECTOR_SHA);if(!exe||!collector)goto done;
 job=CreateJobObjectW(NULL,NULL);if(!job)goto done;
 limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION|JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
 limits.BasicLimitInformation.ActiveProcessLimit=1;
 if(!SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof limits))goto done;
 si.cb=sizeof si;si.lpDesktop=L"WinSta0\\Default";si.dwFlags=STARTF_USESHOWWINDOW;si.wShowWindow=SW_HIDE;
 if(!CreateProcessW(CHILD,command,NULL,NULL,FALSE,CREATE_SUSPENDED|CREATE_NEW_CONSOLE,NULL,ROOT,&si,&pi))goto done;
 if(!AssignProcessToJobObject(job,pi.hProcess)){TerminateProcess(pi.hProcess,90);goto done;}
 if(!identity(pi.hProcess,pi.dwProcessId,&child)||!owner(&child)||!GetProcessTimes(pi.hProcess,&created,&exited,&kernel,&user)){TerminateJobObject(job,91);goto done;}
 f=output(ROOT L"/run/parent-child-identity.json");if(!f){TerminateJobObject(job,92);goto done;}
 fprintf(f,"{\"pid\":%lu,\"creation_filetime\":%llu,",pi.dwProcessId,((unsigned long long)created.dwHighDateTime<<32)|created.dwLowDateTime);emit_identity(f,&child);fprintf(f,"}\n");fclose(f);
 if(ResumeThread(pi.hThread)!=(DWORD)1){TerminateJobObject(job,93);goto done;}
 wait=WaitForSingleObject(pi.hProcess,15000);if(wait!=WAIT_OBJECT_0){TerminateJobObject(job,94);goto done;}
 if(!GetExitCodeProcess(pi.hProcess,&code)||!QueryInformationJobObject(job,JobObjectBasicAccountingInformation,&accounting,sizeof accounting,NULL))goto done;
 if(code==0&&accounting.TotalProcesses==1&&accounting.ActiveProcesses==0&&accounting.TotalTerminatedProcesses==0)rc=0;
done:
 error=GetLastError();
 if(rc&&job)TerminateJobObject(job,95);
 if(pi.hProcess){WaitForSingleObject(pi.hProcess,5000);GetExitCodeProcess(pi.hProcess,&code);}
 if(job)QueryInformationJobObject(job,JobObjectBasicAccountingInformation,&accounting,sizeof accounting,NULL);
 f=output(ROOT L"/run/result.json");if(f){fprintf(f,"{\"launcher_result\":%d,\"child_pid\":%lu,\"wait\":%lu,\"exit_code\":%lu,\"error\":%lu,\"total_job_processes\":%lu,\"active_job_processes\":%lu,\"terminated_job_processes\":%lu,\"elapsed_ms\":%llu,\"kill_on_close\":true,\"active_process_limit\":1}\n",rc,pi.dwProcessId,wait,code,error,accounting.TotalProcesses,accounting.ActiveProcesses,accounting.TotalTerminatedProcesses,GetTickCount64()-start);fclose(f);}else rc=96;
 if(pi.hThread)CloseHandle(pi.hThread);if(pi.hProcess)CloseHandle(pi.hProcess);if(job)CloseHandle(job);if(exe)CloseHandle(exe);if(collector)CloseHandle(collector);return rc;
}
