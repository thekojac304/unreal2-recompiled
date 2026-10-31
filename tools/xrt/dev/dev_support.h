#pragma once
#include <windows.h>
void dev_start(void);
void dev_dump(EXCEPTION_POINTERS *exception, const char *reason);
__declspec(noreturn) void dev_finish(void);
