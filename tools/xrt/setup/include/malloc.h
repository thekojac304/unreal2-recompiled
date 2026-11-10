/* Minimal malloc.h for the translated game code (see README.txt); declarations only, used by clang's mm_malloc.h. */
#ifndef XRT_COMPAT_MALLOC_H
#define XRT_COMPAT_MALLOC_H
#include <stddef.h>
void* _aligned_malloc(size_t n, size_t align);
void _aligned_free(void* p);
#endif
