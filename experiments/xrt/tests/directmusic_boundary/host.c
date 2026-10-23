#define xrt_mod_ehprobe xrt_mod_comprobe
#define xrt_dll_thread_notify unused_probe_notification
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef xrt_dll_thread_notify
/* This fixture is /NOENTRY and has no TLS or DllMain notifications. */
void xrt_dll_thread_notify(CPU*c,uint32_t reason){(void)c;(void)reason;}
