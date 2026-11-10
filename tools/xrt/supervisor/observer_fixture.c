/* Non-game production-observer fixture. Uses the real test-linked runtime.
 * No Unreal executable, assets, renderer device or DirectMusic session loads. */
#define xrt_mod_ehprobe xrt_mod_viewportprobe
#define main unused_probe_main
#include "../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
#include "../../../experiments/xrt/runtime/hle_gui.c"

volatile LONG supervisor_sentinel = 0x55555555;
__declspec(noinline) void supervisor_fixture_stop(void) {
    FILE* f;
    supervisor_sentinel = 0;
    if (!fopen_s(&f, "FORBIDDEN.txt", "w")) { fputs("stop instruction executed", f); fclose(f); }
}
static DWORD WINAPI fixture_thread(void* arg) {
    (void)arg;
    OutputDebugStringA("production observer worker event\n");
    return 0;
}
int main(int argc, char** argv) {
    HANDLE worker; HMODULE library;
    if (argc != 2) return 2;
    xrt_events_init();
    xrt_event("supervisor_fixture", "\"non_game\":true");
    worker = CreateThread(NULL, 0, fixture_thread, NULL, 0, NULL);
    if (!worker || WaitForSingleObject(worker, 3000) != WAIT_OBJECT_0) return 3;
    CloseHandle(worker);
    library = LoadLibraryExW(L"version.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!library) return 4;
    FreeLibrary(library);
    if (!strcmp(argv[1], "module-denied")) {
        library = LoadLibraryW(L".\\observer-policy.dll");
        if (!library) return 5;
        FreeLibrary(library);
    } else if (!strcmp(argv[1], "fatal")) {
        xrt_fatal(NULL, 76, "WM_GETOBJECT: non-game observer fixture boundary");
    } else if (!strcmp(argv[1], "import-fatal")) {
        xrt_fatal(NULL, 75, "call to import %s, which has no host implementation (from %s)",
                  "user32.dll!SupervisorFixtureOnly", "non-game-fixture");
    } else if (strcmp(argv[1], "dispatch")) return 6;
    supervisor_fixture_stop();
    return 7;
}
