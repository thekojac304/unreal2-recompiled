/* dev_host_stubs.c (x64) - the pieces of the developer runtime's process (xrt_main.c, dev_support.c, the D3D8/sound/
 * port adapters) that the runtime sources linked by build_and_run_dev.cmd refer to but the C++ exception probe never
 * reaches. Each one fails loudly if it is reached. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"

static XRT_NORETURN void unexpected(const char* what) {
    fprintf(stderr, "\nXRT FATAL: ehprobe developer host: unexpected call to %s\n", what);
    exit(77);
}

/* xrt_main.c: the probe host maps the probe DLL itself and never loads further modules */
XrtModule* xrt_load_library(CPU* c, const char* host_path) { (void)c; (void)host_path; unexpected("xrt_load_library"); }
int xrt_free_library(CPU* c, XrtModule* m) { (void)c; (void)m; unexpected("xrt_free_library"); }
