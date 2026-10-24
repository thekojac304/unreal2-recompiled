/* Only measured guest imports. Focus is changed by the native fixture driver. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
__declspec(dllexport) DWORD probe_seed, probe_error;
__declspec(dllexport) HWND probe_window;
__declspec(dllexport) HWND probe_read(void) {
    HWND h;SetLastError(probe_seed);h=GetFocus();probe_error=GetLastError();return h;
}
__declspec(dllexport) HWND probe_make(void) {
    return CreateWindowExA(0,"STATIC","xrt focus fixture",WS_POPUP,0,0,16,16,NULL,NULL,NULL,NULL);
}
__declspec(dllexport) int probe_valid(void) {return IsWindow(probe_window);}
__declspec(dllexport) int probe_destroy(void) {return DestroyWindow(probe_window);}
