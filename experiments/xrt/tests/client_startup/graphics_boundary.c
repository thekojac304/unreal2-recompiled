/* Read-only x86 availability probe for the exact Direct3D8 boundary observed in D3DDrv. No window/device. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
int main(void) {
    int hal_available = 0;
    HMODULE dll = LoadLibraryExW(L"d3d8.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    typedef void* (WINAPI* Create8)(UINT);
    typedef UINT (WINAPI* Method)(void*);
    Create8 create = dll ? (Create8)GetProcAddress(dll,"Direct3DCreate8") : NULL;
    void* object = create ? create(120) : NULL;
    DWORD error = GetLastError();
    HDC dc = GetDC(NULL);
    printf("Direct3DCreate8(120)=%s last_error=%lu desktop_dc=%s\n",object?"non-NULL":"NULL",error,dc?"non-NULL":"NULL");
    if (dc) ReleaseDC(NULL,dc);
    if (object) {
        void** table=*(void***)object;
        UINT count=((Method)table[4])(object);
        printf("GetAdapterCount=%u\n",count);
        {
            typedef HRESULT (WINAPI* Caps)(void*,UINT,UINT,void*);
            unsigned char caps[1024];
            for (UINT adapter=0;adapter<count;adapter++) {
                HRESULT hr;
                memset(caps,0,sizeof caps);
                hr=((Caps)table[13])(object,adapter,1,caps);
                printf("GetDeviceCaps(adapter=%u, HAL)=0x%08lx\n",adapter,hr);
                if (SUCCEEDED(hr)) hal_available=1;
            }
        }
        ((Method)table[2])(object);
    }
    return hal_available ? 0 : 1; /* creation alone does not pass the original's HAL prerequisite */
}
