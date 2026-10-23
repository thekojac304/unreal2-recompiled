/* Native x86 D3D8 probe. Explicit DLL, small windowed frame; no global changes.
 * ABI checked against crosire/d3d8to9 source/d3d8{,types}.hpp. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
typedef UINT(WINAPI *Method)(void *);
typedef struct
{
    UINT w, h, format, count, multisample, swap;
    HWND window;
    BOOL windowed, depth;
    UINT depthformat, flags, refresh, interval;
} Present8;
typedef struct
{
    char driver[512], description[512];
    LARGE_INTEGER version;
    DWORD vendor, device, subsystem, revision;
    GUID guid;
    DWORD whql;
} Identifier8;
int wmain(int argc, WCHAR **argv)
{
    int presented = 0;
    WCHAR path[1024];
    HMODULE dll =
        argc == 2 ? LoadLibraryExW(argv[1], NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32)
                  : LoadLibraryExW(L"d3d8.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    typedef void *(WINAPI * Create8)(UINT);
    Create8 create = dll ? (Create8)GetProcAddress(dll, "Direct3DCreate8") : NULL;
    void *object = create ? create(120) : NULL;
    printf("Direct3DCreate8(120)=%s last_error=%lu\n", object ? "non-NULL" : "NULL", GetLastError());
    if (dll && GetModuleFileNameW(dll, path, 1024))
        wprintf(L"loaded=%ls\n", path);
    if (object)
    {
        void **table = *(void ***)object;
        UINT count = ((Method)table[4])(object), adapter;
        printf("GetAdapterCount=%u\n", count);
        for (adapter = 0; adapter < count; adapter++)
        {
            typedef HRESULT(WINAPI * Id)(void *, UINT, DWORD, Identifier8 *);
            typedef HRESULT(WINAPI * Caps)(void *, UINT, UINT, void *);
            typedef HRESULT(WINAPI * Mode)(void *, UINT, UINT *);
            typedef HRESULT(WINAPI * Device)(void *, UINT, UINT, HWND, DWORD, Present8 *, void **);
            Identifier8 id = {0};
            DWORD caps[256] = {0};
            UINT mode[4] = {0};
            HRESULT hr;
            hr = ((Id)table[5])(object, adapter, 0, &id);
            printf("adapter=%u identifier=0x%08lx driver=%s description=%s vendor=%04lx device=%04lx\n", adapter,
                   hr, id.driver, id.description, id.vendor, id.device);
            hr = ((Mode)table[8])(object, adapter, mode);
            printf("display_mode=0x%08lx %ux%u refresh=%u format=%u\n", hr, mode[0], mode[1], mode[2], mode[3]);
            hr = ((Caps)table[13])(object, adapter, 1, caps);
            printf("GetDeviceCaps(adapter=%u, HAL)=0x%08lx\n", adapter, hr);
            if (SUCCEEDED(hr))
            {
                UINT j;
                HWND window;
                void *device = NULL;
                Present8 pp = {0};
                printf("D3DCAPS8=");
                for (j = 0; j < 53; j++)
                    printf("%08lx%s", caps[j], j == 52 ? "\n" : ",");
                window = CreateWindowExW(0, L"STATIC", L"Unreal II graphics boundary",
                                         WS_OVERLAPPEDWINDOW | WS_VISIBLE, CW_USEDEFAULT, CW_USEDEFAULT, 352, 272,
                                         NULL, NULL, GetModuleHandleW(NULL), NULL);
                if (!window)
                {
                    printf("CreateWindow error=%lu\n", GetLastError());
                    continue;
                }
                pp.w = 320;
                pp.h = 240;
                pp.format = mode[3];
                pp.count = 1;
                pp.swap = 1;
                pp.window = window;
                pp.windowed = TRUE;
                hr = ((Device)table[15])(object, adapter, 1, window, 0x20, &pp, &device);
                printf("CreateDevice windowed 320x240 softwareVP=0x%08lx\n", hr);
                if (SUCCEEDED(hr) && device)
                {
                    typedef HRESULT(WINAPI * Clear)(void *, DWORD, const void *, DWORD, DWORD, float, DWORD);
                    typedef HRESULT(WINAPI * Present)(void *, const RECT *, const RECT *, HWND, const RGNDATA *);
                    void **dt = *(void ***)device;
                    hr = ((Clear)dt[36])(device, 0, NULL, 1, 0xff204080, 1.0f, 0);
                    printf("Clear=0x%08lx\n", hr);
                    if (SUCCEEDED(hr))
                    {
                        hr = ((Present)dt[15])(device, NULL, NULL, NULL, NULL);
                        printf("Present=0x%08lx\n", hr);
                        if (SUCCEEDED(hr))
                            presented = 1;
                    }
                    ((Method)dt[2])(device);
                }
                DestroyWindow(window);
            }
        }
        ((Method)table[2])(object);
    }
    if (dll)
        FreeLibrary(dll);
    return presented ? 0 : 1;
}
