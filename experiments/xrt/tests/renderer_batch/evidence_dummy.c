#include <windows.h>
__declspec(dllexport) int disposable_evidence_fixture(void){return 42;}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID reserved){return TRUE;}
