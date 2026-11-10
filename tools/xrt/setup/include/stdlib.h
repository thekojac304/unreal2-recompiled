/* Minimal stdlib.h for the translated game code (see README.txt); only what clang's intrinsic headers declare against. */
#ifndef XRT_COMPAT_STDLIB_H
#define XRT_COMPAT_STDLIB_H
#include <stddef.h>
void* malloc(size_t n);
void free(void* p);
int abs(int);
#endif
