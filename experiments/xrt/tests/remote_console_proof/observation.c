#include "common.h"
int wmain(int argc,wchar_t**argv) {
 Identity id;FILE*f;wchar_t station[128]={0},desktop[128]={0},input[128]={0};HDESK in;
 DWORD mode[3]={0},pids[16]={0},count;BOOL modes[3];HANDLE dllpin;HMODULE dll;int rc;
 int(__cdecl*snapshot)(DWORD,const wchar_t*);ULONGLONG start=GetTickCount64();
 (void)argv;if(argc!=1)return 2;
 if(!identity(GetCurrentProcess(),GetCurrentProcessId(),&id)||!owner(&id))return 3;
 if(!object_name(GetProcessWindowStation(),station,sizeof station)||!object_name(GetThreadDesktop(GetCurrentThreadId()),desktop,sizeof desktop))return 4;
 in=OpenInputDesktop(0,FALSE,DESKTOP_READOBJECTS);if(!in)return 5;
 rc=object_name(in,input,sizeof input);CloseDesktop(in);if(!rc)return 6;
 modes[0]=GetConsoleMode(GetStdHandle(STD_INPUT_HANDLE),&mode[0]);modes[1]=GetConsoleMode(GetStdHandle(STD_OUTPUT_HANDLE),&mode[1]);modes[2]=GetConsoleMode(GetStdHandle(STD_ERROR_HANDLE),&mode[2]);
 count=GetConsoleProcessList(pids,16);
 f=output(ROOT L"/run/child.json");if(!f)return 7;
 fprintf(f,"{\"pid\":%lu,",GetCurrentProcessId());emit_identity(f,&id);
 fprintf(f,",\"station\":\"%ls\",\"desktop\":\"%ls\",\"input_desktop\":\"%ls\",\"stdin_isatty\":%d,\"console_modes_ok\":[%d,%d,%d],\"console_modes\":[%lu,%lu,%lu],\"console_process_count\":%lu,\"console_window\":%llu,\"start_tick\":%llu}\n",station,desktop,input,_isatty(_fileno(stdin)),modes[0],modes[1],modes[2],mode[0],mode[1],mode[2],count,(unsigned long long)(uintptr_t)GetConsoleWindow(),start);fclose(f);
 if(wcscmp(station,L"WinSta0")||wcscmp(desktop,L"Default")||wcscmp(input,L"Default")||!modes[0]||!modes[1]||!modes[2]||!_isatty(_fileno(stdin))||count!=1||pids[0]!=GetCurrentProcessId())return 8;
 dllpin=pin(COLLECTOR,COLLECTOR_SHA);if(!dllpin)return 9;
 dll=LoadLibraryExW(COLLECTOR,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!dll){CloseHandle(dllpin);return 10;}
 snapshot=(int(__cdecl*)(DWORD,const wchar_t*))(uintptr_t)GetProcAddress(dll,"ev_snapshot");
 rc=snapshot?snapshot(GetCurrentProcessId(),ROOT L"/run/environment.raw.json"):-1;
 FreeLibrary(dll);CloseHandle(dllpin);if(rc)return 11;
 Sleep(1500); /* Bounded observation lifetime; no input, graphics device or child creation. */
 f=output(ROOT L"/run/child-complete.json");if(!f)return 12;
 fprintf(f,"{\"pid\":%lu,\"elapsed_ms\":%llu,\"normal_return\":true}\n",GetCurrentProcessId(),GetTickCount64()-start);fclose(f);return 0;
}
